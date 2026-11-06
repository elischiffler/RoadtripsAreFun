"""Open meal windows are advisory metadata, never a routed stop or provider lookup."""

from copy import deepcopy
from datetime import datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.itinerary_models import Itinerary_Day, Itinerary_Payload
from app.models.routing_models.routing_models import Route
from app.models.scheduling_policy import SchedulingPolicy
from app.routers import itinerary_api
from app.routing.meal_slots import add_meal_windows
from app.utils.auth import require_authenticated_user

ZONE = "America/Los_Angeles"


def _day(date, *, zone=ZONE):
    return Itinerary_Day(
        date=datetime.fromisoformat(date).strftime("%A, %B %d %Y"),
        stops=[
            {
                "name": "Existing visit",
                "time": "12:00 PM",
                "arrival_time": f"{date}T12:00:00-07:00",
                "departure_time": f"{date}T13:00:00-07:00",
                "timezone": zone,
                "kind": "arrival",
            }
        ],
    )


def _meals(days):
    return [stop for day in days for stop in day.stops if stop.kind == "meal"]


def _route(start="2027-06-01T10:00:00-07:00", duration=9 * 3600):
    return Route(
        coordinates=[],
        distance=1,
        duration=duration,
        steps=[],
        stops=[
            {
                "name": "Arrive at your destination",
                "type": "end",
                "duration": duration,
                "timezone": ZONE,
                "source_provenance": [{"source": "fixture", "release": "reviewed"}],
                "room_offers": [{"price": 123, "currency": "USD"}],
            }
        ],
        geometry={"coordinates": []},
        cost=0,
        departure_time=datetime.fromisoformat(start),
        start_timezone=ZONE,
        scheduling_policy=SchedulingPolicy(late_driving=True),
    )


def test_first_and_last_day_bounds_keep_only_overlapping_open_windows():
    days = [_day("2027-06-01"), _day("2027-06-02")]
    actual = deepcopy(days)
    meals = _meals(
        add_meal_windows(
            days,
            departure=datetime.fromisoformat("2027-06-01T14:00:00-07:00"),
            trip_end=datetime.fromisoformat("2027-06-02T12:30:00-07:00"),
        )
    )
    assert [row.id for row in meals] == [
        "meal:2027-06-01:dinner",
        "meal:2027-06-02:breakfast",
        "meal:2027-06-02:lunch",
    ]
    # Partially overlapping windows remain suggestions, not fabricated bookings.
    assert meals[-1].window_end == "2027-06-02T14:00:00-07:00"
    assert days == actual


def test_daytime_windows_follow_local_dst_change_without_offset_drift():
    days = [_day("2027-03-13"), _day("2027-03-14")]
    rows = _meals(
        add_meal_windows(
            days,
            departure=datetime(2027, 3, 13, 6, tzinfo=ZoneInfo(ZONE)),
            trip_end=datetime(2027, 3, 14, 21, tzinfo=ZoneInfo(ZONE)),
        )
    )
    assert rows[0].window_start == "2027-03-13T07:00:00-08:00"
    assert rows[3].window_start == "2027-03-14T07:00:00-07:00"
    assert all(row.timezone == ZONE for row in rows)


def test_unreserved_rows_are_idempotent_and_never_contain_place_or_visit_data():
    start = datetime.fromisoformat("2027-06-01T06:00:00-07:00")
    first = add_meal_windows([_day("2027-06-01")], departure=start)
    again = add_meal_windows(first, departure=start)
    assert first == again
    assert len({row.id for row in _meals(again)}) == 3
    # Lunch can overlap the real visit: this is deliberately not a booked slot.
    assert first[0].stops[0].arrival_time == "2027-06-01T12:00:00-07:00"
    assert _meals(first)[1].window_start == "2027-06-01T12:00:00-07:00"
    for row in _meals(again):
        assert row.optional and row.status == "open" and row.time == "Unscheduled"
        assert "May overlap driving or visits" in row.notice
        assert "no time or place is reserved" in row.notice
        assert row.arrival_time is row.departure_time is row.visit_duration is None
        assert row.provider_id is row.source is row.address is row.url is row.price is None
        assert row.hotel_rooms is row.room_offers is None
        assert row.source_provenance == []


