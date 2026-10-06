"""Collection, optional follow-ups and paragraph compatibility on real agent turns."""

import json

import pytest
from fastapi.testclient import TestClient

from app.agent.agent import run_turn
from app.agent.presentation import present_details
from app.agent.providers import FallbackChain, ProviderError
from app.agent.questions import QUESTION_FORMAT_PROMPT
from app.agent.schemas import AgentChatRequest, AgentUsage, LLMResponse
from app.agent.trip_profile import TripProfile
from app.main import app
from app.routers.agent_api import get_agent_dependencies
from app.schemas.chat_schemas import ChatLogSchema

from .conftest import FakeMemory, FakeProvider, FakeTools


@pytest.fixture(autouse=True)
def identity(monkeypatch):
    monkeypatch.setattr("app.agent.agent.get_user_id_from_token", lambda token: "user")


def profile():
    return TripProfile(
        start_address="Boulder, CO, USA",
        start_coords=[40, -105],
        start_timezone="America/Denver",
        destination_address="Marceline, MO, USA",
        destination_coords=[39, -92],
        traveler_count=2,
        hotel_rooms=[{"adults": 2, "child_ages": []}],
        num_stops=6,
        budget=200,
        start_date="2027-11-21T09:00:00-07:00",
        departure_time="09:00",
    )


def structured(fields, introduction="Let's finish the details."):
    return json.dumps(
        {
            "introduction": introduction,
            "requests": [
                {"field": field, "question": "What time and car and evening preferences?"}
                for field in fields
            ],
        }
    )


async def turn(trip, content, formatted=None):
    memory = FakeMemory()
    memory.save_trip_profile("user", "42", trip.to_json())
    provider = FakeProvider(
        responses=[LLMResponse(content=content)],
        question_responses=[formatted] if formatted else None,
    )
    response = await run_turn(
        AgentChatRequest(partitionKey="token", chatId="42", message="Continue"),
        FallbackChain([provider]),
        memory,
        FakeTools(),
    )
    assert TripProfile.from_json(memory.load_trip_profile("user", "42")) == trip
    return response, provider


@pytest.mark.asyncio
async def test_unchanged_no_tool_paragraph_time_car_is_structured():
    trip = profile().model_copy(update={"start_date": None, "departure_time": None})
    response, provider = await turn(
        trip,
        "What time would you like to depart? You can choose 9 AM. Would you like to provide a car or skip it?",
        structured(["departure_time", "car"]),
    )
    assert response.presentation.needed == [
        "What time would you like to leave? You can choose 9:00 AM.",
        "Optional car: would you like to provide a car for this trip, or skip it?",
    ]
    assert response.actions == []
    assert provider.question_calls == 1
    assert response.modelCalls == 3
    assert response.reply.count("• ") == 2
    assert "\n• Optional car:" in response.reply


@pytest.mark.parametrize(
    "fields,expected",
    [
        (["car"], ["Optional car: would you like to provide a car for this trip, or skip it?"]),
        (
            ["car_year", "car_make", "car_model"],
            ["What is the car's year?", "What is the car's make?"],
        ),
        (
            ["budget", "departure_time", "car"],
            ["Optional car: would you like to provide a car for this trip, or skip it?"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_single_ask_vehicle_values_and_saved_values(fields, expected):
    response, provider = await turn(profile(), structured(fields))
    assert response.presentation.needed == expected
    assert provider.question_calls == 0


@pytest.mark.asyncio
async def test_optional_followups_do_not_become_blockers_or_repeat_saved_fields():
    trip = profile().model_copy(update={"car_status": "skipped"})
    response, _ = await turn(
        trip, structured(["budget", "latest_hotel_arrival", "evening_interests"])
    )
    assert trip.missing_details() == []
    assert response.presentation.needed == []
    assert response.presentation.questions == [
        "What latest hotel arrival time would you prefer (optional)?",
        "Which evening interests would you like suggestions for (optional)?",
    ]
    assert "Questions\n• " in response.reply


@pytest.mark.asyncio
async def test_ordinary_answer_stays_exact_and_fallback_failure_is_safe():
    original = "Pack layers, water and a charger."
    response, _ = await turn(profile(), original)
    assert response.reply == original
    assert response.presentation is None
    response, _ = await turn(profile(), "What time and car?", "malformed")
    assert "What time and car?" not in response.reply
    assert "couldn't format" in response.reply
    assert len(response.presentation.needed) <= 2


def test_date_time_and_car_correction_are_separate():
    trip = profile().model_copy(update={"start_date": None, "departure_time": None})
    presentation = present_details(trip, trip, {})
    assert presentation.needed == [
        "What date would you like to leave?",
        "What time would you like to leave? You can choose 9:00 AM.",
    ]
    correction = present_details(trip, trip, {"car": "Please give year, make, and model."})
    assert (
        correction.needed[0]
        == "Optional car: Would you like to correct the car details, or skip the car?"
    )
    assert len(correction.needed) == 2


def test_json_ndjson_and_saved_question_reload():
    client = TestClient(app)

    def deps():
        memory = FakeMemory()
        memory.save_trip_profile("user", "42", profile().to_json())
        return (
            FallbackChain(
                [
                    FakeProvider(
                        responses=[LLMResponse(content=structured(["car", "evening_interests"]))]
                    )
                ]
            ),
            memory,
            FakeTools(),
        )

    app.dependency_overrides[get_agent_dependencies] = deps
    body = {"partitionKey": "token", "chatId": "42", "message": "Continue"}
    try:
        plain = client.post("/agent/chat", json=body).json()
        events = [
            json.loads(line)
            for line in client.post("/agent/chat/stream", json=body).text.splitlines()
        ]
    finally:
        app.dependency_overrides.pop(get_agent_dependencies, None)
    assert next(event["response"] for event in events if event["type"] == "result") == plain
    log = ChatLogSchema.model_validate(
        {
            "id": 1,
            "title": "Trip",
            "messages": [
                {"sender": "bot", "text": plain["reply"], "presentation": plain["presentation"]}
            ],
        }
    )
    assert (
        ChatLogSchema.model_validate_json(log.model_dump_json())
        .messages[0]
        .presentation.model_dump()
        == plain["presentation"]
    )


@pytest.mark.asyncio
async def test_formatter_usage_and_outage_are_accounted_for():
    class Formatter(FakeProvider):
        def complete(self, messages, tools):
            if messages[0].content == QUESTION_FORMAT_PROMPT:
                if self.name == "outage":
                    raise ProviderError("formatter unavailable")
                return LLMResponse(
                    content=structured(["car"]),
                    usage=AgentUsage(promptTokens=22, completionTokens=11),
                )
            return super().complete(messages, tools)

    for name in ("working", "outage"):
        memory = FakeMemory()
        memory.save_trip_profile("user", "42", profile().to_json())
        result = await run_turn(
            AgentChatRequest(partitionKey="token", chatId="42", message="Continue"),
            FallbackChain(
                [Formatter(name=name, responses=[LLMResponse(content="What time and car?")])]
            ),
            memory,
            FakeTools(),
        )
        assert result.modelCalls == 3
        if name == "working":
            assert result.usage.promptTokens == 22
            assert result.usage.completionTokens == 11
        else:
            assert "couldn't format" in result.reply
            assert "What time and car?" not in result.reply


def test_car_verification_failure_remains_visible_without_bundled_asks():
    trip = profile()
    presentation = present_details(
        trip, trip, {"car": "Car verification is unavailable; please try again or say skip/no car."}
    )
    assert presentation.needed == [
        "Optional car: Car verification is unavailable. Would you like to retry verification, or skip the car?"
    ]
