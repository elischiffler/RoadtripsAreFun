#!/usr/bin/env python3
"""Compile inert, guarded catalog staging/cutover SQL for independent review.

Useful when the approved database is reachable only through an authorized SQL
connector. Only catalog tables are referenced. Staging clones the verified
immutable baseline and adds already source-admitted rows in one transaction;
activation and rollback are separate pointer-only transactions.
"""

import hashlib
import json
import re

from app.catalog.ingest import MAX_CATALOG_BYTES, MAX_DATABASE_BYTES, MAX_ROWS

FIELDS = (
    "source_id,name,latitude,longitude,region,categories,address,url,source_updated_at,provenance"
)
RECORD = "source_id text,name text,latitude double precision,longitude double precision,region text,categories text[],address text,url text,source_updated_at text,provenance jsonb"


def literal(value):
    tag = "$payload_" + hashlib.sha256(value.encode()).hexdigest() + "$"
    if tag in value:
        raise ValueError("ambiguous SQL literal")
    return tag + value + tag


def identifiers(old, new, old_fingerprint, new_fingerprint=None):
    if old == new or any(not re.fullmatch(r"[0-9a-f]{64}", x) for x in (old, new)):
        raise ValueError("expected distinct immutable generation hashes")
    if any(
        not re.fullmatch(r"[0-9a-f]{32}", x)
        for x in (
            old_fingerprint,
            *([new_fingerprint] if new_fingerprint is not None else []),
        )
    ):
        raise ValueError("expected actual PostgreSQL content fingerprints")


def generation_guard(generation, count, fingerprint):
    return f"""
  IF NOT EXISTS (SELECT 1 FROM public.places_catalog_imports WHERE generation='{generation}' AND row_count={count}) OR
     (SELECT count(*) FROM public.places_catalog WHERE generation='{generation}')<>{count} OR
     (SELECT md5(jsonb_agg(to_jsonb(p) ORDER BY p.source_id COLLATE "C")::text) FROM public.places_catalog p WHERE generation='{generation}') IS DISTINCT FROM '{fingerprint}'
  THEN RAISE EXCEPTION 'Required catalog generation is incomplete or changed'; END IF;
"""


def storage_guard():
    return f"""
  SELECT COALESCE(sum(pg_total_relation_size(c.oid)),0) INTO catalog_bytes
    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relkind='r'
      AND c.relname IN ('places_catalog','places_catalog_imports','places_catalog_active');
  IF pg_database_size(current_database())>{MAX_DATABASE_BYTES} OR catalog_bytes>{MAX_CATALOG_BYTES}
  THEN RAISE EXCEPTION 'Catalog/database storage ceiling exceeded'; END IF;
"""


