"""Completion, date, partial-result and later-turn itinerary retry contracts."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.agent.tool_dispatcher as td
from app.agent.agent import _collect_action, _tool_result_content
from app.agent.departure import normalize_departure
from app.agent.schemas import ToolCall
from app.agent.tool_dispatcher import AppToolDispatcher
from app.agent.tools import ToolContext
from app.agent.trip_profile import TripProfile

from .conftest import FakeMemory


def _profile(**changes) -> TripProfile:
    departure = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    fields = {
        "start_address": "Denver, CO",
        "start_coords": [39.74, -104.99],
        "destination_address": "Santa Fe, NM",
        "destination_coords": [35.69, -105.94],
        "traveler_count": 2,
        "hotel_rooms": [{"adults": 2, "child_ages": []}],
        "num_stops": 2,
        "budget": 200,
        "start_date": departure,
        "car_status": "skipped",
    }
    fields.update(changes)
    return TripProfile.model_validate(fields)


def _context(profile: TripProfile) -> ToolContext:
    memory = FakeMemory()
    memory.save_trip_profile("user-1", "chat-1", profile.to_json())
    return ToolContext(user_id="user-1", chat_id="chat-1", memory=memory)


def _stub_planning(monkeypatch):
    calls = {}

    def fake_location(**kwargs):
        calls.setdefault("validated", []).append(kwargs["address"])
        lat, lon = {
            "Denver, CO": (39.74, -104.99),
            "Santa Fe, NM": (35.69, -105.94),
        }[kwargs["address"]]
        return SimpleNamespace(
            address=kwargs["address"],
            latitude=lat,
            longitude=lon,
            raw={"annotations": {"timezone": {"name": "America/Denver"}}},
        )

    async def fake_initial(*args):
        calls["endpoints"] = args
        return SimpleNamespace(distance=1000, duration=600)

    async def fake_plan(payload, user_id=None, *, can_select_algorithm=False):
        calls["route_start"] = payload["start"]
        calls["user_id"] = user_id
        return SimpleNamespace(
            stops=[{"name": "Museum", "type": "stop"}],
            cost=120.0,
            distance=1000.0,
            model_dump=lambda **kwargs: {
                "stops": [{"name": "Museum", "type": "stop"}],
                "cost": 120.0,
                "traveler_count": 2,
                "hotel_rooms": [{"adults": 2, "child_ages": []}],
                "coordinates": [[39.74, -104.99], [35.69, -105.94]],
            },
        )

    async def fake_itinerary(payload):
        calls["itinerary_start"] = payload["start_time"]
        return [SimpleNamespace(model_dump=lambda: {"date": "Day 1", "stops": []})]

    monkeypatch.setattr(td, "call_route", fake_initial)
    monkeypatch.setattr(td, "get_location", fake_location)
    monkeypatch.setattr(td, "plan_final_route", fake_plan)
    monkeypatch.setattr(td, "build_itinerary", fake_itinerary)
    monkeypatch.setattr(
        td.MapBox.MapBox_Route, "model_validate", classmethod(lambda cls, value: value)
    )
    monkeypatch.setattr(td.Route_Payload, "model_validate", classmethod(lambda cls, value: value))
    monkeypatch.setattr(
        td.Itinerary_Payload, "model_validate", classmethod(lambda cls, value: value)
    )
    return calls


@pytest.mark.asyncio
async def test_recorded_details_and_skipped_car_can_complete_together(monkeypatch):
    calls = _stub_planning(monkeypatch)
    ctx = _context(TripProfile())
    dispatcher = AppToolDispatcher()
    recorded = await dispatcher.dispatch(
        ToolCall(
            name="record_trip_details",
            arguments={
                "start_address": "Denver, CO",
                "destination_address": "Santa Fe, NM",
                "traveler_count": 2,
                "hotel_rooms": [{"adults": 2, "child_ages": []}],
                "num_stops": 2,
                "budget": 200,
                "departure_date": "October 10, 2099",
                "departure_time": "9 AM",
                "car_status": "skipped",
            },
        ),
        ctx,
    )
    assert recorded.ok is True
    assert set(recorded.result["clarifications"]) == {
        "start_address",
        "destination_address",
        "departure_date",
    }
    blocked = await dispatcher.dispatch(ToolCall(name="complete_trip"), ctx)
    assert not blocked.ok
    from tests.agent.conftest import confirm_pending_locations

    confirm_pending_locations(ctx.memory, ctx.user_id, ctx.chat_id)
    completed = await dispatcher.dispatch(ToolCall(name="complete_trip"), ctx)
    assert completed.ok is True
    assert completed.result["status"] == "complete"
    assert calls["route_start"] == calls["itinerary_start"] == "2099-10-10T09:00:00-06:00"


@pytest.mark.asyncio
async def test_complete_trip_emits_both_existing_actions_with_same_departure(monkeypatch):
    calls = _stub_planning(monkeypatch)
    ctx = _context(_profile())
    result = await AppToolDispatcher().dispatch(ToolCall(name="complete_trip"), ctx)

    assert result.ok is True
    assert result.result["status"] == "complete"
    assert calls["route_start"] == calls["itinerary_start"]
    assert calls["user_id"] == "user-1"
    assert calls["endpoints"] == (39.74, -104.99, 35.69, -105.94)
    assert "validated" not in calls
    actions = []
    _collect_action(result, "chat-1", actions)
    assert [action.type for action in actions] == ["route_updated", "itinerary_updated"]
    assert actions[0].payload == {
        "route": result.result["actions"][0]["route"],
        "stops": [{"name": "Museum", "type": "stop"}],
        "cost": 120.0,
    }
    assert actions[1].payload == {"itinerary": [{"date": "Day 1", "stops": []}]}
    model_message = _tool_result_content(result)
    assert '"status":"complete"' in model_message
    assert '"coordinates"' not in model_message
    assert '"itinerary"' not in model_message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("changes", "missing"),
    [
        ({"start_coords": None}, "validated start location"),
        ({"destination_address": None}, "validated destination"),
        (
            {
                "traveler_count": 2,
                "hotel_rooms": [{"adults": 2, "child_ages": []}],
                "num_stops": None,
            },
            "number of stops",
        ),
        ({"budget": None}, "nightly hotel budget"),
        ({"start_date": None}, "upcoming departure"),
        ({"car_status": "unanswered"}, "car choice or explicit skip"),
    ],
)
async def test_complete_trip_rejects_missing_profile_fields(changes, missing):
    result = await AppToolDispatcher().dispatch(
        ToolCall(name="complete_trip"), _context(_profile(**changes))
    )
    assert result.ok is False
    assert missing in result.error


@pytest.mark.asyncio
async def test_complete_trip_uses_saved_coordinates_without_regeocoding(monkeypatch):
    calls = _stub_planning(monkeypatch)
    monkeypatch.setattr(td, "get_location", lambda **kwargs: None)
    result = await AppToolDispatcher().dispatch(
        ToolCall(name="complete_trip"), _context(_profile())
    )
    assert result.ok is True
    assert calls["endpoints"] == (39.74, -104.99, 35.69, -105.94)


def test_departure_checks_instant_across_timezones():
    now = datetime(2026, 9, 29, 10, 0, tzinfo=UTC)
    future = normalize_departure("2026-09-30T00:30:00+14:00", now=now)
    assert future.astimezone(UTC) == datetime(2026, 9, 29, 10, 30, tzinfo=UTC)
    with pytest.raises(ValueError, match="future"):
        normalize_departure("2026-09-29T23:00:00+14:00", now=now)
    with pytest.raises(ValueError, match="UTC offset"):
        normalize_departure("2026-09-30T09:00:00", now=now)


@pytest.mark.asyncio
async def test_partial_route_can_retry_itinerary_in_later_turn(monkeypatch):
    calls = _stub_planning(monkeypatch)
    ctx = _context(_profile())

    async def failed_itinerary(payload):
        raise HTTPException(status_code=502, detail="Itinerary service unavailable")

    monkeypatch.setattr(td, "build_itinerary", failed_itinerary)
    dispatcher = AppToolDispatcher()
    partial = await dispatcher.dispatch(ToolCall(name="complete_trip"), ctx)
    assert partial.ok is True
    assert partial.result["status"] == "partial"
    assert "Itinerary service unavailable" in partial.result["itinerary_error"]
    assert "itinerary failed" in partial.result["summary"]
    actions = []
    _collect_action(partial, "chat-1", actions)
    assert [action.type for action in actions] == ["route_updated"]

    async def retry_itinerary(payload):
        calls["retry_start"] = payload["start_time"]
        return [SimpleNamespace(model_dump=lambda: {"date": "Day 1", "stops": []})]

    monkeypatch.setattr(td, "build_itinerary", retry_itinerary)
    new_turn = ToolContext(user_id="user-1", chat_id="chat-1", memory=ctx.memory)
    retry = await dispatcher.dispatch(ToolCall(name="generate_itinerary"), new_turn)
    assert retry.ok is True
    assert retry.result["action"] == "itinerary_updated"
    assert calls["retry_start"] == calls["route_start"]


@pytest.mark.asyncio
async def test_complete_trip_preserves_nonretryable_hotel_failure(monkeypatch):
    calls = _stub_planning(monkeypatch)

    async def no_hotels(*args, **kwargs):
        raise td.CandidateProviderError(
            "Google Hotels returned no verifiable prices near the overnight stop."
        )

    monkeypatch.setattr(td, "plan_final_route", no_hotels)
    result = await AppToolDispatcher().dispatch(
        ToolCall(name="complete_trip"), _context(_profile())
    )
    assert not result.ok and not result.retryable
    assert result.error.startswith("Google Hotels returned no verifiable")
    assert "itinerary_start" not in calls
    assert result.result is None


@pytest.mark.asyncio
async def test_completion_preserves_clear_scheduling_error(monkeypatch):
    _stub_planning(monkeypatch)
    detail = "Final route exceeds the daily driving window: Boulder after the 21:00 local cutoff. Choose an earlier departure."

    async def failed_plan(*args, **kwargs):
        raise HTTPException(status_code=422, detail=detail)

    monkeypatch.setattr(td, "plan_final_route", failed_plan)
    result = await AppToolDispatcher().dispatch(
        ToolCall(name="complete_trip"), _context(_profile())
    )
    assert not result.ok and result.error == detail


@pytest.mark.asyncio
async def test_dated_route_is_json_safe_for_persistence_actions_and_later_itinerary(monkeypatch):
    import json

    from app.models.routing_models.routing_models import Route

    calls = _stub_planning(monkeypatch)
    ctx = _context(_profile())
    departure = datetime.fromisoformat(_profile().start_date)

    async def dated_plan(*args, **kwargs):
        return Route(
            coordinates=[[39.74, -104.99], [35.69, -105.94]],
            distance=1000,
            duration=600,
            steps=[],
            cost=120,
            geometry={"coordinates": [[-104.99, 39.74], [-105.94, 35.69]]},
            stops=[{"name": "Museum", "type": "stop", "arrival_time": departure}],
            departure_time=departure,
            traveler_count=2,
            hotel_rooms=[{"adults": 2, "child_ages": []}],
        )

    monkeypatch.setattr(td, "plan_final_route", dated_plan)
    original_save = ctx.memory.save_planned_route

    def strict_save(user_id, chat_id, saved):
        original_save(user_id, chat_id, json.loads(json.dumps(saved)))

    monkeypatch.setattr(ctx.memory, "save_planned_route", strict_save)
    result = await AppToolDispatcher().dispatch(ToolCall(name="complete_trip"), ctx)
    assert result.ok and result.result["status"] == "complete"
    saved = ctx.memory.load_planned_route(ctx.user_id, ctx.chat_id)
    assert datetime.fromisoformat(saved["route"]["departure_time"]) == departure
    assert datetime.fromisoformat(saved["route"]["stops"][0]["arrival_time"]) == departure
    json.dumps(result.result)
    later = ToolContext(user_id=ctx.user_id, chat_id=ctx.chat_id, memory=ctx.memory)
    retry = await AppToolDispatcher().dispatch(ToolCall(name="generate_itinerary"), later)
    assert retry.ok
    assert "itinerary_start" in calls


@pytest.mark.asyncio
async def test_route_save_failure_stops_completion_without_itinerary_or_route_handle(monkeypatch):
    calls = _stub_planning(monkeypatch)
    ctx = _context(_profile())

    def fail_save(*args):
        raise RuntimeError("fixture storage failure")

    monkeypatch.setattr(ctx.memory, "save_planned_route", fail_save)
    result = await AppToolDispatcher().dispatch(ToolCall(name="complete_trip"), ctx)
    assert not result.ok and not result.retryable
    assert (
        result.error
        == "I couldn't save the planned route. Please try creating the route and itinerary again."
    )
    assert "itinerary_start" not in calls
    assert not ctx.artifacts.has("route_1")
    assert ctx.memory.load_planned_route(ctx.user_id, ctx.chat_id) is None


@pytest.mark.asyncio
async def test_route_save_failure_does_not_run_following_model_itinerary_call(monkeypatch):
    from app.agent.agent import run_turn
    from app.agent.providers import FallbackChain
    from app.agent.schemas import AgentChatRequest, LLMResponse
    from tests.agent.conftest import FakeProvider

    _stub_planning(monkeypatch)
    ctx = _context(_profile())
    monkeypatch.setattr("app.agent.agent.get_user_id_from_token", lambda token: ctx.user_id)

    def fail_save(*args):
        raise RuntimeError("fixture storage failure")

    monkeypatch.setattr(ctx.memory, "save_planned_route", fail_save)
    provider = FakeProvider(
        extraction_responses=['{"details":{}}'],
        responses=[
            LLMResponse(
                content='```tool\n{"name":"generate_final_route","arguments":{}}\n```\n'
                '```tool\n{"name":"generate_itinerary","arguments":{}}\n```'
            )
        ],
    )
    response = await run_turn(
        AgentChatRequest(partitionKey="fixture", chatId=ctx.chat_id, message="Create the route"),
        FallbackChain([provider]),
        ctx.memory,
        AppToolDispatcher(),
    )
    assert response.toolsUsed == ["generate_final_route"]
    assert len(response.toolErrors) == 1
    assert "couldn't save the planned route" in response.reply
    assert "route_handle" not in response.reply
