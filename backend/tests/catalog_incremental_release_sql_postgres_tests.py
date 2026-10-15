"""Inert companion exports exercised on actual isolated PostgreSQL 18, never hosted data."""

import copy
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import psycopg2
import pytest
from psycopg2.extras import Json, RealDictCursor

from app.catalog import calendar_enrichment as enrich
from app.catalog import ingest, kaggle_cultural
from tests.catalog_calendar_enrichment_tests import artifact
from tests.catalog_extraction_tests import load_script
from tests.catalog_ingest_tests import bundle, feature
from tests.catalog_postgres_tests import connection as connection

compiler = load_script("catalog_incremental_release_sql")


def execute(connection, statements):
    with connection, connection.cursor() as cur:
        for statement in statements:
            cur.execute(statement)


def state(connection):
    """Include every stored column/timestamp to prove cutovers change only the pointer."""
    with connection, connection.cursor() as cur:
        result = {}
        for table, order in (
            ("places_catalog_imports", "generation"),
            ("places_catalog", "generation,source_id"),
            ("places_catalog_calendars", "generation,source_id"),
            ("places_catalog_active", "singleton"),
        ):
            cur.execute(f"SELECT to_jsonb(t) FROM public.{table} t ORDER BY {order}")
            result[table] = [row[0] for row in cur.fetchall()]
    return result


def snapshots(connection, receipt):
    with connection, connection.cursor(cursor_factory=RealDictCursor) as cur:
        return {
            name: enrich._snapshot(cur, receipt[name]["generation"])
            for name in ("parent", "candidate")
        }


def inputs(connection, tmp_path, monkeypatch, *, additions=True, inherited=True):
    """Admit public synthetic fixtures through prepare's typed adapter seam."""
    place = tmp_path / "parent"
    place.mkdir()
    path, metadata = bundle(place, [feature()])
    rows, _ = ingest.prepare(path, metadata)
    prior = ingest.stage(connection, path, metadata)["generation"]
    ingest.activate(connection, prior)
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    path, payload = artifact(overlay, baseline=rows, generation=prior, manifest=metadata)
    if inherited:
        previous = copy.deepcopy(payload["entries"][0])
        previous.update(
            source_release="synthetic-primary",
            source_attribution="Synthetic original primary source rights",
        )
        previous["source_constraints"].append({"fact": "Synthetic prior operator restriction"})
        metadata.update(calendar_count=1, calendar_enrichment_sha256=enrich.digest([previous]))
        with connection, connection.cursor() as cur:
            cur.execute(
                "UPDATE places_catalog_imports SET manifest=%s WHERE generation=%s",
                (Json(metadata), prior),
            )
            cur.execute(
                "INSERT INTO places_catalog_calendars VALUES(%s,%s,%s)",
                (prior, previous["source_id"], Json(previous)),
            )
        payload["parent"]["manifest_sha256"] = enrich.digest(metadata)
        payload["parent"]["calendar_enrichment_sha256"] = enrich.digest([previous])
    if additions:
        extra = tmp_path / "addition"
        extra.mkdir()
        addition_path, addition_manifest = bundle(
            extra,
            [
                {
                    **feature(
                        id="synthetic-added-place",
                        names={"primary": "Synthetic added $catalog_stage$ museum's gallery"},
                    ),
                    "geometry": {"type": "Point", "coordinates": [-122.45, 37.85]},
                }
            ],
        )
        added_rows, _ = ingest.prepare(addition_path, addition_manifest)
        added_entry = copy.deepcopy(payload["entries"][0])
        added_entry["source_id"] = added_rows[0]["source_id"]
        typed = overlay / "typed-fixture.json"
        typed.write_text('{"synthetic_typed_adapter_fixture":true}')

        def typed_source(source, _manifest, **_ceilings):
            assert source == typed
            return copy.deepcopy(added_rows), {
                "bytes": typed.stat().st_size,
                "scanned": 1,
                "calendar_entries": [copy.deepcopy(added_entry)],
            }

        monkeypatch.setattr(kaggle_cultural, "prepare", typed_source)
        payload["addition_inputs"] = [
            {
                "adapter": "kaggle-cultural",
                "path": typed.name,
                "sha256": hashlib.sha256(typed.read_bytes()).hexdigest(),
                "manifest": {
                    "release": "synthetic-new-primary",
                    "attribution": "Synthetic new primary source rights",
                },
            }
        ]
    path.write_text(json.dumps(payload))
    prepared = enrich.prepare(path)
    enrich.stage(connection, prepared)
    return prepared, compiler.compile_release(connection, prepared)


