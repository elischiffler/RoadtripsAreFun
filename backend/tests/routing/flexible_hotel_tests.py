"""Scheduling gate: actual elapsed durations, local deadlines and booking nights."""

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.agent.persona import AccountPersona
from app.agent.trip_profile import TripProfile
from app.main import app
from app.models.itinerary_models import Itinerary_Payload
from app.models.routing_models.routing_models import Route
from app.models.scheduling_policy import SchedulingPolicy
from app.routers import routing_api
from app.routers.itinerary_api import build_itinerary
from app.routing.base import PlanningError, PlanOptions, PlanResult
from app.routing.cp_sat_scheduler import schedule_cp_sat_route
from app.routing.occupancy import HotelRoom
from app.routing.travel_timing import apply_timing

ZONE = "America/Los_Angeles"
START = datetime(2035, 11, 21, 9, tzinfo=ZoneInfo(ZONE))


def point(duration, kind="end", zone=ZONE):
    return {
        "name": kind,
        "type": kind,
        "duration": duration,
        "coordinates": [34, -118],
        "timezone": zone,
    }


def saved_route(stops, policy):
    return Route(
        coordinates=[],
        distance=1,
        duration=1,
        steps=[],
        stops=stops,
        geometry={"coordinates": []},
        cost=100,
        scheduling_policy=policy,
        start_timezone=ZONE,
    )


@pytest.mark.parametrize(
    "patch",
    [
        {"preferred_hotel_arrival": "21:00"},
        {"morning_restart": "19:00"},
        {"late_cutoff": "25:00"},
        {"late_cutoff": "19:00"},
        {"late_driving": "yes"},
    ],
)
def test_invalid_policy_is_rejected(patch):
    with pytest.raises((ValidationError, ValueError)):
        SchedulingPolicy(**patch)


def test_old_profile_defaults_and_policy_persistence():
    old = TripProfile.from_json('{"num_stops":3}')
    assert old.scheduling_policy == SchedulingPolicy()
    assert TripProfile().is_empty()
    old.scheduling_policy = SchedulingPolicy(late_driving=True, morning_restart="10:30")
    old.evening_interests = ["food"]
    assert TripProfile.from_json(old.to_json()) == old


@pytest.mark.parametrize(
    "late,hours,accepted",
    [
        (False, 11, True),
        (False, 11 + 1 / 60, False),
        (True, 14 + 59 / 60, True),
        (True, 15, True),
        (True, 15 + 1 / 60, False),
    ],
)
@pytest.mark.parametrize("kind", ["hotel", "end"])
def test_actual_reroute_cutoff_inclusive_only_through_midnight(late, hours, accepted, kind):
    stops = [point(hours * 3600, kind)]
    policy = SchedulingPolicy(late_driving=late)
    if kind == "end" and not late:
        accepted = hours <= 12
    if not accepted:
        with pytest.raises(PlanningError, match="driving window"):
            apply_timing(stops, START, policy, ZONE)
        return
    apply_timing(stops, START, policy, ZONE)
    if kind == "hotel" and hours > 11:
        assert stops[0]["check_in_date"] == "2035-11-21"
        assert stops[0]["departure_time"].startswith("2035-11-22T09:00")
        assert stops[0]["late_check_in_notice"] == "Confirm late check-in with the hotel"


def test_narrower_late_cutoff_and_two_hour_visit_are_enforced():
    policy = SchedulingPolicy(late_driving=True, late_cutoff="22:00")
    apply_timing([point(13 * 3600)], START, policy)
    with pytest.raises(PlanningError):
        apply_timing([point(13 * 3600 + 1)], START, policy)
    with pytest.raises(PlanningError):
        apply_timing([point(12 * 3600, "stop")], START, policy)


@pytest.mark.parametrize("start", ["2035-01-31T09:00:00-08:00", "2035-12-31T09:00:00-08:00"])
@pytest.mark.asyncio
async def test_midnight_calendar_rollover_itinerary_and_reload(start):
    policy = SchedulingPolicy(late_driving=True, morning_restart="10:30")
    route = saved_route([point(15 * 3600, "hotel"), point(3600)], policy)
    route = Route.model_validate_json(route.model_dump_json())
    days = await build_itinerary(Itinerary_Payload(route=route, start_time=start))
    assert len(days) == 2
    assert [s.time for s in days[1].stops] == ["12:00 AM", "10:30 AM", "11:30 AM"]
    assert route.stops[0]["check_in_date"] == start[:10]


