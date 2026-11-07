"""Wrapped multiday driving, full hotel quotes and awake-relative meals; offline only."""

from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from app.models.itinerary_models import Itinerary_Payload
from app.models.routing_models.routing_models import Route
from app.routers.itinerary_api import build_itinerary
from app.routing import lodging
from app.routing.base import PlanOptions
from app.routing.cp_sat_scheduler import _over_budget, schedule_cp_sat_route
from app.routing.lodging import LodgingCoverageConflict, lodging_metadata, required_stay
from app.routing.meal_reservations import MealClock, MealScheduleConflict, meal_windows
from app.routing.occupancy import HotelRoom
from app.routing.travel_timing import apply_timing
from tests.one_day_rhythm_tests import policy
from tests.reserved_meal_tests import ZONE, endpoint, moment
from tests.routing.conftest import build_route
from tests.routing_api.route_edit_tests import request, road, run, with_hotel

ROOMS = [{"adults": 2, "child_ages": []}]


def quoted(first, last, *, price=201.37, rooms=None):
    rooms = rooms or ROOMS
    scope = (
        "one_room_one_night_including_taxes_fees"
        if (last - first).days == 1
        else "one_room_stay_including_taxes_fees"
    )
    offers = [
        {
            "room": r,
            "price": price + i,
            "url": f"https://hotel.example/stay?in={first}&out={last}",
            "check_in_date": first.isoformat(),
            "check_out_date": last.isoformat(),
            "price_scope": scope,
        }
        for i, r in enumerate(rooms)
    ]
    return {
        "provider_id": "google:verified-stay",
        "name": "Verified dated stay",
        "coordinates": [40, -105],
        "utility": 0.8,
        "price": sum(o["price"] for o in offers),
        "hotel_rooms": deepcopy(rooms),
        "room_offers": offers,
        "check_in_date": first.isoformat(),
        "check_out_date": last.isoformat(),
        "price_scope": scope
        if len(offers) == 1
        else "independent_room_quotes_not_combined_inventory",
    }


def hotel_for(arrival, departure, duration=3600):
    first, last = required_stay(arrival, departure)
    return {**quoted(first, last), "type": "hotel", "timezone": ZONE, "duration": duration}


@pytest.mark.parametrize(
    "arrival,departure,expected",
    [
        ("2030-06-01T18:00", "2030-06-02T09:00", (date(2030, 6, 1), date(2030, 6, 2))),
        ("2030-06-02T08:00", "2030-06-02T18:00", (date(2030, 6, 1), date(2030, 6, 3))),
        ("2030-06-01T20:00", "2030-06-02T06:00", (date(2030, 6, 1), date(2030, 6, 2))),
        ("2030-06-01T17:00", "2030-06-02T11:00", (date(2030, 5, 31), date(2030, 6, 3))),
    ],
)
def test_conservative_quote_range_is_calendar_based_not_a_hotel_hours_claim(
    arrival, departure, expected
):
    a = datetime.fromisoformat(arrival).replace(tzinfo=ZoneInfo(ZONE))
    d = datetime.fromisoformat(departure).replace(tzinfo=ZoneInfo(ZONE))
    assert required_stay(a, d) == expected
    assert lodging_metadata(a, d, *expected)["access_status"] == "confirmation_required"


def test_dates_are_strict_dates_not_datetimes_and_dst_uses_utc_instants():
    with pytest.raises(ValueError):
        lodging.stay_dates(datetime(2030, 6, 1), date(2030, 6, 2))
    zone = ZoneInfo(ZONE)
    # Positive real elapsed time despite identical local wall clocks.
    a = datetime(2030, 11, 3, 1, 30, tzinfo=zone, fold=0)
    d = a.replace(fold=1)
    assert required_stay(a, d) == (date(2030, 11, 2), date(2030, 11, 3))
    a = datetime(2030, 3, 9, 18, tzinfo=zone)
    d = datetime(2030, 3, 10, 9, tzinfo=zone)
    assert required_stay(a, d) == (date(2030, 3, 9), date(2030, 3, 10))


