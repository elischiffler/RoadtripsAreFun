"""Synthetic seven-identity regressions; no live NPS or parking assertions."""

import copy
from types import SimpleNamespace

import pytest

from app.catalog import repository
from app.models.itinerary_models import Itinerary_Payload
from app.routers.itinerary_api import build_itinerary
from app.routing.sources.visit_durations import DurationCache, estimate_durations
from app.routing.trip_calendar import TripCalendar
from app.routing.visit_calendar import VisitCalendarConflict, solve_visit
from app.routing.visit_duration import VisitDuration, fallback_duration
from tests.routing.catalog_calendar_refresh_tests import IDS, START, authoritative, payload, record


@pytest.mark.asyncio
@pytest.mark.parametrize("identifier", IDS)
@pytest.mark.parametrize(
    "seconds,source",
    [(900, "ai_estimate"), (21600, "ai_estimate"), (7200, "conservative_fallback")],
)
async def test_all_seven_current_holds_override_variable_and_fallback_saved_dwell(
    monkeypatch, identifier, seconds, source
):
    held = record(identifier)
    monkeypatch.setattr(
        repository, "current_records", lambda ids: {identifier: authoritative(held)}
    )
    stale = payload(record(identifier, held=False), policy=False, provenance=False)
    stale.route.stops[0]["visit_duration"] = (
        fallback_duration("provider_failure").model_dump()
        if source == "conservative_fallback"
        else VisitDuration(seconds=seconds, source="ai_estimate", reason="estimated").model_dump()
    )
    saved = stale.model_dump(mode="json")
    before = copy.deepcopy(saved)
    data = Itinerary_Payload.model_validate(copy.deepcopy(saved))
    with pytest.raises(VisitCalendarConflict, match="current catalog access is unresolved"):
        await build_itinerary(data)
    assert saved == before
    assert data.route.stops[0]["visit_duration"]["seconds"] == seconds


@pytest.mark.asyncio
@pytest.mark.parametrize("identifier", IDS)
async def test_cached_short_estimate_never_bypasses_a_new_hold(identifier):
    import json

    class AI:
        calls = 0

        def complete(self, _messages, _tools):
            self.calls += 1
            return SimpleNamespace(
                content=json.dumps({"estimates": [{"provider_id": identifier, "minutes": 15}]})
            )

    ai, cache = AI(), DurationCache()
    before = record(identifier, held=False)
    first = await estimate_durations([before], {}, ai, cache=cache)
    held = record(identifier)
    second = await estimate_durations([held], {}, ai, cache=cache)
    assert ai.calls == 1 and first[0]["visit_duration"] == second[0]["visit_duration"]
    assert second[0]["visit_duration"]["seconds"] == 900

    async def zone(_point):
        return "America/Phoenix"

    assert not await TripCalendar(START, zone).eligible(second[0])
    with pytest.raises(VisitCalendarConflict):
        solve_visit(second[0], START, START.replace(hour=17))


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["inline", "saved", "handle"])
async def test_agent_hold_failure_preserves_saved_trip_and_duration_metadata(monkeypatch, mode):
    from app.agent.schemas import ToolCall
    from app.agent.tool_dispatcher import AppToolDispatcher
    from app.agent.tools import ToolContext
    from app.agent.trip_profile import TripProfile
    from app.routing.occupancy import HotelRoom
    from tests.agent.conftest import FakeMemory

    monkeypatch.setattr(
        repository, "current_records", lambda ids: {IDS[0]: authoritative(record())}
    )
    profile = TripProfile(
        traveler_count=1, hotel_rooms=[HotelRoom(adults=1, child_ages=[])], car_status="skipped"
    )
    route = payload(record(held=False)).route.model_dump(mode="json")
    route["stops"][0]["visit_duration"] = VisitDuration(
        seconds=900, source="ai_estimate", reason="estimated"
    ).model_dump()
    route.update(traveler_count=1, hotel_rooms=[room.model_dump() for room in profile.hotel_rooms])
    memory = FakeMemory()
    memory.save_trip_profile("synthetic-owner", "synthetic-chat", profile.to_json())
    saved = {
        "route": copy.deepcopy(route),
        "profile": profile.model_dump(mode="json"),
        "departure": START.isoformat(),
    }
    memory.save_planned_route("synthetic-owner", "synthetic-chat", copy.deepcopy(saved))
    ctx = ToolContext(user_id="synthetic-owner", chat_id="synthetic-chat", memory=memory)
    args = {"start_time": START.isoformat()}
    if mode == "inline":
        args["route"] = route
    if mode == "handle":
        args["route_handle"] = ctx.artifacts.put("route", route)
    result = await AppToolDispatcher().dispatch(
        ToolCall(name="generate_itinerary", arguments=args), ctx
    )
    assert not result.ok and "current catalog access is unresolved" in result.error
    assert memory.load_planned_route("synthetic-owner", "synthetic-chat") == saved
