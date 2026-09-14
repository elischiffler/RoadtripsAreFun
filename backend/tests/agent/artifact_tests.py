"""Tests for the artifact store + handle-based tool chaining + compact results."""

from __future__ import annotations

import json

import pytest

import app.agent.tool_dispatcher as td
from app.agent.agent import _tool_result_content
from app.agent.schemas import ToolResult
from app.agent.tool_dispatcher import AppToolDispatcher, _extract_endpoints
from app.agent.tools import ArtifactStore, ToolCall, ToolContext

# async tests run under pytest-asyncio auto mode — no file-wide marker (which
# would wrongly tag the sync unit tests below).


# --- ArtifactStore ----------------------------------------------------------


def test_artifact_store_put_get_roundtrip():
    store = ArtifactStore()
    obj = {"big": "payload"}
    handle = store.put("route", obj)
    assert handle == "route_1"
    assert store.get(handle) is obj
    assert store.has(handle)


def test_artifact_store_handles_are_unique_per_kind():
    store = ArtifactStore()
    assert store.put("initial_route", 1) == "initial_route_1"
    assert store.put("initial_route", 2) == "initial_route_2"
    assert store.put("route", 3) == "route_1"


def test_artifact_store_unknown_handle_raises_keyerror():
    with pytest.raises(KeyError):
        ArtifactStore().get("route_99")


# --- _extract_endpoints (flat AND nested) -----------------------------------


def test_extract_endpoints_flat():
    assert _extract_endpoints(
        {"start_lat": 1.0, "start_lon": 2.0, "end_lat": 3.0, "end_lon": 4.0}
    ) == (1.0, 2.0, 3.0, 4.0)


def test_extract_endpoints_nested():
    assert _extract_endpoints(
        {"start": {"latitude": 1.0, "longitude": 2.0}, "end": {"latitude": 3.0, "longitude": 4.0}}
    ) == (1.0, 2.0, 3.0, 4.0)


def test_extract_endpoints_nested_lat_lon_aliases():
    assert _extract_endpoints(
        {"start": {"lat": 1.0, "lon": 2.0}, "end": {"lat": 3.0, "lon": 4.0}}
    ) == (1.0, 2.0, 3.0, 4.0)


def test_extract_endpoints_missing_raises():
    with pytest.raises(ValueError):
        _extract_endpoints({"start_lat": 1.0})


def test_extract_endpoints_coords_arrays():
    # The model reuses the trip-profile *_coords array naming — accept it.
    assert _extract_endpoints(
        {"start_coords": [1.0, 2.0], "end_coords": [3.0, 4.0]}
    ) == (1.0, 2.0, 3.0, 4.0)


def test_extract_endpoints_destination_coords_alias():
    assert _extract_endpoints(
        {"start_coords": [1.0, 2.0], "destination_coords": [3.0, 4.0]}
    ) == (1.0, 2.0, 3.0, 4.0)


def test_extract_endpoints_stringified_coords_arrays():
    # A known model quirk: coordinate arrays arrive as JSON strings.
    assert _extract_endpoints(
        {"start_coords": "[1.0, 2.0]", "end_coords": "[3.0, 4.0]"}
    ) == (1.0, 2.0, 3.0, 4.0)


def test_extract_endpoints_bare_array_under_start_end():
    assert _extract_endpoints(
        {"start": [1.0, 2.0], "end": [3.0, 4.0]}
    ) == (1.0, 2.0, 3.0, 4.0)


def test_extract_endpoints_nested_coordinates_key():
    assert _extract_endpoints(
        {"start": {"coordinates": [1.0, 2.0]}, "end": {"coordinates": [3.0, 4.0]}}
    ) == (1.0, 2.0, 3.0, 4.0)


def test_extract_endpoints_mixed_shapes():
    # Flat start + array end (models mix shapes freely).
    assert _extract_endpoints(
        {"start_lat": 1.0, "start_lon": 2.0, "end_coords": [3.0, 4.0]}
    ) == (1.0, 2.0, 3.0, 4.0)


def test_extract_endpoints_only_start_still_raises():
    # Missing the destination entirely still fails clearly.
    with pytest.raises(ValueError):
        _extract_endpoints({"start_coords": [1.0, 2.0]})


# --- compact model-visible tool result --------------------------------------


def test_tool_result_content_strips_bulky_keys():
    result = ToolResult(
        name="generate_final_route",
        ok=True,
        result={
            "action": "route_updated",
            "route_handle": "route_1",
            "cost": 320,
            "summary": "planned",
            "route": {"geometry": {"coordinates": [[1, 2]] * 1000}},  # huge
            "stops": [{"name": "x"}] * 50,
        },
    )
    content = _tool_result_content(result)
    parsed = json.loads(content)
    # Bulky keys gone from the model-visible message...
    assert "route" not in parsed["result"]
    assert "stops" not in parsed["result"]
    # ...but the handle + summary + scalars remain so the model can chain.
    assert parsed["result"]["route_handle"] == "route_1"
    assert parsed["result"]["cost"] == 320
    assert parsed["result"]["summary"] == "planned"


# --- handle chaining through the real dispatcher ----------------------------


def _ctx(memory=None):
    return ToolContext(user_id="u1", chat_id="42", memory=memory)


