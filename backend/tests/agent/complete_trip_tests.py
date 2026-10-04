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
    assert recorded.result["clarifications"] == {}
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
    assert calls["validated"] == ["Denver, CO", "Santa Fe, NM"]
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
        ({"num_stops": None}, "number of stops"),
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
async def test_complete_trip_stops_when_saved_location_cannot_be_validated(monkeypatch):
    calls = _stub_planning(monkeypatch)
    monkeypatch.setattr(td, "get_location", lambda **kwargs: None)
    result = await AppToolDispatcher().dispatch(
        ToolCall(name="complete_trip"), _context(_profile())
    )
    assert result.ok is False
    assert "validate the start location" in result.error
    assert "endpoints" not in calls


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