def test_budget_is_per_room_per_night_but_total_is_full_quote_once():
    hotel = quoted(date(2030, 6, 1), date(2030, 6, 3), price=201.37)
    hotel["lodging"] = {"nights": 2}
    assert not _over_budget(hotel, 110, 1)
    assert _over_budget(hotel, 100, 1)
    assert hotel["price"] == 201.37


@pytest.mark.asyncio
async def test_multiday_wrapped_drive_and_eight_hour_daytime_sleep_with_all_meals(
    fake_services, monkeypatch
):
    monkeypatch.setattr(lodging, "current_local_date", lambda zone: date(2026, 11, 7))
    services = fake_services.bundle()
    services.timezone_at = AsyncMock(return_value=ZONE)
    lookups = []

    async def hotels(point, check_in, price_range, weights, rooms, *, check_out_date=None):
        assert check_out_date and (check_out_date - check_in).days == 2
        assert price_range == ((0.0, 220.0), "0-220.00")
        lookups.append((check_in, check_out_date))
        return [
            {
                **quoted(check_in, check_out_date),
                "provider_id": f"google:night-{len(lookups)}",
                "coordinates": point,
            }
        ]

    services.cp_sat_hotels = hotels
    selected = policy((20, 6), (8, 16))
    start = moment("20:00", "2030-06-01")
    rooms = [HotelRoom.model_validate(r) for r in ROOMS]
    stops, cost = await schedule_cp_sat_route(
        build_route(30 * 3600),
        [],
        PlanOptions(
            0,
            110,
            start,
            traveler_count=2,
            hotel_rooms=rooms,
            reserve_meal_slots=True,
            scheduling_policy=selected,
        ),
        services,
    )
    assert len(stops) >= 2 and len(lookups) == len(stops)
    assert cost == pytest.approx(len(stops) * 201.37)
    # Actual reroute durations may differ from estimates, but match all quote ranges.
    per_leg = 30 * 3600 / (len(stops) + 1)
    for stop in stops:
        stop["duration"] = per_leg
    stops.append(endpoint(per_leg))
    apply_timing(stops, start, selected, ZONE, reserve_meal_slots=True)
    all_meals = [m for stop in stops for m in stop["meal_breaks"]]
    assert len({m["id"] for m in all_meals}) == len(all_meals)
    hotels = [s for s in stops if s["type"] == "hotel"]
    assert all(h["lodging"]["nights"] == 2 for h in hotels)
    sleeps = [b for h in hotels for b in h["daily_rhythm_blocks"] if b["kind"] == "sleep"]
    assert len(sleeps) == len(hotels)
    for sleep in sleeps:
        a, d = map(datetime.fromisoformat, (sleep["arrival_time"], sleep["departure_time"]))
        assert (
            a.hour == 8
            and d.hour == 16
            and (d.astimezone(UTC) - a.astimezone(UTC)).total_seconds() == 8 * 3600
        )
        for meal in all_meals:
            ma, md = map(datetime.fromisoformat, (meal["arrival_time"], meal["departure_time"]))
            assert md <= a or ma >= d
    assert {
        (
            m["meal_type"],
            datetime.fromisoformat(m["window_start"]).hour,
            datetime.fromisoformat(m["window_end"]).hour,
        )
        for m in all_meals
    } == {("breakfast", 16, 18), ("lunch", 21, 23), ("dinner", 3, 5)}
    dinner = next(m for m in all_meals if m["meal_type"] == "dinner")
    assert dinner["id"].split(":")[1] < dinner["arrival_time"][:10]
    saved = Route(
        coordinates=[[40, -105], [39, -104]],
        distance=100,
        duration=30 * 3600,
        steps=[],
        geometry={"coordinates": [[-105, 40], [-104, 39]]},
        cost=cost,
        stops=stops,
        departure_time=start,
        start_timezone=ZONE,
        scheduling_policy=selected,
        reserve_meal_slots=True,
    )
    before = deepcopy(stops)
    days = await build_itinerary(Itinerary_Payload(route=saved))
    assert saved.stops == before
    assert sum(s.price or 0 for d in days for s in d.stops if s.type == "hotel") == cost
    assert all(
        s.lodging["access_status"] == "confirmation_required"
        for d in days
        for s in d.stops
        if s.type == "hotel"
    )


