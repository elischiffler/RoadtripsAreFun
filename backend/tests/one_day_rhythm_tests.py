"""Full candidate clocks and explicit recurring availability; no providers or DB."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from app.models.daily_schedule import DailySchedule
from app.models.itinerary_models import Itinerary_Payload
from app.models.routing_models.routing_models import Route
from app.models.scheduling_policy import SchedulingPolicy
from app.routers.itinerary_api import build_itinerary
from app.routing.base import PlanningError, PlanOptions
from app.routing.cp_sat_scheduler import schedule_cp_sat_route
from app.routing.daily_rhythm import rest_blocks
from app.routing.travel_timing import apply_timing
from app.routing.trip_modes import (
    OneDayIneligible,
    UnsupportedOvernightRhythm,
    require_one_day,
    require_overnight_rhythm,
)
from tests.reserved_meal_tests import ZONE, endpoint, moment, visit


def rhythm(drive=(9, 20), sleep=(22, 7)):
    slots = ["rest"] * 24
    for label, (start, end) in [("drive", drive), ("sleep", sleep)]:
        for offset in range((end - start) % 24):
            slots[(start + offset) % 24] = label
    return DailySchedule(slots=slots)


def policy(drive=(9, 20), sleep=(22, 7)):
    return SchedulingPolicy(daily_schedule=rhythm(drive, sleep))


def route(stops, start=None, selected_policy=None):
    return Route(
        coordinates=[[40, -105], [39, -104]],
        distance=100,
        duration=sum(s.get("duration", 0) for s in stops),
        steps=[],
        stops=stops,
        geometry={"coordinates": [[-105, 40], [-104, 39]]},
        cost=0,
        start_timezone=ZONE,
        departure_time=start or moment("09:00"),
        scheduling_policy=selected_policy or SchedulingPolicy(late_driving=True),
        reserve_meal_slots=True,
        trip_mode="one_day",
    )


def test_under12_requires_complete_aware_actual_elapsed_including_visits_waits_and_meals():
    stops = [visit(3600, 3600, opens="13:00", closes="17:00"), endpoint(3600)]
    planned = route(stops)
    apply_timing(
        planned.stops,
        planned.departure_time,
        planned.scheduling_policy,
        ZONE,
        reserve_meal_slots=True,
    )
    assert planned.stops[0]["wait_seconds"] > 0
    assert any(s["meal_breaks"] for s in planned.stops)
    elapsed = require_one_day(planned)
    assert elapsed == 6 * 3600
    assert elapsed > planned.duration + 3600
    assert planned.one_day_proof.elapsed_seconds == elapsed


@pytest.mark.parametrize("seconds,allowed", [(43199, True), (43200, False), (43201, False)])
def test_strict_threshold_uses_utc_elapsed_not_driving_duration(seconds, allowed):
    planned = route([endpoint(1)])
    planned.stops[0]["departure_time"] = (
        planned.departure_time.astimezone(UTC) + __import__("datetime").timedelta(seconds=seconds)
    ).isoformat()
    if allowed:
        assert require_one_day(planned) == seconds
    else:
        with pytest.raises(OneDayIneligible):
            require_one_day(planned)


def test_one_day_rejects_hotel_and_missing_timing_or_naive_instants():
    for stops, start in [
        ([{"type": "hotel"}], moment("09:00")),
        ([endpoint(1)], moment("09:00")),
        ([{**endpoint(1), "departure_time": "2035-01-01T10:00:00"}], datetime(2035, 1, 1, 9)),
    ]:
        with pytest.raises(OneDayIneligible):
            require_one_day(route(stops, start))


def test_night_driving_anchors_early_hours_to_previous_travel_day():
    night = policy((20, 8), (9, 17))
    stops = [endpoint(8 * 3600)]
    start = moment("20:00", "2027-06-01")
    apply_timing(stops, start, night, ZONE, reserve_meal_slots=True)
    assert stops[-1]["arrival_time"] == "2027-06-02T04:00:00-07:00"
    assert stops[-1]["deadline"] == "2027-06-02T08:00:00-07:00"
    assert require_one_day(route(stops, start, night)) == 8 * 3600
    assert night.travel_day_for(moment("02:00", "2027-06-02")).isoformat() == "2027-06-01"
    with pytest.raises(ValueError, match="outside"):
        night.travel_day_for(moment("12:00", "2027-06-02"))


@pytest.mark.parametrize(
    "date,seconds,arrival",
    [
        ("2027-03-13", 10 * 3600, "2027-03-14T07:00:00-07:00"),
        ("2027-11-06", 10 * 3600, "2027-11-07T05:00:00-08:00"),
    ],
)
def test_night_clock_dst_is_elapsed_utc_not_wall_clock(date, seconds, arrival):
    night = policy((20, 8), (9, 17))
    stops = [endpoint(seconds)]
    start = moment("20:00", date)
    apply_timing(stops, start, night, ZONE, reserve_meal_slots=True)
    assert stops[-1]["arrival_time"] == arrival
    assert require_one_day(route(stops, start, night)) == seconds


def test_night_route_cannot_cross_reserved_sleep_or_rest_cutoff():
    with pytest.raises(PlanningError):
        apply_timing(
            [endpoint(13 * 3600)],
            moment("20:00"),
            policy((20, 8), (9, 17)),
            ZONE,
            reserve_meal_slots=True,
        )


def test_overlapping_or_multiple_blocks_and_conflicting_legacy_overrides_reject():
    for slots in [["drive"] * 24, ["sleep"] * 24, rhythm().slots[:23], ["drive", "sleep"] * 12]:
        with pytest.raises(ValidationError):
            DailySchedule(slots=slots)
    with pytest.raises(ValidationError, match="not both"):
        SchedulingPolicy(daily_schedule=rhythm(), morning_restart="10:00")
    assert SchedulingPolicy().model_dump()["daily_schedule"] is None
    assert SchedulingPolicy(late_driving=True).arrival_cutoff(final=True) == "24:00"


def test_overnight_rhythm_requires_representable_evening_arrival_and_nightly_sleep():
    require_overnight_rhythm(policy())
    require_overnight_rhythm(policy((9, 0), (0, 7)))
    for custom in [policy((20, 8), (9, 17)), policy((9, 14), (22, 7))]:
        with pytest.raises(UnsupportedOvernightRhythm):
            require_overnight_rhythm(custom)


def test_hotel_idle_accounts_rest_sleep_and_dst_booking_dates():
    selected = policy()
    stops = [
        {
            "name": "Nightly quote",
            "type": "hotel",
            "duration": 3600,
            "timezone": ZONE,
            "check_in_date": "2027-03-13",
        },
        endpoint(3600),
    ]
    apply_timing(stops, moment("18:00", "2027-03-13"), selected, ZONE, reserve_meal_slots=True)
    hotel = stops[0]
    assert hotel["check_in_date"] == "2027-03-13"
    assert hotel["departure_time"] == "2027-03-14T09:00:00-07:00"
    blocks = hotel["daily_rhythm_blocks"]
    assert [b["kind"] for b in blocks] == ["rest", "sleep", "rest"]
    assert sum(b["duration_seconds"] for b in blocks) == 13 * 3600
    assert "confirm hotel" in hotel["check_in_timing_notice"]


@pytest.mark.asyncio
async def test_one_day_scheduler_needs_neither_occupancy_nor_hotel_service():
    from types import SimpleNamespace

    from app.models.routing_models.routing_models import MapBox
    from tests.routing_api.guided_flow_tests import _payload

    initial = MapBox.MapBox_Route.model_validate(_payload()["initial_route"])
    hotel = AsyncMock(side_effect=AssertionError("hotel service must not run"))
    options = PlanOptions(num_stops=0, budget=0, start=moment("20:00"), trip_mode="one_day")
    assert await schedule_cp_sat_route(
        initial, [], options, SimpleNamespace(cp_sat_hotels=None)
    ) == ([], 0)
    hotel.assert_not_called()


@pytest.mark.asyncio
async def test_one_day_rebuild_recomputes_proof_and_rejects_extended_route(monkeypatch):
    from app.routers import itinerary_api

    monkeypatch.setattr(itinerary_api, "refresh_for_timing", AsyncMock())
    planned = route([endpoint(8 * 3600)], moment("09:00"))
    planned.one_day_proof = None
    days = await build_itinerary(Itinerary_Payload(route=planned))
    assert days and planned.one_day_proof.elapsed_seconds > planned.duration
    forged = planned.model_copy(deep=True)
    forged.stops[-1]["duration"] = 11 * 3600
    with pytest.raises(PlanningError):
        await build_itinerary(Itinerary_Payload(route=forged))
    assert planned.stops[-1]["duration"] == 8 * 3600


def test_unrelated_dst_boundary_outside_actual_stay_cannot_reject_rest_blocks():
    custom = rhythm((9, 20), (22, 1))
    blocks = rest_blocks(moment("20:00", "2027-11-08"), moment("09:00", "2027-11-09"), custom)
    assert [block["kind"] for block in blocks] == ["rest", "sleep", "rest"]
    assert sum(block["duration_seconds"] for block in blocks) == 13 * 3600
    with pytest.raises(PlanningError, match="ambiguous"):
        rest_blocks(moment("20:00", "2027-11-06"), moment("09:00", "2027-11-07"), custom)


def test_actual_nonexistent_dst_sleep_boundary_requires_a_different_hour():
    with pytest.raises(PlanningError, match="ambiguous or missing"):
        rest_blocks(
            moment("20:00", "2027-03-13"), moment("09:00", "2027-03-14"), rhythm((9, 20), (22, 2))
        )


@pytest.mark.asyncio
async def test_saved_one_day_edit_refreshes_proof_and_rejects_actual_elapsed_over12():
    from tests.routing_api.route_edit_tests import request, run, saved_route

    saved = saved_route()
    saved["trip_mode"] = "one_day"
    saved["departure_time"] = "2030-06-01T06:00:00+00:00"
    saved["scheduling_policy"] = {"late_driving": True}
    result, _ = await run(request(route=saved), duration=1800)
    assert result.route.trip_mode == "one_day"
    assert result.route.reserve_meal_slots is True
    assert result.route.one_day_proof.elapsed_seconds < 43200
    with pytest.raises(OneDayIneligible):
        await run(request(route=saved), duration=3 * 3600)


@pytest.mark.asyncio
async def test_one_day_rebuild_cannot_accept_hotel_or_caller_forged_proof(monkeypatch):
    from app.routers import itinerary_api

    monkeypatch.setattr(itinerary_api, "refresh_for_timing", AsyncMock())
    planned = route(
        [{"name": "Hotel", "type": "hotel", "duration": 0, "timezone": ZONE}, endpoint(0)]
    )
    with pytest.raises(OneDayIneligible, match="hotel"):
        await build_itinerary(Itinerary_Payload(route=planned))
    planned = route([endpoint(11 * 3600)], moment("06:00"))
    from app.models.trip_mode import OneDayProof

    planned.one_day_proof = OneDayProof(elapsed_seconds=1, validated_at=datetime.now(UTC))
    with pytest.raises(OneDayIneligible):
        await build_itinerary(Itinerary_Payload(route=planned))


@pytest.mark.asyncio
async def test_explicit_itinerary_start_override_is_used_for_recomputed_elapsed(monkeypatch):
    from app.routers import itinerary_api

    monkeypatch.setattr(itinerary_api, "refresh_for_timing", AsyncMock())
    planned = route([endpoint(3600)], moment("06:00"))
    new_start = moment("10:00")
    await build_itinerary(Itinerary_Payload(route=planned, start_time=new_start))
    assert planned.departure_time == new_start
    assert planned.one_day_proof.elapsed_seconds == 3600


def test_westbound_zone_change_cannot_drive_during_next_stops_rest_window():
    from app.routing.trip_modes import RhythmAvailabilityConflict

    start = datetime(2027, 6, 1, 9, tzinfo=ZoneInfo("America/Denver"))
    with pytest.raises(RhythmAvailabilityConflict):
        apply_timing(
            [endpoint(600, "America/Los_Angeles")],
            start,
            policy(),
            "America/Denver",
            reserve_meal_slots=True,
        )
    # A later departure is available in both endpoint planning clocks.
    allowed = [endpoint(600, "America/Los_Angeles")]
    apply_timing(
        allowed, start.replace(hour=10), policy(), "America/Denver", reserve_meal_slots=True
    )
    assert allowed[-1]["arrival_time"] == "2027-06-01T09:10:00-07:00"
    # No-rhythm saved routes retain their original local-cutoff behavior.
    legacy = [endpoint(600, "America/Los_Angeles")]
    apply_timing(legacy, start, SchedulingPolicy(), "America/Denver")
    assert legacy[-1]["arrival_time"] == "2027-06-01T08:10:00-07:00"


def test_spring_forward_night_proof_can_fit_12_wall_hours_but11_actual_hours_with_breakfast():
    selected = policy((20, 8), (9, 17))
    start = moment("20:00", "2027-03-13")
    stops = [endpoint(int(10.5 * 3600))]
    apply_timing(stops, start, selected, ZONE, reserve_meal_slots=True)
    assert stops[-1]["arrival_time"] == "2027-03-14T08:00:00-07:00"
    assert stops[-1]["meal_breaks"][0]["meal_type"] == "breakfast"
    assert require_one_day(route(stops, start, selected)) == 11 * 3600
