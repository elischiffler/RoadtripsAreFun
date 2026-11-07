"""Meal breaks are real elapsed reservations, tested without provider or DB access."""

import json
from copy import deepcopy
from datetime import datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agent.progress_stream import stream_turn
from app.models.itinerary_models import Itinerary_Payload
from app.models.routing_models.routing_models import Route
from app.models.scheduling_policy import SchedulingPolicy
from app.routers import itinerary_api, routing_api
from app.routing.meal_reservations import MealClock, MealScheduleConflict, MealScheduleHTTPError
from app.routing.sources.evenings import current_suggestions
from app.routing.travel_timing import apply_timing
from app.utils.auth import require_authenticated_user

ZONE = "America/Los_Angeles"


def moment(clock, date="2027-06-01", zone=ZONE):
    return datetime.fromisoformat(f"{date}T{clock}").replace(tzinfo=ZoneInfo(zone))


def endpoint(seconds, zone=ZONE):
    return {"name": "Destination", "type": "end", "duration": seconds, "timezone": zone}


def visit(seconds, dwell=90 * 60, *, opens=None, closes=None):
    stop = {
        "provider_id": "fixture:visit",
        "name": "Visit",
        "type": "stop",
        "duration": seconds,
        "timezone": ZONE,
        "visit_duration": {
            "schema_version": "roadtrips-visit-duration/1",
            "seconds": dwell,
            "source": "ai_estimate",
            "reason": "estimated",
        },
    }
    if opens:
        stop["source_provenance"] = [
            {
                "dataset": "Synthetic fixture",
                "source_visit_calendar": {
                    "schema_version": "roadtrips-source-visit-calendar/1",
                    "weekly_windows": [
                        {"weekdays": list(range(7)), "opens": opens, "closes": closes}
                    ],
                    "source_receipts": [{"source_url": "https://operator.example/fixture"}],
                },
            }
        ]
    return stop


def timed(stops, start="09:00", policy=None, date="2027-06-01"):
    apply_timing(
        stops, moment(start, date), policy or SchedulingPolicy(), ZONE, reserve_meal_slots=True
    )
    return [meal for stop in stops for meal in stop["meal_breaks"]]


def test_long_road_leg_pauses_but_preserves_measured_driving_seconds():
    stops = [endpoint(10 * 3600)]
    rows = timed(stops)
    assert [row["meal_type"] for row in rows] == ["lunch", "dinner"]
    assert stops[0]["duration"] == 10 * 3600
    assert stops[0]["arrival_time"] == "2027-06-01T20:45:00-07:00"
    assert sum(row["duration_seconds"] for row in rows) == 105 * 60
    for row in rows:
        assert row["status"] == "reserved" and not row["optional"]
        assert "safe stopping location" in row["notice"]
        assert not {"coordinates", "provider_id", "address", "url"} & row.keys()
        assert datetime.fromisoformat(row["window_start"]) <= datetime.fromisoformat(
            row["arrival_time"]
        )
        assert datetime.fromisoformat(row["departure_time"]) <= datetime.fromisoformat(
            row["window_end"]
        )


@pytest.mark.parametrize("start,seconds", [("09:00", 600), ("12:00", 600), ("11:55", 600)])
def test_partial_trip_cannot_manufacture_full_meal_or_predeparture_breakfast(start, seconds):
    stops = [endpoint(seconds)]
    assert timed(stops, start) == []


def test_eligible_partial_lunch_is_reserved_before_short_trip_finishes():
    stops = [endpoint(50 * 60)]
    rows = timed(stops, "12:00")
    assert [r["meal_type"] for r in rows] == ["lunch"]
    assert rows[0]["arrival_time"] == "2027-06-01T12:05:00-07:00"
    assert stops[0]["arrival_time"] == "2027-06-01T13:35:00-07:00"


def test_unsplit_published_visit_can_precede_lunch_without_false_infeasibility():
    stops = [visit(2 * 3600, opens="11:00", closes="12:30"), endpoint(3600)]
    rows = timed(stops)
    assert stops[0]["arrival_time"] == "2027-06-01T11:00:00-07:00"
    assert stops[0]["departure_time"] == "2027-06-01T12:30:00-07:00"
    assert rows[0]["arrival_time"] >= stops[0]["departure_time"]


