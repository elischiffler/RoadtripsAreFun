#!/usr/bin/env python3
"""Exercise reviewed public additions against one synthetic local parent only.

Hard-coded loopback/disposable database identity; never reads DATABASE_URL.
Uses ordinary incremental preparation, staging, queries, activation and rollback.
This is development proof, not a production-parent export or release artifact.
"""

import argparse
import json
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import Json, execute_values

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from app.catalog import calendar_enrichment as enrich
from app.catalog import repository
from app.catalog.personas import DATASET

from scripts.catalog_incremental_bundle import build


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def prove(review, output, *, port=55432):
    review, output = Path(review).resolve(), Path(output).absolute()
    if output.exists() or not 1024 <= port <= 65535:
        raise ValueError("proof output exists or invalid local port")
    selectors = json.loads((review / "addition-inputs.json").read_bytes())
    selectors = [item for item in selectors if item["selected_source_ids"]]
    if len(selectors) != 1 or selectors[0]["adapter"] != "usfs-current":
        raise ValueError("proof expects exactly the reviewed USFS addition input")
    expected = json.loads((review / "additions.preview.json").read_bytes())
    # Explicitly synthetic parent; no copied hosted catalog clears a local gate.
    parent = [
        {
            "source_id": "local-synthetic-parent",
            "name": "Synthetic development fixture",
            "latitude": 0.0,
            "longitude": 0.0,
            "region": "CA",
            "categories": ["daytime"],
            "address": None,
            "url": None,
            "source_updated_at": None,
            "provenance": [{"dataset": "Synthetic local fixture; no real place claim"}],
        }
    ]
    metadata = {
        "release": "local-synthetic-parent",
        "attribution": "Synthetic local fixture",
    }
    prior = enrich.digest(metadata)
    # Fixed target, fixed test identity and no ambient configuration or credentials.
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=port,
        dbname="catalog_expansion_20261021",
        user="catalog_test",
        password="local_catalog_only",
        connect_timeout=5,
    )
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            if cur.fetchone()[0] != "catalog_expansion_20261021":
                raise ValueError("refusing unexpected local database")
            cur.execute((ROOT / "backend/sql/places_catalog.sql").read_text())
            cur.execute("SELECT count(*) FROM places_catalog_imports")
            if cur.fetchone()[0]:
                raise ValueError(
                    "proof database already contains a catalog; preserve it"
                )
            cur.execute(
                "INSERT INTO places_catalog_imports(generation,release,manifest,row_count) VALUES(%s,%s,%s,1)",
                (prior, metadata["release"], Json(metadata)),
            )
            fields = enrich.FIELDS.split(",")
            execute_values(
                cur,
                f"INSERT INTO places_catalog(generation,{enrich.FIELDS}) VALUES %s",
                [
                    (
                        prior,
                        *(
                            Json(row[key]) if key == "provenance" else row[key]
                            for key in fields
                        ),
                    )
                    for row in parent
                ],
            )
            cur.execute("INSERT INTO places_catalog_active VALUES(true,%s)", (prior,))
        output.mkdir(parents=True)
        write(output / "parent.json", parent)
        write(output / "parent.manifest.json", metadata)
        source = selectors[0]
        licenses = [
            {
                "identifier": key,
                "path": str(Path(source["path"]).parent / item["path"]),
                "sha256": item["sha256"],
                "source_url": item["url"],
            }
            for key, item in source["manifest"]["licenses"].items()
        ]
        config = {
            "baseline_rows": str(output / "parent.json"),
            "baseline_manifest": str(output / "parent.manifest.json"),
            "baseline_normalized_rows_sha256": enrich.rows_digest(parent),
            "parent_generation": prior,
            "release": "local-public-expansion-proof-20261021",
            "attribution": source["manifest"]["attribution"],
            "calendar_inputs": [],
            "licenses": licenses,
            "addition_inputs": selectors,
            # Charge the full prospect scan, in addition to selected native rows.
            "source_scanned_rows": 7776,
            "additional_source_catalogs": {
                "usfs": {
                    key: source["manifest"][key]
                    for key in ("release", "attribution", "source_url")
                }
            },
        }
        write(output / "config.json", config)
        assembled = build(output / "config.json", output / "portable-import")
        prepared = enrich.prepare(output / "portable-import/catalog.enrichment.json")
        if {r["source_id"]: r for r in prepared["additions"]} != {
            r["source_id"]: r for r in expected
        }:
            raise ValueError("ordinary incremental replay differs from campaign output")
        first, second = enrich.stage(conn, prepared), enrich.stage(conn, prepared)
        if first["existing"] or not second["existing"]:
            raise ValueError("stage idempotency failed")
        with conn.cursor() as cur:
            cur.execute("SELECT generation FROM places_catalog_active")
            if cur.fetchone()[0] != prior:
                raise ValueError("staging changed active pointer")
        conn.rollback()
        enrich.activate(conn, prepared)
        original_get, original_put = (
            repository.chat_crud._get_conn,
            repository.chat_crud._put_conn,
        )
        original_url = repository.settings.DATABASE_URL
        repository.chat_crud._get_conn, repository.chat_crud._put_conn = (
            lambda: conn,
            lambda _: None,
        )
        repository.settings.DATABASE_URL = "local-proof-only"
        found = 0
        try:
            for row in expected:
                matches = repository.nearby(
                    [row["latitude"], row["longitude"]],
                    ["daytime"],
                    require_visit_calendar=True,
                )
                actual = next(
                    (
                        place
                        for place in matches
                        if place["provider_id"] == row["source_id"]
                    ),
                    None,
                )
                if (
                    actual is None
                    or actual["coordinates"] != [row["latitude"], row["longitude"]]
                    or not actual.get("description")
                    or not any(
                        p.get("dataset") == DATASET for p in actual["source_provenance"]
                    )
                ):
                    raise ValueError(
                        "native query lost an admitted identity, profile or arrival"
                    )
                found += 1
        finally:
            repository.chat_crud._get_conn, repository.chat_crud._put_conn = (
                original_get,
                original_put,
            )
            repository.settings.DATABASE_URL = original_url
        enrich.activate(conn, prepared, rollback=True)
        with conn.cursor() as cur:
            cur.execute("SELECT generation FROM places_catalog_active")
            if cur.fetchone()[0] != prior:
                raise ValueError("rollback failed")
            cur.execute(
                "SELECT pg_database_size(current_database()), pg_total_relation_size('places_catalog'), pg_indexes_size('places_catalog')"
            )
            db_bytes, row_bytes, index_bytes = cur.fetchone()
        report = {
            "scope": "Actual public-source replay and local PostgreSQL; synthetic one-row parent, never a production-parent replacement",
            "accepted_public_places": len(expected),
            "native_queries_with_profile_and_calendar": found,
            "stage_idempotent": True,
            "staging_kept_pointer": True,
            "rollback_verified": True,
            "database_bytes": db_bytes,
            "places_relation_bytes": row_bytes,
            "places_index_bytes": index_bytes,
            "assembly": assembled,
            "ai_calls": 0,
            "external_writes": False,
        }
        write(output / "proof.json", report)
        return report
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", type=int, default=55432)
    print(json.dumps(prove(**vars(parser.parse_args())), indent=2))
