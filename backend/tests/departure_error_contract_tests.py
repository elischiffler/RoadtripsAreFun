"""Only the real upcoming-departure guard exposes a fixed public stream error."""

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.agent import departure
from app.agent.progress_stream import stream_turn
from app.core.departure_errors import (
    DEPARTURE_NOT_UPCOMING_CODE,
    DEPARTURE_NOT_UPCOMING_MESSAGE,
    DepartureNotUpcomingHTTPError,
)
from app.models.routing_models.routing_models import Route_Payload
from app.routers import routing_api
from app.routing.base import DepartureNotUpcoming, PlanningError
from app.utils.auth import require_authenticated_user
from tests.routing.conftest import build_route


@pytest.fixture
def boundary(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2035, 6, 1, 16, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(departure, "datetime", Clock)
    timezone = AsyncMock(return_value="America/Los_Angeles")
    monkeypatch.setattr(
        routing_api, "_build_services", lambda: SimpleNamespace(timezone_at=timezone)
    )
    planner = SimpleNamespace(
        plan=AsyncMock(side_effect=AssertionError("No expired trip planning"))
    )
    monkeypatch.setattr(routing_api, "get_planner", lambda _: planner)
    database = AsyncMock(side_effect=AssertionError("No expired trip account lookup"))
    monkeypatch.setattr(routing_api, "load_account_persona", database)
    roads = AsyncMock(side_effect=AssertionError("No expired trip provider lookup"))
    monkeypatch.setattr(routing_api, "_call_route", roads)
    monkeypatch.setattr(routing_api, "owner_routing_claims", lambda *_: None)
    app = FastAPI()
    app.include_router(routing_api.router)
    app.dependency_overrides[require_authenticated_user] = lambda: "fixture-account"
    return TestClient(app), timezone, planner, database, roads


def payload(start):
    data = {
        "initial_route": build_route(3600).model_dump(mode="json"),
        "num_stops": 3,
        "budget": 150,
        "traveler_count": 1,
        "hotel_rooms": [{"adults": 1, "child_ages": []}],
    }
    if start != "omitted":
        data["start"] = start
    return data


@pytest.mark.parametrize(
    "start",
    ["omitted", None, "2035-06-01T15:59:00Z", "2035-06-01T16:00:00Z", "2035-06-01T09:00:00"],
)
def test_actual_core_guard_maps_missing_null_past_and_now_to_safe_http_and_stream(boundary, start):
    client, timezone, planner, database, roads = boundary
    data = payload(start)
    ordinary = client.post("/generate-final-route", json=data)
    assert ordinary.status_code == 422
    assert ordinary.json() == {"detail": "Choose a departure date and time in the future."}
    streamed = client.post("/generate-final-route/stream", json=data)
    assert streamed.status_code == 200
    events = [json.loads(row) for row in streamed.text.splitlines()]
    assert events[-1] == {
        "type": "error",
        "status": 422,
        "code": "departure_not_upcoming",
        "detail": "Choose a departure date and time in the future.",
    }
    assert not any(event["type"] == "result" for event in events)
    planner.plan.assert_not_awaited()
    database.assert_not_called()
    roads.assert_not_awaited()
    if start != "2035-06-01T09:00:00":
        timezone.assert_not_awaited()


@pytest.mark.asyncio
async def test_core_raises_typed_domain_error_preserving_planning_error_contract(boundary):
    with pytest.raises(DepartureNotUpcoming) as caught:
        await routing_api.plan_final_route(
            Route_Payload.model_validate(payload(None)), "fixture-account"
        )
    assert isinstance(caught.value, PlanningError)
    assert caught.value.status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure,status",
    [
        (HTTPException(422, DEPARTURE_NOT_UPCOMING_MESSAGE), 422),
        (HTTPException(503, "private-provider-body"), 503),
        (RuntimeError("private-provider-body"), 503),
    ],
)
async def test_unknown_failures_even_matching_message_remain_redacted(failure, status):
    async def fail():
        raise failure

    events = [json.loads(row) async for row in stream_turn(fail)]
    assert events[-1] == {"type": "error", "status": status}
    assert not any(event["type"] == "result" for event in events)


@pytest.mark.asyncio
async def test_dedicated_transport_class_emits_fixed_constants_not_mutable_exception_details():
    async def fail():
        exception = DepartureNotUpcomingHTTPError()
        exception.detail = "private-provider-body"
        raise exception

    events = [json.loads(row) async for row in stream_turn(fail)]
    assert events[-1] == {
        "type": "error",
        "status": 422,
        "code": DEPARTURE_NOT_UPCOMING_CODE,
        "detail": DEPARTURE_NOT_UPCOMING_MESSAGE,
    }
