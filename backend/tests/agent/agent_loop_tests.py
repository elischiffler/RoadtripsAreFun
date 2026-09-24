"""Tests for the agent loop (design doc §7)."""

from __future__ import annotations

import json

import pytest

from app.agent.agent import MAX_TOOL_ITERATIONS, SUMMARY_WINDOW, run_turn
from app.agent.providers import FallbackChain
from app.agent.schemas import (
    AgentChatRequest,
    LLMMessage,
    LLMResponse,
    ToolResult,
    ToolSpec,
)

from .conftest import FakeMemory, FakeProvider, FakeTools, make_usage

pytestmark = pytest.mark.asyncio


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


async def test_run_turn_simple_no_tool_reply(fake_memory, fake_tools):
    provider = FakeProvider(responses=[LLMResponse(content="Sure, where to?", usage=make_usage())])
    chain = FallbackChain([provider])

    result = await run_turn(_request(), chain, fake_memory, fake_tools)

    assert result.reply == "Sure, where to?"
    assert result.toolsUsed == []
    assert result.provider == "fake"
    assert result.usage.promptTokens == 100
    assert provider.calls == 1


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
    assert "Done." in rolled.summary


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
    contents = [m.content for m in provider.seen_messages[0]]
    # The verbatim recent turns appear in the assembled message list...
    for turn in window:
        assert turn.content in contents
    # ...ahead of the new user message, which is last.
    assert provider.seen_messages[0][-1].content == "newest question"


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
    second_call_messages = provider.seen_messages[1]
    assert any(
        m.role == "tool" and "needs start/end coordinates" in m.content
        for m in second_call_messages
    )
