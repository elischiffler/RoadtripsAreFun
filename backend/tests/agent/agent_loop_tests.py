"""Tests for the agent loop (design doc §7)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.agent.agent import MAX_TOOL_ITERATIONS, SUMMARY_WINDOW, run_turn
from app.agent.providers import FallbackChain
from app.agent.schemas import (
    AgentChatRequest,
    AgentUsage,
    LLMMessage,
    LLMResponse,
    ToolResult,
    ToolSpec,
)
from app.agent.tool_dispatcher import AppToolDispatcher
from app.agent.trip_profile import TripProfile

from .conftest import FakeMemory, FakeProvider, FakeTools, make_usage

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "field,label", [("start_address", "starting location"), ("destination_address", "destination")]
)
async def test_saved_location_receipt_uses_geocode_even_when_model_omits_it(
    fake_memory, monkeypatch, field, label
):
    address = "Salem-Leckrone Airport, Salem, Marion County, Illinois, United States of America"
    monkeypatch.setattr(
        "app.agent.tool_dispatcher.get_location",
        lambda **kwargs: SimpleNamespace(
            address=address,
            latitude=38.6404024,
            longitude=-88.9644242,
            raw={"annotations": {"timezone": {"name": "America/Chicago"}}},
        ),
    )
    provider = FakeProvider(
        responses=[LLMResponse(content="What date would you like to leave?")],
        extraction_responses=[json.dumps({"details": {field: "Salem-Leckrone Airport"}})],
    )
    result = await run_turn(
        _request("drive from SLO"), FallbackChain([provider]), fake_memory, AppToolDispatcher()
    )
    assert result.reply.startswith(f"Saved {label}: {address}.")
    assert result.tripProfile[field] == address
    assert address in provider.seen_messages[1][0].content
    if field == "start_address":
        assert '"start_timezone":"America/Chicago"' in provider.seen_messages[1][0].content

    followup = FakeProvider(responses=[LLMResponse(content="What time?")])
    followup_result = await run_turn(
        _request("October 17"), FallbackChain([followup]), fake_memory, AppToolDispatcher()
    )
    assert address in followup.seen_messages[1][0].content
    assert "Saved starting location:" not in followup_result.reply
    assert "Saved destination:" not in followup_result.reply


async def test_failed_location_is_not_confirmed_and_other_details_survive(fake_memory, monkeypatch):
    fake_memory.save_trip_profile(
        "user-123",
        "42",
        TripProfile(start_address="Denver", start_coords=[39.74, -104.99]).to_json(),
    )
    monkeypatch.setattr("app.agent.tool_dispatcher.get_location", lambda **kwargs: None)
    provider = FakeProvider(
        responses=[LLMResponse(content="Please clarify your starting city.")],
        extraction_responses=['{"details":{"start_address":"SLO","budget":180}}'],
    )
    result = await run_turn(
        _request("SLO, $180 hotels"), FallbackChain([provider]), fake_memory, AppToolDispatcher()
    )
    assert "Saved starting location" not in result.reply
    assert result.tripProfile["budget"] == 180
    assert result.tripProfile["start_address"] == "Denver"
    assert "start_address" in result.validationIssues


async def test_tool_continuation_refreshes_saved_profile(fake_memory):
    class UpdatingTools(FakeTools):
        async def dispatch(self, call, ctx):
            ctx.memory.save_trip_profile(
                ctx.user_id, ctx.chat_id, TripProfile(budget=180).to_json()
            )
            return ToolResult(name=call.name, ok=True, result={"action": "trip_profile_updated"})

    provider = FakeProvider(
        responses=[
            LLMResponse(content=_tool_block("update_trip_profile")),
            LLMResponse(content="Saved."),
        ]
    )
    await run_turn(_request(), FallbackChain([provider]), fake_memory, UpdatingTools())
    assert '"budget":180.0' in provider.seen_messages[-1][0].content


@pytest.fixture(autouse=True)
def _verified_test_user(monkeypatch):
    # These tests exercise the agent loop, not Cognito; auth has dedicated tests.
    monkeypatch.setattr("app.agent.agent.get_user_id_from_token", lambda token: "user-123")


def _request(message: str = "plan me a trip") -> AgentChatRequest:
    return AgentChatRequest(partitionKey="user-123", chatId="42", message=message)


def _tool_block(name: str, arguments: dict | None = None, prose: str = "") -> str:
    """Render a text-protocol ```tool block (optionally with leading prose).

    Tool calls now travel as fenced JSON inside the model's reply content (the
    gateway has no native function-calling), so tests script them the same way.
    """
    body = json.dumps({"tool": name, "arguments": arguments or {}})
    block = f"```tool\n{body}\n```"
    return f"{prose}\n{block}" if prose else block


@pytest.fixture
def geocoded_locations(monkeypatch):
    locations = {
        "las vegas": ("Las Vegas, NV", 36.17, -115.14, "America/Los_Angeles"),
        "houston": ("Houston, TX", 29.76, -95.37, "America/Chicago"),
    }

    def geocode(*, geocoder, address, **kwargs):
        label, latitude, longitude, timezone = locations[address.lower()]
        return SimpleNamespace(
            address=label,
            latitude=latitude,
            longitude=longitude,
            raw={"annotations": {"timezone": {"name": timezone}}},
        )

    monkeypatch.setattr("app.agent.tool_dispatcher.get_location", geocode)


async def test_every_turn_extracts_json_and_validates_all_supplied_fields(
    fake_memory, geocoded_locations, monkeypatch
):
    from fastapi import HTTPException

    async def car_not_verified(**kwargs):
        raise HTTPException(status_code=404, detail="No matching variant")

    monkeypatch.setattr("app.agent.tool_dispatcher.get_car_details", car_not_verified)
    provider = FakeProvider(
        responses=[LLMResponse(content="Please clarify your car and departure date.")],
        extraction_responses=[
            json.dumps(
                {
                    "details": {
                        "start_address": "las vegas",
                        "destination_address": "houston",
                        "num_stops": 8,
                        "budget": 150,
                        "departure_time": "11 am",
                        "car_year": 2023,
                        "car_make": "Mazda",
                        "car_model": "CX-5",
                    }
                }
            )
        ],
    )
    result = await run_turn(
        _request(
            "I am going from las vegas to houston, leaving at 11 am with a 2023 Mazda CX-5, 8 stops and $150 hotels"
        ),
        FallbackChain([provider]),
        fake_memory,
        AppToolDispatcher(),
    )
    saved = TripProfile.from_json(fake_memory.load_trip_profile("user-123", "42"))
    assert saved.start_address == "Las Vegas, NV"
    assert saved.destination_address == "Houston, TX"
    assert saved.num_stops == 8
    assert saved.budget == 150
    assert saved.departure_time == "11:00"
    assert saved.start_date is None
    assert saved.car_status == "unanswered"
    assert "car" in result.validationIssues
    assert result.toolsUsed == ["record_trip_details"]
    assert set(result.extractedFields) == {
        "start_address",
        "destination_address",
        "num_stops",
        "budget",
        "departure_time",
        "car_year",
        "car_make",
        "car_model",
    }
    assert provider.extraction_calls == 1
    assert result.modelCalls == 2

    skip_provider = FakeProvider(
        responses=[LLMResponse(content="What date would you like to leave?")],
        extraction_responses=['{"details":{"car_status":"skipped"}}'],
    )
    skip_result = await run_turn(
        _request("skip"), FallbackChain([skip_provider]), fake_memory, AppToolDispatcher()
    )
    saved_after_skip = TripProfile.from_json(fake_memory.load_trip_profile("user-123", "42"))
    assert saved_after_skip.car_status == "skipped"
    assert saved_after_skip.budget == 150
    assert saved_after_skip.departure_time == "11:00"
    assert '"budget":150.0' in skip_provider.seen_messages[1][0].content
    assert skip_result.extractedFields == ["car_status"]


async def test_later_date_and_skip_use_saved_time(fake_memory, geocoded_locations):
    first = FakeProvider(
        responses=[LLMResponse(content="What date would you like to leave?")],
        extraction_responses=[
            json.dumps(
                {
                    "details": {
                        "start_address": "las vegas",
                        "destination_address": "houston",
                        "departure_time": "11 am",
                        "budget": 150,
                    }
                }
            )
        ],
    )
    await run_turn(
        _request("Start in Las Vegas and end in Houston at 11 am, $150 hotels"),
        FallbackChain([first]),
        fake_memory,
        AppToolDispatcher(),
    )
    second = FakeProvider(
        responses=[LLMResponse(content="I have your departure date and car choice.")],
        extraction_responses=[
            json.dumps({"details": {"departure_date": "October 3, 2099", "car_status": "skipped"}})
        ],
    )
    result = await run_turn(
        _request("October 3, 2099. Skip the car."),
        FallbackChain([second]),
        fake_memory,
        AppToolDispatcher(),
    )
    saved = TripProfile.from_json(fake_memory.load_trip_profile("user-123", "42"))
    assert saved.start_date == "2099-10-03T11:00:00-07:00"
    assert saved.departure_time == "11:00"
    assert saved.budget == 150
    assert saved.car_status == "skipped"
    assert result.validationIssues == {}


async def test_provider_outage_does_not_trigger_string_extraction(fake_memory, fake_tools):
    from app.agent.providers import ProvidersExhausted

    with pytest.raises(ProvidersExhausted):
        await run_turn(
            _request("from las vegas to houston"),
            FallbackChain([FakeProvider(fail=True)]),
            fake_memory,
            fake_tools,
        )
    assert fake_tools.dispatched == []


async def test_malformed_extraction_does_not_claim_data_was_saved(fake_memory, fake_tools):
    provider = FakeProvider(extraction_responses=["not JSON", "still not JSON"])
    result = await run_turn(_request("8 stops"), FallbackChain([provider]), fake_memory, fake_tools)
    assert result.tripProfile == {"car_status": "unanswered", "pending_locations": {}}
    assert result.toolsUsed == []
    assert "couldn't read" in result.reply
    assert result.modelCalls == 2


async def test_validated_patch_survives_reply_provider_outage(fake_memory, geocoded_locations):
    from app.agent.extraction import EXTRACTION_PROMPT
    from app.agent.providers import ProviderError

    class ExtractThenFail(FakeProvider):
        def complete(self, messages, tools):
            if messages[0].content != EXTRACTION_PROMPT:
                raise ProviderError("gateway unavailable")
            return super().complete(messages, tools)

    provider = ExtractThenFail(
        extraction_responses=[
            json.dumps(
                {"details": {"start_address": "las vegas", "destination_address": "houston"}}
            )
        ]
    )
    result = await run_turn(
        _request("from las vegas to houston"),
        FallbackChain([provider]),
        fake_memory,
        AppToolDispatcher(),
    )
    assert result.tripProfile["start_address"] == "Las Vegas, NV"
    assert [action.type for action in result.actions] == ["trip_profile_updated"]
    assert "temporarily unavailable" in result.reply
    assert result.modelCalls == 2


async def test_run_turn_simple_no_tool_reply(fake_memory, fake_tools):
    provider = FakeProvider(responses=[LLMResponse(content="Sure, where to?", usage=make_usage())])
    chain = FallbackChain([provider])

    result = await run_turn(_request(), chain, fake_memory, fake_tools)

    assert result.reply == "Sure, where to?"
    assert result.toolsUsed == []
    assert result.provider == "fake"
    assert result.usage.promptTokens == 100
    assert result.modelCalls == 2
    assert provider.calls == 1
    assert provider.extraction_calls == 1


async def test_usage_includes_structured_extraction(fake_memory, fake_tools):
    from app.agent.extraction import EXTRACTION_PROMPT

    class UsageProvider(FakeProvider):
        def complete(self, messages, tools):
            response = super().complete(messages, tools)
            if messages[0].content == EXTRACTION_PROMPT:
                response.usage = make_usage(prompt=40, completion=4)
            return response

    provider = UsageProvider(
        responses=[LLMResponse(content="What is your starting city?", usage=make_usage())]
    )
    result = await run_turn(_request(), FallbackChain([provider]), fake_memory, fake_tools)
    assert result.modelCalls == 2
    assert result.usage.promptTokens == 140
    assert result.usage.completionTokens == 24


async def test_run_turn_executes_tool_and_feeds_result_back(fake_memory):
    tools = FakeTools(
        specs=[ToolSpec(name="generate_final_route", description="plan", parameters={})],
        results={
            "generate_final_route": ToolResult(
                name="generate_final_route",
                ok=True,
                result={"route_handle": "route_1", "action": "route_updated"},
            )
        },
    )
    provider = FakeProvider(
        responses=[
            # First call: request a tool via a ```tool block.
            LLMResponse(
                content=_tool_block("generate_final_route", {"route_handle": "initial_route_1"})
            ),
            # Second call: final textual reply (no tool block).
            LLMResponse(content="Your trip is planned."),
        ]
    )
    chain = FallbackChain([provider])

    result = await run_turn(_request(), chain, fake_memory, tools)

    assert result.reply == "Your trip is planned."
    assert result.toolsUsed == ["generate_final_route"]
    assert len(tools.dispatched) == 1
    assert tools.dispatched[0].arguments == {"route_handle": "initial_route_1"}
    # The successful state-mutating tool surfaced a typed action.
    assert [a.type for a in result.actions] == ["route_updated"]
    assert result.actions[0].chatId == "42"
    assert provider.calls == 2
    assert result.modelCalls == 3


