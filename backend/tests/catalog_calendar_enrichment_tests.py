"""Calendar companions preserve source rows and fail closed before writes."""

import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.catalog import calendar_enrichment as enrich
from app.catalog.repository import source_attribution
from app.routing.visit_calendar import calendar_eligible, source_calendar


def artifact(tmp_path, baseline=None, generation="a" * 64, manifest=None):
    """Synthetic publisher facts, never production or claimed operator data."""
    baseline = baseline or [{"source_id": "synthetic", "name": "Synthetic test fixture"}]
    body = tmp_path / "hours.txt"
    body.write_text("Synthetic fixture: Saturday 09:00-14:00. Wednesday closed.")
    snapshot = tmp_path / "baseline.json"
    snapshot.write_text(json.dumps(baseline))
    receipt = {
        "source_url": "https://operator.example/synthetic-hours",
        "snapshot_sha256": hashlib.sha256(body.read_bytes()).hexdigest(),
        "evidence_path": "hours.txt",
        "checked_at": "2026-10-15T00:00:00Z",
    }
    entry = {
        "source_id": baseline[0]["source_id"],
        "source_visit_calendar": {
            "schema_version": "roadtrips-source-visit-calendar/1",
            "weekly_windows": [{"weekdays": [5], "opens": "09:00", "closes": "14:00"}],
            "source_receipts": [receipt],
        },
        "source_constraints": [
            {"source_url": receipt["source_url"], "fact": "Synthetic Saturday clocks"}
        ],
        "transformation": {"method": "Synthetic unit-test literal extraction"},
    }
    payload = {
        "schema_version": enrich.SCHEMA,
        "release": "synthetic-calendar-fixture",
        "attribution": "Synthetic unit-test data",
        "parent": {
            "generation": generation,
            "manifest_sha256": enrich.digest(manifest or {}),
            "normalized_rows_sha256": enrich.rows_digest(baseline),
            "calendar_enrichment_sha256": enrich.EMPTY_SHA256,
            "row_count": len(baseline),
            "snapshot_path": snapshot.name,
            "snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        },
        "entries": [entry],
        "licenses": [
            {
                "identifier": "Synthetic-test-only",
                "evidence_path": body.name,
                "snapshot_sha256": receipt["snapshot_sha256"],
            }
        ],
    }
    path = tmp_path / "enrichment.json"
    path.write_text(json.dumps(payload))
    return path, payload


def write(path, payload):
    path.write_text(json.dumps(payload))


def test_bounded_source_verified_companion_retains_parent_and_rights(tmp_path):
    path, payload = artifact(tmp_path)
    prepared = enrich.prepare(path)
    assert prepared["entries"] == payload["entries"]
    assert prepared["report"]["rows"] == 1
    # Shared hours/rights body is counted once, plus parent snapshot and payload.
    assert prepared["report"]["evidence_files"] == 2
    assert prepared["report"]["bytes"] == sum(p.stat().st_size for p in tmp_path.iterdir())
    assert enrich.prepare(path)["generation"] == prepared["generation"]


@pytest.mark.parametrize(
    "relative",
    [
        "../outside",
        "/tmp/outside",
        "C:/outside",
        "evidence/../hours.txt",
        "dir\\hours.txt",
        "dir:hours.txt",
        "evidence//hours.txt",
        "CON.txt",
        "dir/NUL.bin",
        "evidence. /hours.txt",
        "evidence./hours.txt",
        "dir\x01/hours.txt",
    ],
)
def test_portable_paths_cannot_escape_or_break_windows(tmp_path, relative):
    path, payload = artifact(tmp_path)
    payload["entries"][0]["source_visit_calendar"]["source_receipts"][0]["evidence_path"] = relative
    write(path, payload)
    with pytest.raises(ValueError, match="portable"):
        enrich.prepare(path)


def test_corrupt_source_or_missing_rights_rejected(tmp_path):
    path, payload = artifact(tmp_path)
    (tmp_path / "hours.txt").write_text("Corrupted fixture")
    with pytest.raises(ValueError, match="checksum"):
        enrich.prepare(path)
    path, payload = artifact(tmp_path)
    payload["licenses"] = []
    write(path, payload)
    with pytest.raises(ValueError, match="reuse evidence"):
        enrich.prepare(path)


def test_unknown_ids_duplicate_calendars_and_oversize_fail_before_database(tmp_path):
    path, payload = artifact(tmp_path)
    payload["entries"][0]["source_id"] = "wrong"
    write(path, payload)
    with pytest.raises(ValueError, match="unknown parent"):
        enrich.prepare(path)
    path, payload = artifact(tmp_path)
    payload["entries"].append(copy.deepcopy(payload["entries"][0]))
    write(path, payload)
    with pytest.raises(ValueError, match="unique identities"):
        enrich.prepare(path)
    with pytest.raises(ValueError, match="hard ceiling"):
        enrich.prepare(path, max_rows=50_001)
    with pytest.raises(ValueError, match="byte ceiling"):
        enrich.prepare(path, max_bytes=10)


def test_calendar_contract_and_unknown_holds_remain_fail_closed(tmp_path):
    path, payload = artifact(tmp_path)
    entry = payload["entries"][0]
    entry["source_visit_calendar"]["weekly_windows"][0]["closes"] = "08:00"
    write(path, payload)
    with pytest.raises(ValueError, match="explicit source windows"):
        enrich.prepare(path)
    path, payload = artifact(tmp_path)
    payload["entries"][0]["source_visit_calendar"]["unknown_reasons"] = [
        "Unresolved party eligibility"
    ]
    write(path, payload)
    prepared = enrich.prepare(path)
    record = {"provider_id": "usda-market:synthetic", "source_provenance": prepared["entries"]}
    assert source_calendar(record) is not None
    assert calendar_eligible(record) is False


def test_projection_retains_unknown_original_calendar_without_mutating_it(tmp_path):
    path, payload = artifact(tmp_path)
    original = [
        {
            "dataset": "Original source",
            "source_visit_calendar": {"unknown_reasons": ["Unknown hours"]},
            "season": "Original agency season",
        }
    ]
    frozen = copy.deepcopy(original)
    projected = enrich.project(original, payload["entries"][0])
    assert original == frozen
    assert projected[0]["superseded_source_visit_calendar"] == frozen[0]["source_visit_calendar"]
    assert projected[0]["season"] == frozen[0]["season"]
    assert len([p for p in projected if "source_visit_calendar" in p]) == 1
    assert calendar_eligible(
        {"provider_id": "usda-market:synthetic", "source_provenance": projected}
    )


def test_closed_only_calendar_cannot_consume_automatic_discovery_slots(tmp_path):
    path, payload = artifact(tmp_path)
    calendar = payload["entries"][0]["source_visit_calendar"]
    calendar["weekly_windows"] = []
    calendar["date_overrides"] = [{"date": "2026-10-17", "windows": []}]
    assert not calendar_eligible(
        {"provider_id": "usda-market:synthetic", "source_provenance": payload["entries"]}
    )
    write(path, payload)
    with pytest.raises(ValueError, match="explicit source windows"):
        enrich.prepare(path)


@pytest.mark.parametrize(
    "fields",
    [
        {"source_attribution": []},
        {"source_release": "version"},
        {"source_attribution": "credit", "source_release": 2},
        {"source_attribution": ""},
    ],
)
def test_malformed_optional_source_metadata_is_rejected_before_lookup(tmp_path, fields):
    path, payload = artifact(tmp_path)
    payload["entries"][0].update(fields)
    write(path, payload)
    with pytest.raises(ValueError, match="bounded nonempty strings"):
        enrich.prepare(path)


def test_supplementary_calendar_preserves_primary_source_credits():
    row = {
        "source_id": "usfs:fixture",
        "attribution": "Parent USFS; Census; OpenStreetMap ODbL",
        "source_catalogs": {},
        "provenance": [],
        "calendar_enrichment": {"source_attribution": "Operator calendar facts"},
    }
    result = source_attribution(row)
    for credit in ("USFS", "Census", "OpenStreetMap ODbL", "Operator calendar facts"):
        assert credit in result
    row["calendar_enrichment"].update(
        source_release="NY fixture",
        source_attribution="NY CC-BY; Open NY terms; OpenStreetMap ODbL",
    )
    result = source_attribution(row)
    assert "NY CC-BY" in result and "Open NY terms" in result
    assert "Parent USFS" not in result


def test_empty_failed_acquisition_is_retained_but_cannot_supply_positive_facts(tmp_path):
    path, payload = artifact(tmp_path)
    failed = tmp_path / "failed-http.bin"
    failed.write_bytes(b"")
    empty = {"evidence_path": failed.name, "snapshot_sha256": hashlib.sha256(b"").hexdigest()}
    payload["source_inputs"] = [empty]
    write(path, payload)
    assert enrich.prepare(path)["report"]["rows"] == 1
    payload["entries"][0]["source_visit_calendar"]["source_receipts"][0].update(empty)
    write(path, payload)
    with pytest.raises(ValueError, match="evidence is empty"):
        enrich.prepare(path)


def test_cli_frozen_rollback_does_not_prepare_expired_sources(tmp_path, monkeypatch, capsys):
    filename = Path(__file__).parents[2] / "scripts/catalog_incremental_import.py"
    spec = importlib.util.spec_from_file_location("incremental_cli_fixture", filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    receipt = tmp_path / "receipt.json"
    receipt.write_text('{"fixture":true}', encoding="utf-8")
    checksum = hashlib.sha256(receipt.read_bytes()).hexdigest()
    connection = SimpleNamespace(close=lambda: None)
    monkeypatch.setitem(
        sys.modules,
        "scripts.catalog_import",
        SimpleNamespace(connect_target=lambda target: connection),
    )
    monkeypatch.setattr(
        enrich,
        "prepare",
        lambda *_a, **_k: pytest.fail("expired sources must not be prepared for recovery"),
    )
    calls = []
    monkeypatch.setattr(
        enrich,
        "rollback",
        lambda conn, frozen: calls.append((conn, frozen)) or {"generation": "parent"},
    )
    monkeypatch.setattr(
        sys, "argv", [str(filename), str(receipt), "--rollback", "--receipt-sha256", checksum]
    )
    module.main()
    assert calls == [(connection, {"fixture": True})]
    assert json.loads(capsys.readouterr().out)["database_write"] is True
    monkeypatch.setattr(
        sys, "argv", [str(filename), str(receipt), "--rollback", "--receipt-sha256", "0" * 64]
    )
    with pytest.raises(ValueError, match="reviewed receipt SHA-256"):
        module.main()
    assert len(calls) == 1