def remove_candidate(connection, compiled):
    generation = compiled["generation"]
    with connection, connection.cursor() as cur:
        for table in ("places_catalog_calendars", "places_catalog", "places_catalog_imports"):
            cur.execute(f"DELETE FROM {table} WHERE generation=%s", (generation,))


@pytest.mark.parametrize("additions", [False, True])
def test_export_is_inert_and_stage_cutovers_reproduce_every_frozen_field(
    connection, tmp_path, monkeypatch, additions
):
    prepared, compiled = inputs(connection, tmp_path, monkeypatch, additions=additions)
    frozen = copy.deepcopy(prepared)
    before = state(connection)
    again = compiler.compile_release(connection, prepared)
    assert again == compiled and prepared == frozen and state(connection) == before
    receipt = compiled["frozen_receipt"]
    assert snapshots(connection, receipt) == {
        name: receipt[name] for name in ("parent", "candidate")
    }
    assert receipt["candidate"]["row_count"] == receipt["parent"]["row_count"] + int(additions)
    assert receipt["candidate"]["calendar_count"] == 1 + int(additions)
    assert (
        compiled["migration_sql"]
        == (Path(__file__).parents[1] / "sql/places_catalog_calendars.sql").read_text()
    )
    assert (
        compiled["migration_sha256"]
        == hashlib.sha256(compiled["migration_sql"].encode()).hexdigest()
    )
    assert "imported_at" not in "\n".join(compiled["stage_statements"])
    remove_candidate(connection, compiled)
    old_state = state(connection)
    execute(connection, compiled["stage_statements"])
    staged = state(connection)
    assert staged["places_catalog_active"] == old_state["places_catalog_active"]
    assert snapshots(connection, receipt) == {
        name: receipt[name] for name in ("parent", "candidate")
    }
    for row in old_state["places_catalog"]:
        assert row in staged["places_catalog"]
        assert {**row, "generation": compiled["generation"]} in staged["places_catalog"]
    candidate_entries = [
        e["entry"]
        for e in staged["places_catalog_calendars"]
        if e["generation"] == compiled["generation"]
    ]
    inherited = next(
        e for e in candidate_entries if e["source_id"] == prepared["baseline"][0]["source_id"]
    )
    assert inherited["source_release"] == "synthetic-primary"
    assert inherited["source_constraints"][-1]["entry"]["source_release"] == "synthetic-primary"
    execute(connection, compiled["stage_statements"])
    assert state(connection) == staged
    for operation, expected in (
        ("activation_statements", compiled["generation"]),
        ("activation_statements", compiled["generation"]),
        ("stage_statements", compiled["generation"]),
        ("rollback_statements", receipt["parent"]["generation"]),
        ("rollback_statements", receipt["parent"]["generation"]),
        ("activation_statements", compiled["generation"]),
    ):
        execute(connection, compiled[operation])
        after = state(connection)
        assert after["places_catalog_active"] == [{"singleton": True, "generation": expected}]
        assert {k: v for k, v in after.items() if k != "places_catalog_active"} == {
            k: v for k, v in staged.items() if k != "places_catalog_active"
        }


@pytest.mark.parametrize("generation", ["parent", "candidate"])
@pytest.mark.parametrize(
    "changed",
    ["rows", "provenance", "manifest", "release", "row_count", "calendar", "missing_calendar"],
)
def test_all_exported_operations_reject_every_generation_tamper(
    connection, tmp_path, monkeypatch, generation, changed
):
    _, compiled = inputs(connection, tmp_path, monkeypatch)
    target = compiled["frozen_receipt"][generation]["generation"]
    with connection, connection.cursor() as cur:
        if changed == "rows":
            cur.execute(
                "UPDATE places_catalog SET name='Changed synthetic row' WHERE generation=%s",
                (target,),
            )
        elif changed == "provenance":
            cur.execute(
                "UPDATE places_catalog SET provenance=provenance || '[{\"changed\":true}]'::jsonb WHERE generation=%s",
                (target,),
            )
        elif changed == "manifest":
            cur.execute(
                "UPDATE places_catalog_imports SET manifest=manifest || '{\"changed\":true}'::jsonb WHERE generation=%s",
                (target,),
            )
        elif changed == "release":
            cur.execute(
                "UPDATE places_catalog_imports SET release='Changed synthetic release' WHERE generation=%s",
                (target,),
            )
        elif changed == "row_count":
            cur.execute(
                "UPDATE places_catalog_imports SET row_count=row_count+1 WHERE generation=%s",
                (target,),
            )
        elif changed == "calendar":
            cur.execute(
                'UPDATE places_catalog_calendars SET entry=entry || \'{"transformation":{"changed":true}}\'::jsonb WHERE generation=%s',
                (target,),
            )
        else:
            cur.execute("DELETE FROM places_catalog_calendars WHERE generation=%s", (target,))
    before = state(connection)
    for operation in ("stage_statements", "activation_statements", "rollback_statements"):
        with pytest.raises(
            psycopg2.Error, match="incomplete or changed|metadata or companions changed"
        ):
            execute(connection, compiled[operation])
        assert state(connection) == before


