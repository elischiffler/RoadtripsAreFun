"""Real PostgreSQL companion cutovers and negative controls, public fixtures only."""

import copy
import json

import pytest
from psycopg2.extras import Json

from app.catalog import calendar_enrichment as enrich
from app.catalog import ingest, repository
from app.routing.visit_calendar import calendar_eligible
from tests.catalog_calendar_enrichment_tests import artifact
from tests.catalog_ingest_tests import bundle, feature
from tests.catalog_postgres_tests import connection as connection


def inputs(connection, tmp_path):
    place = tmp_path / "place"
    place.mkdir()
    path, manifest = bundle(place, [feature()])
    rows, _ = ingest.prepare(path, manifest)
    prior = ingest.stage(connection, path, manifest)["generation"]
    ingest.activate(connection, prior)
    overlay = tmp_path / "overlay"
    overlay.mkdir()
    path, _ = artifact(overlay, baseline=rows, generation=prior, manifest=manifest)
    return enrich.prepare(path), prior, rows


def active(connection):
    with connection.cursor() as cur:
        cur.execute("SELECT generation FROM places_catalog_active")
        generation = cur.fetchone()[0]
    connection.rollback()
    return generation


def test_current_record_refresh_uses_active_hold_and_preserves_unknown_outdoor_filter(
    connection, tmp_path
):
    prepared, prior, baseline = inputs(connection, tmp_path)
    path, payload = artifact(
        tmp_path / "overlay",
        baseline=baseline,
        generation=prior,
        manifest=_parent_manifest(connection, prior),
    )
    payload["entries"][0]["source_visit_calendar"]["unknown_reasons"] = [
        "Synthetic unresolved selected parking access"
    ]
    path.write_text(json.dumps(payload))
    held = enrich.prepare(path)
    sid = baseline[0]["source_id"]
    before = repository.current_records([sid])[sid]
    enrich.stage(connection, held)
    assert repository.current_records([sid]) == {sid: before}
    enrich.activate(connection, held)
    current = repository.current_records([sid])[sid]
    assert current["coordinates"] == [baseline[0]["latitude"], baseline[0]["longitude"]]
    assert current["source_provenance"][-2]["source_visit_calendar"]["unknown_reasons"]
    assert not calendar_eligible(current)
    assert repository.nearby([37.8, -122.4], ["daytime"], require_visit_calendar=True) == []
    assert repository.current_records(["missing"]) == {}


def _parent_manifest(connection, generation):
    with connection.cursor() as cur:
        cur.execute(
            "SELECT manifest FROM places_catalog_imports WHERE generation=%s", (generation,)
        )
        return cur.fetchone()[0]


def test_companion_stage_cutover_rollback_preserves_rows_and_credits(connection, tmp_path):
    prepared, prior, baseline = inputs(connection, tmp_path)
    assert repository.nearby([37.8, -122.4], ["daytime"], require_visit_calendar=True) == []
    staged = enrich.stage(connection, prepared)
    assert active(connection) == prior
    assert staged["existing"] is False
    assert enrich.stage(connection, prepared)["existing"] is True
    assert enrich.activate(connection, prepared)["previous_generation"] == prior
    found = repository.nearby([37.8, -122.4], ["daytime"], require_visit_calendar=True)
    assert len(found) == 1 and calendar_eligible(found[0])
    assert found[0]["source_provenance"][:-2] == baseline[0]["provenance"]
    assert (
        found[0]["source_provenance"][-2]["source_visit_calendar"]
        == prepared["entries"][0]["source_visit_calendar"]
    )
    with connection.cursor() as cur:
        cur.execute(
            "SELECT provenance FROM places_catalog WHERE generation=%s", (staged["generation"],)
        )
        assert cur.fetchone()[0] == baseline[0]["provenance"]
    connection.rollback()
    assert enrich.activate(connection, prepared)["generation"] == staged["generation"]
    assert enrich.activate(connection, prepared, rollback=True)["generation"] == prior
    assert enrich.activate(connection, prepared, rollback=True)["generation"] == prior
    assert repository.nearby([37.8, -122.4], ["daytime"], require_visit_calendar=True) == []


