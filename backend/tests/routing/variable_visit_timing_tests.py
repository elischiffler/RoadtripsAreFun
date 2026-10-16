"""Synthetic source-window controls, not live opening or travel-time claims."""

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.models.itinerary_models import Itinerary_Payload
from app.models.routing_models.routing_models import Route
from app.models.scheduling_policy import SchedulingPolicy, advance, seconds_until
from app.routers.itinerary_api import build_itinerary
from app.routing.base import PlanningError, PlanOptions
from app.routing.cp_sat_scheduler import schedule_cp_sat_route
from app.routing.discovery import SelectedAttraction, make_discovery_plan
from app.routing.occupancy import HotelRoom
from app.routing.sources.persona_candidates import attraction_candidates
from app.routing.sources.visit_durations import DurationCache
from app.routing.travel_timing import apply_timing
from app.routing.trip_calendar import TripCalendar, possible_visit
from app.routing.visit_calendar import VisitCalendarConflict, solve_visit
from app.routing.visit_duration import VisitDuration, fallback_duration

ZONE = ZoneInfo("America/Los_Angeles")


def place(*, opens="10:00", closes="12:00", end_day_offset=0, **rules):
    return {
        "provider_id": "synthetic:variable-window",
        "name": "Synthetic duration window",
        "categories": ["culture"],
        "timezone": ZONE.key,
        "source_provenance": [
            {
                "source_visit_calendar": {
                    "schema_version": "roadtrips-source-visit-calendar/1",
                    "weekly_windows": [
                        {
                            "weekdays": list(range(7)),
                            "opens": opens,
                            "closes": closes,
                            "end_day_offset": end_day_offset,
                        }
                    ],
                    "source_receipts": [{"source_url": "https://operator.example/synthetic"}],
                    **rules,
                }
            }
        ],
    }


def instant(value):
    return datetime.fromisoformat(value).replace(tzinfo=ZONE)


def duration(seconds):
    return VisitDuration(seconds=seconds, source="ai_estimate", reason="estimated").model_dump()


def baseline(seconds=3600):
    return SimpleNamespace(
        duration=seconds,
        distance=1000.0,
        legs=[],
        geometry=SimpleNamespace(coordinates=[[-118, 34], [-117.98, 34]]),
    )


def candidate(seconds, **rules):
    return {
        **place(**rules),
        "coordinates": [34, -117.99],
        "utility": 0.8,
        "detour_seconds": 0,
        "route_progress_seconds": 1800,
        "visit_duration": duration(seconds),
    }


def test_cp_sat_uses_full_variable_dwell_in_a_verified_window():
    record = place()
    earliest = instant("2030-07-01T09:30")
    deadline = earliest.replace(hour=20)
    start, availability = solve_visit(record, earliest, deadline, dwell=5400)
    assert start.hour == 10 and start.minute == 0
    assert availability["visit_end"] == "2030-07-01T11:30:00-07:00"
    assert availability["dwell_seconds"] == 5400 and availability["wait_seconds"] == 1800
    with pytest.raises(VisitCalendarConflict, match="full visit"):
        solve_visit(record, earliest, deadline, dwell=7500)


def test_variable_dwell_cannot_bypass_an_explicit_calendar_hold_or_fixed_start():
    earliest = instant("2030-07-01T10:00")
    deadline = earliest.replace(hour=20)
    for record in [
        place(unknown_reasons=["explicit operator hold"]),
        place(date_overrides=[{"date": "2030-07-01", "windows": []}]),
        place(fixed_starts=["2030-07-01T11:30:00-07:00"]),
    ]:
        with pytest.raises(VisitCalendarConflict):
            solve_visit(record, earliest, deadline, dwell=3600)


@pytest.mark.asyncio
async def test_estimates_preserve_the_deliberate_unknown_outdoor_policy():
    start = instant("2030-07-01T09:00")
    legacy = {"provider_id": "synthetic:legacy-outdoor", "coordinates": [34, -118]}
    assert solve_visit(legacy, start, start.replace(hour=20))[1]["status"] == "unknown"
    new = {**legacy, "visit_duration": duration(3600)}
    arrival, availability = solve_visit(new, start, start.replace(hour=20))
    assert arrival == start and availability == {
        "status": "unknown",
        "ticket_availability": "unknown",
    }
    assert possible_visit(new, start, ZONE)
    assert await TripCalendar(start, None).eligible(new)


