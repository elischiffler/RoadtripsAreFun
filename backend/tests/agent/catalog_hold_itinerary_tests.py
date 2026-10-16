"""Real chat dispatch paths must refresh a saved or inline catalog calendar."""

import copy

import pytest

from app.agent.schemas import ToolCall
from app.agent.tool_dispatcher import AppToolDispatcher
from app.agent.tools import ToolContext
from app.agent.trip_profile import TripProfile
from app.catalog import repository
from app.routing.occupancy import HotelRoom
from tests.agent.conftest import FakeMemory
from tests.routing.catalog_calendar_refresh_tests import IDS, START, authoritative, payload, record


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["inline", "saved", "handle"])
async def test_chat_itinerary_paths_withhold_current_hold_and_preserve_saved_route(
    monkeypatch, mode
):
    monkeypatch.setattr(
        repository, "current_records", lambda ids: {IDS[0]: authoritative(record())}
    )
    profile = TripProfile(
        traveler_count=1, hotel_rooms=[HotelRoom(adults=1, child_ages=[])], car_status="skipped"
    )
    route = payload(record(held=False)).route.model_dump(mode="json")
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
