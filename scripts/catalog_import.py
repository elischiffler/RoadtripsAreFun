#!/usr/bin/env python3
"""Run from repository root with backend on PYTHONPATH. Dry-run is the default.

Database operations use existing DATABASE_URL; never accept credentials in CLI
arguments. Schema application and activation are separate explicit operations.
"""

import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlparse

from app.catalog.ingest import activate, prepare, stage


def connect_target(target):
    """Use existing injected credentials, with a separate explicit production gate."""
    import psycopg2

    value = os.environ.get("DATABASE_URL", "")
    parsed = urlparse(value)
    if target == "neon":
        if (
            parsed.scheme not in {"postgres", "postgresql"}
            or not (parsed.hostname or "").endswith(".neon.tech")
            or parsed.path != "/neondb"
        ):
            raise ValueError("Neon target requires an existing verified neondb connection")
        conn = psycopg2.connect(
            value,
            connect_timeout=5,
            sslmode="verify-full",
            sslrootcert=os.environ.get("PGSSLROOTCERT", "/etc/ssl/certs/ca-certificates.crt"),
        )
    else:
        dsn = psycopg2.extensions.parse_dsn(value)
        if dsn.get("host") not in {
            "localhost",
            "127.0.0.1",
            "postgres",
            "restore",
            "/tmp/catalog-pg-socket",
        }:
            raise ValueError("local target must explicitly select an isolated local host")
        if not dsn.get("dbname") or dsn["dbname"] == "neondb":
            raise ValueError("local target must select a named disposable database")
        conn = psycopg2.connect(value, connect_timeout=5, sslmode="disable")
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT current_setting('server_version_num')::int / 10000")
            if cur.fetchone()[0] != 18:
                raise ValueError("catalog migration was validated for PostgreSQL 18 only")
        conn.rollback()
        return conn
    except BaseException:
        conn.close()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--stage", action="store_true")
    parser.add_argument("--activate", metavar="GENERATION")
    parser.add_argument("--apply-schema", action="store_true")
    parser.add_argument("--target", choices=["local", "neon"], default="local")
    parser.add_argument("--max-rows", type=int, default=500)
    parser.add_argument("--max-bytes", type=int, default=20 * 1024 * 1024)
    args = parser.parse_args()
    modes = sum((args.stage, bool(args.activate), args.apply_schema))
    if modes > 1:
        parser.error("choose one explicit database operation")
    if not args.activate and not args.apply_schema and (not args.input or not args.manifest):
        parser.error("--input and --manifest are required")
    manifest = None
    if args.manifest:
        with args.manifest.open("rb") as stream:
            content = stream.read(32_769)
        if len(content) > 32_768:
            raise ValueError("manifest exceeds 32 KiB")
        manifest = json.loads(content)
    if modes == 0:
        _, report = prepare(args.input, manifest, max_rows=args.max_rows, max_bytes=args.max_bytes)
    else:
        conn = connect_target(args.target)
        try:
            if args.apply_schema:
                with conn, conn.cursor() as cur:
                    cur.execute("SET LOCAL lock_timeout='5s'")
                    cur.execute(
                        (
                            Path(__file__).resolve().parents[1] / "backend/sql/places_catalog.sql"
                        ).read_text()
                    )
                report = {"schema_applied": True}
            elif args.activate:
                report = activate(conn, args.activate)
            else:
                report = stage(
                    conn,
                    args.input,
                    manifest,
                    max_rows=args.max_rows,
                    max_bytes=args.max_bytes,
                )
        finally:
            conn.close()
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Connection exceptions can contain credentials/hostnames; never print them.
        raise SystemExit(
            f"Catalog operation failed ({type(exc).__name__}); no secrets logged"
        ) from None