def test_unknown_end_does_not_invent_a_cutoff_or_unknown_departure_a_date():
    days = [_day("2027-06-01")]
    start = datetime.fromisoformat("2027-06-01T10:00:00-07:00")
    assert [row.meal_type for row in _meals(add_meal_windows(days, departure=start))] == [
        "lunch",
        "dinner",
    ]
    assert add_meal_windows(days, departure=None) == days


def test_unknown_timezone_stays_naive_and_day_zones_are_retained():
    first, second = _day("2027-06-01", zone=None), _day("2027-06-02", zone="America/Denver")
    first.stops[0].arrival_time = None
    first.stops[0].departure_time = None
    rows = _meals(add_meal_windows([first, second], departure=datetime(2027, 6, 1, 6)))
    assert rows[0].window_start == "2027-06-01T07:00:00" and rows[0].timezone is None
    assert rows[3].window_start == "2027-06-02T07:00:00-06:00"
    assert rows[3].timezone == "America/Denver"


@pytest.fixture
def no_catalog(monkeypatch):
    lookup = AsyncMock()
    monkeypatch.setattr(itinerary_api, "refresh_for_timing", lookup)
    return lookup


@pytest.mark.asyncio
async def test_build_opt_in_preserves_all_actual_times_provenance_and_room_quotes(no_catalog):
    original = _route()
    legacy = await itinerary_api.build_itinerary(Itinerary_Payload(route=original))
    timed_stops = deepcopy(original.stops)
    opted = Itinerary_Payload(route=original, include_meal_slots=True)
    with_meals = await itinerary_api.build_itinerary(opted)
    assert not _meals(legacy)
    assert [row.meal_type for row in _meals(with_meals)] == ["lunch", "dinner"]
    assert original.stops == timed_stops
    assert [row for day in with_meals for row in day.stops if row.kind != "meal"] == [
        row for day in legacy for row in day.stops
    ]
    assert await itinerary_api.build_itinerary(opted) == with_meals
    assert no_catalog.await_count == 3


@pytest.mark.asyncio
async def test_midnight_route_does_not_offer_meals_after_actual_final_arrival(no_catalog):
    route = _route("2027-06-01T22:00:00-07:00", 2 * 3600)
    days = await itinerary_api.build_itinerary(
        Itinerary_Payload(route=route, include_meal_slots=True)
    )
    assert len(days) == 2
    assert days[-1].stops[0].arrival_time == "2027-06-02T00:00:00-07:00"
    assert _meals(days) == []


@pytest.mark.asyncio
async def test_saved_route_recovers_departure_from_actual_first_arrival(no_catalog):
    route = _route()
    route.departure_time = None
    route.stops[0]["arrival_time"] = "2027-06-01T19:00:00-07:00"
    rows = _meals(
        await itinerary_api.build_itinerary(Itinerary_Payload(route=route, include_meal_slots=True))
    )
    assert [row.meal_type for row in rows] == ["lunch", "dinner"]
    assert all(row.id.startswith("meal:2027-06-01:") for row in rows)


@pytest.mark.asyncio
async def test_last_waypoint_is_not_assumed_to_be_a_final_destination(no_catalog):
    route = _route(duration=2 * 3600)
    route.stops[0]["type"] = "generic"
    rows = _meals(
        await itinerary_api.build_itinerary(Itinerary_Payload(route=route, include_meal_slots=True))
    )
    assert [row.meal_type for row in rows] == ["lunch", "dinner"]


@pytest.mark.parametrize("opt_in", [False, True])
def test_authenticated_endpoint_preserves_default_and_exposes_opt_in(no_catalog, opt_in):
    app = FastAPI()
    app.include_router(itinerary_api.router)
    app.dependency_overrides[require_authenticated_user] = lambda: "fixture-account"
    payload = {"route": _route().model_dump(mode="json")}
    if opt_in:
        payload["include_meal_slots"] = True
    response = TestClient(app).post("/generate-itinerary", json=payload)
    assert response.status_code == 200
    days = [Itinerary_Day.model_validate(day) for day in response.json()]
    assert bool(_meals(days)) == opt_in
    no_catalog.assert_awaited_once()


def test_legacy_itinerary_json_still_parses_with_optional_meal_fields():
    row = Itinerary_Day.model_validate(
        {"date": "Tuesday, June 01 2027", "stops": [{"name": "Visit", "time": "10:00 AM"}]}
    ).stops[0]
    assert row.id is row.meal_type is row.window_start is row.window_end is None