async def test_usage_sums_all_model_calls_even_when_some_fields_are_missing(
    fake_memory, fake_tools
):
    provider = FakeProvider(
        responses=[
            LLMResponse(
                content=_tool_block("noop"),
                usage=make_usage(prompt=120, completion=12),
            ),
            LLMResponse(
                content=_tool_block("noop"),
                usage=AgentUsage(completionTokens=8),
            ),
            LLMResponse(content="Done.", usage=make_usage(prompt=180, completion=18)),
        ]
    )
    result = await run_turn(_request(), FallbackChain([provider]), fake_memory, fake_tools)
    assert result.modelCalls == 4
    assert result.usage.promptTokens == 300
    assert result.usage.completionTokens == 38


async def test_action_carries_trip_payload_to_client(fake_memory):
    # A state-mutating tool's route/itinerary payload must ride back on the
    # action so the frontend can write it into ChatData (no GET-by-chat endpoint).
    route_dict = {"geometry": {"coordinates": [[1, 2]]}, "cost": 320}
    tools = FakeTools(
        results={
            "generate_final_route": ToolResult(
                name="generate_final_route",
                ok=True,
                result={
                    "action": "route_updated",
                    "route": route_dict,
                    "stops": [{"name": "Red Rocks"}],
                    "cost": 320,
                },
            )
        },
    )
    provider = FakeProvider(
        responses=[
            LLMResponse(content=_tool_block("generate_final_route", {"num_stops": 2})),
            LLMResponse(content="Your trip is planned!"),
        ]
    )
    chain = FallbackChain([provider])

    result = await run_turn(_request(), chain, fake_memory, tools)

    assert [a.type for a in result.actions] == ["route_updated"]
    payload = result.actions[0].payload
    assert payload is not None
    assert payload["route"] == route_dict
    assert payload["cost"] == 320
    assert payload["stops"] == [{"name": "Red Rocks"}]


