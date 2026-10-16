"""Explicit access holds survive saved/client payloads and optional fallbacks.

All clocks and responses here are synthetic controls. Real source and PostgreSQL
replay are retained separately in the release bundle.
"""

import copy
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException

from app.catalog import repository
from app.catalog.identity import catalog_source_id
from app.models.itinerary_models import Itinerary_Payload
from app.routers.itinerary_api import build_itinerary, generate_itinerary
from app.routing.base import PlanningError
from app.routing.catalog_calendars import refresh_for_timing
from app.routing.sources import evenings
from app.routing.trip_calendar import possible_visit
from app.routing.visit_calendar import VisitCalendarConflict, calendar_eligible, solve_visit

IDS = [f"nps-heritage:{code}" for code in ["wupa", "manz", "chyo", "jica", "hamp", "chir", "scbl"]]
ZONE = ZoneInfo("America/Phoenix")
START = datetime(2026, 10, 20, 9, tzinfo=ZONE)
POINT = [35.52, -111.37]


def record(sid=IDS[0], *, held=True):
    return {
        "provider_id": sid,
        "name": "Synthetic source hold regression",
        "source": "nps-heritage",
        "coordinates": POINT.copy(),
        "categories": ["daytime", "nature", "culture"],
        "source_attribution": "Synthetic NPS-shaped control; not live visitor facts",
        "source_provenance": [
            {
                "source_visit_calendar": {
                    "schema_version": "roadtrips-source-visit-calendar/1",
                    "weekly_windows": [
                        {"weekdays": list(range(7)), "opens": "09:00", "closes": "17:00"}
                    ],
                    "source_receipts": [{"source_url": "https://operator.example/synthetic"}],
                    "unknown_reasons": ["Unresolved selected parking access"] if held else [],
                }
            }
        ],
        "url": "https://operator.example/synthetic",
    }


def authoritative(item):
    return {
        key: copy.deepcopy(item[key])
        for key in ["coordinates", "categories", "source_provenance", "source_attribution"]
    }


def payload(item, *, kind="stop", policy=True, provenance=True):
    stop = {**copy.deepcopy(item), "type": kind, "duration": 60, "timezone": ZONE.key}
    if not provenance:
        stop.pop("source_provenance")
        stop.pop("categories")  # The scheduler does not otherwise carry categories.
    route = {
        "coordinates": [POINT],
        "distance": 1000,
        "duration": 60,
        "steps": [],
        "stops": [stop],
        "geometry": {"type": "LineString", "coordinates": [[-111.38, 35.52], [-111.37, 35.52]]},
        "cost": 0,
        "start_timezone": ZONE.key,
        "departure_time": START,
    }
    if policy:
        route["scheduling_policy"] = {}
    return Itinerary_Payload.model_validate({"route": route, "start_time": START})


@pytest.mark.asyncio
@pytest.mark.parametrize("sid", IDS)
@pytest.mark.parametrize("kind", ["stop", "generic", "attraction"])
@pytest.mark.parametrize("policy,provenance", [(True, True), (False, False)])
async def test_all_seven_current_holds_override_stale_or_stripped_payload(
    monkeypatch, sid, kind, policy, provenance
):
    calls = []

    def current(ids):
        calls.append(ids)
        return {sid: authoritative(record(sid))}

    monkeypatch.setattr(repository, "current_records", current)
    data = payload(record(sid, held=False), kind=kind, policy=policy, provenance=provenance)
    with pytest.raises(VisitCalendarConflict, match="current catalog access is unresolved"):
        await build_itinerary(data)
    assert calls == [[sid]]
    assert not calendar_eligible(data.route.stops[0])
    assert not possible_visit(data.route.stops[0], START, ZONE)
    with pytest.raises(VisitCalendarConflict):
        solve_visit(data.route.stops[0], START, START.replace(hour=17))


@pytest.mark.asyncio
async def test_http_itinerary_rejects_previously_positive_calendar(monkeypatch):
    monkeypatch.setattr(
        repository, "current_records", lambda ids: {IDS[0]: authoritative(record())}
    )
    body = payload(record(held=False)).model_dump(mode="json")

    async def json_body():
        return body

    with pytest.raises(HTTPException) as error:
        await generate_itinerary(SimpleNamespace(json=json_body))
    assert error.value.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["stop", "generic", "attraction"])
async def test_explicit_hold_cannot_become_unknown_outdoor_after_identity_removal(kind):
    item = {**record(), "type": kind}
    item.pop("provider_id")
    item.pop("source")
    with pytest.raises(VisitCalendarConflict):
        await refresh_for_timing([item])


