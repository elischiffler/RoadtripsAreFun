"""Synthetic admission controls; no source claims, services or database access."""

import copy
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.catalog import admission
from app.catalog.identity import catalog_source_id, identity
from app.routing.catalog_calendars import explicit_calendar_ineligible, refresh_for_timing
from app.routing.trip_calendar import TripCalendar
from app.routing.visit_calendar import (
    VisitCalendarConflict,
    calendar_eligible,
    requires_calendar,
    solve_visit,
)

NOW = int(time.time())
POINT = [37.8, -122.4]


def marker(sid="catalog-pilot:synthetic", *, tier="T2", now=NOW):
    return {
        "dataset": admission.DATASET,
        "catalog_admission": {
            "schema_version": admission.SCHEMA,
            "tier": tier,
            "source_id": sid,
            "review_status": "approved",
            "reviewed_at_epoch": now - 60,
            "expires_at_epoch": now + 3600,
            "gates": {key: tier == "T3" or key in admission.BASE_GATES for key in admission.GATES},
        },
    }


def record(sid="catalog-pilot:synthetic", *, tier="T2", calendar=False):
    result = {
        "provider_id": sid,
        "name": "Synthetic pilot fixture",
        "coordinates": POINT.copy(),
        "categories": ["daytime", "nature"],
        "source": "catalog-pilot",
        "source_provenance": [marker(sid, tier=tier)],
        "url": "https://operator.example/synthetic",
    }
    if calendar:
        result["source_provenance"].append(
            {
                "source_visit_calendar": {
                    "schema_version": "roadtrips-source-visit-calendar/1",
                    "weekly_windows": [
                        {"weekdays": list(range(7)), "opens": "09:00", "closes": "17:00"}
                    ],
                    "source_receipts": [{"source_url": "https://operator.example/synthetic-hours"}],
                }
            }
        )
    return result


def test_browse_and_routing_are_distinct_and_identity_is_registered():
    row = record()
    assert admission.requires_admission(row)
    assert admission.browse_eligible(row, now_epoch=NOW)
    assert not admission.routing_eligible(row, now_epoch=NOW)
    assert identity(row["provider_id"]) == (row["provider_id"], "catalog-pilot")
    assert catalog_source_id(row["provider_id"]) == row["provider_id"]
    raw = {"source_id": row["provider_id"], "provenance": row["source_provenance"]}
    assert admission.browse_eligible(raw, now_epoch=NOW)
    assert not admission.routing_eligible(raw, now_epoch=NOW)
    raw["provider_id"] = "catalog-pilot:other"
    assert admission.admission_details(raw, now_epoch=NOW) is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "roadtrips-catalog-admission/999"),
        ("tier", "T1"),
        ("tier", []),
        ("tier", {}),
        ("review_status", "pending"),
        ("source_id", "catalog-pilot:another"),
        ("source_id", 7),
        ("reviewed_at_epoch", str(NOW - 60)),
        ("reviewed_at_epoch", True),
        ("reviewed_at_epoch", NOW + 1),
        ("reviewed_at_epoch", -1),
        ("expires_at_epoch", NOW),
        ("expires_at_epoch", NOW - 1),
        ("expires_at_epoch", NOW + admission.MAX_REVIEW_SECONDS),
        ("expires_at_epoch", 10**100),
        ("expires_at_epoch", float("inf")),
        ("expires_at_epoch", {}),
        ("gates", []),
    ],
)
def test_invalid_contract_fields_fail_closed_without_exceptions(field, value, monkeypatch):
    monkeypatch.setattr(admission.time, "time", lambda: NOW)
    item = record(tier="T3", calendar=True)
    item["source_provenance"][0]["catalog_admission"][field] = value
    assert admission.admission_details(item, now_epoch=NOW) is None
    assert not admission.routing_eligible(item, now_epoch=NOW)
    assert not admission.browse_eligible(item, now_epoch=NOW)
    assert not calendar_eligible(item)