async def test_partial_completion_cannot_be_reported_as_ready(fake_memory):
    route_dict = {"coordinates": [[39.74, -104.99], [35.69, -105.94]]}
    tools = FakeTools(
        results={
            "complete_trip": ToolResult(
                name="complete_trip",
                ok=True,
                result={
                    "status": "partial",
                    "itinerary_error": "upstream unavailable",
                    "actions": [{"action": "route_updated", "route": route_dict}],
                },
            )
        }
    )
    provider = FakeProvider(
        responses=[
            LLMResponse(content=_tool_block("complete_trip")),
            LLMResponse(content="Your whole trip is ready!"),
        ]
    )
    result = await run_turn(_request(), FallbackChain([provider]), fake_memory, tools)
    assert (
        result.reply
        == "Your route is ready, but the itinerary could not be created. Please retry it."
    )
    assert [action.type for action in result.actions] == ["route_updated"]
    assert result.actions[0].payload == {"route": route_dict}


async def test_tool_loop_terminates_at_cap(fake_memory, fake_tools):
    # A provider that always asks for a tool would loop forever without the cap.
    always_tool = LLMResponse(content=_tool_block("noop"))
    provider = FakeProvider(responses=[always_tool])
    chain = FallbackChain([provider])

    result = await run_turn(_request(), chain, fake_memory, fake_tools)

    # MAX_TOOL_ITERATIONS provider re-calls inside the loop, plus the initial call.
    assert provider.calls == MAX_TOOL_ITERATIONS + 1
    assert len(fake_tools.dispatched) == MAX_TOOL_ITERATIONS
    # Loop ended cleanly (no infinite spin); reply is whatever text was present.
    assert isinstance(result.reply, str)


