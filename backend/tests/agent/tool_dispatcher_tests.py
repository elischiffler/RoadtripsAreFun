"""Tests for the real tool dispatcher (design doc §5, Stream A-tools).

Every underlying capability is monkeypatched at the ``tool_dispatcher`` module
level, so these run with no network and no DB — the fake-injection template from
``tests/routing/conftest.py`` / ``tests/agent/conftest.py``. ``dispatch`` is
async, so tests are async (pytest-asyncio ``asyncio_mode=auto``).

For each tool we assert:
- specs() advertises the expected names,
- the success path returns ``ok=True`` with the expected result keys,
- the failure path returns ``ok=False`` with an error and does NOT raise,
- state-mutating tools include the ``action`` key.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import app.agent.tool_dispatcher as td
from app.agent.memory import MemoryFact
from app.agent.schemas import ToolCall
from app.agent.tool_dispatcher import AppToolDispatcher
from app.agent.tools import ToolContext

from .conftest import FakeMemory

pytestmark = pytest.mark.asyncio


EXPECTED_TOOLS = {
    "validate_location",
    "get_initial_route",
    "generate_final_route",
    "generate_itinerary",
    "get_car_budget",
    "recall_facts",
    "remember_fact",
    "get_trip_profile",
    "update_trip_profile",
}


def _ctx(memory=None) -> ToolContext:
    return ToolContext(user_id="user-1", chat_id="42", memory=memory)


def _dispatcher() -> AppToolDispatcher:
    return AppToolDispatcher()


# --------------------------------------------------------------------------- #
# specs()
# --------------------------------------------------------------------------- #


async def test_specs_advertises_expected_tools():
    specs = _dispatcher().specs()
    names = {spec.name for spec in specs}
    assert names == EXPECTED_TOOLS
    # Every spec carries a JSON-Schema object for its parameters.
    for spec in specs:
        assert spec.description
        assert spec.parameters.get("type") == "object"


async def test_unknown_tool_returns_error_not_raise():
    result = await _dispatcher().dispatch(ToolCall(name="does_not_exist"), _ctx())
    assert result.ok is False
    assert "Unknown tool" in result.error


# --------------------------------------------------------------------------- #
# validate_location
# --------------------------------------------------------------------------- #


async def test_validate_location_success(monkeypatch):
    fake_location = SimpleNamespace(address="Boston, MA, USA", latitude=42.36, longitude=-71.06)
    monkeypatch.setattr(td, "get_location", lambda **kwargs: fake_location)

    result = await _dispatcher().dispatch(
        ToolCall(name="validate_location", arguments={"address": "Boston"}), _ctx()
    )
    assert result.ok is True
    assert result.result["address"] == "Boston, MA, USA"
    assert result.result["latitude"] == 42.36
    assert result.result["longitude"] == -71.06


async def test_validate_location_not_found_returns_error(monkeypatch):
    monkeypatch.setattr(td, "get_location", lambda **kwargs: None)
    result = await _dispatcher().dispatch(
        ToolCall(name="validate_location", arguments={"address": "nowhere"}), _ctx()
    )
    assert result.ok is False
    assert "not found" in result.error.lower()


async def test_validate_location_missing_args_returns_error():
    result = await _dispatcher().dispatch(ToolCall(name="validate_location", arguments={}), _ctx())
    assert result.ok is False
    assert "address" in result.error


# --------------------------------------------------------------------------- #
# get_initial_route
# --------------------------------------------------------------------------- #


async def test_get_initial_route_success(monkeypatch):
    fake_route = SimpleNamespace(
        distance=1000.0, duration=600.0, model_dump=lambda: {"distance": 1000.0}
    )

    async def fake_call_route(start_lat, start_lon, end_lat, end_lon, *args, **kwargs):
        return fake_route

    monkeypatch.setattr(td, "call_route", fake_call_route)

    result = await _dispatcher().dispatch(
        ToolCall(
            name="get_initial_route",
            arguments={
                "start_lat": 42.0,
                "start_lon": -71.0,
                "end_lat": 40.0,
                "end_lon": -74.0,
            },
        ),
        _ctx(),
    )
    assert result.ok is True
    # Handle-based: the model gets a handle + scalars + summary, NOT the route.
    assert result.result["route_handle"].startswith("initial_route_")
    assert result.result["distance_meters"] == 1000.0
    assert result.result["duration_seconds"] == 600.0
    assert "route" not in result.result  # heavy object stays server-side
    assert "summary" in result.result


async def test_get_initial_route_failure_returns_error(monkeypatch):
    async def boom(*args, **kwargs):
        raise HTTPException(status_code=502, detail="Mapbox down")

    monkeypatch.setattr(td, "call_route", boom)
    result = await _dispatcher().dispatch(
        ToolCall(
            name="get_initial_route",
            arguments={"start_lat": 1, "start_lon": 2, "end_lat": 3, "end_lon": 4},
        ),
        _ctx(),
    )
    assert result.ok is False
    assert "Mapbox down" in result.error


# --------------------------------------------------------------------------- #
# generate_final_route  (state-mutating -> action key)
# --------------------------------------------------------------------------- #


async def test_generate_final_route_success_has_action(monkeypatch):
    fake_route = SimpleNamespace(
        stops=[{"name": "Red Rocks", "type": "stop", "coordinates": [39.6, -105.2]}],
        cost=320.0,
        distance=500000.0,
        model_dump=lambda: {"cost": 320.0},
    )

    async def fake_plan(payload):
        return fake_route

    monkeypatch.setattr(td, "plan_final_route", fake_plan)
    monkeypatch.setattr(td.Route_Payload, "model_validate", classmethod(lambda cls, v: v))
    # Stored artifact is a raw dict here; resolve validates it via MapBox_Route
    # (stubbed to pass through).
    monkeypatch.setattr(td.MapBox.MapBox_Route, "model_validate", classmethod(lambda cls, v: v))

    # Seed the artifact store with an initial route + get its handle (mirrors
    # get_initial_route running first).
    ctx = _ctx()
    handle = ctx.artifacts.put("initial_route", {})

    result = await _dispatcher().dispatch(
        ToolCall(
            name="generate_final_route",
            arguments={"route_handle": handle, "num_stops": 2, "budget": 400},
        ),
        ctx,
    )
    assert result.ok is True
    assert result.result["action"] == "route_updated"
    assert result.result["cost"] == 320.0
    # New Route is stored + a handle returned; full route still present for the
    # frontend action payload (run_turn trims it out of the model-visible msg).
    assert result.result["route_handle"].startswith("route_")
    assert result.result["stops"][0]["name"] == "Red Rocks"
    assert "route" in result.result  # full payload for the frontend
    assert ctx.artifacts.has(result.result["route_handle"])


async def test_generate_final_route_failure_returns_error(monkeypatch):
    from app.routing import PlanningError

    async def boom(payload):
        raise PlanningError("no feasible trip", status_code=422)

    monkeypatch.setattr(td, "plan_final_route", boom)
    monkeypatch.setattr(td.MapBox.MapBox_Route, "model_validate", classmethod(lambda cls, v: v))
    monkeypatch.setattr(td.Route_Payload, "model_validate", classmethod(lambda cls, v: v))

    result = await _dispatcher().dispatch(
        ToolCall(
            name="generate_final_route",
            arguments={"initial_route": {}, "num_stops": 2, "budget": 400},
        ),
        _ctx(),
    )
    # PlanningError is a generic Exception here -> caught, not raised.
    assert result.ok is False
    assert "no feasible trip" in result.error


# --------------------------------------------------------------------------- #
# generate_itinerary  (state-mutating -> action key)
# --------------------------------------------------------------------------- #


async def test_generate_itinerary_success_has_action(monkeypatch):
    fake_day = SimpleNamespace(model_dump=lambda: {"date": "Monday", "stops": []})

    async def fake_build(payload):
        return [fake_day]

    monkeypatch.setattr(td, "build_itinerary", fake_build)
    monkeypatch.setattr(td.Itinerary_Payload, "model_validate", classmethod(lambda cls, v: v))

    result = await _dispatcher().dispatch(
        ToolCall(name="generate_itinerary", arguments={"route": {}}), _ctx()
    )
    assert result.ok is True
    assert result.result["action"] == "itinerary_updated"
    assert result.result["itinerary"] == [{"date": "Monday", "stops": []}]


async def test_generate_itinerary_failure_returns_error(monkeypatch):
    async def boom(payload):
        raise HTTPException(status_code=400, detail="Incomplete route provided")

    monkeypatch.setattr(td, "build_itinerary", boom)
    monkeypatch.setattr(td.Itinerary_Payload, "model_validate", classmethod(lambda cls, v: v))

    result = await _dispatcher().dispatch(
        ToolCall(name="generate_itinerary", arguments={"route": {}}), _ctx()
    )
    assert result.ok is False
    assert "Incomplete route" in result.error


# --------------------------------------------------------------------------- #
# get_car_budget
# --------------------------------------------------------------------------- #


async def test_get_car_budget_success_with_distance(monkeypatch):
    async def fake_details(model, make, year):
        return {"combination_mpg": 30.0}

    async def fake_gas():
        return 3.0

    monkeypatch.setattr(td, "get_car_details", fake_details)
    monkeypatch.setattr(td, "get_gas_price", fake_gas)

    result = await _dispatcher().dispatch(
        ToolCall(
            name="get_car_budget",
            arguments={
                "make": "Mazda",
                "model": "CX-3",
                "year": 2020,
                "distance_meters": 1609344,  # 1000 miles
            },
        ),
        _ctx(),
    )
    assert result.ok is True
    assert result.result["combination_mpg"] == 30.0
    assert result.result["gas_price"] == 3.0
    # 1000 miles / 30 mpg = 33.33 gal * $3 = $100.0
    assert result.result["estimated_fuel_cost"] == pytest.approx(100.0, abs=0.5)


async def test_get_car_budget_failure_returns_error(monkeypatch):
    async def boom(model, make, year):
        raise HTTPException(status_code=404, detail="Could not find that car")

    monkeypatch.setattr(td, "get_car_details", boom)
    result = await _dispatcher().dispatch(
        ToolCall(
            name="get_car_budget",
            arguments={"make": "Foo", "model": "Bar", "year": 1900},
        ),
        _ctx(),
    )
    assert result.ok is False
    assert "Could not find that car" in result.error


# --------------------------------------------------------------------------- #
# recall_facts / remember_fact  (against FakeMemory)
# --------------------------------------------------------------------------- #


async def test_recall_facts_returns_facts():
    memory = FakeMemory(facts=[MemoryFact(key="home_city", value="Boston, MA")])
    result = await _dispatcher().dispatch(
        ToolCall(name="recall_facts", arguments={}), _ctx(memory=memory)
    )
    assert result.ok is True
    assert result.result["facts"][0]["key"] == "home_city"
    assert result.result["facts"][0]["value"] == "Boston, MA"


async def test_recall_facts_without_memory_returns_error():
    result = await _dispatcher().dispatch(
        ToolCall(name="recall_facts", arguments={}), _ctx(memory=None)
    )
    assert result.ok is False
    assert "memory" in result.error.lower()


async def test_remember_fact_upserts():
    memory = FakeMemory()
    result = await _dispatcher().dispatch(
        ToolCall(
            name="remember_fact",
            arguments={"key": "pref.avoid", "value": "big cities"},
        ),
        _ctx(memory=memory),
    )
    assert result.ok is True
    assert result.result["remembered"]["key"] == "pref.avoid"
    # The fact was actually written to the store, scoped to the chat.
    assert len(memory.upserted) == 1
    assert memory.upserted[0].key == "pref.avoid"
    assert memory.upserted[0].source_chat_id == "42"


async def test_remember_fact_without_memory_returns_error():
    result = await _dispatcher().dispatch(
        ToolCall(name="remember_fact", arguments={"key": "k", "value": "v"}),
        _ctx(memory=None),
    )
    assert result.ok is False
    assert "memory" in result.error.lower()
