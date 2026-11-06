"""Synthetic full import assembly and isolated PostgreSQL binding protection.

Typed-source replay is replaced with explicit synthetic records; all selection,
portable bundling, calendar validation and storage behavior remains real.
"""

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from psycopg2.extras import Json

from app.catalog import automated_nps
from app.catalog import calendar_enrichment as enrich
from app.catalog.automated_bindings import bind_calendar
from tests.catalog_postgres_tests import connection as connection  # noqa: F401

SPEC = importlib.util.spec_from_file_location(
    "automation_integration_cli",
    Path(__file__).resolve().parents[2] / "scripts/catalog_automated_import.py",
)
CLI = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CLI
SPEC.loader.exec_module(CLI)


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True))


def row(sid="nps-heritage:test", *, native="7", code="test", latitude=37.0):
    return {
        "source_id": sid,
        "name": "Synthetic " + sid,
        "latitude": latitude,
        "longitude": -122.0,
        "region": "CA",
        "categories": ["daytime", "visitor_center"],
        "address": "Synthetic fixture address",
        "url": "https://operator.example/synthetic",
        "source_updated_at": None,
        "provenance": [
            {
                "dataset": "Synthetic National Park Service visitor facility",
                "record_id": native,
                "park_code": code,
                "source_release": "original-primary",
                "source_attribution": "Original factual source rights",
            }
        ],
    }


def calendar(sid, *, held=False):
    return {
        "source_id": sid,
        "source_visit_calendar": {
            "schema_version": "roadtrips-source-visit-calendar/1",
            "weekly_windows": [{"weekdays": list(range(7)), "opens": "09:00", "closes": "17:00"}],
            "source_receipts": [
                {
                    "source_url": "https://operator.example/synthetic",
                    "snapshot_sha256": "a" * 64,
                    "checked_at": "2026-10-20T00:00:00Z",
                    "evidence_path": "hours.txt",
                }
            ],
            "unknown_reasons": ["Synthetic unresolved parking access"] if held else [],
        },
        "source_constraints": [
            {"fact": "Synthetic daily source clocks, no factual operator claim"}
        ],
        "transformation": {"method": "Synthetic typed source replay"},
        "source_release": "new-primary",
        "source_attribution": "New operator factual credits",
    }


def setup_import(tmp_path, monkeypatch, *, inherited=False):
    parent_dir = tmp_path / "parent"
    parent_dir.mkdir()
    baseline = [row()]
    inherited_entries = [calendar(baseline[0]["source_id"], held=True)] if inherited else []
    manifest = {
        "release": "original-primary",
        "attribution": "Original factual source rights",
        "normalized_rows_sha256": enrich.rows_digest(baseline),
        "calendar_enrichment_sha256": enrich.digest(inherited_entries),
        "source_catalogs": {
            "nps-public": {
                "release": "original-nps-primary",
                "attribution": "Original NPS factual source rights",
                "source_url": "https://operator.example/original",
            }
        },
    }
    parent = {
        "generation": "a" * 64,
        "row_count": len(baseline),
        "manifest_sha256": enrich.digest(manifest),
        "normalized_rows_sha256": enrich.rows_digest(baseline),
        "calendar_enrichment_sha256": enrich.digest(inherited_entries),
        "release": manifest["release"],
    }
    for name, value in (
        ("rows.json", baseline),
        ("calendars.json", inherited_entries),
        ("manifest.json", manifest),
        ("snapshot.json", parent),
    ):
        write(parent_dir / name, value)
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source = source_dir / "bundle.json"
    write(source, {"synthetic_typed_adapter": True})
    (source_dir / "hours.txt").write_text("Synthetic daily hours 09:00-17:00; no factual claim.")
    (source_dir / "rights.txt").write_text("Synthetic rights fixture.")
    metadata = {
        "release": "new-primary",
        "attribution": "New operator factual credits",
        "source_url": "https://operator.example/synthetic",
        "licenses": {
            "Synthetic-test-only": {
                "path": "rights.txt",
                "url": "https://operator.example/rights",
                "sha256": hashlib.sha256((source_dir / "rights.txt").read_bytes()).hexdigest(),
            }
        },
    }
    write(Path(str(source) + ".manifest.json"), metadata)
    candidate = row("nps-public:facility:test:7")
    extra = row("nps-public:facility:neww:8", native="8", code="neww", latitude=39.0)
    nearby = row("nps-public:facility:near:9", native="9", code="near", latitude=37.0001)
    candidate_rows = [candidate, extra, nearby]

    def replay(path, _manifest, *, max_rows, max_bytes):
        assert json.loads(Path(path).read_text()) == {"synthetic_typed_adapter": True}
        assert max_rows > 0 and max_bytes > 0
        hours = Path(path).parent / "hours.txt"
        entries = [calendar(value["source_id"]) for value in candidate_rows]
        for entry in entries:
            entry["source_visit_calendar"]["source_receipts"][0]["snapshot_sha256"] = (
                hashlib.sha256(hours.read_bytes()).hexdigest()
            )
        return copy.deepcopy(candidate_rows), {
            "scanned": 3,
            "bytes": Path(path).stat().st_size + hours.stat().st_size,
            "calendar_entries": entries,
        }

    monkeypatch.setattr(automated_nps, "prepare", replay)
    return parent_dir, source, baseline, inherited_entries, manifest