async def test_run_turn_tool_failure_is_fed_back_not_raised(fake_memory):
    tools = FakeTools(
        results={
            "broken": ToolResult(name="broken", ok=False, error="upstream 500"),
        }
    )
    provider = FakeProvider(
        responses=[
            LLMResponse(content=_tool_block("broken")),
            LLMResponse(content="I hit a snag with that; let me try another way."),
        ]
    )
    chain = FallbackChain([provider])

    result = await run_turn(_request(), chain, fake_memory, tools)

    assert result.reply.startswith("I hit a snag")
    assert result.toolsUsed == ["broken"]
    # A failed tool contributes no action.
    assert result.actions == []


# --------------------------------------------------------------------------- #
# Memory write-back + short-term memory (design doc §7 step 6)
# --------------------------------------------------------------------------- #


def _recent_window(n: int) -> list[LLMMessage]:
    """A verbatim recent window of ``n`` alternating user/assistant turns."""
    turns: list[LLMMessage] = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        turns.append(LLMMessage(role=role, content=f"turn {i}"))
    return turns


async def test_write_back_rolls_summary_when_window_exceeds_threshold(fake_tools):
    # A recent window at/over SUMMARY_WINDOW should trigger a summary roll.
    memory = FakeMemory(recent_turns=_recent_window(SUMMARY_WINDOW))
    provider = FakeProvider(responses=[LLMResponse(content="Done.")])
    chain = FallbackChain([provider])

    result = await run_turn(_request(), chain, memory, fake_tools)

    assert result.reply == "Done."
    # save_conversation was called exactly once as part of write-back.
    assert len(memory.saved_conversations) == 1
    rolled = memory.saved_conversations[0]
    assert rolled.summary_turn_count == 1
    assert rolled.summary  # a truthful note was appended
    assert "turn 0" in rolled.summary
    assert "turn 1" in rolled.summary
    assert "Done." not in rolled.summary