def stage_statements(rows, manifest, *, old, old_count, old_fingerprint, baseline):
    """Accept only a previously source-admitted complete replacement and baseline."""
    new = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    identifiers(old, new, old_fingerprint)
    if not 0 < old_count < len(rows) <= MAX_ROWS or len(baseline) != old_count:
        raise ValueError("invalid bounded expansion counts")
    prior = {row["source_id"]: row for row in baseline}
    replacement = {row["source_id"]: row for row in rows}
    if len(prior) != old_count or len(replacement) != len(rows):
        raise ValueError("duplicate source identities")
    if any(replacement.get(key) != value for key, value in prior.items()):
        raise ValueError("replacement changes preserved source fields/provenance")
    added = [row for row in rows if row["source_id"] not in prior]
    raw = json.dumps(added, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    metadata = json.dumps(manifest, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    body = f"""DO $catalog_stage$
DECLARE
  items constant jsonb := {literal(raw)}::jsonb;
  metadata constant jsonb := {literal(metadata)}::jsonb;
  gen constant text := '{new}';
  catalog_bytes bigint;
BEGIN
  IF current_setting('server_version_num')::int / 10000 <> 18 THEN RAISE EXCEPTION 'PostgreSQL 18 required'; END IF;
  IF (SELECT generation FROM public.places_catalog_active WHERE singleton=true) IS DISTINCT FROM '{old}' THEN RAISE EXCEPTION 'Unexpected active generation'; END IF;
  {generation_guard(old, old_count, old_fingerprint)}
  {storage_guard()}
  IF jsonb_array_length(items)<>{len(added)} THEN RAISE EXCEPTION 'Payload count mismatch'; END IF;
  IF EXISTS (SELECT 1 FROM public.places_catalog_imports WHERE generation=gen AND (manifest<>metadata OR row_count<>{len(rows)} OR release<>metadata->>'release')) THEN RAISE EXCEPTION 'Immutable catalog metadata conflict'; END IF;
  INSERT INTO public.places_catalog_imports(generation,release,manifest,row_count)
    VALUES(gen,metadata->>'release',metadata,{len(rows)}) ON CONFLICT(generation) DO NOTHING;
  INSERT INTO public.places_catalog(generation,{FIELDS})
    SELECT gen,{FIELDS} FROM public.places_catalog WHERE generation='{old}' ON CONFLICT(generation,source_id) DO NOTHING;
  INSERT INTO public.places_catalog(generation,{FIELDS})
    SELECT gen,{FIELDS} FROM jsonb_to_recordset(items) AS r({RECORD}) ON CONFLICT(generation,source_id) DO NOTHING;
  IF (SELECT count(*) FROM public.places_catalog WHERE generation=gen)<>{len(rows)} THEN RAISE EXCEPTION 'Stored catalog count differs'; END IF;
  IF EXISTS (
    SELECT {FIELDS} FROM public.places_catalog WHERE generation=gen
    EXCEPT (SELECT {FIELDS} FROM public.places_catalog WHERE generation='{old}' UNION ALL SELECT {FIELDS} FROM jsonb_to_recordset(items) AS r({RECORD}))
  ) OR EXISTS (
    (SELECT {FIELDS} FROM public.places_catalog WHERE generation='{old}' UNION ALL SELECT {FIELDS} FROM jsonb_to_recordset(items) AS r({RECORD}))
    EXCEPT SELECT {FIELDS} FROM public.places_catalog WHERE generation=gen
  ) THEN RAISE EXCEPTION 'Immutable catalog content differs'; END IF;
  {storage_guard()}
  {generation_guard(old, old_count, old_fingerprint)}
  IF (SELECT generation FROM public.places_catalog_active WHERE singleton=true) IS DISTINCT FROM '{old}' THEN RAISE EXCEPTION 'Staging changed active generation'; END IF;
END
$catalog_stage$;"""
    if "$catalog_stage$" in raw or "$catalog_stage$" in metadata:
        raise ValueError("ambiguous SQL block delimiter")
    return new, [
        "SET LOCAL statement_timeout='30s'",
        "SET LOCAL lock_timeout='5s'",
        "SELECT pg_advisory_xact_lock(827461905)",
        body,
    ]


def cutover_statements(
    *, old, new, old_count, new_count, old_fingerprint, new_fingerprint, rollback=False
):
    identifiers(old, new, old_fingerprint, new_fingerprint)
    if not 0 < old_count < new_count <= MAX_ROWS:
        raise ValueError("invalid expansion counts")
    target, previous = (old, new) if rollback else (new, old)
    body = f"""DO $catalog_cutover$
DECLARE previous text;
BEGIN
  IF current_setting('server_version_num')::int / 10000 <> 18 THEN RAISE EXCEPTION 'PostgreSQL 18 required'; END IF;
  SELECT generation INTO previous FROM public.places_catalog_active WHERE singleton=true FOR UPDATE;
  IF previous IS NULL OR previous NOT IN ('{old}','{new}') THEN RAISE EXCEPTION 'Unexpected active generation'; END IF;
  {generation_guard(old, old_count, old_fingerprint)}
  {generation_guard(new, new_count, new_fingerprint)}
  IF EXISTS (SELECT {FIELDS} FROM public.places_catalog WHERE generation='{old}' EXCEPT SELECT {FIELDS} FROM public.places_catalog WHERE generation='{new}') THEN RAISE EXCEPTION 'Baseline facts/provenance not preserved'; END IF;
  IF previous='{previous}' THEN UPDATE public.places_catalog_active SET generation='{target}' WHERE singleton=true;
  ELSIF previous<>'{target}' THEN RAISE EXCEPTION 'Unexpected transition'; END IF;
  IF (SELECT generation FROM public.places_catalog_active WHERE singleton=true) IS DISTINCT FROM '{target}' THEN RAISE EXCEPTION 'Cutover failed'; END IF;
END
$catalog_cutover$;"""
    return [
        "SET LOCAL statement_timeout='5s'",
        "SET LOCAL lock_timeout='5s'",
        "SELECT pg_advisory_xact_lock(827461905)",
        body,
    ]