def test_pointer_only_frozen_rollback_has_no_source_or_storage_freshness_dependency(
    connection, tmp_path, monkeypatch
):
    _, compiled = inputs(connection, tmp_path, monkeypatch)
    execute(connection, compiled["activation_statements"])
    before = state(connection)
    for name in ("prepare", "_expected", "recovery_receipt"):
        monkeypatch.setattr(
            enrich, name, lambda *_a, **_kw: pytest.fail("frozen SQL must not readmit sources")
        )
    monkeypatch.setattr(ingest, "MAX_CATALOG_BYTES", 1)
    rollback = compiler.cutover_statements(compiled["frozen_receipt"], rollback=True)
    execute(connection, rollback)
    execute(connection, rollback)
    after = state(connection)
    assert (
        after["places_catalog_active"][0]["generation"]
        == compiled["frozen_receipt"]["parent"]["generation"]
    )
    assert {k: v for k, v in before.items() if k != "places_catalog_active"} == {
        k: v for k, v in after.items() if k != "places_catalog_active"
    }


def test_export_requires_actual_staging_and_rejects_changed_prepared_receipt_or_empty_calendar(
    connection, tmp_path, monkeypatch
):
    prepared, compiled = inputs(connection, tmp_path, monkeypatch)
    remove_candidate(connection, compiled)
    before = state(connection)
    with pytest.raises(ValueError, match="changed or incomplete"):
        compiler.compile_release(connection, prepared)
    assert state(connection) == before
    execute(connection, compiled["stage_statements"])
    altered = copy.deepcopy(prepared)
    altered["entries"][0]["source_constraints"].append({"fact": "Unreviewed synthetic change"})
    with pytest.raises(ValueError, match="after source verification"):
        compiler.compile_release(connection, altered)
    broken = copy.deepcopy(compiled["frozen_receipt"])
    broken["candidate"]["rows_md5"] = "injected SQL"
    with pytest.raises(ValueError, match="fingerprint"):
        compiler.cutover_statements(broken)
    with connection, connection.cursor(cursor_factory=RealDictCursor) as cur:
        metadata, entries = enrich._expected(cur, prepared)
    entries[0]["source_visit_calendar"].update(
        weekly_windows=[], date_overrides=[], unknown_reasons=[]
    )
    with pytest.raises(ValueError, match="explicit source windows"):
        compiler.stage_statements(prepared, metadata, entries, compiled["frozen_receipt"])


def test_resource_limits_include_companion_relation_and_failed_stage_is_atomic(
    connection, tmp_path, monkeypatch
):
    prepared, compiled = inputs(connection, tmp_path, monkeypatch)
    with connection, connection.cursor(cursor_factory=RealDictCursor) as cur:
        metadata, entries = enrich._expected(cur, prepared)
        cur.execute("SELECT pg_total_relation_size('places_catalog_calendars') AS bytes")
        companion_bytes = cur.fetchone()["bytes"]
        storage = enrich._storage(cur)
    assert companion_bytes > 0
    # Ceiling would pass the old three-relation accounting and fail including companions.
    monkeypatch.setattr(ingest, "MAX_CATALOG_BYTES", storage["catalog_bytes"] - companion_bytes + 1)
    statements = compiler.stage_statements(prepared, metadata, entries, compiled["frozen_receipt"])
    before = state(connection)
    with pytest.raises(psycopg2.Error, match="storage ceiling"):
        execute(connection, statements)
    assert state(connection) == before
    for field, value in (
        ("bytes", ingest.MAX_BYTES + 1),
        ("source_scanned_rows", ingest.MAX_ROWS + 1),
    ):
        altered = copy.deepcopy(prepared)
        altered["report"][field] = value
        with pytest.raises(ValueError, match="row/input ceilings"):
            compiler.stage_statements(altered, metadata, entries, compiled["frozen_receipt"])