async def test_write_back_skips_summary_below_threshold(fake_tools):
    # A short window (below SUMMARY_WINDOW) must NOT roll the summary.
    memory = FakeMemory(recent_turns=_recent_window(SUMMARY_WINDOW - 1))
    provider = FakeProvider(responses=[LLMResponse(content="Hi.")])
    chain = FallbackChain([provider])

    result = await run_turn(_request(), chain, memory, fake_tools)

    assert result.reply == "Hi."
    assert memory.saved_conversations == []


async def test_reply_survives_save_conversation_failure(fake_tools):
    # Write-back is best-effort: a save failure must not break the reply.
    memory = FakeMemory(recent_turns=_recent_window(SUMMARY_WINDOW), raise_on_save=True)
    provider = FakeProvider(responses=[LLMResponse(content="Still works.")])
    chain = FallbackChain([provider])

    result = await run_turn(_request(), chain, memory, fake_tools)

    assert result.reply == "Still works."
    # The save was attempted but raised; nothing was recorded, no exception rose.
    assert memory.saved_conversations == []


async def test_recent_turns_are_threaded_into_provider_messages(fake_tools):
    window = _recent_window(3)
    memory = FakeMemory(recent_turns=window)
    provider = FakeProvider(responses=[LLMResponse(content="ok")])
    chain = FallbackChain([provider])

    await run_turn(_request("newest question"), chain, memory, fake_tools)

    assert provider.seen_messages, "provider should have been called at least once"
    contents = [m.content for m in provider.seen_messages[1]]
    # The verbatim recent turns appear in the assembled message list...
    for turn in window:
        assert turn.content in contents
    # ...ahead of the new user message, which is last.
    assert provider.seen_messages[1][-1].content == "newest question"


