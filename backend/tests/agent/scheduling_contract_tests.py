"""Chat persistence, remote serialization and JSON/NDJSON use the same policy."""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.agent import routing_remote
from app.agent.extraction import parse_trip_patch
from app.agent.providers import FallbackChain
from app.agent.schemas import LLMResponse, ToolCall
from app.agent.tool_dispatcher import AppToolDispatcher
from app.agent.tools import ToolContext
from app.agent.trip_profile import TripProfile
from app.main import app
from app.models.itinerary_models import Itinerary_Payload
from app.models.routing_models.routing_models import Route_Payload
from app.models.scheduling_policy import SchedulingPolicy
from app.routers.agent_api import get_agent_dependencies
from tests.agent.conftest import FakeMemory, FakeProvider
from tests.routing.flexible_hotel_tests import START, point, saved_route


async def record(memory, arguments):
    return await AppToolDispatcher().dispatch(
        ToolCall(name="record_trip_details", arguments=arguments),
        ToolContext(user_id="user", chat_id="trip", memory=memory),
    )


@pytest.mark.asyncio
async def test_policy_patches_merge_preserve_siblings_and_do_not_enable_late_driving_implicitly():
    memory = FakeMemory()
    first = await record(memory, {"scheduling_policy": {"morning_restart": "10:30"}})
    assert first.ok and first.result["clarifications"] == {}
    second = await record(
        memory,
        {
            "scheduling_policy": {"late_driving": True, "late_cutoff": "midnight"},
            "evening_interests": ["culture"],
        },
    )
    policy = second.result["trip_profile"]["scheduling_policy"]
    assert policy["late_driving"] and policy["morning_restart"] == "10:30"
    invalid = await record(
        memory, {"scheduling_policy": {"latest_hotel_arrival": "17:00"}, "budget": 250}
    )
    assert invalid.ok and "scheduling_policy" in invalid.result["clarifications"]
    loaded = TripProfile.from_json(memory.load_trip_profile("user", "trip"))
    assert loaded.budget == 250 and loaded.scheduling_policy == SchedulingPolicy(**policy)
    await record(memory, {"scheduling_policy": {"late_driving": False}, "evening_interests": []})
    loaded = TripProfile.from_json(memory.load_trip_profile("user", "trip"))
    assert not loaded.scheduling_policy.late_driving and loaded.evening_interests == []


def test_extraction_retains_optional_policy_and_explicit_decline():
    patch = parse_trip_patch(
        '{"details":{"scheduling_policy":{"late_driving":true,"late_cutoff":"24:00"},"evening_interests":[],"departure_time":"11 AM"}}'
    )
    assert patch["scheduling_policy"]["late_driving"] is True
    assert patch["evening_interests"] == []


@pytest.mark.parametrize("stream", [False, True])
def test_chat_json_and_ndjson_record_same_explicit_late_preference(monkeypatch, stream):
    memory = FakeMemory()
    provider = FakeProvider(
        responses=[LLMResponse(content="Saved your late-driving preference.")],
        extraction_responses=[
            '{"details":{"scheduling_policy":{"late_driving":true,"late_cutoff":"24:00"},"evening_interests":["food"]}}'
        ],
    )
    monkeypatch.setattr("app.agent.agent.get_user_id_from_token", lambda token: "user")
    app.dependency_overrides[get_agent_dependencies] = lambda: (
        FallbackChain([provider]),
        memory,
        AppToolDispatcher(),
    )
    try:
        response = TestClient(app).post(
            "/agent/chat/stream" if stream else "/agent/chat",
            json={
                "partitionKey": "fixture",
                "chatId": "trip",
                "message": "I can drive until midnight and would like optional dinner ideas.",
            },
        )
    finally:
        app.dependency_overrides.pop(get_agent_dependencies, None)
    assert response.status_code == 200
    body = (
        [json.loads(line) for line in response.text.splitlines()][-1]["response"]
        if stream
        else response.json()
    )
    assert body["tripProfile"]["scheduling_policy"]["late_driving"] is True
    assert body["tripProfile"]["evening_interests"] == ["food"]
    assert TripProfile.from_json(
        memory.load_trip_profile("user", "trip")
    ).scheduling_policy.late_driving


@pytest.mark.asyncio
async def test_remote_round_trip_preserves_policy_timing_and_suggestions(monkeypatch):
    from tests.routing.conftest import build_route

    route = build_route()
    policy = SchedulingPolicy(late_driving=True, morning_restart="10:00")
    hotel = point(9 * 3600, "hotel")
    hotel["evening_suggestions"] = [
        {
            "name": "Cafe",
            "optional": True,
            "status": "tentative",
            "notice": "Check opening hours",
            "travel_seconds": [600, 600],
            "visit_time": None,
            "return_time": None,
            "return_by": "2035-11-22T00:00:00-08:00",
        }
    ]
    final = saved_route([hotel, point(3600)], policy)
    from app.routers.itinerary_api import build_itinerary

    days = await build_itinerary(Itinerary_Payload(route=final, start_time=START))
    bodies = []

    def respond(request):
        bodies.append(json.loads(request.content))
        result = (
            final.model_dump(mode="json")
            if request.url.path == "/generate-final-route"
            else [day.model_dump(mode="json") for day in days]
        )
        return httpx.Response(200, json=result)

    client = httpx.AsyncClient
    monkeypatch.setattr(routing_remote.settings, "ROUTING_REMOTE_URL", "https://fixture.test")
    monkeypatch.setattr(
        routing_remote.httpx,
        "AsyncClient",
        lambda **kwargs: client(transport=httpx.MockTransport(respond), **kwargs),
    )
    payload = Route_Payload(
        initial_route=route,
        num_stops=2,
        budget=200,
        start=START,
        scheduling_policy=policy,
        evening_interests=["food"],
    )
    received = await routing_remote.plan_final_route_remote(payload, "fixture-token")
    itinerary = await routing_remote.build_itinerary_remote(
        Itinerary_Payload(route=received, start_time=START), "fixture-token"
    )
    assert bodies[0]["scheduling_policy"] == policy.model_dump()
    assert bodies[0]["evening_interests"] == ["food"] and bodies[0]["num_stops"] == 2
    assert received == final and itinerary == days
    assert any(stop.optional for day in itinerary for stop in day.stops)