def test_lunch_fits_opening_wait_and_source_visit_remains_13_to_14():
    stops = [visit(2 * 3600, 3600, opens="13:00", closes="14:00"), endpoint(3600)]
    rows = timed(stops)
    assert stops[0]["arrival_time"] == "2027-06-01T13:00:00-07:00"
    assert rows[0]["arrival_time"] == "2027-06-01T12:00:00-07:00"
    assert rows[0]["departure_time"] == "2027-06-01T12:45:00-07:00"


def test_deferred_lunch_is_not_omitted_by_zero_or_tiny_final_leg():
    for seconds in [0, 0.00000001]:
        stops = [visit(3 * 3600, 50 * 60), endpoint(seconds)]
        rows = timed(stops)
        assert len(rows) == 1 and rows[0]["meal_type"] == "lunch"
        assert rows[0]["arrival_time"] == "2027-06-01T12:50:00-07:00"
        assert stops[-1]["arrival_time"].startswith("2027-06-01T13:35:00")


def test_nominal_bounds_control_eligibility_but_not_actual_break_end():
    clock = MealClock(moment("09:00"), moment("13:30"))
    due = clock._next(moment("12:50"), moment("13:40"), ZoneInfo(ZONE))
    assert clock._reserve(due, moment("12:50"), ZoneInfo(ZONE)) == moment("13:35")
    short = MealClock(moment("12:00"), moment("12:10"))
    assert short.finish(moment("13:30"), ZoneInfo(ZONE)) == moment("13:30")
    assert short.breaks == []  # A prior delay cannot invent eligibility.


@pytest.mark.parametrize("restart", ["07:00", "07:15", "09:00"])
def test_hotel_rest_reserves_dinner_and_breakfast_without_moving_restart(restart):
    stops = [
        {"name": "Hotel", "type": "hotel", "duration": 8 * 3600, "timezone": ZONE},
        endpoint(3 * 3600),
    ]
    rows = timed(stops, policy=SchedulingPolicy(morning_restart=restart))
    breakfast = next(r for r in rows if r["meal_type"] == "breakfast")
    assert breakfast["duration_seconds"] == 1800
    assert stops[0]["departure_time"] == f"2027-06-02T{restart}:00-07:00"
    if restart == "09:00":
        assert breakfast in stops[0]["meal_breaks"]
        assert breakfast["departure_time"] <= stops[0]["departure_time"]
    else:
        assert breakfast in stops[1]["meal_breaks"]
        assert breakfast["arrival_time"] >= stops[0]["departure_time"]


def test_dst_and_cross_zone_rows_keep_elapsed_durations_without_duplicate_meals():
    stops = [
        {"name": "Hotel", "type": "hotel", "duration": 7 * 3600, "timezone": ZONE},
        endpoint(5 * 3600, "America/Denver"),
    ]
    rows = timed(stops, date="2027-03-13")
    assert len({r["id"] for r in rows}) == len(rows)
    for row in rows:
        start = datetime.fromisoformat(row["arrival_time"])
        end = datetime.fromisoformat(row["departure_time"])
        assert (end - start).total_seconds() == row["duration_seconds"]
    breakfast = next(r for r in rows if r["meal_type"] == "breakfast")
    assert breakfast["arrival_time"].endswith("-07:00")


def test_meal_elapsed_time_counts_against_actual_destination_cutoff():
    stops = [endpoint(10 * 3600)]
    with pytest.raises(MealScheduleConflict) as error:
        timed(stops, policy=SchedulingPolicy(latest_destination_arrival="20:00"))
    assert error.value.status_code == 422


def test_legacy_timing_and_saved_route_reservation_replay_are_unchanged_or_idempotent():
    legacy = [endpoint(6 * 3600)]
    apply_timing(legacy, moment("09:00"), SchedulingPolicy(), ZONE)
    assert "meal_breaks" not in legacy[0]
    assert legacy[0]["arrival_time"] == "2027-06-01T15:00:00-07:00"
    reserved = deepcopy(legacy)
    timed(reserved)
    first = deepcopy(reserved)
    reserved[0]["meal_breaks"].append({"name": "Forged", "duration_seconds": 0})
    timed(reserved)
    assert reserved == first


@pytest.fixture
def no_catalog(monkeypatch):
    monkeypatch.setattr(itinerary_api, "refresh_for_timing", AsyncMock())


