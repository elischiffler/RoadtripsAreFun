"""Replay validated collection with a deliberately noncompliant prose model."""

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.agent.agent import run_turn
from app.agent.presentation import detail_request, present_details
from app.agent.providers import FallbackChain, ProvidersExhausted
from app.agent.schemas import AgentChatRequest, LLMResponse, ToolResult
from app.agent.tool_dispatcher import AppToolDispatcher
from app.agent.trip_profile import TripProfile
from app.main import app
from app.routers.agent_api import get_agent_dependencies
from app.routing.occupancy import HotelRoom
from app.schemas.chat_schemas import ChatLogSchema

from .complete_trip_tests import _profile, _stub_planning
from .conftest import FakeMemory, FakeProvider, FakeTools, confirm_pending_locations


@pytest.fixture(autouse=True)
def local_identity(monkeypatch):
    monkeypatch.setattr("app.agent.agent.get_user_id_from_token", lambda token: "user")


def profile():
    return TripProfile(
        start_address="Boulder, CO, USA",
        start_coords=[40, -105],
        start_timezone="America/Denver",
        destination_address="Marceline, MO, USA",
        destination_coords=[39, -92],
        num_stops=6,
        budget=200,
        departure_time="10:00",
        car={"year": 2023, "make": "Mazda", "model": "CX-5"},
        traveler_count=2,
        hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
    )


async def turn(memory, patch, message="details", provider=None, tools=None):
    provider = provider or FakeProvider(
        extraction_responses=[json.dumps({"details": patch})],
        responses=[
            LLMResponse(content="Everything is ready! Saved all fields. What time and car?")
        ],
    )
    return await run_turn(
        AgentChatRequest(partitionKey="token", chatId="42", message=message),
        FallbackChain([provider]),
        memory,
        tools or AppToolDispatcher(),
    )


@pytest.mark.asyncio
async def test_conversation_corrections_invalids_and_no_change(monkeypatch):
    monkeypatch.setattr(
        "app.agent.tool_dispatcher.get_location",
        lambda **kw: SimpleNamespace(
            address=kw["address"] + ", USA",
            latitude=40,
            longitude=-105,
            raw={"annotations": {"timezone": {"name": "America/Denver"}}},
        ),
    )

    async def car(**kw):
        return {"combination_mpg": 28}

    monkeypatch.setattr("app.agent.tool_dispatcher.get_car_details", car)
    memory = FakeMemory()
    memory.save_trip_profile(
        "user",
        "42",
        TripProfile(traveler_count=2, hotel_rooms=[HotelRoom(adults=2, child_ages=[])]).to_json(),
    )
    first = await turn(memory, {"start_address": "Boulder", "destination_address": "Marceline"})
    assert first.presentation.updated == []
    assert "Boulder, USA" in first.presentation.needed[0]
    assert "Marceline, USA" in first.presentation.needed[1]
    confirmed = confirm_pending_locations(memory, "user", "42")
    assert confirmed.start_address == "Boulder, USA"
    assert confirmed.destination_address == "Marceline, USA"
    second = await turn(
        memory,
        {"departure_time": "10 AM", "car_year": 2023, "car_make": "Mazda", "car_model": "CX-5"},
    )
    assert second.presentation.updated == [
        "Departure time: 10:00 (America/Denver)",
        "Optional car: 2023 Mazda CX-5",
    ]
    third = await turn(memory, {"num_stops": 6, "budget": 200})
    assert third.presentation.updated == [
        "Attraction stops: 6",
        "Hotel budget: $200 per room per night",
    ]
    assert third.presentation.needed == ["What date would you like to leave?"]
    assert "Everything is ready" not in third.reply
    fourth = await turn(memory, {"departure_date": "November 21"})
    assert fourth.tripProfile["start_date"].endswith("11-21T10:00:00-07:00")
    assert fourth.tripProfile["start_date"][:4] in fourth.presentation.updated[0]
    assert fourth.presentation.needed == []
    assert "ready" not in fourth.reply
    correction = await turn(memory, {"budget": 180, "num_stops": 99})
    assert correction.presentation.updated == ["Hotel budget: $180 per room per night"]
    assert correction.tripProfile["num_stops"] == 6
    assert correction.presentation.needed == [
        "Attraction stops: Please give a whole number from 1 to 10."
    ]
    unchanged = await turn(memory, {"budget": 180})
    assert unchanged.presentation.updated == []
    assert "Updated trip details" not in unchanged.reply
    unrelated = await turn(memory, {}, message="Why is the sky blue?")
    assert unrelated.presentation is None


@pytest.mark.asyncio
async def test_no_change_question_summary_skip_and_outage():
    memory = FakeMemory()
    memory.save_trip_profile("user", "42", profile().to_json())
    question = await turn(memory, {}, message="What else do you need?")
    assert question.presentation.updated == []
    assert question.presentation.needed == ["What date would you like to leave?"]
    summary = await turn(memory, {}, message="Show trip details")
    assert summary.presentation.title == "Trip details"
    assert "Hotel budget: $200 per room per night" in summary.presentation.updated
    skipped = await turn(memory, {"car_status": "skipped"})
    assert skipped.presentation.updated == ["Optional car: skipped"]
    assert all("car" not in question.lower() for question in skipped.presentation.needed)

    class Outage(FakeProvider):
        def complete(self, messages, tools):
            if len(messages) and messages[0].content.startswith("Extract trip"):
                return super().complete(messages, tools)
            raise ProvidersExhausted("offline")

    outage = await turn(
        memory, {}, provider=Outage(extraction_responses=['{"details":{"budget":210}}'])
    )
    assert outage.presentation.updated == ["Hotel budget: $210 per room per night"]
    assert outage.presentation.needed == ["What date would you like to leave?"]
    assert "temporarily unavailable" in outage.reply


