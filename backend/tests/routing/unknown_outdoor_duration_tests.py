"""Mock-only policy regression: an estimate does not establish opening hours."""

import copy
import json
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.agent.persona import ATTRIBUTE_KEYS, default_weights
from app.agent.schemas import LLMResponse
from app.models.itinerary_models import Itinerary_Payload
from app.models.routing_models.routing_models import Route
from app.models.scheduling_policy import SchedulingPolicy, seconds_until
from app.routers.itinerary_api import build_itinerary
from app.routing.base import PlanningError, PlanOptions
from app.routing.occupancy import HotelRoom
from app.routing.planners.cp_sat import CPSatPlanner
from app.routing.sources import persona_candidates as source
from app.routing.sources import visit_durations
from app.routing.sources.visit_durations import DurationCache
from app.routing.travel_timing import apply_timing
from app.routing.trip_calendar import TripCalendar, possible_visit
from app.routing.visit_calendar import VisitCalendarConflict, solve_visit
from app.routing.visit_duration import VisitDuration

ZONE = ZoneInfo("America/Los_Angeles")
START = datetime(2030, 7, 1, 9, tzinfo=ZONE)


def outdoor():
    return {
        "provider_id": "synthetic:unknown-outdoor",
        "name": "Synthetic outdoor control",
        "coordinates": [34, -117.99],
        "categories": ["daytime", "nature"],
        "source": "synthetic-unit-control",
        "source_release": "unit-only",
        "source_provenance": [],
    }


def duration(seconds):
    return VisitDuration(seconds=seconds, source="ai_estimate", reason="estimated").model_dump()


@pytest.fixture(autouse=True)
def forbid_default_ai(monkeypatch):
    def forbidden():
        raise AssertionError("Only the injected mock AI may be used")

    monkeypatch.setattr(source, "build_default_chain", forbidden)
    monkeypatch.setattr(visit_durations, "_CACHE", DurationCache())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "minutes,seconds,label",
    [(60, 3600, "ai_estimate"), (180, 10800, "ai_estimate"), (None, 7200, "conservative_fallback")],
)
async def test_unknown_outdoor_survives_discovery_solver_scheduling_and_itinerary(
    fake_services, minutes, seconds, label
):
    place = outdoor()
    original = copy.deepcopy(place)

    class Places:
        async def attractions_near(self, _point):
            return [copy.deepcopy(place)]

    class AI:
        duration_calls = 0

        def complete(self, messages, _tools):
            prompt = messages[-1].content
            if "Estimate a realistic visit length" in prompt:
                self.duration_calls += 1
                return LLMResponse(
                    content="invalid"
                    if minutes is None
                    else json.dumps(
                        {"estimates": [{"provider_id": place["provider_id"], "minutes": minutes}]}
                    )
                )
            marker = "Rate only these source-record names, preserving each exactly: "
            names = json.loads(prompt.split(marker, 1)[1])
            return LLMResponse(
                content=json.dumps(
                    {
                        "candidates": [
                            {"name": name, "attribute_ratings": dict.fromkeys(ATTRIBUTE_KEYS, 0.8)}
                            for name in names
                        ]
                    }
                )
            )

    baseline = SimpleNamespace(
        duration=3600.0,
        distance=1000.0,
        legs=[],
        geometry=SimpleNamespace(coordinates=[[-118, 34], [-117.98, 34]]),
    )
    ai, discoveries = AI(), []

    async def candidates(route, plan, weights):
        result = await source.attraction_candidates(route, plan, weights, ai=ai, places=Places())
        discoveries.append(result)
        return result

    async def roads(*_args):
        return SimpleNamespace(duration=3600.0, legs=[SimpleNamespace(duration=1800)] * 2)

    async def zone(_point):
        return ZONE.key

    async def hotels(*_args):
        pytest.fail("The controlled short trip requires no hotel")

    services = fake_services.bundle()
    services.cp_sat_candidates = candidates
    services.candidate_route = roads
    services.timezone_at = zone
    services.cp_sat_hotels = hotels
    result = await CPSatPlanner().plan(
        baseline,
        PlanOptions(
            1,
            100,
            START,
            weights=default_weights(),
            traveler_count=1,
            hotel_rooms=[HotelRoom(adults=1, child_ages=[])],
        ),
        services,
    )
    assert [item["provider_id"] for item in discoveries[0].candidates] == [place["provider_id"]]
    assert len(result.stopping_points) == 1 and ai.duration_calls == 1
    stop = result.stopping_points[0]
    assert (
        stop["visit_duration"]["seconds"] == seconds and stop["visit_duration"]["source"] == label
    )
    stop["duration"] = 1800  # Synthetic actual-road timing, not real routing evidence.
    stops = [stop, {"name": "Destination", "type": "end", "duration": 1800, "timezone": ZONE.key}]
    apply_timing(stops, START, SchedulingPolicy(), ZONE.key)
    assert stop["availability"] == {"status": "unknown", "ticket_availability": "unknown"}
    assert (
        seconds_until(
            datetime.fromisoformat(stop["arrival_time"]),
            datetime.fromisoformat(stop["departure_time"]),
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
        scheduling_policy=SchedulingPolicy(),
        departure_time=START,
        start_timezone=ZONE.key,
    )
    days = await build_itinerary(Itinerary_Payload(route=route))
    displayed = next(
        item for day in days for item in day.stops if item.provider_id == place["provider_id"]
    )
    assert displayed.availability == {"status": "unknown", "ticket_availability": "unknown"}
    assert (
        displayed.arrival_time == stop["arrival_time"]
        and displayed.departure_time == stop["departure_time"]
    )
    assert place == original


@pytest.mark.asyncio
async def test_unknown_outdoor_still_enforces_duration_bounds_and_daily_budget():
    place = outdoor() | {
        "type": "stop",
        "duration": 9 * 3600,
        "timezone": ZONE.key,
        "visit_duration": duration(3600),
    }
    assert possible_visit(place, START, ZONE)
    assert await TripCalendar(START, None).eligible(place)
    apply_timing([place], START, SchedulingPolicy(), ZONE.key)
    assert place["departure_time"][11:16] == "19:00"
    place["visit_duration"] = duration(10800)
    with pytest.raises(PlanningError, match="daily driving window"):
        apply_timing([place], START, SchedulingPolicy(), ZONE.key)
    place["visit_duration"]["seconds"] = 899
    with pytest.raises(PlanningError, match="Invalid visit duration"):
        await TripCalendar(START, None).eligible(place)


@pytest.mark.asyncio
async def test_timed_venue_without_hours_remains_ineligible_with_an_estimate():
    timed = outdoor() | {"categories": ["culture"], "visit_duration": duration(900)}
    assert not possible_visit(timed, START, ZONE)
    assert not await TripCalendar(START, None).eligible(timed)
    with pytest.raises(VisitCalendarConflict):
        solve_visit(timed, START, START.replace(hour=20))