def route(stops, **kwargs):
    return Route(
        coordinates=[],
        distance=1,
        duration=sum(s["duration"] for s in stops),
        steps=[],
        stops=stops,
        geometry={"coordinates": []},
        cost=0,
        scheduling_policy=SchedulingPolicy(),
        start_timezone=ZONE,
        departure_time=moment("09:00"),
        reserve_meal_slots=True,
        **kwargs,
    )


@pytest.mark.asyncio
async def test_itinerary_renders_only_recomputed_reserved_rows_without_advisory_duplicates(
    no_catalog,
):
    planned = route([endpoint(6 * 3600)])
    planned.stops[0]["meal_breaks"] = [{"name": "Forged"}]
    payload = Itinerary_Payload(route=planned, include_meal_slots=True)
    days = await itinerary_api.build_itinerary(payload)
    meals = [s for d in days for s in d.stops if s.kind == "meal"]
    assert len(meals) == 1 and meals[0].status == "reserved"
    assert meals[0].time != "Unscheduled" and meals[0].duration_seconds == 2700
    assert meals[0].arrival_time and meals[0].departure_time
    assert await itinerary_api.build_itinerary(payload) == days


@pytest.mark.asyncio
async def test_meal_delay_never_claims_published_opening_wait(no_catalog):
    planned = route([visit(3 * 3600, 3 * 3600), endpoint(0)])
    days = await itinerary_api.build_itinerary(Itinerary_Payload(route=planned))
    physical = next(s for d in days for s in d.stops if s.name == "Visit")
    assert planned.stops[0]["wait_seconds"] == 0
    assert "published opening" not in (physical.notice or "")


@pytest.mark.parametrize("missing", ["policy", "departure", "end", "zone"])
def test_direct_authenticated_itinerary_rejects_incomplete_claimed_reservations(
    no_catalog, missing
):
    planned = route([endpoint(6 * 3600)])
    if missing == "policy":
        planned.scheduling_policy = None
    if missing == "departure":
        planned.departure_time = None
    if missing == "end":
        planned.stops[-1]["type"] = "generic"
    if missing == "zone":
        planned.start_timezone = None
    app = FastAPI()
    app.include_router(itinerary_api.router)
    app.dependency_overrides[require_authenticated_user] = lambda: "fixture"
    response = TestClient(app).post(
        "/generate-itinerary", json={"route": planned.model_dump(mode="json")}
    )
    assert response.status_code == 422


def test_timed_optional_evening_outing_cannot_overlap_reserved_dinner():
    hotel = {
        "arrival_time": "2027-06-01T17:00:00-07:00",
        "deadline": "2027-06-01T20:00:00-07:00",
        "meal_breaks": [
            {
                "arrival_time": "2027-06-01T18:00:00-07:00",
                "departure_time": "2027-06-01T19:00:00-07:00",
            }
        ],
        "evening_suggestions": [
            {
                "travel_seconds": [600, 600],
                "visit_time": "2027-06-01T17:40:00-07:00",
                "return_time": "2027-06-01T18:50:00-07:00",
            }
        ],
    }
    assert list(current_suggestions(hotel)) == []


@pytest.mark.asyncio
async def test_stream_exposes_only_allowlisted_meal_infeasibility_not_provider_details(monkeypatch):
    async def conflict():
        raise MealScheduleHTTPError()

    result = [json.loads(row) async for row in stream_turn(conflict)]
    assert result[-1] == {
        "type": "error",
        "status": 422,
        "code": "meal_schedule_conflict",
        "detail": MealScheduleConflict.public_message,
    }
    from fastapi import HTTPException

    async def provider():
        raise HTTPException(422, "private provider payload")

    result = [json.loads(row) async for row in stream_turn(provider)]
    assert result[-1] == {"type": "error", "status": 422}
    monkeypatch.setattr(
        routing_api, "plan_final_route", AsyncMock(side_effect=MealScheduleConflict())
    )
    with pytest.raises(MealScheduleHTTPError):
        await routing_api._plan_for_http(None, user_id="fixture", can_select_algorithm=False)


@pytest.mark.asyncio
async def test_westbound_itinerary_keeps_absolute_route_order_across_local_clocks(no_catalog):
    stops = [visit(5 * 3600, 15 * 60), endpoint(15 * 60)]
    stops[0]["timezone"] = "America/Denver"
    planned = route(stops)
    days = await itinerary_api.build_itinerary(Itinerary_Payload(route=planned))
    physical = [row.name for day in days for row in day.stops if row.kind == "arrival"]
    assert physical == ["Visit", "Destination"]
