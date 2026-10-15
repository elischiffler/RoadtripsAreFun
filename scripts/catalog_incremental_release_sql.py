"""Compile inert companion catalog release SQL from an actually staged local PG18.

No returned statement is executed here and the active pointer is never changed.
Each statement list must be executed as one transaction by the release owner.
Rollback consumes only the frozen receipt, with no source-admission clock.
"""

import copy
import hashlib
import ipaddress
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from app.catalog import calendar_enrichment as enrich
from app.catalog import ingest
from app.routing.visit_calendar import source_calendar
from psycopg2.extras import RealDictCursor

from scripts.catalog_release_sql import (
    FIELDS,
    RECORD,
    generation_guard,
    identifiers,
    literal,
)

SCHEMA = "roadtrips-catalog-incremental-release-sql/1"


def _json(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def _local_connection(connection):
    """Compilation fingerprints come from a caller-supplied local rehearsal only."""
    parameters = connection.get_dsn_parameters()
    for key in ("host", "hostaddr"):
        host = parameters.get(key, "")
        if not host or (
            key == "host" and (host == "localhost" or host.startswith("/"))
        ):
            continue
        try:
            local = ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = False
        if not local:
            raise ValueError(
                "incremental SQL compilation requires a local rehearsal connection"
            )


def _bounded(prepared):
    enrich._prepared_guard(prepared)
    report = prepared["report"]
    rows, baseline, additions = (
        prepared["rows"],
        prepared["baseline"],
        prepared["additions"],
    )
    if (
        not 0 < len(baseline) <= len(rows) <= ingest.MAX_ROWS
        or len({row["source_id"] for row in rows}) != len(rows)
        or len({row["source_id"] for row in additions}) != len(additions)
        or {row["source_id"] for row in additions}
        & {row["source_id"] for row in baseline}
        or report.get("rows") != len(rows)
        or report.get("additions") != len(additions)
        or type(report.get("source_scanned_rows")) is not int
        or not len(rows) <= report["source_scanned_rows"] <= ingest.MAX_ROWS
        or type(report.get("bytes")) is not int
        or not 0 < report["bytes"] <= ingest.MAX_BYTES
    ):
        raise ValueError("incremental SQL exceeds unchanged row/input ceilings")


def _entries_guard(entries, row_count):
    if not 1 <= len(entries) <= row_count or len(
        {e["source_id"] for e in entries}
    ) != len(entries):
        raise ValueError("incremental SQL requires unique complete companion entries")
    for entry in entries:
        calendar = source_calendar({"source_provenance": [entry]})
        if calendar is None or not (
            calendar.weekly_windows
            or any(item.windows for item in calendar.date_overrides)
            or (calendar.date_overrides and calendar.unknown_reasons)
        ):
            raise ValueError(
                "incremental SQL companion has no valid explicit source windows"
            )


def _storage_guard():
    return f"""
  SELECT COALESCE(sum(pg_total_relation_size(c.oid)),0) INTO catalog_bytes
    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind='r'
      AND c.relname IN ('places_catalog','places_catalog_imports','places_catalog_active','places_catalog_calendars');
  IF pg_database_size(current_database())>{ingest.MAX_DATABASE_BYTES} OR catalog_bytes>{ingest.MAX_CATALOG_BYTES}
  THEN RAISE EXCEPTION 'Catalog/database storage ceiling exceeded'; END IF;
"""


def _generation_guard(snapshot):
    generation = snapshot["generation"]
    return (
        generation_guard(generation, snapshot["row_count"], snapshot["rows_md5"])
        + f"""
  IF NOT EXISTS (
    SELECT 1 FROM public.places_catalog_imports
    WHERE generation='{generation}' AND release=manifest->>'release'
      AND md5(jsonb_build_object('manifest',manifest,'release',release,'row_count',row_count)::text)='{snapshot["metadata_md5"]}'
  ) OR (SELECT count(*) FROM public.places_catalog_calendars WHERE generation='{generation}')<>{snapshot["calendar_count"]} OR
    (SELECT md5(COALESCE(jsonb_agg(c.entry ORDER BY c.source_id COLLATE "C"),'[]'::jsonb)::text)
      FROM public.places_catalog_calendars c WHERE generation='{generation}') IS DISTINCT FROM '{snapshot["calendars_md5"]}'
  THEN RAISE EXCEPTION 'Required catalog metadata or companions changed'; END IF;
"""
    )


def _baseline_guard(old, new):
    return f"""
  IF EXISTS (
    SELECT {FIELDS} FROM public.places_catalog WHERE generation='{old}'
    EXCEPT SELECT {FIELDS} FROM public.places_catalog WHERE generation='{new}'
  ) THEN RAISE EXCEPTION 'Baseline raw source fields/provenance not preserved'; END IF;
"""


def _transaction(body, *, staging=False):
    return [
        f"SET LOCAL statement_timeout='{'30' if staging else '5'}s'",
        "SET LOCAL lock_timeout='5s'",
        "SELECT pg_advisory_xact_lock(827461905)",
        "DO " + literal(body) + ";",
    ]


def stage_statements(prepared, manifest, entries, receipt):
    """Compile only content already verified by compile_release's local rehearsal."""
    _bounded(prepared)
    enrich.validate_recovery_receipt(receipt)
    old, new = receipt["parent"]["generation"], receipt["candidate"]["generation"]
    identifiers(
        old, new, receipt["parent"]["rows_md5"], receipt["candidate"]["rows_md5"]
    )
    _entries_guard(entries, len(prepared["rows"]))
    if (
        old != prepared["parent"]["generation"]
        or new != prepared["generation"]
        or receipt["parent"]["row_count"] != len(prepared["baseline"])
        or receipt["candidate"]["row_count"] != len(prepared["rows"])
        or receipt["candidate"]["calendar_count"] != len(entries)
        or manifest.get("calendar_enrichment_sha256") != enrich.digest(entries)
        or manifest.get("calendar_count") != len(entries)
        or any(
            manifest.get(key) != value for key, value in prepared["manifest"].items()
        )
    ):
        raise ValueError("incremental SQL content differs from frozen rehearsal")
    added_raw, entries_raw, metadata_raw = map(
        _json, (prepared["additions"], entries, manifest)
    )
    if (
        len(metadata_raw.encode()) > 32768
        or sum(len(value.encode()) for value in (added_raw, entries_raw, metadata_raw))
        > ingest.MAX_BYTES
    ):
        raise ValueError(
            "incremental SQL payload exceeds unchanged input/metadata ceilings"
        )
    body = f"""DECLARE
  items constant jsonb := {literal(added_raw)}::jsonb;
  companions constant jsonb := {literal(entries_raw)}::jsonb;
  metadata constant jsonb := {literal(metadata_raw)}::jsonb;
  previous text;
  catalog_bytes bigint;
BEGIN
  IF current_setting('server_version_num')::int / 10000 <> 18 THEN RAISE EXCEPTION 'PostgreSQL 18 required'; END IF;
  SELECT generation INTO previous FROM public.places_catalog_active WHERE singleton=true FOR UPDATE;
  IF previous IS NULL OR previous NOT IN ('{old}','{new}') THEN RAISE EXCEPTION 'Unexpected active generation'; END IF;
  {_generation_guard(receipt["parent"])}
  {_storage_guard()}
  IF {prepared["report"]["source_scanned_rows"]}>{ingest.MAX_ROWS} OR {prepared["report"]["bytes"]}>{ingest.MAX_BYTES}
    OR jsonb_array_length(items)<>{len(prepared["additions"])} OR jsonb_array_length(companions)<>{len(entries)}
    OR octet_length(metadata::text)>32768
  THEN RAISE EXCEPTION 'Incremental row/input count or metadata ceiling exceeded'; END IF;
  IF EXISTS (SELECT 1 FROM public.places_catalog_imports WHERE generation='{new}') THEN
    {_generation_guard(receipt["candidate"])}
  ELSE
    INSERT INTO public.places_catalog_imports(generation,release,manifest,row_count)
      VALUES('{new}',metadata->>'release',metadata,{len(prepared["rows"])});
    INSERT INTO public.places_catalog(generation,{FIELDS})
      SELECT '{new}',{FIELDS} FROM public.places_catalog WHERE generation='{old}';
    INSERT INTO public.places_catalog(generation,{FIELDS})
      SELECT '{new}',{FIELDS} FROM jsonb_to_recordset(items) AS r({RECORD});
    INSERT INTO public.places_catalog_calendars(generation,source_id,entry)
      SELECT '{new}',e->>'source_id',e FROM jsonb_array_elements(companions) AS e;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM public.places_catalog_imports WHERE generation='{new}' AND manifest=metadata) OR
    EXISTS (SELECT entry FROM public.places_catalog_calendars WHERE generation='{new}' EXCEPT SELECT value FROM jsonb_array_elements(companions)) OR
    EXISTS (SELECT value FROM jsonb_array_elements(companions) EXCEPT SELECT entry FROM public.places_catalog_calendars WHERE generation='{new}')
  THEN RAISE EXCEPTION 'Immutable expected metadata or complete companions differ'; END IF;
  IF EXISTS (
    SELECT {FIELDS} FROM public.places_catalog WHERE generation='{new}'
    EXCEPT (SELECT {FIELDS} FROM public.places_catalog WHERE generation='{old}' UNION ALL SELECT {FIELDS} FROM jsonb_to_recordset(items) AS r({RECORD}))
  ) OR EXISTS (
    (SELECT {FIELDS} FROM public.places_catalog WHERE generation='{old}' UNION ALL SELECT {FIELDS} FROM jsonb_to_recordset(items) AS r({RECORD}))
    EXCEPT SELECT {FIELDS} FROM public.places_catalog WHERE generation='{new}'
  ) THEN RAISE EXCEPTION 'Immutable typed additions or raw source fields differ'; END IF;
  {_generation_guard(receipt["parent"])}
  {_generation_guard(receipt["candidate"])}
  {_baseline_guard(old, new)}
  {_storage_guard()}
  IF (SELECT generation FROM public.places_catalog_active WHERE singleton=true) IS DISTINCT FROM previous
  THEN RAISE EXCEPTION 'Staging changed active generation'; END IF;
END"""
    return _transaction(body, staging=True)


def cutover_statements(receipt, *, rollback=False):
    """Compile pointer-only transitions guarded by both immutable PG18 snapshots."""
    enrich.validate_recovery_receipt(receipt)
    old, new = receipt["parent"]["generation"], receipt["candidate"]["generation"]
    identifiers(
        old, new, receipt["parent"]["rows_md5"], receipt["candidate"]["rows_md5"]
    )
    target = old if rollback else new
    # Frozen recovery mirrors calendar_enrichment.rollback: no source freshness
    # or storage-growth precondition can prevent restoring unchanged generations.
    storage = "" if rollback else _storage_guard()
    body = f"""DECLARE
  previous text;
  catalog_bytes bigint;
BEGIN
  IF current_setting('server_version_num')::int / 10000 <> 18 THEN RAISE EXCEPTION 'PostgreSQL 18 required'; END IF;
  SELECT generation INTO previous FROM public.places_catalog_active WHERE singleton=true FOR UPDATE;
  IF previous IS NULL OR previous NOT IN ('{old}','{new}') THEN RAISE EXCEPTION 'Unexpected active generation'; END IF;
  {_generation_guard(receipt["parent"])}
  {_generation_guard(receipt["candidate"])}
  {_baseline_guard(old, new)}
  {storage}
  IF previous<>'{target}' THEN UPDATE public.places_catalog_active SET generation='{target}' WHERE singleton=true; END IF;
  IF (SELECT generation FROM public.places_catalog_active WHERE singleton=true) IS DISTINCT FROM '{target}'
  THEN RAISE EXCEPTION 'Incremental pointer cutover failed'; END IF;
END"""
    return _transaction(body)


def compile_release(connection, prepared):
    """Return SQL/receipt after actual staging; execute no migration or catalog write."""
    _local_connection(connection)
    _bounded(prepared)
    with connection, connection.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SHOW server_version_num")
        if int(cur.fetchone()["server_version_num"]) // 10000 != 18:
            raise ValueError("PostgreSQL 18 required for release fingerprints")
    receipt = enrich.recovery_receipt(connection, prepared)
    with connection, connection.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SET LOCAL statement_timeout='5s'")
        cur.execute("SET LOCAL lock_timeout='5s'")
        cur.execute("SELECT pg_advisory_xact_lock(827461905)")
        cur.execute(
            "SELECT generation FROM public.places_catalog_active WHERE singleton=true"
        )
        active = cur.fetchone()
        if not active or active["generation"] not in {
            receipt["parent"]["generation"],
            receipt["candidate"]["generation"],
        }:
            raise ValueError(
                "unexpected active generation during incremental SQL compilation"
            )
        manifest, entries = enrich._expected(cur, prepared)
        for name in ("parent", "candidate"):
            if enrich._snapshot(cur, receipt[name]["generation"]) != receipt[name]:
                raise ValueError("release rehearsal changed during SQL compilation")
        enrich._storage(cur)
    migration = (ROOT / "backend/sql/places_catalog_calendars.sql").read_text()
    return {
        "schema_version": SCHEMA,
        "generation": prepared["generation"],
        "migration_sql": migration,
        "migration_sha256": hashlib.sha256(migration.encode()).hexdigest(),
        "stage_statements": stage_statements(prepared, manifest, entries, receipt),
        "activation_statements": cutover_statements(receipt),
        "rollback_statements": cutover_statements(receipt, rollback=True),
        "frozen_receipt": copy.deepcopy(receipt),
    }
