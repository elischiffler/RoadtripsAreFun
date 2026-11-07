"""Frozen Nov7 public evidence replay; never a fresh live-catalog check."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from app.catalog import admission, place_context, release_holds
from app.catalog.identity import catalog_source_id
from app.models.guided_planning import RouteAlternativesRequest
from app.routing import alternatives
from app.routing.visit_calendar import calendar_eligible

SNAPSHOT = json.loads(
    (Path(__file__).parent / "fixtures/semantic_context24_current.json").read_text()
)
REGISTRY = json.loads(place_context.REGISTRY_PATH.read_text())
RECORDS = SNAPSHOT["records"]
EXPECTED_ELIGIBLE = {
    "overture:03f811cd-0401-40ad-b75c-1ae7328cf6b7",
    "overture:05672cd0-77c3-41db-97c1-929f3c0ebe9d",
    "overture:57193dd5-6aa9-4857-98bc-60e2097c3af0",
    "overture:a83224d1-0e20-459e-94bf-7163444a2821",
    "overture:e4919ff5-f961-431a-9f46-0ecdd6b20a5d",
    "catalog-pilot:entertainment-reno",
    "catalog-pilot:wikidata:Q8031716",
    "nps-heritage:crmo",
    "nps:cave",
    "nps:pefo",
    "wikidata-park:Q5160318",
}
HISTORICAL_HOLDS = {
    "catalog-pilot:wikidata:Q1050851",
    "catalog-pilot:wikidata:Q1099139",
    "catalog-pilot:wikidata:Q14708625",
    "catalog-pilot:wikidata:Q48803945",
}


@pytest.fixture
def inspected_clock(monkeypatch):
    # Replay real dated admission contracts; production still uses real time.
    assert SNAPSHOT["observed_at"] == "2026-11-07T03:41:23.291Z"
    assert type(SNAPSHOT["observed_epoch"]) is int
    monkeypatch.setattr(admission.time, "time", lambda: SNAPSHOT["observed_epoch"])


def test_original_seven_bindings_remain_exact_and_new_batch_is_display_only():
    baseline = json.dumps(
        REGISTRY["entries"][:7], sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert hashlib.sha256(baseline.encode()).hexdigest() == (
        "4292a2c1d6927071927aa422bdee0872d0d28354cc72d06a04dacf4d0d7d33b8"
    )
    assert len(REGISTRY["entries"]) == 31
    incoming = REGISTRY["entries"][7:]
    assert len(incoming) == len(RECORDS) == 24
    by_id = {entry["identity"]["provider_id"]: entry for entry in incoming}
    assert set(by_id) == {r["provider_id"] for r in RECORDS}
    assert not set(by_id) & {e["identity"]["provider_id"] for e in REGISTRY["entries"][:7]}
    for record in RECORDS:
        entry = by_id[record["provider_id"]]
        assert entry["identity"] == {
            "provider_id": record["provider_id"],
            "source": record["source"],
            "name": record["name"],
            "coordinates": record["coordinates"],
        }
        assert set(entry["context"]) == {"summary"}  # no new images, fit or score fields
        assert entry["review"]["claims"] == entry["context"]["summary"]
        sid = catalog_source_id(record["provider_id"])
        assert entry["review"]["current_source_row_sha256"] == SNAPSHOT["source_row_sha256"][sid]


@pytest.mark.parametrize("record", RECORDS, ids=lambda row: row["name"])
def test_real_snapshot_policy_gates_every_new_binding_without_source_mutation(
    inspected_clock, record
):
    original = deepcopy(record)
    expected = record["provider_id"] in EXPECTED_ELIGIBLE
    policy_before = admission.admission_details(record)
    assert calendar_eligible(record) is expected
    context = place_context.context_for_admitted_place(record)
    assert (context is not None) is expected
    assert (alternatives._public_place(record).place_context is not None) is expected
    assert admission.admission_details(record) == policy_before
    assert record == original  # includes all original provenance and qualification data


def test_recommendation_browse_and_route_map_suppress_all_thirteen_ineligible_records(
    inspected_clock, monkeypatch
):
    original = deepcopy(RECORDS)
    monkeypatch.setattr(alternatives, "catalog_nearby", lambda *args, **kwargs: deepcopy(RECORDS))
    # The injected catalog read tests policy filtering, not geographic coverage.
    result = alternatives.browse_alternatives(RouteAlternativesRequest(points=[(40, -105)]))
    assert {place.provider_id for place in result.places} == EXPECTED_ELIGIBLE
    assert len(result.places) == 11
    assert all(place.place_context is not None for place in result.places)
    context_map = place_context.route_place_context([{**r, "type": "stop"} for r in RECORDS])
    assert set(context_map) == EXPECTED_ELIGIBLE
    assert RECORDS == original
    suppressed = [r for r in RECORDS if r["provider_id"] not in EXPECTED_ELIGIBLE]
    assert len(suppressed) == 13
    assert sum((admission.admission_details(r) or {}).get("tier") == "T2" for r in suppressed) == 10
    assert sum(not admission.requires_admission(r) for r in suppressed) == 3


def test_display_review_cannot_renew_real_expired_T3_contracts(inspected_clock, monkeypatch):
    t3 = [r for r in RECORDS if (admission.admission_details(r) or {}).get("tier") == "T3"]
    assert len(t3) == 2
    assert all(place_context.context_for_admitted_place(r) for r in t3)
    original = deepcopy(t3)
    monkeypatch.setattr(
        admission.time,
        "time",
        lambda: SNAPSHOT["observed_epoch"] + admission.MAX_REVIEW_SECONDS + 1,
    )
    assert all(place_context.context_for_admitted_place(r) is None for r in t3)
    assert t3 == original


def test_editorial_content_cannot_clear_exact_payload_acquisition_holds(inspected_clock):
    rows = [r for r in RECORDS if r["provider_id"] in HISTORICAL_HOLDS]
    assert len(rows) == 4
    for record in rows:
        assert not release_holds.blocked(record)  # exact existing pinned resolution is intact
        assert admission.admission_details(record)["tier"] == "T2"
        assert place_context.context_for_admitted_place(record) is None
        changed = deepcopy(record)
        changed["url"] += "?unreviewed-payload-change"
        assert release_holds.blocked(changed)
        before = deepcopy(changed)
        assert place_context.context_for_admitted_place(changed) is None
        assert release_holds.blocked(changed)
        assert changed == before


def test_source_trims_and_image_omissions_are_retained():
    entries = {e["identity"]["provider_id"]: e for e in REGISTRY["entries"][7:]}
    garden = entries["catalog-pilot:wikidata:Q1099139"]
    assert garden["review"]["source_urls"] == ["https://ncbg.unc.edu/"]
    assert not any(word in garden["context"]["summary"] for word in ("Piedmont", "gallery", "rear"))
    assert "adjoining" not in entries["catalog-pilot:wikidata:Q5302612"]["context"]["summary"]
    assert "Whale sharks" not in entries["catalog-pilot:wikidata:Q1155919"]["context"]["summary"]
    assert all("image" not in e["context"] for e in entries.values())
    assert not any(
        e["identity"]["provider_id"] == "catalog-pilot:fdep-beach:FL297"
        for e in REGISTRY["entries"]
    )