def test_midnight_window_fits_entire_visit_and_next_day_closure_is_binding():
    earliest = instant("2030-07-01T23:00")
    deadline = instant("2030-07-02T02:00")
    record = place(opens="23:00", closes="01:00", end_day_offset=1)
    start, availability = solve_visit(record, earliest, deadline, dwell=5400)
    assert availability["visit_end"] == "2030-07-02T00:30:00-07:00"
    assert seconds_until(start, advance(start, 5400)) == 5400
    record["source_provenance"][0]["source_visit_calendar"]["date_overrides"] = [
        {"date": "2030-07-02", "windows": []}
    ]
    with pytest.raises(VisitCalendarConflict):
        solve_visit(record, earliest, deadline, dwell=5400)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "seconds,expected_end", [(3600, "11:00"), (7200, "12:00"), (9000, "12:30")]
)
async def test_initial_scheduler_final_road_timing_and_reloaded_itinerary_agree(
    fake_services, seconds, expected_end
):
    record = candidate(seconds, closes="12:30")
    start = instant("2030-07-01T09:00")
    services = fake_services.bundle()

    async def timezone(_point):
        return ZONE.key

    async def hotels(*_args):
        pytest.fail("This controlled short trip needs no hotel")

    services.timezone_at = timezone
    services.cp_sat_hotels = hotels
    policy = SchedulingPolicy()
    options = PlanOptions(
        1,
        100,
        start,
        traveler_count=1,
        hotel_rooms=[HotelRoom(adults=1, child_ages=[])],
        scheduling_policy=policy,
    )
    stops, _ = await schedule_cp_sat_route(
        baseline(), [SelectedAttraction(1800, record)], options, services
    )
    assert stops[0]["visit_duration"] == record["visit_duration"]
    assert stops[0]["availability"]["visit_end"][11:16] == expected_end
    stops[0]["duration"] = 1800  # Explicit actual-road fixture, not real travel evidence.
    stops.append(
        {
            "name": "Arrive at your destination",
            "type": "end",
            "duration": 1800,
            "timezone": ZONE.key,
        }
    )
    apply_timing(stops, start, policy, ZONE.key)
    assert stops[0]["departure_time"][11:16] == expected_end
    assert (
        seconds_until(
            datetime.fromisoformat(stops[0]["arrival_time"]),
            datetime.fromisoformat(stops[0]["departure_time"]),
        )
        == seconds
    )
    route = Route(
        coordinates=[],
        distance=1000,
        duration=3600,
        steps=[],
        stops=stops,
        geometry={"coordinates": []},
        cost=0,
        scheduling_policy=policy,
        departure_time=start,
        start_timezone=ZONE.key,
    )
    reloaded = Route.model_validate_json(route.model_dump_json())
    days = await build_itinerary(Itinerary_Payload(route=reloaded))
    displayed = next(s for day in days for s in day.stops if s.provider_id == record["provider_id"])
    assert displayed.arrival_time == stops[0]["arrival_time"]
    assert displayed.departure_time == stops[0]["departure_time"]
    assert displayed.visit_duration == record["visit_duration"]
    assert any(s.paired_departure for day in days for s in day.stops)


def test_final_actual_road_legs_recheck_full_dwell_and_driving_budget():
    start = instant("2030-07-01T09:00")
    short = candidate(3600, closes="20:00") | {"type": "stop", "duration": 9 * 3600}
    apply_timing([short], start, SchedulingPolicy(), ZONE.key)
    assert short["departure_time"][11:16] == "19:00"
    long = candidate(10800, closes="23:00") | {"type": "stop", "duration": 9 * 3600}
    with pytest.raises(PlanningError):
        apply_timing([long], start, SchedulingPolicy(), ZONE.key)
    closing = candidate(5400, closes="12:00") | {"type": "stop", "duration": 2 * 3600}
    with pytest.raises(VisitCalendarConflict, match="full visit"):
        apply_timing([closing], start, SchedulingPolicy(), ZONE.key)
    closing["visit_duration"] = fallback_duration("provider_failure").model_dump()
    with pytest.raises(VisitCalendarConflict):
        apply_timing([closing], start, SchedulingPolicy(), ZONE.key)