@pytest.mark.asyncio
async def test_prior_night_in_past_fails_before_provider_work(fake_services, monkeypatch):
    monkeypatch.setattr(lodging, "current_local_date", lambda zone: date(2030, 6, 1))
    services = fake_services.bundle()
    services.timezone_at = AsyncMock(return_value=ZONE)
    services.cp_sat_hotels = AsyncMock()
    with pytest.raises(LodgingCoverageConflict):
        await schedule_cp_sat_route(
            build_route(15 * 3600),
            [],
            PlanOptions(
                0,
                100,
                moment("05:00", "2030-06-01"),
                traveler_count=2,
                hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
                scheduling_policy=policy((20, 6), (8, 16)),
            ),
            services,
        )
    services.cp_sat_hotels.assert_not_called()


def test_wake_cycle_ids_midnight_window_and_early_departure_include_prior_cycle():
    selected = policy((23, 7), (15, 23)).daily_schedule
    assert meal_windows(selected) == (
        ("breakfast", 23, 25, 1800),
        ("lunch", 28, 30, 2700),
        ("dinner", 34, 36, 3600),
    )
    start = moment("00:00", "2030-06-02")
    clock = MealClock(start, start + timedelta(hours=2), selected)
    finish = clock.drive(start, 3600, ZoneInfo(ZONE))
    finish = clock.finish(finish, ZoneInfo(ZONE))
    breakfast = clock.breaks[0]
    assert breakfast["id"] == "meal:2030-06-01:breakfast"
    assert (
        breakfast["window_start"][:10] == "2030-06-01"
        and breakfast["window_end"][:10] == "2030-06-02"
    )
    assert finish > start


@pytest.mark.parametrize("day", ["2030-03-09", "2030-11-02"])
def test_relevant_shifted_dst_boundary_fails_without_inventing_an_offset(day):
    selected = (
        policy((20, 6), (7, 15)).daily_schedule
        if day.endswith("03-09")
        else policy((20, 6), (6, 14)).daily_schedule
    )
    start = moment("20:00", day)
    clock = MealClock(start, start + timedelta(hours=12), selected)
    with pytest.raises(MealScheduleConflict):
        clock.drive(start, 9 * 3600, ZoneInfo(ZONE))


def test_unrelated_previous_dst_meal_window_does_not_reject_next_wake_cycle():
    selected = policy((20, 6), (7, 15)).daily_schedule
    start = moment("20:00", "2030-03-10")
    clock = MealClock(start, start + timedelta(hours=12), selected)
    assert clock.drive(start, 7 * 3600, ZoneInfo(ZONE)) > start


