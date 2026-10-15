#!/usr/bin/env python3
"""Measure real bounded discovery and rollback in a disposable PostgreSQL 18 DB.

Only public source catalogs are loaded; no application or production data is
read. The original 500 remains available for pointer-only rollback. Retained
real driving geometry is sampled exactly as in the 500-place measurement.
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
from app.catalog import ingest, repository  # noqa: E402
from app.routing.sources.evenings import LiveEveningProvider  # noqa: E402
from app.routing.sources.persona_candidates import LivePlaceProvider  # noqa: E402

from scripts.catalog_500_discovery import queries  # noqa: E402
from scripts.catalog_expansion_release import read  # noqa: E402


class MeasuredCursor:
    def __init__(self, cursor, observations):
        self.cursor, self.observations = cursor, observations

    def __enter__(self):
        self.cursor.__enter__()
        return self

    def __exit__(self, *arguments):
        return self.cursor.__exit__(*arguments)

    def execute(self, statement, parameters=None):
        started = time.perf_counter()
        result = self.cursor.execute(statement, parameters)
        if "WITH candidates AS" in statement:
            self.observations.append(
                {
                    "execute_ms": (time.perf_counter() - started) * 1000,
                    "sql": self.cursor.query.decode(),
                }
            )
        return result

    def __getattr__(self, name):
        return getattr(self.cursor, name)


class MeasuredConnection:
    def __init__(self, connection, observations):
        self.connection, self.observations = connection, observations

    def cursor(self, *arguments, **keywords):
        return MeasuredCursor(self.connection.cursor(*arguments, **keywords), self.observations)

    def rollback(self):
        return self.connection.rollback()


def fingerprint(connection, generation):
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT count(*), md5(jsonb_agg(to_jsonb(p) ORDER BY source_id COLLATE "C")::text) '
            "FROM places_catalog p WHERE generation=%s",
            (generation,),
        )
        count, digest = cursor.fetchone()
    connection.rollback()
    return {"rows": count, "md5": digest}


def measure(database_url, baseline, catalog, corridors, output, max_rows, max_bytes):
    parsed = urlparse(database_url)
    if (
        parsed.scheme not in {"postgres", "postgresql"}
        or parsed.hostname not in {"localhost", "127.0.0.1"}
        or parsed.path != "/catalog_expansion_validation"
    ):
        raise ValueError("refusing a non-disposable or non-loopback database")
    if output.exists():
        raise ValueError("report already exists")
    routes = read(corridors / "routes.json")
    import hashlib

    for receipt in routes["receipts"]:
        if (
            hashlib.sha256((corridors / receipt["path"]).read_bytes()).hexdigest()
            != receipt["sha256"]
        ):
            raise ValueError("retained route/geocode checksum mismatch")
    connection = psycopg2.connect(database_url)
    observations = []
    measured = MeasuredConnection(connection, observations)
    repository.settings.DATABASE_URL = database_url
    repository.chat_crud._get_conn = lambda: measured
    repository.chat_crud._put_conn = lambda _: None
    with connection, connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), current_setting('server_version_num')::int")
        database, version = cursor.fetchone()
        if database != "catalog_expansion_validation" or version // 10000 != 18:
            raise ValueError("guarded database identity/version differs")
        cursor.execute((ROOT / "backend/sql/places_catalog.sql").read_text())
    results, generations, fingerprints = {}, {}, {}
    for label, path in (("baseline_500", baseline), ("expanded", catalog)):
        manifest = read(path.with_suffix(path.suffix + ".manifest.json"))
        staged = ingest.stage(connection, path, manifest, max_rows=max_rows, max_bytes=max_bytes)
        generation = staged["generation"]
        ingest.activate(connection, generation)
        before = len(observations)
        discovery = queries(routes, corridors)
        timings = [item["execute_ms"] for item in observations[before:]]
        results[label] = {
            "discovery": discovery,
            "query_count": len(timings),
            "execute_ms": {
                "median": statistics.median(timings),
                "p95": sorted(timings)[int((len(timings) - 1) * 0.95)],
                "max": max(timings),
            },
            "storage": staged,
        }
        generations[label] = generation
        fingerprints[label] = fingerprint(connection, generation)
    plans = []
    for item in observations[-2:]:
        with connection.cursor() as cursor:
            cursor.execute("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + item["sql"])
            plans.append(cursor.fetchone()[0])
        connection.rollback()
    expanded = generations["expanded"]
    all_rows, _ = ingest.prepare(
        catalog,
        read(catalog.with_suffix(catalog.suffix + ".manifest.json")),
        max_rows=max_rows,
        max_bytes=max_bytes,
    )
    typed = []
    probes = [
        next(
            row
            for row in all_rows
            if row["source_id"].startswith("usda-market:") and row["region"] == state
        )
        for state in ("CA", "CT", "DE", "VT")
    ]
    probes.extend(
        next(
            row
            for row in all_rows
            if row["source_id"].startswith("wikidata-park:") and category in row["categories"]
        )
        for category in ("amusement_park", "roadside_attraction", "museum", "nightlife")
    )
    for row in probes:
        point = [row["latitude"], row["longitude"]]
        found = asyncio.run(LivePlaceProvider().attractions_near(point))
        match = next((place for place in found if place.provider_id == row["source_id"]), None)
        if match is None or match.source_provenance[:-1] != row["provenance"]:
            raise ValueError("new source identity/provenance failed typed daytime discovery")
        typed.append(
            {
                "provider_id": match.provider_id,
                "source": match.source,
                "region": row["region"],
                "source_release": match.source_release,
                "provenance_retained": True,
            }
        )
        evening = asyncio.run(
            LiveEveningProvider().nearby(point, ["food", "nightlife"], datetime.now(UTC))
        )
        if row["source_id"].startswith("usda-market:") and any(
            place.provider_id == row["source_id"] for place in evening
        ):
            raise ValueError("daytime market incorrectly appeared as an evening restaurant")
        if "nightlife" in row["categories"] and not any(
            place.provider_id == row["source_id"] and place.opening_intervals is None
            for place in evening
        ):
            raise ValueError(
                "published evening destination failed typed discovery with unknown hours"
            )
    if not ingest.stage(
        connection,
        catalog,
        read(catalog.with_suffix(catalog.suffix + ".manifest.json")),
        max_rows=max_rows,
        max_bytes=max_bytes,
    )["existing"]:
        raise ValueError("staging is not idempotent")
    rollback = ingest.activate(connection, generations["baseline_500"])
    if rollback["previous_generation"] != expanded:
        raise ValueError("rollback did not replace the expanded pointer")
    if fingerprint(connection, generations["baseline_500"]) != fingerprints["baseline_500"]:
        raise ValueError("preserved generation changed")
    ingest.activate(connection, expanded)
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_database_size(current_database()), pg_total_relation_size('places_catalog'), pg_indexes_size('places_catalog')"
        )
        database_bytes, catalog_bytes, index_bytes = cursor.fetchone()
    connection.rollback()
    connection.close()
    proof = {
        "checked_at": datetime.now(UTC).isoformat(),
        "postgres_version_num": version,
        "target_is_disposable_loopback": True,
        "generations": generations,
        "fingerprints": fingerprints,
        "results": results,
        "sample_explain_analyze_buffers": plans,
        "stage_idempotent": True,
        "rollback_to_500_and_reactivation": True,
        "typed_source_probes": typed,
        "markets_excluded_from_evening_restaurant_results": True,
        "database_bytes": database_bytes,
        "catalog_bytes": catalog_bytes,
        "index_bytes": index_bytes,
        "production_calls_or_changes": False,
        "limitations": "Nearby discovery along real geometry; no detour, solver, itinerary, live-hours or user-route success is implied. Browser saved-trip verification remains pending.",
    }
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(proof, stream, indent=2)
        stream.write("\n")
    return proof


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    for argument in ("baseline", "catalog", "corridors", "output"):
        parser.add_argument("--" + argument, required=True, type=Path)
    parser.add_argument("--max-rows", required=True, type=int)
    parser.add_argument("--max-bytes", required=True, type=int)
    args = parser.parse_args()
    result = measure(**vars(args))
    print(
        json.dumps(
            {
                "counts": result["fingerprints"],
                "timing": {k: v["execute_ms"] for k, v in result["results"].items()},
            },
            indent=2,
        )
    )