def test_missing_pointer_and_modified_payload_cannot_stage_or_cutover(
    connection, tmp_path, monkeypatch
):
    _, compiled = inputs(connection, tmp_path, monkeypatch)
    before = state(connection)
    tampered = copy.deepcopy(compiled["stage_statements"])
    tampered[-1] = tampered[-1].replace("museum's gallery", "unreviewed replacement")
    with pytest.raises(psycopg2.Error, match="typed additions or raw source fields"):
        execute(connection, tampered)
    assert state(connection) == before
    with connection, connection.cursor() as cur:
        cur.execute("DELETE FROM places_catalog_active")
    before = state(connection)
    for operation in ("stage_statements", "activation_statements", "rollback_statements"):
        with pytest.raises(psycopg2.Error, match="Unexpected active generation"):
            execute(connection, compiled[operation])
        assert state(connection) == before


def test_additive_migration_is_exact_idempotent_before_replaying_stage(
    connection, tmp_path, monkeypatch
):
    _, compiled = inputs(connection, tmp_path, monkeypatch, inherited=False)
    remove_candidate(connection, compiled)
    with connection, connection.cursor() as cur:
        cur.execute("DROP TABLE places_catalog_calendars")
        cur.execute(compiled["migration_sql"])
        cur.execute(compiled["migration_sql"])
    execute(connection, compiled["stage_statements"])
    assert snapshots(connection, compiled["frozen_receipt"]) == {
        name: compiled["frozen_receipt"][name] for name in ("parent", "candidate")
    }


def test_compiler_refuses_nonlocal_rehearsal_connection():
    connection = SimpleNamespace(get_dsn_parameters=lambda: {"host": "database.example"})
    with pytest.raises(ValueError, match="local rehearsal"):
        compiler.compile_release(connection, {})


@pytest.mark.parametrize("field", ["name", "provenance"])
def test_full_baseline_equality_is_independent_of_matching_row_fingerprints(
    connection, tmp_path, monkeypatch, field
):
    prepared, compiled = inputs(connection, tmp_path, monkeypatch)
    candidate = compiled["generation"]
    with connection, connection.cursor() as cur:
        value = "Changed baseline fixture" if field == "name" else Json([{"changed": True}])
        cur.execute(
            f"UPDATE places_catalog SET {field}=%s WHERE generation=%s AND source_id=%s",
            (value, candidate, prepared["baseline"][0]["source_id"]),
        )
    receipt = copy.deepcopy(compiled["frozen_receipt"])
    with connection, connection.cursor(cursor_factory=RealDictCursor) as cur:
        receipt["candidate"] = enrich._snapshot(cur, candidate)
    before = state(connection)
    # Even a separately recomputed matching fingerprint cannot authorize replacing
    # a parent's raw value. Both cutover directions compare every raw field.
    for rollback in (False, True):
        with pytest.raises(psycopg2.Error, match="Baseline raw source fields/provenance"):
            execute(connection, compiler.cutover_statements(receipt, rollback=rollback))
        assert state(connection) == before


def test_post_insert_companion_storage_failure_rolls_back_every_staged_write(
    connection, tmp_path, monkeypatch
):
    prepared, compiled = inputs(connection, tmp_path, monkeypatch, inherited=False)
    with connection, connection.cursor(cursor_factory=RealDictCursor) as cur:
        metadata, entries = enrich._expected(cur, prepared)
    remove_candidate(connection, compiled)
    with connection, connection.cursor() as cur:
        # A fresh empty companion relation measures the actual page growth of its
        # first insertion; this is the additive migration's real release state.
        cur.execute("DROP TABLE places_catalog_calendars")
        cur.execute(compiled["migration_sql"])
    with connection, connection.cursor(cursor_factory=RealDictCursor) as cur:
        storage = enrich._storage(cur)
    monkeypatch.setattr(ingest, "MAX_CATALOG_BYTES", storage["catalog_bytes"] + 1)
    statements = compiler.stage_statements(prepared, metadata, entries, compiled["frozen_receipt"])
    before = state(connection)
    with pytest.raises(psycopg2.Error, match="storage ceiling"):
        execute(connection, statements)
    assert state(connection) == before