def test_nominal_arrival_before18_does_not_reject_actual_meal_aware_quote_after18():
    selected = policy((9, 20), (22, 7))
    start = moment("10:00", "2030-06-01")
    hotel = hotel_for(moment("18:15", "2030-06-01"), moment("09:00", "2030-06-02"), 7.5 * 3600)
    stops = [hotel, endpoint(3600)]
    apply_timing(stops, start, selected, ZONE, reserve_meal_slots=True)
    assert stops[0]["arrival_time"] == "2030-06-01T18:15:00-07:00"
    assert stops[0]["lodging"]["nights"] == 1
    forged = deepcopy(stops)
    forged[0]["check_out_date"] = "2030-06-03"
    with pytest.raises(LodgingCoverageConflict):
        apply_timing(forged, start, selected, ZONE, reserve_meal_slots=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("compatible", [True, False])
async def test_edit_uses_actual_meal_clock_for_quote_coverage_and_never_changes_saved_input(
    compatible,
):
    saved = with_hotel()
    saved["departure_time"] = "2030-06-01T10:00:00+00:00"
    saved["reserve_meal_slots"] = True
    saved["scheduling_policy"] = policy((9, 20), (22, 7)).model_dump()
    hotel_coordinates = saved["stops"][1]["coordinates"]
    saved["stops"][1].update(quoted(date(2030, 6, 1), date(2030, 6, 2)))
    saved["stops"][1]["coordinates"] = hotel_coordinates
    if not compatible:
        saved["stops"][1]["check_out_date"] = "2030-06-03"
    payload = request(route=saved, action="replace", stop_index=0)
    before = deepcopy(payload.model_dump())
    response = road(3, 0)
    response.legs[1].duration = 19800
    response.legs[2].duration = 3600
    response.duration = 23400
    if not compatible:
        with pytest.raises(LodgingCoverageConflict):
            await run(payload, response=response)
    else:
        result, _ = await run(payload, response=response)
        hotel = result.route.stops[1]
        assert hotel["arrival_time"] == "2030-06-01T18:15:00+00:00"
        assert hotel["lodging"]["check_in_date"] == "2030-06-01"
    assert payload.model_dump() == before


@pytest.mark.parametrize("compatible", [True, False])
def test_http_edit_revalidates_actual_quote_dates_without_persistence(monkeypatch, compatible):
    from unittest.mock import MagicMock

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.crud import chat_crud
    from app.routers import routing_api
    from app.routing.route_edit import preview_route_edit
    from app.utils.auth import require_authenticated_user
    from tests.routing_api.route_edit_tests import catalog

    saved = with_hotel()
    saved["departure_time"] = "2030-06-01T10:00:00+00:00"
    saved["reserve_meal_slots"] = True
    saved["scheduling_policy"] = policy((9, 20), (22, 7)).model_dump()
    old_coordinates = saved["stops"][1]["coordinates"]
    saved["stops"][1].update(quoted(date(2030, 6, 1), date(2030, 6, 2)))
    saved["stops"][1]["coordinates"] = old_coordinates
    if not compatible:
        saved["stops"][1]["check_out_date"] = "2030-06-03"
    value = request(route=saved, action="replace", stop_index=0)
    original = value.model_dump(mode="json")
    response = road(3, 0)
    response.legs[1].duration = 19800
    response.legs[2].duration = 3600
    response.duration = 23400

    async def actual_preview(payload, **kwargs):
        return await preview_route_edit(
            payload,
            route_call=AsyncMock(return_value=response),
            timezone_at=AsyncMock(return_value="UTC"),
            catalog_lookup=catalog,
        )

    monkeypatch.setattr(routing_api, "preview_route_edit", actual_preview)
    monkeypatch.setattr(
        routing_api, "_build_services", lambda: type("Services", (), {"timezone_at": None})()
    )
    save = MagicMock(side_effect=AssertionError("preview must never save"))
    monkeypatch.setattr(chat_crud, "update_chat_component", save)
    application = FastAPI()
    application.include_router(routing_api.router)
    application.dependency_overrides[require_authenticated_user] = lambda: "signed-fixture-owner"
    result = TestClient(application).post("/route-edit", json=original)
    assert result.status_code == (200 if compatible else 422)
    if compatible:
        hotel = result.json()["route"]["stops"][1]
        assert hotel["arrival_time"] == "2030-06-01T18:15:00+00:00"
        assert hotel["lodging"]["check_out_date"] == "2030-06-02"
    assert value.model_dump(mode="json") == original
    save.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("edited", [False, True])
async def test_switch_to_legacy_removes_copied_sleep_rows_and_notices_but_preserves_booked_data(
    edited,
):
    from app.models.scheduling_policy import SchedulingPolicy

    saved = with_hotel()
    saved["departure_time"] = "2030-06-01T15:00:00+00:00"
    saved["reserve_meal_slots"] = True
    saved["scheduling_policy"] = SchedulingPolicy().model_dump()
    hotel = saved["stops"][1]
    hotel["check_out_date"] = "2030-06-02"
    booking = quoted(date(2030, 6, 1), date(2030, 6, 2), price=hotel["price"])
    for key in ("hotel_rooms", "room_offers", "price_scope"):
        hotel[key] = booking[key]
    hotel["daily_rhythm_blocks"] = [
        {
            "name": "STALE SLEEP",
            "kind": "sleep",
            "arrival_time": "2030-06-02T07:00:00+00:00",
            "departure_time": "2030-06-02T08:00:00+00:00",
        }
    ]
    hotel["check_in_timing_notice"] = "STALE RHYTHM NOTICE"
    hotel["lodging"] = {"notice": "STALE LODGING", "access_status": "confirmation_required"}
    original = deepcopy(saved)
    if edited:
        payload = request(route=saved, action="replace", stop_index=0)
        response = road(3, 0)
        response.legs[1].duration = response.legs[2].duration = 3600
        response.duration = 7200
        result, _ = await run(payload, response=response)
        updated, days = result.route, result.itinerary
    else:
        for stop in saved["stops"]:
            stop["timezone"] = "UTC"
        saved["stops"][0]["duration"] = 0
        saved["stops"][1]["duration"] = saved["stops"][2]["duration"] = 3600
        planned = Route.model_validate(saved)
        # Trusted frozen catalog facts for the physical attraction are unchanged.
        from tests.routing_api.route_edit_tests import catalog

        days = await build_itinerary(Itinerary_Payload(route=planned), catalog_lookup=catalog)
        updated = planned
    updated_hotel = updated.stops[1]
    assert updated_hotel["check_in_date"] == original["stops"][1]["check_in_date"]
    assert updated_hotel["check_out_date"] == original["stops"][1]["check_out_date"]
    assert updated_hotel["price"] == original["stops"][1]["price"]
    assert updated_hotel["room_offers"] == original["stops"][1]["room_offers"]
    assert updated_hotel["hotel_rooms"] == original["stops"][1]["hotel_rooms"]
    assert all(
        key not in updated_hotel
        for key in ("daily_rhythm_blocks", "check_in_timing_notice", "lodging")
    )
    assert "STALE" not in str([day.model_dump() for day in days])
    breakfast = next(s for d in days for s in d.stops if s.kind == "meal" and s.name == "Breakfast")
    assert breakfast.arrival_time == "2030-06-02T07:00:00+00:00"
    assert breakfast.departure_time == "2030-06-02T07:30:00+00:00"


def test_http_itinerary_cannot_enable_internal_nominal_quote_bypass():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import itinerary_api
    from app.utils.auth import require_authenticated_user

    selected = policy((9, 20), (22, 7))
    hotel = hotel_for(moment("18:15", "2030-06-01"), moment("09:00", "2030-06-02"), 7.5 * 3600)
    hotel["check_out_date"] = "2030-06-03"
    hotel["_nominal"] = True
    planned = Route(
        coordinates=[[40, -105], [39, -104]],
        distance=100,
        duration=8.5 * 3600,
        steps=[],
        geometry={"coordinates": [[-105, 40], [-104, 39]]},
        cost=201.37,
        stops=[hotel, endpoint(3600)],
        departure_time=moment("10:00", "2030-06-01"),
        start_timezone=ZONE,
        scheduling_policy=selected,
        reserve_meal_slots=True,
    )
    application = FastAPI()
    application.include_router(itinerary_api.router)
    application.dependency_overrides[require_authenticated_user] = lambda: "fixture-owner"
    body = {"route": {**planned.model_dump(mode="json"), "_nominal": True}, "_nominal": True}
    result = TestClient(application).post("/generate-itinerary", json=body)
    assert result.status_code == 422
    assert "dated hotel quote" in result.json()["detail"]


@pytest.mark.asyncio
async def test_legacy_absent_policy_also_discards_only_derived_rhythm_display_state():
    from tests.routing_api.route_edit_tests import catalog

    saved = with_hotel()
    saved["scheduling_policy"] = None
    saved["reserve_meal_slots"] = False
    hotel = saved["stops"][1]
    hotel["daily_rhythm_blocks"] = [
        {
            "name": "STALE SLEEP",
            "kind": "sleep",
            "arrival_time": "2030-06-02T07:00:00+00:00",
            "departure_time": "2030-06-02T08:00:00+00:00",
        }
    ]
    hotel["check_in_timing_notice"] = "STALE NOTICE"
    hotel["lodging"] = {"notice": "STALE LODGING"}
    original = deepcopy(hotel)
    planned = Route.model_validate(saved)
    days = await build_itinerary(Itinerary_Payload(route=planned), catalog_lookup=catalog)
    assert "STALE" not in str([day.model_dump() for day in days])
    assert all(
        key not in planned.stops[1]
        for key in ("lodging", "daily_rhythm_blocks", "check_in_timing_notice")
    )
    assert planned.stops[1]["check_in_date"] == original["check_in_date"]
    assert planned.stops[1]["price"] == original["price"]