@pytest.mark.asyncio
async def test_remaining_variable_dwell_changes_overnight_placement(fake_services):
    start = instant("2030-07-01T09:00")
    services = fake_services.bundle()

    async def timezone(_point):
        return ZONE.key

    async def hotels(point, day, _band, _weights, rooms):
        return [
            {
                "provider_id": "synthetic:hotel",
                "name": "Synthetic hotel quote",
                "coordinates": point,
                "price": 80,
                "utility": 0.8,
                "hotel_rooms": [room.model_dump() for room in rooms],
                "room_offers": [],
                "price_scope": "one_room_one_night_including_taxes_fees",
                "check_in_date": day.isoformat(),
            }
        ]

    services.timezone_at = timezone
    services.cp_sat_hotels = hotels
    options = PlanOptions(
        1, 100, start, traveler_count=1, hotel_rooms=[HotelRoom(adults=1, child_ages=[])]
    )

    async def run(seconds):
        record = candidate(seconds, opens="08:00", closes="23:00")
        record["route_progress_seconds"] = 9 * 3600
        return await schedule_cp_sat_route(
            baseline(10 * 3600), [SelectedAttraction(9 * 3600, record)], options, services
        )

    short, short_cost = await run(3600)
    long, long_cost = await run(10800)
    assert [stop["type"] for stop in short] == ["stop"] and short_cost == 0
    assert [stop["type"] for stop in long] == ["hotel", "stop"] and long_cost == 80
    assert long[1]["availability"]["visit_start"].startswith("2030-07-02T09:00")


def test_trip_discovery_and_cp_sat_use_the_same_duration_and_midnight_rollover():
    start = instant("2030-07-01T09:00")
    record = candidate(3600, closes="11:00")
    assert possible_visit(record, start, ZONE)
    record["visit_duration"] = duration(7200)
    assert not possible_visit(record, start, ZONE)
    night = candidate(3600, opens="23:00", closes="01:00", end_day_offset=1) | {
        "type": "stop",
        "duration": 1800,
    }
    late_start = instant("2030-07-01T22:30")
    apply_timing([night], late_start, SchedulingPolicy(late_driving=True), ZONE.key)
    assert night["departure_time"] == "2030-07-02T00:00:00-07:00"
    night["visit_duration"] = duration(3900)
    with pytest.raises(PlanningError):
        apply_timing([night], late_start, SchedulingPolicy(late_driving=True), ZONE.key)


@pytest.mark.asyncio
async def test_live_discovery_seam_estimates_after_match_and_admits_short_verified_window(
    monkeypatch,
):
    import json

    from app.agent.persona import ATTRIBUTE_KEYS, default_weights
    from app.agent.schemas import LLMResponse
    from app.routing.sources import visit_durations

    monkeypatch.setattr(visit_durations, "_CACHE", DurationCache())
    record = candidate(3600, closes="11:00")
    record.pop("visit_duration")
    record["categories"] = ["daytime", "culture"]
    record["activities"] = ["Synthetic exhibit activity"]
    record["description"] = "Synthetic place details for the duration prompt"
    prompts = []

    class Places:
        async def attractions_near(self, _point):
            return [record]

    class AI:
        def complete(self, messages, _tools):
            prompt = messages[-1].content
            prompts.append(prompt)
            if "Estimate a realistic visit length" in prompt:
                assert '"score":' in prompt and "traveler_preferences" in prompt
                assert "Synthetic exhibit activity" in prompt and record["description"] in prompt
                return LLMResponse(
                    content=json.dumps(
                        {"estimates": [{"provider_id": record["provider_id"], "minutes": 60}]}
                    )
                )
            return LLMResponse(
                content=json.dumps(
                    {
                        "candidates": [
                            {
                                "name": record["name"],
                                "attribute_ratings": dict.fromkeys(ATTRIBUTE_KEYS, 0.8),
                            }
                        ]
                    }
                )
            )

    async def timezone(_point):
        return ZONE.key

    plan = make_discovery_plan(baseline(), 1)
    plan.trip_calendar = TripCalendar(instant("2030-07-01T09:00"), timezone)
    result = await attraction_candidates(
        baseline(), plan, default_weights(), ai=AI(), places=Places()
    )
    assert len(result.candidates) == 1
    assert result.candidates[0]["visit_duration"]["seconds"] == 3600
    assert len(prompts) == 2