@pytest.mark.parametrize(
    "violation",
    [
        "calendar",
        "source_rows",
        "parent_metadata",
        "new_metadata",
        "parent_release",
        "new_release",
        "coordinated_calendar_metadata",
        "pointer",
    ],
)
def test_companion_rejects_changed_immutable_content(connection, tmp_path, violation):
    prepared, prior, _ = inputs(connection, tmp_path)
    staged = enrich.stage(connection, prepared)
    with connection, connection.cursor() as cur:
        if violation == "calendar":
            cur.execute(
                "UPDATE places_catalog_calendars SET entry=jsonb_set(entry,'{source_visit_calendar,weekly_windows,0,closes}','\"15:00\"') WHERE generation=%s",
                (staged["generation"],),
            )
        elif violation == "source_rows":
            cur.execute(
                "UPDATE places_catalog SET name='Changed fixture' WHERE generation=%s", (prior,)
            )
        elif violation == "parent_metadata":
            cur.execute(
                'UPDATE places_catalog_imports SET manifest=manifest || \'{"attribution":"Changed fixture"}\'::jsonb WHERE generation=%s',
                (prior,),
            )
        elif violation == "new_metadata":
            cur.execute(
                'UPDATE places_catalog_imports SET manifest=manifest || \'{"attribution":"Changed fixture"}\'::jsonb WHERE generation=%s',
                (staged["generation"],),
            )
        elif violation in {"parent_release", "new_release"}:
            cur.execute(
                "UPDATE places_catalog_imports SET release='Changed fixture' WHERE generation=%s",
                (prior if violation == "parent_release" else staged["generation"],),
            )
        elif violation == "coordinated_calendar_metadata":
            cur.execute(
                "UPDATE places_catalog_calendars SET entry=jsonb_set(entry,'{source_visit_calendar,weekly_windows,0,closes}','\"15:00\"') WHERE generation=%s",
                (staged["generation"],),
            )
            cur.execute(
                "UPDATE places_catalog_imports SET manifest=jsonb_set(manifest,'{calendar_enrichment_sha256}',to_jsonb(%s::text)) WHERE generation=%s",
                (
                    enrich.digest(
                        [
                            {
                                **prepared["entries"][0],
                                "source_visit_calendar": {
                                    **prepared["entries"][0]["source_visit_calendar"],
                                    "weekly_windows": [
                                        {"weekdays": [5], "opens": "09:00", "closes": "15:00"}
                                    ],
                                },
                            }
                        ]
                    ),
                    staged["generation"],
                ),
            )
        else:
            cur.execute("DELETE FROM places_catalog_active")
    with pytest.raises(ValueError):
        enrich.stage(connection, prepared)
    with pytest.raises(ValueError):
        enrich.activate(connection, prepared)
    with pytest.raises(ValueError):
        enrich.activate(connection, prepared, rollback=True)


def test_companion_storage_rejection_leaves_parent_and_pointer(connection, tmp_path, monkeypatch):
    prepared, prior, _ = inputs(connection, tmp_path)
    monkeypatch.setattr(ingest, "MAX_CATALOG_BYTES", 1)
    with pytest.raises(ValueError, match="storage ceiling"):
        enrich.stage(connection, prepared)
    assert active(connection) == prior
    with connection.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM places_catalog_imports WHERE generation=%s",
            (prepared["generation"],),
        )
        assert cur.fetchone()[0] == 0
    connection.rollback()


def test_prepare_contract_is_not_mutated_by_staging(connection, tmp_path):
    prepared, _, _ = inputs(connection, tmp_path)
    snapshot = copy.deepcopy(prepared)
    enrich.stage(connection, prepared)
    assert prepared == snapshot


def test_mutating_prepared_source_facts_cannot_stage_under_reviewed_generation(
    connection, tmp_path
):
    prepared, prior, _ = inputs(connection, tmp_path)
    prepared["entries"][0]["source_visit_calendar"]["weekly_windows"][0]["closes"] = "15:00"
    with pytest.raises(ValueError, match="after source verification"):
        enrich.stage(connection, prepared)
    assert active(connection) == prior