def test_actual_arrival_timezone_controls_deadline():
    east = point(8 * 3600, zone="America/New_York")
    apply_timing([east], START, SchedulingPolicy(), ZONE)
    assert east["arrival_time"] == "2035-11-21T20:00:00-05:00"
    with pytest.raises(PlanningError):
        apply_timing(
            [point(9 * 3600 + 60, zone="America/New_York")], START, SchedulingPolicy(), ZONE
        )


def test_dst_duration_is_elapsed_time_and_restart_uses_new_offset():
    start = datetime(2035, 11, 3, 23, tzinfo=ZoneInfo(ZONE))
    hotel = point(3600, "hotel")
    end = point(3600)
    apply_timing([hotel, end], start, SchedulingPolicy(late_driving=True), ZONE)
    assert hotel["arrival_time"] == "2035-11-04T00:00:00-07:00"
    assert hotel["departure_time"] == "2035-11-04T09:00:00-08:00"
    assert end["arrival_time"] == "2035-11-04T10:00:00-08:00"


def test_first_day_can_depart_after_preferred_arrival():
    end = point(3600)
    apply_timing([end], START.replace(hour=18, minute=30), SchedulingPolicy(), ZONE)
    assert end["arrival_time"].startswith("2035-11-21T19:30")


@pytest.mark.parametrize("stored_departure", [False, True])
def test_direct_http_itinerary_recovers_saved_travel_day(allow_provider_auth, stored_departure):
    start = START.replace(hour=23)
    policy = SchedulingPolicy(late_driving=True)
    stops = [point(3600, "hotel"), point(3600)]
    apply_timing(stops, start, policy, ZONE)
    route = saved_route(stops, policy)
    if stored_departure:
        route.departure_time = start
    response = TestClient(app).post(
        "/generate-itinerary", json={"route": route.model_dump(mode="json")}
    )
    assert response.status_code == 200, response.text
    days = response.json()
    assert "November 21 2035" in days[0]["date"]
    assert days[0]["stops"][0]["time"] == "11:00 PM"
    assert [s["time"] for s in days[1]["stops"]] == ["12:00 AM", "09:00 AM", "10:00 AM"]