@pytest.mark.parametrize("status", ["complete", "partial", "failed"])
@pytest.mark.asyncio
async def test_planning_outcomes(status):
    memory = FakeMemory()
    memory.save_trip_profile(
        "user",
        "42",
        profile().model_copy(update={"start_date": "2027-11-21T10:00:00-07:00"}).to_json(),
    )
    result = {
        "status": status,
        "actions": [{"action": "route_updated", "route": {"warnings": ["Hotel budget exceeded"]}}],
    }
    if status == "complete":
        result["actions"].append({"action": "itinerary_updated", "itinerary": [{"day": 1}]})
    provider = FakeProvider(
        responses=[
            LLMResponse(content='```tool\n{"tool":"complete_trip","arguments":{}}\n```'),
            LLMResponse(content="Whole trip ready!"),
        ]
    )
    response = await turn(
        memory,
        {},
        provider=provider,
        tools=FakeTools(
            results={
                "complete_trip": ToolResult(
                    name="complete_trip",
                    ok=status != "failed",
                    result=result if status != "failed" else None,
                    error="Provider unavailable" if status == "failed" else None,
                )
            }
        ),
        message="What else do you need?",
    )
    assert "Whole trip ready" not in response.reply
    if status == "complete":
        assert response.presentation.title == "Trip details"
        assert "route and itinerary are ready" in response.reply
        assert "Hotel budget exceeded" in response.presentation.notes
    elif status == "partial":
        assert "itinerary could not be created" in response.reply
    else:
        assert "Provider unavailable" in response.reply


@pytest.mark.asyncio
async def test_real_dispatcher_completes_route_and_itinerary_before_full_confirmation(monkeypatch):
    calls = _stub_planning(monkeypatch)
    memory = FakeMemory()
    memory.save_trip_profile("user", "42", _profile().to_json())
    provider = FakeProvider(
        responses=[
            LLMResponse(content='```tool\n{"tool":"complete_trip","arguments":{}}\n```'),
            LLMResponse(content="Where would you like to start?"),
        ]
    )
    response = await turn(memory, {}, provider=provider, message="Finish it")
    assert calls["route_start"] == calls["itinerary_start"]
    assert [action.type for action in response.actions] == ["route_updated", "itinerary_updated"]
    assert response.presentation.title == "Trip details"
    assert response.presentation.needed == []
    assert "Optional car: skipped" in response.presentation.updated
    assert "Your route and itinerary are ready." in response.presentation.notes


@pytest.mark.asyncio
async def test_model_failure_before_extraction_keeps_saved_questions():
    memory = FakeMemory()
    memory.save_trip_profile("user", "42", profile().to_json())
    response = await turn(memory, {}, provider=FakeProvider(fail=True))
    assert response.presentation.updated == []
    assert response.presentation.needed == ["What date would you like to leave?"]
    assert "temporarily unavailable" in response.reply


def test_unanswered_car_and_failed_address_receipts():
    before = profile()
    after = before.model_copy(
        update={"car": None, "car_status": "unanswered", "start_date": "2027-11-21T10:00:00-07:00"}
    )
    assert "Optional car" in present_details(before, after, {}).needed[0]
    presentation = present_details(before, before, {"start_address": "Please clarify it."})
    assert presentation.updated == []
    assert presentation.needed[0] == "Starting location: Please clarify it."


def test_general_questions_are_not_collection_requests():
    assert detail_request("What else should I pack?") is None
    assert detail_request("Summarize why the sky is blue") is None
    assert detail_request("What else do you need?") == "collect"


def test_json_stream_parity_and_chatlog_roundtrip():
    client = TestClient(app)

    def deps():
        memory = FakeMemory()
        memory.save_trip_profile("user", "42", profile().to_json())
        return FallbackChain([FakeProvider()]), memory, FakeTools()

    app.dependency_overrides[get_agent_dependencies] = deps
    body = {"partitionKey": "token", "chatId": "42", "message": "Show trip details"}
    try:
        plain = client.post("/agent/chat", json=body).json()
        events = [
            json.loads(line)
            for line in client.post("/agent/chat/stream", json=body).text.splitlines()
        ]
    finally:
        app.dependency_overrides.pop(get_agent_dependencies, None)
    final = next(event for event in events if event["type"] == "result")
    assert final["response"] == plain
    message = {"text": plain["reply"], "sender": "bot", "presentation": plain["presentation"]}
    log = ChatLogSchema.model_validate(
        {"id": 1, "title": "Trip", "messages": [message, {"text": "Old message", "sender": "bot"}]}
    )
    restored = ChatLogSchema.model_validate_json(log.model_dump_json())
    assert restored.messages[0].presentation.model_dump() == plain["presentation"]
    assert restored.messages[1].presentation is None