@pytest.mark.asyncio
@pytest.mark.parametrize("suggestions", [[None], [123, "invalid"], None, "invalid"])
async def test_malformed_optional_payload_is_dropped_without_failing_route(suggestions):
    hotel = {
        "type": "hotel",
        "coordinates": POINT,
        "price": 123,
        "evening_suggestions": suggestions,
    }
    await refresh_for_timing([hotel])
    assert hotel["evening_suggestions"] == [] and hotel["price"] == 123


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mutation",
    [
        "missing_source_identity",
        "missing_provenance_identity",
        "aliased_namespace",
        "changed_coordinates",
        "missing_active_row",
        "lookup_failure",
    ],
)
async def test_identity_arrival_and_lookup_fail_closed(monkeypatch, mutation):
    item = {**record(held=False), "type": "stop"}
    if mutation == "missing_source_identity":
        item.pop("provider_id")
    if mutation == "missing_provenance_identity":
        item.pop("provider_id")
        item.pop("source")
        item["source_provenance"].append(
            {"dataset": "Roadtrips active catalog", "generation": "synthetic"}
        )
    if mutation == "aliased_namespace":
        item["provider_id"] = "overture:" + IDS[0]
    if mutation == "changed_coordinates":
        item["coordinates"] = [0, 0]

    def current(ids):
        if mutation == "lookup_failure":
            raise RuntimeError("private connection diagnostic must not escape")
        return (
            {} if mutation == "missing_active_row" else {IDS[0]: authoritative(record(held=False))}
        )

    monkeypatch.setattr(repository, "current_records", current)
    with pytest.raises(PlanningError) as error:
        await refresh_for_timing([item])
    assert "private connection" not in str(error.value)
    assert error.value.status_code == (503 if mutation == "lookup_failure" else 422)
    if mutation == "changed_coordinates":
        assert item["coordinates"] == [0, 0]  # Never silently move a road-routed arrival.
    assert catalog_source_id("overture:" + IDS[0]) is None


@pytest.mark.asyncio
async def test_unchanged_active_calendar_and_ordinary_outdoor_control_remain_usable(monkeypatch):
    monkeypatch.setattr(
        repository, "current_records", lambda ids: {IDS[0]: authoritative(record(held=False))}
    )
    days = await build_itinerary(payload(record(held=False)))
    assert any(
        stop.availability and stop.availability.get("status") == "within_published_window"
        for day in days
        for stop in day.stops
    )
    ordinary = {
        "provider_id": "manual:outdoor",
        "type": "stop",
        "coordinates": POINT,
        "categories": ["daytime", "nature"],
    }
    await refresh_for_timing([ordinary])
    assert calendar_eligible(ordinary)
    assert solve_visit(ordinary, START, START.replace(hour=17))[1]["status"] == "unknown"


@pytest.mark.asyncio
async def test_saved_evening_hold_is_refreshed_and_removed_without_losing_hotel(monkeypatch):
    monkeypatch.setattr(
        repository, "current_records", lambda ids: {IDS[0]: authoritative(record())}
    )
    stale = {**record(held=False), "status": "tentative", "travel_seconds": [60, 60]}
    hotel = {"type": "hotel", "coordinates": POINT, "evening_suggestions": [stale], "price": 123}
    await refresh_for_timing([hotel])
    assert hotel["evening_suggestions"] == [] and hotel["price"] == 123


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["lookup", "identity", "arrival"])
async def test_unverifiable_optional_alone_never_fails_the_route(monkeypatch, failure):
    stale = record(held=False)
    if failure == "identity":
        stale.pop("provider_id")
    if failure == "arrival":
        stale["coordinates"] = [0, 0]

    def current(ids):
        if failure == "lookup":
            raise RuntimeError("synthetic unavailable DB")
        return {IDS[0]: authoritative(record(held=False))}

    monkeypatch.setattr(repository, "current_records", current)
    hotel = {"type": "hotel", "coordinates": POINT, "evening_suggestions": [stale], "price": 123}
    await refresh_for_timing([hotel])
    assert hotel["evening_suggestions"] == [] and hotel["price"] == 123


@pytest.mark.asyncio
@pytest.mark.parametrize("known", [False, True])
async def test_evening_provider_intervals_cannot_override_source_hold(known):
    class Provider:
        async def nearby(self, *args):
            return [
                {
                    **record(),
                    "category": "culture",
                    "opening_intervals": [{"opens": START, "closes": START.replace(hour=17)}]
                    if known
                    else None,
                }
            ]

        async def travel(self, *args):
            pytest.fail("Held source must be rejected before directions")

    hotel = {"type": "hotel", "coordinates": POINT, "evening_suggestions": []}
    await evenings._hotel_suggestions(hotel, START, START.replace(hour=17), ["culture"], Provider())
    assert hotel["evening_suggestions"] == []


@pytest.mark.asyncio
async def test_live_evening_and_saved_display_reject_explicit_hold(monkeypatch):
    monkeypatch.setattr(repository, "nearby", lambda *args, **kwargs: [record()])
    assert await evenings.LiveEveningProvider().nearby(POINT, ["culture"], START) == []
    hotel = {
        "arrival_time": START.isoformat(),
        "deadline": START.replace(hour=17).isoformat(),
        "evening_suggestions": [{**record(), "travel_seconds": [60, 60]}],
    }
    assert list(evenings.current_suggestions(hotel)) == []