@pytest.mark.parametrize("key", admission.GATES)
def test_false_or_mistyped_t3_gate_never_routes(key):
    item = record(tier="T3", calendar=True)
    for invalid in [False, "true", 1, None]:
        item["source_provenance"][0]["catalog_admission"]["gates"][key] = invalid
        assert not admission.routing_eligible(item, now_epoch=NOW)
        assert not calendar_eligible(item)


@pytest.mark.parametrize("shape", [None, {}, [], "invalid"])
def test_new_namespace_with_missing_or_malformed_provenance_never_becomes_legacy(shape):
    item = record(tier="T3")
    item["source_provenance"] = shape
    assert admission.requires_admission(item)
    assert not admission.routing_eligible(item, now_epoch=NOW)
    assert not calendar_eligible(item)
    assert explicit_calendar_ineligible(item)


def test_duplicate_conflicting_missing_and_unknown_contract_keys_fail_closed():
    item = record(tier="T3", calendar=True)
    for facts in [
        [marker(tier="T3"), marker(tier="T3")],
        [marker(tier="T2"), marker(tier="T3")],
        [{"dataset": admission.DATASET}],
        [{"dataset": "wrong", "catalog_admission": marker()["catalog_admission"]}],
    ]:
        item["source_provenance"] = facts
        assert not admission.routing_eligible(item, now_epoch=NOW)
        assert not admission.browse_eligible(item, now_epoch=NOW)
    for key in admission.CONTRACT_KEYS:
        item = record(tier="T3")
        del item["source_provenance"][0]["catalog_admission"][key]
        assert not admission.routing_eligible(item, now_epoch=NOW)
    item = record(tier="T3")
    item["source_provenance"][0]["catalog_admission"]["unreviewed_override"] = True
    assert not admission.routing_eligible(item, now_epoch=NOW)
    item = record(tier="T3")
    item["source_provenance"][0]["catalog_admission"]["gates"]["new_gate"] = True
    assert not admission.routing_eligible(item, now_epoch=NOW)


def test_unmarked_legacy_policy_is_preserved_but_legacy_is_not_relabeled_for_browse():
    item = {"provider_id": "usfs:synthetic", "categories": ["daytime", "nature"]}
    assert not admission.requires_admission(item)
    assert admission.routing_eligible(item)
    assert not admission.browse_eligible(item)
    assert calendar_eligible(item)
    start = datetime(2026, 10, 21, 9, tzinfo=ZoneInfo("America/Los_Angeles"))
    assert solve_visit(item, start, start + timedelta(hours=3))[1]["status"] == "unknown"
    item["source_provenance"] = [marker("usfs:synthetic", tier="T2")]
    assert not admission.routing_eligible(item)
    assert not calendar_eligible(item)


@pytest.mark.asyncio
async def test_t2_outdoor_and_t3_missing_calendar_fail_before_timezone_and_final_timing():
    calls = []

    async def timezone(point):
        calls.append(point)
        raise AssertionError("ineligible admission must never resolve a timezone")

    start = datetime(2026, 10, 21, 9, tzinfo=ZoneInfo("America/Los_Angeles"))
    trip = TripCalendar(start, timezone)
    for item in [record(), record(tier="T3")]:
        assert requires_calendar(item)
        assert not calendar_eligible(item)
        assert explicit_calendar_ineligible(item)
        assert not await trip.eligible(item)
        with pytest.raises(VisitCalendarConflict):
            solve_visit(item, start, start + timedelta(hours=3))
    assert calls == []
    ready = record(tier="T3", calendar=True)
    assert admission.routing_eligible(ready)
    assert calendar_eligible(ready)
    assert solve_visit(ready, start, start + timedelta(hours=3))[0] == start


@pytest.mark.asyncio
async def test_current_t2_replaces_stale_or_stripped_t3_and_removes_optional_suggestions():
    current = record()
    stale = record(tier="T3", calendar=True)
    stale.pop("source_provenance")
    calls = []

    def lookup(ids):
        calls.append(ids)
        return {
            current["provider_id"]: {
                key: copy.deepcopy(current[key])
                for key in ("coordinates", "categories", "source_provenance")
            }
        }

    with pytest.raises(VisitCalendarConflict, match="current catalog access is unresolved"):
        await refresh_for_timing([{**stale, "type": "stop"}], catalog_lookup=lookup)
    assert calls == [[current["provider_id"]]]
    hotel = {"type": "hotel", "evening_suggestions": [stale]}
    await refresh_for_timing([hotel], catalog_lookup=lookup)
    assert hotel["evening_suggestions"] == []


