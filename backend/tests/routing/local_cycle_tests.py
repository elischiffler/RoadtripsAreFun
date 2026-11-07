"""Known destination-zone cycles cannot inherit an extra origin-zone day."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from app.routing.base import PlanningError, PlanOptions
from app.routing.cp_sat_scheduler import schedule_cp_sat_route
from app.routing.occupancy import HotelRoom
from app.routing.travel_timing import apply_timing
from app.routing.trip_modes import RhythmClockConflict
from tests.one_day_rhythm_tests import policy
from tests.reserved_meal_tests import endpoint, visit
from tests.routing.conftest import build_route
from tests.routing.unrestricted_rhythm_tests import quoted


@pytest.mark.asyncio
@pytest.mark.parametrize("day,cutoff", [("2030-03-09", 2), ("2030-11-02", 1)])
@pytest.mark.parametrize("reserved", [False, True])
async def test_estimated_and_actual_cross_zone_dst_cutoffs_have_same_typed_conflict(
    fake_services, day, cutoff, reserved
):
    initial = build_route(3600)
    origin = list(reversed(initial.geometry.coordinates[0]))
    services = fake_services.bundle()

    async def zones(point):
        return "America/Phoenix" if list(point) == origin else "America/Los_Angeles"

    services.timezone_at = zones
    services.cp_sat_hotels = AsyncMock(side_effect=AssertionError("unexpected hotel lookup"))
    schedule = policy((20, cutoff), (cutoff, 10))
    start = datetime.fromisoformat(day + "T21:00").replace(tzinfo=ZoneInfo("America/Phoenix"))
    options = PlanOptions(
        0,
        150,
        start,
        traveler_count=2,
        hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
        scheduling_policy=schedule,
        reserve_meal_slots=reserved,
    )
    for operation in (
        lambda: schedule_cp_sat_route(initial, [], options, services),
        lambda: apply_timing(
            [endpoint(3600)],
            start,
            schedule,
            "America/Phoenix",
            reserve_meal_slots=reserved,
        ),
    ):
        with pytest.raises(RhythmClockConflict) as caught:
            result = operation()
            if hasattr(result, "__await__"):
                await result
        assert caught.value.status_code == 422
    assert fake_services.find_hotel_calls == 0
    services.cp_sat_hotels.assert_not_awaited()


@pytest.mark.asyncio
async def test_scheduler_does_not_translate_unrelated_provider_value_error(fake_services):
    services = fake_services.bundle()

    async def zones(point):
        raise ValueError("synthetic provider failure")

    services.timezone_at = zones
    with pytest.raises(ValueError, match="synthetic provider failure"):
        await schedule_cp_sat_route(
            build_route(3600),
            [],
            PlanOptions(0, 150, datetime(2030, 6, 1, 9, tzinfo=UTC)),
            services,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("day,restart", [("2030-03-09", 2), ("2030-11-02", 1)])
@pytest.mark.parametrize("hours", [1, 5])
async def test_dst_restart_conflicts_only_when_an_overnight_is_actually_needed(
    fake_services, day, restart, hours
):
    initial = build_route(hours * 3600)
    origin = list(reversed(initial.geometry.coordinates[0]))
    services = fake_services.bundle()

    async def zones(point):
        return "America/Phoenix" if list(point) == origin else "America/Los_Angeles"

    services.timezone_at = zones
    services.cp_sat_hotels = AsyncMock(side_effect=AssertionError("unexpected hotel lookup"))
    start = datetime.fromisoformat(day + "T18:00").replace(tzinfo=ZoneInfo("America/Phoenix"))
    options = PlanOptions(
        0,
        150,
        start,
        traveler_count=2,
        hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
        scheduling_policy=policy((restart, 20), (20, restart)),
    )
    if hours == 1:
        # Tomorrow's missing/ambiguous restart is irrelevant to a trip that
        # finishes tonight, so no extra dates should be prevalidated.
        assert await schedule_cp_sat_route(initial, [], options, services) == ([], 0)
    else:
        with pytest.raises(RhythmClockConflict) as caught:
            await schedule_cp_sat_route(initial, [], options, services)
        assert caught.value.status_code == 422
    services.cp_sat_hotels.assert_not_awaited()


@pytest.mark.parametrize("reserved", [False, True])
def test_new_york09_to_los_angeles06_cannot_drive_across_sleep08_09(reserved):
    start = datetime(2030, 6, 1, 9, tzinfo=ZoneInfo("America/New_York"))
    with pytest.raises(PlanningError):
        apply_timing(
            [endpoint(4 * 3600)],
            start,
            policy((9, 8), (8, 9)),
            "America/New_York",
            reserve_meal_slots=reserved,
        )


@pytest.mark.parametrize("reserved", [False, True])
def test_short_westbound_leg_uses_yesterdays_local_cycle_and_todays_cutoff(reserved):
    start = datetime(2030, 6, 1, 9, tzinfo=ZoneInfo("America/New_York"))
    stops = [endpoint(3600)]
    apply_timing(
        stops, start, policy((9, 8), (8, 9)), "America/New_York", reserve_meal_slots=reserved
    )
    assert stops[0]["arrival_time"] == "2030-06-01T07:00:00-07:00"
    assert stops[0]["deadline"] == "2030-06-01T08:00:00-07:00"
    assert stops[0]["travel_day"] == "2030-05-31"


@pytest.mark.parametrize("seconds", [0, 1])
def test_zero_road_tail_at_completed_cutoff_is_valid_but_new_driving_is_not(seconds):
    start = datetime(2030, 6, 1, 6, tzinfo=ZoneInfo("America/Los_Angeles"))
    stops = [visit(0, 2 * 3600), endpoint(seconds)]
    if seconds:
        with pytest.raises(PlanningError):
            apply_timing(stops, start, policy((9, 8), (8, 9)), "America/Los_Angeles")
    else:
        apply_timing(stops, start, policy((9, 8), (8, 9)), "America/Los_Angeles")
        assert stops[-1]["arrival_time"] == "2030-06-01T08:00:00-07:00"
        assert stops[-1]["deadline"] == "2030-06-01T08:00:00-07:00"


@pytest.mark.parametrize(
    "origin,start_clock,target,seconds,expected,anchor,cutoff",
    [
        (
            "America/New_York",
            "2030-06-02T01:00",
            "America/Los_Angeles",
            7200,
            "2030-06-02T00:00:00-07:00",
            "2030-06-01",
            "2030-06-02T08:00:00-07:00",
        ),
        (
            "Pacific/Apia",
            "2030-06-01T20:00",
            "Pacific/Honolulu",
            7200,
            "2030-05-31T23:00:00-10:00",
            "2030-05-31",
            "2030-06-01T08:00:00-10:00",
        ),
        (
            "America/Los_Angeles",
            "2030-03-09T20:00",
            "America/Los_Angeles",
            9 * 3600,
            "2030-03-10T06:00:00-07:00",
            "2030-03-09",
            "2030-03-10T08:00:00-07:00",
        ),
        (
            "America/Los_Angeles",
            "2030-11-02T20:00",
            "America/Los_Angeles",
            9 * 3600,
            "2030-11-03T04:00:00-08:00",
            "2030-11-02",
            "2030-11-03T08:00:00-08:00",
        ),
    ],
)
def test_local_date_midnight_and_dst_use_target_cycle_without_backwards_elapsed(
    origin, start_clock, target, seconds, expected, anchor, cutoff
):
    start = datetime.fromisoformat(start_clock).replace(tzinfo=ZoneInfo(origin))
    stops = [endpoint(seconds, target)]
    apply_timing(stops, start, policy((20, 8), (9, 17)), origin)
    assert stops[0]["arrival_time"] == expected
    assert stops[0]["travel_day"] == anchor
    assert stops[0]["deadline"] == cutoff
    assert (
        datetime.fromisoformat(expected).astimezone(UTC) - start.astimezone(UTC)
    ).total_seconds() == seconds


@pytest.mark.asyncio
@pytest.mark.parametrize("reserved", [False, True])
@pytest.mark.parametrize("with_attraction", [False, True])
async def test_estimated_hotel_capacity_quote_dates_and_restart_use_actual_hotel_cycle(
    fake_services,
    reserved,
    with_attraction,
):
    initial = build_route((6 if with_attraction else 4) * 3600)
    origin = [initial.geometry.coordinates[0][1], initial.geometry.coordinates[0][0]]
    services = fake_services.bundle()

    async def timezone(point):
        # Synthetic resolver distinguishes the origin and subsequent positions;
        # no real geography or provider availability is asserted.
        return "America/New_York" if list(point) == origin else "America/Los_Angeles"

    services.timezone_at = timezone
    calls = []

    async def hotels(point, first, price_range, weights, rooms, *, check_out_date=None):
        calls.append((first, check_out_date))
        return [{**quoted(first, check_out_date, price=120), "coordinates": point}]

    services.cp_sat_hotels = hotels
    start = datetime(2030, 6, 1, 9, tzinfo=ZoneInfo("America/New_York"))
    stops, cost = await schedule_cp_sat_route(
        initial,
        (
            [
                (
                    4 * 3600,
                    {
                        "provider_id": "fixture:cycle-visit",
                        "name": "Synthetic cycle visit",
                        "coordinates": [40.0, -100.0],
                        "detour_seconds": 0.0,
                    },
                )
            ]
            if with_attraction
            else []
        ),
        PlanOptions(
            1 if with_attraction else 0,
            150,
            start,
            traveler_count=2,
            hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
            scheduling_policy=policy((9, 8), (8, 9)),
            reserve_meal_slots=reserved,
        ),
        services,
    )
    assert len(stops) == (2 if with_attraction else 1) and cost == 120
    predicted = datetime.fromisoformat(stops[0]["lodging"]["planned_arrival"])
    cutoff = datetime.fromisoformat("2030-06-01T08:00:00-07:00")
    # Existing meal-capacity bisection conservatively rounds below the cutoff.
    assert 0 <= (cutoff - predicted).total_seconds() < 0.001
    assert stops[0]["lodging"]["planned_departure"] == "2030-06-01T09:00:00-07:00"
    assert stops[0]["check_in_date"] == "2030-05-31"
    assert stops[0]["check_out_date"] == "2030-06-01"
    assert len(calls) == 1
    for stop in stops:
        stop["duration"] = 2 * 3600
    stops.append(endpoint(2 * 3600))
    apply_timing(
        stops, start, policy((9, 8), (8, 9)), "America/New_York", reserve_meal_slots=reserved
    )
    assert stops[0]["arrival_time"] == "2030-06-01T08:00:00-07:00"
    assert stops[0]["departure_time"] == "2030-06-01T09:00:00-07:00"
    end = datetime.fromisoformat(stops[-1]["arrival_time"])
    assert end < datetime.fromisoformat(stops[-1]["deadline"])
    assert end.date().isoformat() == "2030-06-01"


@pytest.mark.asyncio
async def test_actual_candidate_hotel_zone_must_not_start_positive_drive_during_sleep(
    fake_services,
):
    initial = build_route(30 * 3600)
    services = fake_services.bundle()
    hotel_point = [40.0, -100.0]

    async def timezone(point):
        return "America/Chicago" if list(point) == hotel_point else "America/New_York"

    services.timezone_at = timezone

    async def hotels(point, first, price_range, weights, rooms, *, check_out_date=None):
        return [{**quoted(first, check_out_date, price=120), "coordinates": hotel_point}]

    services.cp_sat_hotels = hotels
    start = datetime(2030, 6, 1, 9, tzinfo=ZoneInfo("America/New_York"))
    with pytest.raises(PlanningError):
        await schedule_cp_sat_route(
            initial,
            [],
            PlanOptions(
                0,
                150,
                start,
                traveler_count=2,
                hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
                scheduling_policy=policy((9, 8), (8, 9)),
            ),
            services,
        )
