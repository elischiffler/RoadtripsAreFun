"""Tests for the B1 remote-routing proxy (local dev -> deployed whitelisted backend)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.agent.routing_remote as rr
import app.agent.tool_dispatcher as td
from app.agent.tool_dispatcher import AppToolDispatcher
from app.agent.tools import ToolCall, ToolContext
from app.agent.trip_profile import TripProfile

from .conftest import FakeMemory


def _ctx(*, car_skipped=False):
    memory = FakeMemory() if car_skipped else None
    if memory:
        memory.save_trip_profile(
            "u1",
            "42",
            TripProfile(
                car_status="skipped",
                traveler_count=2,
                hotel_rooms=[{"adults": 2, "child_ages": []}],
            ).to_json(),
        )
    return ToolContext(user_id="u1", chat_id="42", auth_token="verified-token", memory=memory)


def test_remote_enabled_reflects_config(monkeypatch):
    monkeypatch.setattr(rr.settings, "ROUTING_REMOTE_URL", None)
    assert rr.remote_enabled() is False
    monkeypatch.setattr(rr.settings, "ROUTING_REMOTE_URL", "https://deployed.example")
    assert rr.remote_enabled() is True


@pytest.mark.asyncio
async def test_get_initial_route_uses_remote_when_enabled(monkeypatch):
    monkeypatch.setattr(rr.settings, "ROUTING_REMOTE_URL", "https://deployed.example")

    called = {}

    async def fake_remote(a, b, c, d, token):
        called["args"] = (a, b, c, d, token)
        return SimpleNamespace(distance=664000.0, duration=26000.0)

    # The tool calls routing_remote.call_route_remote; the LOCAL call_route must
    # NOT be used.
    monkeypatch.setattr(rr, "call_route_remote", fake_remote)

    async def local_boom(*a, **k):
        raise AssertionError("local call_route should not be used when remote is enabled")

    monkeypatch.setattr(td, "call_route", local_boom)

    result = await AppToolDispatcher().dispatch(
        ToolCall(
            name="get_initial_route",
            arguments={"start_lat": 35.3, "start_lon": -120.4, "end_lat": 36.2, "end_lon": -115.1},
        ),
        _ctx(),
    )
    assert result.ok is True, result.error
    assert result.result["route_handle"].startswith("initial_route_")
    assert called["args"] == (35.3, -120.4, 36.2, -115.1, "verified-token")


@pytest.mark.asyncio
async def test_get_initial_route_uses_local_when_disabled(monkeypatch):
    monkeypatch.setattr(rr.settings, "ROUTING_REMOTE_URL", None)

    async def fake_local(a, b, c, d, *args, **kwargs):
        return SimpleNamespace(distance=1.0, duration=1.0)

    monkeypatch.setattr(td, "call_route", fake_local)

    def remote_boom(*a, **k):
        raise AssertionError("remote must not be used when ROUTING_REMOTE_URL is unset")

    monkeypatch.setattr(rr, "call_route_remote", remote_boom)

    result = await AppToolDispatcher().dispatch(
        ToolCall(
            name="get_initial_route",
            arguments={"start_lat": 1, "start_lon": 2, "end_lat": 3, "end_lon": 4},
        ),
        _ctx(),
    )
    assert result.ok is True, result.error


@pytest.mark.asyncio
async def test_generate_final_route_uses_remote_when_enabled(monkeypatch):
    monkeypatch.setattr(rr.settings, "ROUTING_REMOTE_URL", "https://deployed.example")
    monkeypatch.setattr(td.MapBox.MapBox_Route, "model_validate", classmethod(lambda cls, v: v))
    monkeypatch.setattr(td.Route_Payload, "model_validate", classmethod(lambda cls, v: v))

    async def fake_remote_plan(payload, token, *, identity_token=None):
        assert token == "verified-token"
        return SimpleNamespace(
            stops=[{"name": "S", "type": "stop"}],
            cost=250.0,
            distance=664000.0,
            warnings=None,
            model_dump=lambda **kwargs: {"cost": 250.0},
        )

    monkeypatch.setattr(rr, "plan_final_route_remote", fake_remote_plan)

    async def local_boom(payload):
        raise AssertionError("local plan_final_route should not run when remote is enabled")

    monkeypatch.setattr(td, "plan_final_route", local_boom)

    ctx = _ctx(car_skipped=True)
    handle = ctx.artifacts.put("initial_route", {})
    result = await AppToolDispatcher().dispatch(
        ToolCall(
            name="generate_final_route",
            arguments={"route_handle": handle, "num_stops": 2, "budget": 300},
        ),
        ctx,
    )
    assert result.ok is True, result.error
    assert result.result["action"] == "route_updated"
    assert result.result["cost"] == 250.0


@pytest.mark.asyncio
async def test_remote_call_route_hits_expected_endpoint(monkeypatch):
    """rr.call_route_remote posts to {base}/get-initial-route and validates."""
    import httpx

    monkeypatch.setattr(rr.settings, "ROUTING_REMOTE_URL", "https://deployed.example/")
    seen = {}

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"stub": "route"}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None, headers=None):
            seen["url"] = url
            seen["params"] = params
            seen["headers"] = headers
            return _Resp()

    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    monkeypatch.setattr(rr.MapBox.MapBox_Route, "model_validate", classmethod(lambda cls, v: v))

    await rr.call_route_remote(1.0, 2.0, 3.0, 4.0, "verified-token")
    assert seen["url"] == "https://deployed.example/get-initial-route"
    assert seen["params"] == {"start_lat": 1.0, "start_lon": 2.0, "end_lat": 3.0, "end_lon": 4.0}
    assert seen["headers"] == {"Authorization": "Bearer verified-token"}


def test_remote_route_rejects_missing_token():
    with pytest.raises(ValueError, match="Authenticated token"):
        rr._auth(None)


@pytest.mark.asyncio
@pytest.mark.parametrize("identity_token", [None, "signed-identity-token"])
async def test_remote_final_route_forwards_override_and_auth(monkeypatch, identity_token):
    import httpx

    monkeypatch.setattr(rr.settings, "ROUTING_REMOTE_URL", "https://deployed.example")
    seen = {}

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None, headers=None):
            seen.update(url=url, body=json, headers=headers)
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"cost": 1})

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    monkeypatch.setattr(rr.Route, "model_validate", classmethod(lambda cls, data: data))
    payload = SimpleNamespace(
        model_dump=lambda mode: {"algorithm": "cp_sat", "persona_weights": {"nature": 2}}
    )
    await rr.plan_final_route_remote(payload, "verified-token", identity_token=identity_token)
    assert seen == {
        "url": "https://deployed.example/generate-final-route",
        "body": {"algorithm": "cp_sat", "persona_weights": {"nature": 2}},
        "headers": {
            "Authorization": "Bearer verified-token",
            **({"X-Cognito-Id-Token": identity_token} if identity_token else {}),
        },
    }
