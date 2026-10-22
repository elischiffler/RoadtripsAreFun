"""Offline controls for retrospective holds; no source or production requests."""

import copy
import hashlib
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.catalog import admission, ingest, release_holds
from app.catalog import calendar_enrichment as enrich
from app.routing.visit_calendar import calendar_eligible
from tests.catalog_admission_tests import NOW, record
from tests.catalog_pilot_tests import artifact, replay


def test_all_133_holds_override_renewed_approvals_and_cannot_become_legacy():
    assert len(release_holds.SOURCE_IDS) == 133
    raw = Path(release_holds.__file__).with_name("release_holds.json").read_bytes()
    assert hashlib.sha256(raw).hexdigest() == release_holds.AUDIT_SHA256
    for sid in release_holds.SOURCE_IDS:
        for tier in ("T2", "T3"):
            value = record(sid, tier=tier, calendar=True)
            original = copy.deepcopy(value)
            assert admission.admission_details(value, now_epoch=NOW) is None
            assert not admission.browse_eligible(value, now_epoch=NOW)
            assert not admission.routing_eligible(value, now_epoch=NOW)
            assert not calendar_eligible(value)
            assert value == original
        value["source_provenance"] = []
        assert not admission.routing_eligible(value, now_epoch=NOW)
        assert release_holds.blocked({"source_id": sid, "unknown_field": None})
    assert admission.browse_eligible(record(), now_epoch=NOW)
    assert not admission.routing_eligible(record(), now_epoch=NOW)
    assert admission.routing_eligible(
        record("usfs:legacy") | {"source": "usfs", "source_provenance": []}
    )


def test_aliases_and_conflicting_review_identity_cannot_clear_a_hold():
    sid = sorted(release_holds.SOURCE_IDS)[0]
    for provenance in (
        [{"aliases": [None, {}, sid]}],
        [{"catalog_admission": {"source_id": sid}}],
    ):
        value = {"source_id": "another-identity", "provenance": provenance}
        assert release_holds.blocked(value)
        assert not admission.routing_eligible(value, now_epoch=NOW)
    assert not release_holds.blocked({"source_id": [], "provenance": [None, {}]})


def test_pilot_replay_retains_held_identity_and_original_input_without_admission(tmp_path):
    payload = artifact(tmp_path)
    sid = "catalog-pilot:wikidata:Q21028346"
    payload["records"][0]["pilot_id"] = sid
    original = copy.deepcopy(payload)
    rows, report = replay(tmp_path, payload)
    assert rows == [] and report["profiles"] == []
    assert report["decisions"] == [
        {"pilot_id": sid, "tier": "T1", "reason": "release_hold:retrospective_acquisition_audit"}
    ]
    assert payload == original


def test_staging_refuses_holds_before_using_any_connection(monkeypatch):
    held = {"source_id": sorted(release_holds.SOURCE_IDS)[0], "unknown_field": None}
    monkeypatch.setattr(ingest, "prepare", lambda *a, **kw: ([held], {}))
    with pytest.raises(ValueError, match="release hold"):
        ingest.stage(None, "synthetic-unused", {})
    assert held["unknown_field"] is None


def test_activation_checks_even_previously_staged_generations_before_pointer_write():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [(1, 1), (1,)]
    with pytest.raises(ValueError, match="release hold"):
        ingest.activate(connection, "previously-staged-held-generation")
    assert not any(
        "INSERT INTO places_catalog_active" in call.args[0]
        for call in cursor.execute.call_args_list
    )


def test_incremental_stage_and_both_activation_directions_cannot_include_holds():
    held = {"source_id": sorted(release_holds.SOURCE_IDS)[0]}
    prepared = {"rows": [held], "baseline": [held]}
    with pytest.raises(ValueError, match="release hold"):
        enrich.stage(None, prepared)
    for rollback in (False, True):
        with pytest.raises(ValueError, match="release hold"):
            enrich.activate(None, prepared, rollback=rollback)


def test_frozen_recovery_cannot_reactivate_a_newly_held_parent():
    parent, candidate = "a" * 64, "b" * 64

    def fingerprint(generation):
        return {
            "generation": generation,
            "row_count": 1,
            "calendar_count": 0,
            "metadata_md5": "a" * 32,
            "rows_md5": "b" * 32,
            "calendars_md5": "c" * 32,
        }

    receipt = {
        "schema_version": enrich.RECOVERY_SCHEMA,
        "parent": fingerprint(parent),
        "candidate": fingerprint(candidate),
    }
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [
        {"server_version_num": "180000"},
        {"generation": candidate},
        {"held_count": 1},
    ]
    with pytest.raises(ValueError, match="release hold"):
        enrich.rollback(connection, receipt)
    assert not any(
        "UPDATE places_catalog_active" in call.args[0] for call in cursor.execute.call_args_list
    )