def test_explicit_itinerary_departure_overrides_route(allow_provider_auth):
    route = saved_route([point(3600)], SchedulingPolicy())
    route.departure_time = START
    response = TestClient(app).post(
        "/generate-itinerary",
        json={
            "route": route.model_dump(mode="json"),
            "start_time": START.replace(hour=10).isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()[0]["stops"][0]["time"] == "10:00 AM"
    assert response.json()[0]["stops"][1]["time"] == "11:00 AM"


def services_with_hotels(fake_services, outcomes):
    services = fake_services.bundle()
    calls = []

    async def zone_at(coords):
        return ZONE

    async def hotels(coords, stay_date, prices, weights, hotel_rooms):
        calls.append((coords, stay_date))
        found = outcomes[min(len(calls) - 1, len(outcomes) - 1)]
        if not found:
            return []
        return [
            {
                "provider_id": "hotel-1",
                "hotel_rooms": [room.model_dump() for room in hotel_rooms],
                "room_offers": [{"room": hotel_rooms[0].model_dump(), "price": 120, "url": None}],
                "price_scope": "one_room_one_night_including_taxes_fees",
                "name": "Verified hotel",
                "coordinates": coords,
                "price": 120,
                "utility": 0.8,
            }
        ]

    services.cp_sat_hotels = hotels
    services.timezone_at = zone_at
    return services, calls


@pytest.mark.asyncio
@pytest.mark.parametrize("misses,expected_hour", [(0, 18), (1, 17.5), (2, 18.5)])
async def test_hotel_search_around_soft_target(route, fake_services, misses, expected_hour):
    route.duration = 16 * 3600
    services, calls = services_with_hotels(fake_services, [False] * misses + [True])
    stops, cost = await schedule_cp_sat_route(
        route,
        [],
        PlanOptions(
            0, 100, START, traveler_count=2, hotel_rooms=[HotelRoom(adults=2, child_ages=[])]
        ),
        services,
    )
    assert len(calls) == misses + 1
    # The search point is the corridor position reached at that local hour.
    expected = services.find_position(
        route.geometry.coordinates, route.legs[0].steps, (expected_hour - 9) * 3600
    )
    assert stops[0]["coordinates"] == expected
    assert stops[0]["check_in_date"] == "2035-11-21"
    assert cost == 120 and "warning" in stops[0]


@pytest.mark.asyncio
async def test_unavailable_hotels_bound_retry_and_keep_failure_useful(route, fake_services):
    route.duration = 16 * 3600
    services, calls = services_with_hotels(fake_services, [False])
    with pytest.raises(PlanningError, match="earlier departure"):
        await schedule_cp_sat_route(
            route,
            [],
            PlanOptions(
                0, 100, START, traveler_count=2, hotel_rooms=[HotelRoom(adults=2, child_ages=[])]
            ),
            services,
        )
    assert len(calls) == 6


@pytest.mark.asyncio
@pytest.mark.parametrize("late,hour", [(False, 20), (True, 24)])
async def test_later_available_hotel_can_reach_effective_cutoff(route, fake_services, late, hour):
    route.duration = 20 * 3600
    services, calls = services_with_hotels(fake_services, [False] * 4 + [True])
    policy = SchedulingPolicy(late_driving=late)
    stops, _ = await schedule_cp_sat_route(
        route,
        [],
        PlanOptions(
            0,
            200,
            START,
            scheduling_policy=policy,
            traveler_count=2,
            hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
        ),
        services,
    )
    expected = services.find_position(
        route.geometry.coordinates, route.legs[0].steps, (hour - 9) * 3600
    )
    assert calls[4][0] == expected and stops[0]["coordinates"] == expected
    assert calls[4][1].isoformat() == "2035-11-21"


@pytest.mark.asyncio
async def test_late_mode_avoids_unnecessary_hotel_without_dropping_stops(route, fake_services):
    route.duration = 12 * 3600
    attraction = {"provider_id": "a", "name": "a", "coordinates": [34, -118]}
    services, calls = services_with_hotels(fake_services, [True])
    normal, _ = await schedule_cp_sat_route(
        route,
        [(2, attraction)],
        PlanOptions(
            1, 100, START, traveler_count=2, hotel_rooms=[HotelRoom(adults=2, child_ages=[])]
        ),
        services,
    )
    late, _ = await schedule_cp_sat_route(
        route,
        [(2, attraction)],
        PlanOptions(
            1,
            100,
            START,
            scheduling_policy=SchedulingPolicy(late_driving=True),
            traveler_count=2,
            hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
        ),
        services,
    )
    assert [s["type"] for s in late] == ["stop"]
    assert sum(s["type"] == "stop" for s in normal) == 1
    assert sum(s["type"] == "hotel" for s in normal) == 1
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_late_departure_hotel_uses_preceding_booking_night(route, fake_services):
    route.duration = 10 * 3600
    services, calls = services_with_hotels(fake_services, [True])
    policy = SchedulingPolicy(late_driving=True)
    stops, _ = await schedule_cp_sat_route(
        route,
        [],
        PlanOptions(
            0,
            100,
            START.replace(hour=23),
            scheduling_policy=policy,
            traveler_count=2,
            hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
        ),
        services,
    )
    assert calls[0][1].isoformat() == "2035-11-21"
    # Actual reroute reaches the overnight at midnight: the next departure is that morning.
    stops[0]["duration"] = 3600
    apply_timing(stops, START.replace(hour=23), policy, ZONE)
    assert stops[0]["arrival_time"].startswith("2035-11-22T00:00")
    assert stops[0]["departure_time"].startswith("2035-11-22T09:00")


@pytest.mark.parametrize(
    "late,seconds,status",
    [(False, 11 * 3600 + 60, 422), (True, 15 * 3600, 200), (True, 15 * 3600 + 60, 422)],
)
def test_http_final_detours_enforce_same_hard_limit(
    monkeypatch, allow_provider_auth, route, late, seconds, status
):
    hotel = point(0, "hotel")
    hotel["check_in_date"] = "2035-11-21"

    class Planner:
        async def plan(self, initial, options, services):
            assert options.scheduling_policy.late_driving is late
            return PlanResult(stopping_points=[hotel], total_cost=120)

    final = route.model_copy(deep=True)
    first = final.legs[0].model_copy(update={"duration": seconds})
    last = final.legs[0].model_copy(update={"duration": 3600})
    final.legs = [first, last]
    final.duration = seconds + 3600

    async def reroute(*args):
        return final

    monkeypatch.setattr(routing_api, "get_planner", lambda _: Planner())
    monkeypatch.setattr(routing_api, "_call_route", reroute)
    monkeypatch.setattr(routing_api, "load_account_persona", lambda _: AccountPersona.default())
    monkeypatch.setattr(
        routing_api,
        "get_location",
        lambda **kwargs: SimpleNamespace(
            address="fixture", raw={"annotations": {"timezone": {"name": ZONE}}}
        ),
    )
    response = TestClient(app).post(
        "/generate-final-route",
        json={
            "initial_route": route.model_dump(mode="json"),
            "traveler_count": 2,
            "hotel_rooms": [{"adults": 2, "child_ages": []}],
            "num_stops": 0,
            "budget": 200,
            "start": START.isoformat(),
            "scheduling_policy": {"late_driving": late},
        },
    )
    assert response.status_code == status, response.text
    if status == 200:
        hotel = response.json()["stops"][0]
        assert hotel["arrival_time"].startswith("2035-11-22T00:00")
        assert hotel["departure_time"].startswith("2035-11-22T09:00")


@pytest.mark.asyncio
async def test_itinerary_departure_uses_start_location_clock_even_with_utc_input():
    route = saved_route([point(3600)], SchedulingPolicy())
    itinerary = await build_itinerary(
        Itinerary_Payload(route=route, start_time="2035-11-21T17:00:00+00:00")
    )
    assert itinerary[0].stops[0].time == "09:00 AM"
    assert itinerary[0].stops[1].time == "10:00 AM"


@pytest.mark.parametrize("seconds,accepted", [(41438.484, True), (43200, True), (43200.001, False)])
def test_boulder_final_arrival_grace_is_bounded(seconds, accepted):
    start = datetime(2026, 10, 19, 9, tzinfo=ZoneInfo("America/Denver"))
    end = point(seconds, zone="America/Denver")
    if not accepted:
        with pytest.raises(PlanningError, match="21:00 local cutoff"):
            apply_timing([end], start, SchedulingPolicy())
        return
    apply_timing([end], start, SchedulingPolicy())
    assert end["deadline"] == "2026-10-19T21:00:00-06:00"
    assert end["warning"].startswith("Final destination arrival")
    if seconds == 41438.484:
        assert end["arrival_time"] == "2026-10-19T20:30:38.484000-06:00"


@pytest.mark.parametrize(
    "policy",
    [
        SchedulingPolicy(latest_destination_arrival="20:00"),
        SchedulingPolicy(preferred_hotel_arrival="17:00", latest_hotel_arrival="19:00"),
        SchedulingPolicy(late_driving=True, latest_destination_arrival="20:00"),
    ],
)
def test_explicit_final_restrictions_survive_serialization(policy):
    policy = SchedulingPolicy.model_validate_json(policy.model_dump_json())
    with pytest.raises(PlanningError):
        apply_timing([point(11.5 * 3600)], START, policy)


@pytest.mark.parametrize("duration", [-1, float("nan"), float("inf")])
def test_final_grace_never_accepts_invalid_durations(duration):
    with pytest.raises(PlanningError, match="invalid leg duration"):
        apply_timing([point(duration)], START, SchedulingPolicy())


@pytest.mark.asyncio
async def test_estimated_final_arrival_uses_same_grace(route, fake_services):
    route.duration = 11.5 * 3600
    services, calls = services_with_hotels(fake_services, [True])
    stops, cost = await schedule_cp_sat_route(
        route,
        [],
        PlanOptions(
            0, 100, START, traveler_count=2, hotel_rooms=[HotelRoom(adults=2, child_ages=[])]
        ),
        services,
    )
    assert stops == [] and cost == 0 and calls == []
    apply_timing([point(route.duration)], START, SchedulingPolicy())