@pytest.mark.parametrize("primary", [True, False])
def test_inherited_primary_credits_survive_later_operator_calendar(connection, tmp_path, primary):
    prepared, prior, baseline = inputs(connection, tmp_path)
    previous = copy.deepcopy(prepared["entries"][0])
    previous.update(
        source_release="synthetic-primary",
        source_attribution="Original CC-BY; Open NY terms; OpenStreetMap ODbL",
    )
    if not primary:
        previous.pop("source_release")
    with connection, connection.cursor() as cur:
        cur.execute("SELECT manifest FROM places_catalog_imports WHERE generation=%s", (prior,))
        metadata = cur.fetchone()[0]
        metadata.update(calendar_enrichment_sha256=enrich.digest([previous]), calendar_count=1)
        cur.execute(
            "UPDATE places_catalog_imports SET manifest=%s WHERE generation=%s",
            (Json(metadata), prior),
        )
        cur.execute(
            "INSERT INTO places_catalog_calendars VALUES(%s,%s,%s)",
            (prior, previous["source_id"], Json(previous)),
        )
    folder = tmp_path / "later"
    folder.mkdir()
    path, payload = artifact(folder, baseline=baseline, generation=prior, manifest=metadata)
    payload["parent"]["calendar_enrichment_sha256"] = enrich.digest([previous])
    payload["entries"][0]["source_attribution"] = "Later operator calendar"
    path.write_text(json.dumps(payload))
    next_prepared = enrich.prepare(path)
    enrich.stage(connection, next_prepared)
    enrich.activate(connection, next_prepared)
    found = repository.nearby([37.8, -122.4], ["daytime"], require_visit_calendar=True)[0]
    assert found["source_release"] == (
        "synthetic-primary" if primary else next_prepared["manifest"]["release"]
    )
    for credit in (
        "Original CC-BY",
        "Open NY terms",
        "OpenStreetMap ODbL",
        "Later operator calendar",
    ):
        assert credit in found["source_attribution"]
    assert found["source_provenance"][-2]["source_constraints"][-1]["entry"] == previous


def test_supplement_cannot_replace_existing_namespace_credits(connection, tmp_path):
    prepared, prior, baseline = inputs(connection, tmp_path)
    with connection, connection.cursor() as cur:
        cur.execute("SELECT manifest FROM places_catalog_imports WHERE generation=%s", (prior,))
        metadata = cur.fetchone()[0]
        metadata["source_catalogs"] = {
            "overture": {"release": "original", "attribution": "Original credits"}
        }
        cur.execute(
            "UPDATE places_catalog_imports SET manifest=%s WHERE generation=%s",
            (Json(metadata), prior),
        )
    folder = tmp_path / "namespace"
    folder.mkdir()
    path, payload = artifact(folder, baseline=baseline, generation=prior, manifest=metadata)
    payload["additional_source_catalogs"] = {
        "overture": {"release": "changed", "attribution": "Changed credits"}
    }
    path.write_text(json.dumps(payload))
    changed = enrich.prepare(path)
    with pytest.raises(ValueError, match="preserved source catalog credits"):
        enrich.stage(connection, changed)
    assert active(connection) == prior


def test_frozen_rollback_needs_no_sources_or_fresh_admission(connection, tmp_path, monkeypatch):
    prepared, prior, _ = inputs(connection, tmp_path)
    enrich.stage(connection, prepared)
    receipt = enrich.recovery_receipt(connection, prepared)
    assert active(connection) == prior
    enrich.activate(connection, prepared)
    monkeypatch.setattr(
        enrich, "prepare", lambda *_a, **_k: pytest.fail("recovery must not re-admit sources")
    )
    assert enrich.rollback(connection, receipt)["generation"] == prior
    assert enrich.rollback(connection, receipt)["generation"] == prior


@pytest.mark.parametrize("changed", ["metadata", "calendar", "rows", "receipt"])
def test_frozen_rollback_rejects_changed_fingerprints(connection, tmp_path, changed):
    prepared, prior, _ = inputs(connection, tmp_path)
    enrich.stage(connection, prepared)
    receipt = enrich.recovery_receipt(connection, prepared)
    enrich.activate(connection, prepared)
    with connection, connection.cursor() as cur:
        if changed == "metadata":
            cur.execute(
                'UPDATE places_catalog_imports SET manifest=manifest || \'{"attribution":"changed"}\'::jsonb WHERE generation=%s',
                (prior,),
            )
        elif changed == "calendar":
            cur.execute(
                'UPDATE places_catalog_calendars SET entry=entry || \'{"transformation":{"changed":true}}\'::jsonb WHERE generation=%s',
                (prepared["generation"],),
            )
        elif changed == "rows":
            cur.execute(
                "UPDATE places_catalog SET name='Changed fixture' WHERE generation=%s", (prior,)
            )
        else:
            receipt["parent"]["rows_md5"] = "0" * 32
    with pytest.raises(ValueError, match="changed"):
        enrich.rollback(connection, receipt)
    assert active(connection) == prepared["generation"]