def test_unused_retained_source_bytes_cannot_bypass_aggregate_evidence_limit(tmp_path, monkeypatch):
    from scripts import catalog_incremental_bundle

    parent, source, *_ = setup_import(tmp_path, monkeypatch)
    unused = source.parent / "unused-discovery.bin"
    unused.write_bytes(b"x" * 2048)
    # Typed replay does not read this file; the portable bundle still retains it.
    monkeypatch.setattr(catalog_incremental_bundle, "MAX_RETAINED_BYTES", 1024)
    with pytest.raises(ValueError, match="retained source evidence exceeds ceiling"):
        CLI.bundle(parent, [("automated-nps", source)], tmp_path / "bounded-output")


def test_source_replay_selects_new_arrival_and_binds_calendar_without_replacing_parent_fields(
    tmp_path, monkeypatch
):
    parent, source, baseline, _, manifest = setup_import(tmp_path, monkeypatch)
    output = tmp_path / "assembled"
    report = CLI.bundle(parent, [("automated-nps", source)], output)
    prepared = enrich.prepare(output / "catalog.enrichment.json")
    item = prepared["manifest"]["addition_inputs"][0]
    assert item["selected_source_ids"] == ["nps-public:facility:neww:8"]
    assert item["calendar_bindings"] == {"nps-public:facility:test:7": baseline[0]["source_id"]}
    assert prepared["baseline"] == baseline
    assert prepared["rows"][0] == baseline[0]
    assert {entry["source_id"] for entry in prepared["entries"]} == {
        baseline[0]["source_id"],
        "nps-public:facility:neww:8",
    }
    bound = next(
        entry for entry in prepared["entries"] if entry["source_id"] == baseline[0]["source_id"]
    )
    assert "source_release" not in bound
    assert bound["source_attribution"] == "New operator factual credits"
    assert prepared["manifest"]["additional_source_catalogs"] == {}
    assert json.loads((parent / "manifest.json").read_text()) == manifest
    assert (
        bound["source_visit_calendar"]["source_receipts"][0]["evidence_path"]
        == "inputs/source-00/hours.txt"
    )
    assert report["arrival_decisions"] == {"selected": 1, "held": 1, "calendar_update": 1}


def test_existing_companion_hold_blocks_auto_binding_while_other_safe_additions_survive(
    tmp_path, monkeypatch
):
    parent, source, baseline, previous, _ = setup_import(tmp_path, monkeypatch, inherited=True)
    output = tmp_path / "assembled"
    CLI.bundle(parent, [("automated-nps", source)], output)
    prepared = enrich.prepare(output / "catalog.enrichment.json")
    item = prepared["manifest"]["addition_inputs"][0]
    assert item["calendar_bindings"] == {}
    assert {entry["source_id"] for entry in prepared["entries"]} == {"nps-public:facility:neww:8"}
    assert json.loads((parent / "calendars.json").read_text()) == previous
    assert prepared["baseline"] == baseline


def test_forged_binding_cannot_move_arrival_or_select_unreplayed_source_identity(
    tmp_path, monkeypatch
):
    parent, source, baseline, _, _ = setup_import(tmp_path, monkeypatch)
    output = tmp_path / "assembled"
    CLI.bundle(parent, [("automated-nps", source)], output)
    path = output / "catalog.enrichment.json"
    original = json.loads(path.read_text())
    changed = copy.deepcopy(original)
    changed["addition_inputs"][0]["selected_source_ids"].append("unreplayed-facility")
    write(path, changed)
    with pytest.raises(ValueError, match="selected source identities"):
        enrich.prepare(path)
    changed = copy.deepcopy(original)
    changed["addition_inputs"][0]["calendar_bindings"]["nps-public:facility:neww:8"] = baseline[0][
        "source_id"
    ]
    changed["addition_inputs"][0]["selected_source_ids"] = []
    write(path, changed)
    with pytest.raises(ValueError, match="bindings"):
        enrich.prepare(path)
    candidate = copy.deepcopy(baseline[0])
    candidate.update(source_id="nps-public:facility:test:7", latitude=37.1)
    with pytest.raises(ValueError, match="identical native facility"):
        bind_calendar(candidate, baseline[0], calendar(candidate["source_id"]))