@pytest.mark.asyncio
async def test_custom_provider_browse_records_do_not_consume_rating_or_duration_budget():
    from app.agent.persona import default_weights
    from tests.routing.persona_candidates_tests import FakeAI, FakePlaces, _ratings, discover

    ready = record("catalog-pilot:ready", tier="T3", calendar=True)
    ready["name"] = "Ready synthetic fixture"
    blocked = [record(f"catalog-pilot:blocked-{index}") for index in range(61)]
    ai = FakeAI([{"name": ready["name"], "attribute_ratings": _ratings()}])
    duration_calls = []

    async def durations(records, *_args):
        duration_calls.append([item["provider_id"] for item in records])
        return records

    found = await discover(
        None,
        [POINT],
        default_weights(),
        places=FakePlaces(attractions=[*blocked, ready]),
        ai=ai,
        duration_estimator=durations,
    )
    assert [item["provider_id"] for item in found] == [ready["provider_id"]]
    assert duration_calls == [[ready["provider_id"]]]
    assert ai.calls == 1


@pytest.mark.asyncio
async def test_pilot_evenings_are_withheld_even_with_t3_and_dated_opening_intervals(monkeypatch):
    from app.catalog import repository
    from app.routing.sources import evenings

    start = datetime(2026, 10, 21, 18, tzinfo=ZoneInfo("America/Los_Angeles"))
    pilot = record(tier="T3", calendar=True)
    pilot["category"] = "culture"
    pilot["opening_intervals"] = [
        {"opens": start.isoformat(), "closes": (start + timedelta(hours=4)).isoformat()}
    ]
    legacy = {
        **record("usfs:legacy-evening"),
        "source": "usfs",
        "source_provenance": [],
        "category": "culture",
        "categories": ["culture"],
    }
    travel_calls = []

    class Provider:
        async def nearby(self, *_args):
            return [*[copy.deepcopy(pilot) for _ in range(61)], legacy]

        async def travel(self, _hotel, coordinates):
            travel_calls.append(coordinates)
            return [60, 60]

    hotel = {"type": "hotel", "coordinates": POINT, "evening_suggestions": []}
    await evenings._hotel_suggestions(
        hotel, start, start + timedelta(hours=4), ["culture"], Provider()
    )
    assert [item["provider_id"] for item in hotel["evening_suggestions"]] == [legacy["provider_id"]]
    assert travel_calls == [POINT]
    live_calls = []

    def nearby(*_args, **kwargs):
        live_calls.append(kwargs)
        return [pilot, legacy]

    monkeypatch.setattr(repository, "nearby", nearby)
    assert [
        item.provider_id
        for item in await evenings.LiveEveningProvider().nearby(POINT, ["culture"], start)
    ] == [legacy["provider_id"]]
    assert live_calls[0]["legacy_only"] is True
    display = {
        "arrival_time": start.isoformat(),
        "deadline": (start + timedelta(hours=4)).isoformat(),
        "evening_suggestions": [{**pilot, "travel_seconds": [60, 60]}],
    }
    assert list(evenings.current_suggestions(display)) == []

    def lookup(ids):
        assert ids == [pilot["provider_id"]]
        return {
            pilot["provider_id"]: {
                key: copy.deepcopy(pilot[key])
                for key in ("coordinates", "categories", "source_provenance")
            }
        }

    hotel["evening_suggestions"] = [pilot]
    await refresh_for_timing([hotel], catalog_lookup=lookup)
    assert hotel["evening_suggestions"] == []


def test_empty_namespace_identity_is_never_admitted():
    item = record(admission.PREFIX, tier="T3", calendar=True)
    assert not admission.browse_eligible(item)
    assert not admission.routing_eligible(item)
