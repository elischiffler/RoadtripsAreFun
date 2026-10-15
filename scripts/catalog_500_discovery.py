#!/usr/bin/env python3
"""Measure actual catalog discovery in a named disposable loopback PostgreSQL DB.

This stages/activates public catalogs ONLY in catalog_500_validation or
catalog_500_restore on localhost. It rejects every other database/host. Route
responses must be retained real OSRM GeoJSON receipts. No itinerary, live venue
opening, hotel, detour, model-rating or production success is implied.
"""

import argparse
import asyncio
import hashlib
import json
import math
import sys
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from urllib.parse import urlparse

import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.catalog import ingest, repository
from app.routing.sources.evenings import LiveEveningProvider
from app.routing.sources.persona_candidates import LivePlaceProvider

MAX_BYTES = 64 * 1024 * 1024


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def distance(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    value = (
        math.sin((lat1 - lat2) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon1 - lon2) / 2) ** 2
    )
    return 2 * 3958.7613 * math.asin(min(1, math.sqrt(value)))


def samples(coordinates):
    # Select real geometry vertices after each four miles of driving geometry.
    # No invented city, venue or interpolated off-road coordinates are added.
    points = [[lat, lon] for lon, lat in coordinates]
    chosen, accumulated = [points[0]], 0
    for previous, point in pairwise(points):
        accumulated += distance(previous, point)
        if accumulated >= 4:
            chosen.append(point)
            accumulated = 0
    if chosen[-1] != points[-1]:
        chosen.append(points[-1])
    return chosen


def queries(routes, directory):
    output = {}
    for route in routes["routes"]:
        data = read(directory / route["response_path"])
        if data.get("code") != "Ok" or not data.get("routes"):
            raise ValueError("route receipt did not contain a successful driving route")
        actual = data["routes"][0]
        points = samples(actual["geometry"]["coordinates"])
        ids, evening, occupied = set(), set(), 0
        for point in points:
            daytime = repository.nearby(point, ["daytime"], radius_miles=5, limit=60)
            occupied += bool(daytime)
            ids.update(row["provider_id"] for row in daytime)
            evening.update(
                row["provider_id"]
                for row in repository.nearby(
                    point,
                    ["food", "culture", "nightlife"],
                    radius_miles=5,
                    limit=60,
                )
            )
        output[route["id"]] = {
            "role": route["role"],
            "route_distance_miles": actual["distance"] / 1609.344,
            "route_response_sha256": hashlib.sha256(
                (directory / route["response_path"]).read_bytes()
            ).hexdigest(),
            "sample_points": len(points),
            "samples_with_daytime_hits": occupied,
            "unique_daytime_hits": len(ids),
            "daytime_provider_ids": sorted(ids),
            "unique_evening_category_hits": len(evening),
            "evening_provider_ids": sorted(evening),
        }
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--corridors", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    target = urlparse(args.database_url)
    if (
        target.scheme not in {"postgres", "postgresql"}
        or target.hostname not in {"127.0.0.1", "localhost"}
        or target.path not in {"/catalog_500_validation", "/catalog_500_restore"}
    ):
        raise ValueError("refusing a non-disposable or non-loopback database")
    if args.output.exists():
        raise ValueError("report already exists")
    routes = read(args.corridors / "routes.json")
    for receipt in routes["receipts"]:
        if (
            hashlib.sha256((args.corridors / receipt["path"]).read_bytes()).hexdigest()
            != receipt["sha256"]
        ):
            raise ValueError("geocode or route receipt checksum mismatch")
    conn = psycopg2.connect(args.database_url)
    repository.settings.DATABASE_URL = args.database_url
    repository.chat_crud._get_conn = lambda: conn
    repository.chat_crud._put_conn = lambda connection: None
    with conn, conn.cursor() as cursor:
        cursor.execute("SELECT current_database(), version()")
        database, version = cursor.fetchone()
        if database != target.path[1:]:
            raise ValueError("connected database differs from guarded target")
        cursor.execute((ROOT / "backend/sql/places_catalog.sql").read_text())
    results, generations = {}, {}
    for label, path, expected in (
        ("baseline_243", args.baseline, 243),
        ("prepared_500", args.catalog, 500),
    ):
        manifest = read(path.with_suffix(path.suffix + ".manifest.json"))
        staged = ingest.stage(conn, path, manifest, max_rows=500, max_bytes=MAX_BYTES)
        ingest.activate(conn, staged["generation"])
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT count(*) FROM places_catalog WHERE generation=%s",
                (staged["generation"],),
            )
            if cursor.fetchone()[0] != expected:
                raise ValueError("actual staged row count differs")
        conn.rollback()
        results[label] = queries(routes, args.corridors)
        generations[label] = staged["generation"]
    rows, _ = ingest.prepare(
        args.catalog,
        read(args.catalog.with_suffix(args.catalog.suffix + ".manifest.json")),
        max_rows=500,
        max_bytes=MAX_BYTES,
    )
    typed = []
    for state in ("CA", "WA", "AK"):
        row = next(
            r
            for r in rows
            if r["source_id"].startswith("usfs:") and r["region"] == state
        )
        point = [row["latitude"], row["longitude"]]
        found = asyncio.run(LivePlaceProvider().attractions_near(point))
        ids = [place.provider_id for place in found]
        if row["source_id"] not in ids:
            raise ValueError("new native identity failed typed attraction discovery")
        typed.append(
            {
                "state": state,
                "probe_point": point,
                "target_id": row["source_id"],
                "returned_ids": ids,
            }
        )
    lucky = next(
        r for r in rows if r["source_id"] == "440a13bb-c07b-4b4f-87aa-8dcbe7b691f1"
    )
    evening = asyncio.run(
        LiveEveningProvider().nearby(
            [lucky["latitude"], lucky["longitude"]],
            ["nightlife"],
            datetime.now(UTC),
        )
    )
    if not any(
        p.provider_id == "overture:" + lucky["source_id"]
        and p.opening_intervals is None
        for p in evening
    ):
        raise ValueError(
            "the new public sports-bar record failed typed evening discovery"
        )
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT pg_database_size(current_database()), (SELECT count(*) FROM places_catalog_imports)"
        )
        database_bytes, generation_count = cursor.fetchone()
        cursor.execute(
            "SELECT coalesce(sum(pg_total_relation_size(c.oid)),0) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r'"
        )
        table_bytes = int(cursor.fetchone()[0])
    conn.rollback()
    conn.close()
    output = {
        "checked_at": datetime.now(UTC).isoformat(),
        "database": database,
        "postgres_version": version,
        "target_is_disposable_loopback": True,
        "active_count": 500,
        "generation_count": generation_count,
        "generation_fingerprints": generations,
        "discovery": results,
        "typed_attraction_probes": typed,
        "typed_evening_probe": {
            "provider_ids": [p.provider_id for p in evening],
            "opening_hours_remain_unknown": True,
        },
        "database_bytes": database_bytes,
        "public_tables_and_indexes_bytes": table_bytes,
        "production_calls_or_changes": False,
        "limitations": "Actual five-mile catalog queries along retained real driving geometry. Counts are neither detour feasibility nor itinerary/solver success. Missing corridors and uneven categories remain possible. The user's failing route was unavailable.",
    }
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: {
                    "243": results["baseline_243"][key]["unique_daytime_hits"],
                    "500": results["prepared_500"][key]["unique_daytime_hits"],
                }
                for key in results["prepared_500"]
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
