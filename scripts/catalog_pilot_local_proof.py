#!/usr/bin/env python3
"""Exercise real reviewed pilot rows in a fixed disposable loopback database.

The synthetic parent proves development preservation/idempotency only. It cannot
stand in for the unavailable live parent, production DDL or release approval.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import Json, RealDictCursor, execute_values

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]


def write(path, value):
    Path(path).write_text(
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    )


def prove(source, output, *, port=55433):
    from scripts.run_offline_tests import install

    install(loopback=True)
    from app.catalog import admission, repository
    from app.catalog import calendar_enrichment as enrich
    from app.catalog.pilot_personas import DATASET
    from app.routing.visit_calendar import calendar_eligible

    from scripts.catalog_incremental_bundle import build

    source, output = Path(source).resolve(), Path(output).absolute()
    if port not in {55433, 55434}:
        raise ValueError(
            "only the two explicit disposable loopback fixture ports are allowed"
        )
    if output.exists():
        raise ValueError("choose a new immutable proof output directory")
    expected = json.loads((source / "replay/additions.preview.json").read_bytes())
    if not expected:
        raise ValueError("proof requires reviewed source-admitted places")
    # Explicit local fixture credentials and target, no ambient DATABASE_URL.
    connection = psycopg2.connect(
        host="127.0.0.1",
        hostaddr="127.0.0.1",
        port=port,
        dbname="catalog_pilot_600_20261021",
        user="catalog_test",
        password="local_catalog_pilot_only",
        connect_timeout=5,
    )
    parent = [
        {
            "source_id": "local-pilot-synthetic-parent",
            "name": "Synthetic development fixture",
            "latitude": 0.0,
            "longitude": 0.0,
            "region": "CA",
            "categories": ["daytime"],
            "address": None,
            "url": None,
            "source_updated_at": None,
            "provenance": [{"dataset": "Synthetic parent, not a real attraction"}],
        }
    ]
    metadata = {
        "release": "synthetic-pilot-parent",
        "attribution": "Synthetic local fixture",
    }
    prior = enrich.digest(metadata)

    def prior_rows():
        with connection.cursor(cursor_factory=RealDictCursor) as rows_cur:
            return enrich._rows(rows_cur, prior)

    try:
        with connection, connection.cursor() as cur:
            cur.execute("SELECT current_database()")
            if cur.fetchone()[0] != "catalog_pilot_600_20261021":
                raise ValueError("refusing unexpected local database")
            cur.execute((ROOT / "backend/sql/places_catalog.sql").read_text())
            cur.execute("SELECT count(*) FROM places_catalog_imports")
            existing = cur.fetchone()[0]
            if existing:
                cur.execute("SELECT generation FROM places_catalog_active")
                active = cur.fetchone()
                if existing != 1 or active != (prior,) or prior_rows() != parent:
                    raise ValueError(
                        "proof catalog already contains other data; preserve it"
                    )
            else:
                cur.execute(
                    "INSERT INTO places_catalog_imports VALUES(%s,%s,%s,1,now())",
                    (prior, metadata["release"], Json(metadata)),
                )
                execute_values(
                    cur,
                    f"INSERT INTO places_catalog(generation,{enrich.FIELDS}) VALUES %s",
                    [
                        (
                            prior,
                            *(
                                Json(row[key]) if key == "provenance" else row[key]
                                for key in enrich.FIELDS.split(",")
                            ),
                        )
                        for row in parent
                    ],
                )
                cur.execute(
                    "INSERT INTO places_catalog_active VALUES(true,%s)", (prior,)
                )
        output.mkdir(mode=0o700, parents=True)
        write(output / "parent.json", parent)
        write(output / "parent.manifest.json", metadata)
        manifest = json.loads((source / "reviewed.manifest.json").read_bytes())
        files = [
            p.relative_to(source).as_posix()
            for p in sorted(source.rglob("*"))
            if p.is_file() and "replay" not in p.relative_to(source).parts
        ]
        config = {
            "baseline_rows": str(output / "parent.json"),
            "baseline_manifest": str(output / "parent.manifest.json"),
            "baseline_normalized_rows_sha256": enrich.rows_digest(parent),
            "parent_generation": prior,
            "release": "local-reviewed-pilot-600-20261021",
            "attribution": manifest["attribution"],
            "calendar_inputs": [],
            "source_scanned_rows": 0,
            "licenses": [
                {
                    "identifier": ident,
                    "path": str(ROOT / "frontend/public/licenses" / name),
                    "source_url": url,
                }
                for ident, name, url in [
                    (
                        "CC-BY-4.0",
                        "CC-BY-4.0.txt",
                        "https://creativecommons.org/licenses/by/4.0/",
                    ),
                    (
                        "CC0-1.0",
                        "CC0-1.0.txt",
                        "https://www.wikidata.org/wiki/Wikidata:Copyright",
                    ),
                    (
                        "LicenseRef-US-Agency-Factual-Data",
                        "LicenseRef-US-Agency-Factual-Data.txt",
                        "https://www.doi.gov/copyright",
                    ),
                    (
                        "LicenseRef-NY-Open-Data",
                        "LicenseRef-NY-Open-Data.txt",
                        "https://data.ny.gov/dataset/OPEN-NY-Terms-Of-Use/77gx-ii52",
                    ),
                ]
            ],
            "addition_inputs": [
                {
                    "adapter": "reviewed-browse-pilot",
                    "path": str(source / "reviewed.json"),
                    "manifest": manifest,
                    "files": files,
                }
            ],
            "additional_source_catalogs": {
                "catalog-pilot": {
                    "release": manifest["release"],
                    "attribution": manifest["attribution"],
                    "source_url": "https://www.wikidata.org/wiki/Wikidata:Copyright",
                }
            },
        }
        write(output / "config.json", config)
        assembled = build(output / "config.json", output / "portable-import")
        prepared = enrich.prepare(output / "portable-import/catalog.enrichment.json")
        if prepared["additions"] != expected:
            raise ValueError("typed incremental replay differs from reviewed pilot")
        first, second = (
            enrich.stage(connection, prepared),
            enrich.stage(connection, prepared),
        )
        if first["existing"] or not second["existing"]:
            raise ValueError("staging was not idempotent")
        with connection.cursor() as cur:
            cur.execute("SELECT generation FROM places_catalog_active")
            if cur.fetchone()[0] != prior:
                raise ValueError("staging changed the active pointer")
        connection.rollback()
        activated = enrich.activate(connection, prepared)
        original = (
            repository.chat_crud._get_conn,
            repository.chat_crud._put_conn,
            repository.settings.DATABASE_URL,
        )
        repository.chat_crud._get_conn, repository.chat_crud._put_conn = (
            lambda: connection,
            lambda _: None,
        )
        repository.settings.DATABASE_URL = "local-proof-only"
        queried = 0
        try:
            for row in expected:
                point = [row["latitude"], row["longitude"]]
                found = next(
                    (
                        r
                        for r in repository.browse_nearby(point)
                        if r["provider_id"] == row["source_id"]
                    ),
                    None,
                )
                if (
                    found is None
                    or not admission.browse_eligible(found)
                    or admission.routing_eligible(found)
                    or calendar_eligible(found)
                ):
                    raise ValueError("actual repository browse/routing result differs")
                if not any(
                    p.get("dataset") == DATASET and len(p["attribute_ratings"]) == 14
                    for p in found["source_provenance"]
                ):
                    raise ValueError("stored profile was not retrieved")
                if repository.nearby(point, ["culture"]):
                    raise ValueError(
                        "browse-only records leaked into automatic nearby queries"
                    )
                queried += 1
        finally:
            (
                repository.chat_crud._get_conn,
                repository.chat_crud._put_conn,
                repository.settings.DATABASE_URL,
            ) = original
        receipt = enrich.recovery_receipt(connection, prepared)
        write(output / "recovery-receipt.json", receipt)
        rolled_back = enrich.rollback(connection, receipt)
        with connection.cursor() as cur:
            if prior_rows() != parent:
                raise ValueError("parent source rows changed")
            cur.execute("SELECT generation FROM places_catalog_active")
            if cur.fetchone()[0] != prior:
                raise ValueError("rollback did not restore the parent")
            cur.execute(
                "SELECT pg_database_size(current_database()),pg_total_relation_size('places_catalog'),pg_indexes_size('places_catalog'),pg_total_relation_size('places_catalog_calendars')"
            )
            db, table, indexes, companions = cur.fetchone()
        connection.rollback()
        report = {
            "scope": "Disposable synthetic-parent development proof; not production/live-parent reconciliation",
            "source_admitted_browse": len(expected),
            "source_manifest_sha256": manifest["sha256"],
            "source_additions_sha256": enrich.rows_digest(expected),
            "actual_repository_queries": queried,
            "itinerary_ready": 0,
            "live_net_new": None,
            "staged_twice_idempotent": second["existing"],
            "stage_preserved_pointer": True,
            "parent_content_preserved": True,
            "activated": activated,
            "rolled_back": rolled_back,
            "generation": prepared["generation"],
            "assembled": assembled,
            "database_bytes": db,
            "places_relation_bytes_including_indexes_toast": table,
            "places_index_bytes": indexes,
            "calendar_relation_bytes": companions,
            "external_network_and_ai": "blocked; fixed disposable loopback database only",
            "production_writes": False,
            "disposable_loopback_port": port,
        }
        write(output / "proof.json", report)
        return report
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--port", type=int, choices=(55433, 55434), default=55433)
    args = parser.parse_args()
    print(json.dumps(prove(args.source, args.output, port=args.port), indent=2))


if __name__ == "__main__":
    main()