async def test_full_route_chain_by_handle(monkeypatch):
    from types import SimpleNamespace

    async def fake_call_route(a, b, c, d, *args, **kwargs):
        return SimpleNamespace(distance=664000.0, duration=26000.0)

    async def fake_plan(payload):
        return SimpleNamespace(
            stops=[{"name": "Stop", "type": "stop"}],
            cost=250.0,
            distance=664000.0,
            model_dump=lambda: {"cost": 250.0},
        )

    async def fake_build(payload):
        return [SimpleNamespace(model_dump=lambda: {"date": "Day 1", "stops": []})]

    monkeypatch.setattr(td, "call_route", fake_call_route)
    monkeypatch.setattr(td, "plan_final_route", fake_plan)
    monkeypatch.setattr(td, "build_itinerary", fake_build)
    monkeypatch.setattr(td.MapBox.MapBox_Route, "model_validate", classmethod(lambda cls, v: v))
    monkeypatch.setattr(td.Route_Payload, "model_validate", classmethod(lambda cls, v: v))
    monkeypatch.setattr(td.Itinerary_Payload, "model_validate", classmethod(lambda cls, v: v))

    d = AppToolDispatcher()
    ctx = _ctx()

    # 1. get_initial_route -> handle
    r1 = await d.dispatch(
        ToolCall(
            name="get_initial_route",
            arguments={"start_lat": 35.3, "start_lon": -120.4, "end_lat": 36.2, "end_lon": -115.1},
        ),
        ctx,
    )
    assert r1.ok, r1.error
    init_handle = r1.result["route_handle"]
    assert "route" not in r1.result  # heavy object not returned to model

    # 2. generate_final_route with that handle -> new handle
    r2 = await d.dispatch(
        ToolCall(
            name="generate_final_route",
            arguments={"route_handle": init_handle, "num_stops": 2, "budget": 300},
        ),
        ctx,
    )
    assert r2.ok, r2.error
    route_handle = r2.result["route_handle"]
    assert r2.result["action"] == "route_updated"
    assert "route" in r2.result  # full payload present for the frontend action

    # 3. generate_itinerary with the route handle
    r3 = await d.dispatch(
        ToolCall(name="generate_itinerary", arguments={"route_handle": route_handle}),
        ctx,
    )
    assert r3.ok, r3.error
    assert r3.result["action"] == "itinerary_updated"
    assert r3.result["itinerary"] == [{"date": "Day 1", "stops": []}]


async def test_generate_final_route_unresolved_handle_and_no_coords_errors():
    # An unresolvable handle with NO stored coordinates to rebuild from is a hard
    # error — but the message now points at the recovery path (validate + record
    # the endpoints, or call get_initial_route) rather than just "bad handle".
    d = AppToolDispatcher()
    result = await d.dispatch(
        ToolCall(
            name="generate_final_route",
            arguments={"route_handle": "nope_1", "num_stops": 2, "budget": 300},
        ),
        _ctx(),
    )
    assert result.ok is False
    assert "initial route" in result.error.lower()


async def test_generate_final_route_rebuilds_from_trip_coords_across_turns(monkeypatch):
    # THE cross-turn bug: get_initial_route ran in an earlier turn, so its handle
    # is gone from THIS turn's (fresh) artifact store. With the start/destination
    # coordinates recorded on the trip profile, generate_final_route rebuilds the
    # initial route instead of failing with "needs route_handle".
    from types import SimpleNamespace

    from .conftest import FakeMemory

    rebuilt = {}

    async def fake_call_route(start_lat, start_lon, end_lat, end_lon):
        rebuilt["args"] = (start_lat, start_lon, end_lat, end_lon)
        return SimpleNamespace(distance=100000.0, duration=3600.0)

    async def fake_plan(payload):
        return SimpleNamespace(stops=[], cost=0.0, distance=100000.0, model_dump=lambda: {})

    # conftest's autouse _routing_local fixture already forces the LOCAL path
    # (ROUTING_REMOTE_URL=None), so call_route (not the remote proxy) is used.
    monkeypatch.setattr(td, "call_route", fake_call_route)
    monkeypatch.setattr(td, "plan_final_route", fake_plan)
    monkeypatch.setattr(td.MapBox.MapBox_Route, "model_validate", classmethod(lambda cls, v: v))
    monkeypatch.setattr(td.Route_Payload, "model_validate", classmethod(lambda cls, v: v))

    memory = FakeMemory()
    d = AppToolDispatcher()
    ctx = ToolContext(user_id="u1", chat_id="42", memory=memory)
    # Record the endpoints on the profile (what update_trip_profile would store).
    await d.dispatch(
        ToolCall(
            name="update_trip_profile",
            arguments={
                "start_coords": [40.01, -105.27],
                "destination_coords": [40.71, -74.0],
                "num_stops": 8,
                "budget": 600,
            },
        ),
        ctx,
    )
    # A brand-new turn's context: fresh (empty) artifact store, same memory.
    next_turn_ctx = ToolContext(user_id="u1", chat_id="42", memory=memory)
    result = await d.dispatch(
        ToolCall(
            name="generate_final_route",
            arguments={"route_handle": "initial_route_1"},  # stale handle from a prior turn
        ),
        next_turn_ctx,
    )
    assert result.ok is True, result.error
    # The initial route was rebuilt from the trip's stored coordinates.
    assert rebuilt["args"] == (40.01, -105.27, 40.71, -74.0)
    assert result.result["action"] == "route_updated"