async def test_run_turn_surfaces_failed_tool_in_tool_errors(fake_memory):
    """A failed tool is fed back to the model (not raised) and never becomes an
    action, but its error must be surfaced in ``toolErrors`` for the client."""
    tools = FakeTools(
        specs=[ToolSpec(name="update_trip_profile", description="trip", parameters={})],
        results={
            "update_trip_profile": ToolResult(
                name="update_trip_profile",
                ok=False,
                error="Invalid arguments: num_stops must be between 1 and 10",
            ),
        },
    )
    provider = FakeProvider(
        responses=[
            # First: request the (doomed) tool.
            LLMResponse(content=_tool_block("update_trip_profile", {"num_stops": 25})),
            # Second: plain reply after seeing the error.
            LLMResponse(content="Let's pick between 1 and 10 stops."),
        ]
    )
    chain = FallbackChain([provider])

    result = await run_turn(_request(), chain, fake_memory, tools)

    assert result.toolsUsed == ["update_trip_profile"]
    # No action emitted for a failed tool...
    assert result.actions == []
    # ...but the error is surfaced for the client to log.
    assert len(result.toolErrors) == 1
    assert result.toolErrors[0].name == "update_trip_profile"
    assert "between 1 and 10" in result.toolErrors[0].error


async def test_run_turn_feeds_tool_error_back_and_lets_model_recover(fake_memory):
    """After a tool fails, the loop must feed the error back and re-ask the model,
    so the model can explain/recover — the final reply is the model's recovery
    prose, and the failing tool's error rode back in the message history."""
    tools = FakeTools(
        specs=[ToolSpec(name="get_initial_route", description="route", parameters={})],
        results={
            "get_initial_route": ToolResult(
                name="get_initial_route",
                ok=False,
                error="get_initial_route needs start/end coordinates",
            ),
        },
    )
    provider = FakeProvider(
        responses=[
            # Turn 1: request the (doomed) tool.
            LLMResponse(content=_tool_block("get_initial_route", {})),
            # Turn 2: the model, having seen the error fed back, recovers with prose.
            LLMResponse(content="I couldn't map that route yet — what city are you starting from?"),
        ]
    )
    chain = FallbackChain([provider])

    result = await run_turn(_request(), chain, fake_memory, tools)

    # The reply is the recovery prose, not a fabricated success.
    assert "starting from" in result.reply
    # The model was re-asked (2 provider calls) after the failure fed back.
    assert provider.calls == 2
    # A second provider call means the tool error was appended to the history and
    # the model saw it (that assembled message list is captured by FakeProvider).
    second_call_messages = provider.seen_messages[2]
    assert any(
        m.role == "tool" and "needs start/end coordinates" in m.content
        for m in second_call_messages
    )


async def test_required_provider_failure_stops_retries_and_returns_error(fake_memory):
    provider = FakeProvider(responses=[LLMResponse(content=_tool_block("generate_final_route"))])
    tools = FakeTools(
        results={
            "generate_final_route": ToolResult(
                name="generate_final_route",
                ok=False,
                retryable=False,
                error="Google Hotels prices are temporarily unavailable. Please try again later.",
            )
        }
    )
    result = await run_turn(_request(), FallbackChain([provider]), fake_memory, tools)
    assert provider.calls == 1
    assert result.toolsUsed == ["generate_final_route"]
    assert len(result.toolErrors) == 1
    assert "Google Hotels prices are temporarily unavailable" in result.reply
    assert "couldn't finish" in result.reply
    assert result.actions == []


async def test_failed_completion_does_not_run_queued_itinerary_or_retry_route(fake_memory):
    provider = FakeProvider(
        responses=[
            LLMResponse(
                content="\n".join(
                    [
                        _tool_block("complete_trip"),
                        _tool_block("generate_itinerary"),
                        _tool_block("generate_final_route"),
                    ]
                )
            )
        ]
    )
    tools = FakeTools(
        results={
            "complete_trip": ToolResult(
                name="complete_trip",
                ok=False,
                retryable=False,
                error="Google Hotels returned no verifiable prices near the overnight stop.",
            )
        }
    )
    result = await run_turn(_request(), FallbackChain([provider]), fake_memory, tools)
    assert result.toolsUsed == ["complete_trip"]
    assert [call.name for call in tools.dispatched] == ["complete_trip"]
    assert provider.calls == 1
    assert "no verifiable prices" in result.reply
    assert result.actions == []