def seed_parent(connection, parent_dir):
    baseline = json.loads((parent_dir / "rows.json").read_text())
    entries = json.loads((parent_dir / "calendars.json").read_text())
    manifest = json.loads((parent_dir / "manifest.json").read_text())
    generation = json.loads((parent_dir / "snapshot.json").read_text())["generation"]
    with connection, connection.cursor() as cur:
        cur.execute(
            "INSERT INTO places_catalog_imports(generation,release,manifest,row_count) VALUES(%s,%s,%s,%s)",
            (generation, manifest["release"], Json(manifest), len(baseline)),
        )
        for value in baseline:
            cur.execute(
                "INSERT INTO places_catalog(generation,source_id,name,latitude,longitude,region,categories,address,url,source_updated_at,provenance) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    generation,
                    *(
                        Json(value[key]) if key == "provenance" else value[key]
                        for key in enrich.FIELDS.split(",")
                    ),
                ),
            )
        for entry in entries:
            cur.execute(
                "INSERT INTO places_catalog_calendars VALUES(%s,%s,%s)",
                (generation, entry["source_id"], Json(entry)),
            )
        cur.execute("INSERT INTO places_catalog_active VALUES(true,%s)", (generation,))
    return generation


def test_isolated_postgres_source_replay_stage_activation_and_rollback_preserve_parent_credits(
    connection, tmp_path, monkeypatch
):
    parent, source, baseline, _, manifest = setup_import(tmp_path, monkeypatch)
    old = seed_parent(connection, parent)
    output = tmp_path / "assembled"
    CLI.bundle(parent, [("automated-nps", source)], output)
    prepared = enrich.prepare(output / "catalog.enrichment.json")
    enrich.stage(connection, prepared)
    with connection.cursor() as cur:
        cur.execute("SELECT generation FROM places_catalog_active")
        assert cur.fetchone()[0] == old
    connection.rollback()
    enrich.activate(connection, prepared)
    with connection.cursor() as cur:
        cur.execute(
            "SELECT manifest FROM places_catalog_imports WHERE generation=%s",
            (prepared["generation"],),
        )
        stored = cur.fetchone()[0]
        assert stored["source_catalogs"] == manifest["source_catalogs"]
        cur.execute(
            "SELECT source_id,name,latitude,longitude,provenance FROM places_catalog WHERE generation=%s AND source_id=%s",
            (prepared["generation"], baseline[0]["source_id"]),
        )
        actual = cur.fetchone()
        assert actual == (
            baseline[0]["source_id"],
            baseline[0]["name"],
            baseline[0]["latitude"],
            baseline[0]["longitude"],
            baseline[0]["provenance"],
        )
        cur.execute(
            "SELECT entry FROM places_catalog_calendars WHERE generation=%s AND source_id=%s",
            (prepared["generation"], baseline[0]["source_id"]),
        )
        assert "source_release" not in cur.fetchone()[0]
    connection.rollback()
    assert enrich.activate(connection, prepared, rollback=True)["generation"] == old


def test_isolated_postgres_rejects_binding_over_existing_companion_hold(
    connection, tmp_path, monkeypatch
):
    parent, source, _, previous, _ = setup_import(tmp_path, monkeypatch, inherited=True)
    old = seed_parent(connection, parent)
    output = tmp_path / "assembled"
    CLI.bundle(parent, [("automated-nps", source)], output)
    path = output / "catalog.enrichment.json"
    payload = json.loads(path.read_text())
    payload["addition_inputs"][0]["calendar_bindings"] = {
        "nps-public:facility:test:7": "nps-heritage:test"
    }
    write(path, payload)
    prepared = enrich.prepare(path)
    with pytest.raises(ValueError, match="cannot overwrite prior calendar facts or holds"):
        enrich.stage(connection, prepared)
    with connection.cursor() as cur:
        cur.execute("SELECT generation FROM places_catalog_active")
        assert cur.fetchone()[0] == old
        cur.execute("SELECT entry FROM places_catalog_calendars WHERE generation=%s", (old,))
        assert [row[0] for row in cur.fetchall()] == previous
    connection.rollback()


def test_binding_rejects_conflicting_native_identity_and_embedded_source_hold():
    parent = row()
    candidate = row("nps-public:facility:test:7")
    candidate["provenance"].append(
        {**candidate["provenance"][0], "record_id": "different-facility"}
    )
    with pytest.raises(ValueError, match="identical native facility"):
        bind_calendar(candidate, parent, calendar(candidate["source_id"]))
    candidate["provenance"].pop()
    parent["provenance"].append(calendar(parent["source_id"], held=True))
    with pytest.raises(ValueError, match="existing calendar"):
        bind_calendar(candidate, parent, calendar(candidate["source_id"]))


def test_offline_build_refuses_changed_parent_metadata_before_writing_artifact(
    tmp_path, monkeypatch
):
    parent, source, _, _, manifest = setup_import(tmp_path, monkeypatch)
    manifest["attribution"] = "Changed parent credits"
    write(parent / "manifest.json", manifest)
    output = tmp_path / "assembled"
    with pytest.raises(ValueError, match="parent metadata differs"):
        CLI.bundle(parent, [("automated-nps", source)], output)
    assert not output.exists()
