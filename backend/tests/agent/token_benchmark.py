"""Offline before/after prompt benchmark with fixed scripted conversations.

Run from backend/: python -m tests.agent.token_benchmark
The token count is a lexical proxy, not provider-billed usage. Scripted model
responses test whether the same tool chain still completes, not model quality.
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
from pathlib import Path
from types import ModuleType

from app.agent import agent
from app.agent.memory import ConversationMemory
from app.agent.schemas import (
    AgentChatRequest,
    AgentClientContext,
    AgentUsage,
    LLMMessage,
    LLMResponse,
    ToolResult,
)
from app.agent.trip_profile import TripProfile

BASELINE_REF = "ff370b5"
ROOT = Path(__file__).resolve().parents[3]


def token_proxy(text: str) -> int:
    return len(re.findall(r"\w+|[^\w\s]", text))


def tool_block(name: str, args: dict | None = None) -> str:
    return "```tool\n" + json.dumps({"tool": name, "arguments": args or {}}) + "\n```"


class ScriptedProvider:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls = 0
        self.prompt_tokens = 0

    def complete(self, messages, tools):
        assert all("G" * 100 not in m.content and "D" * 100 not in m.content for m in messages)
        self.prompt_tokens += token_proxy("\n".join(m.content for m in messages))
        text = self.responses[self.calls]
        self.calls += 1
        return LLMResponse(
            content=text,
            provider="scripted",
            usage=AgentUsage(promptTokens=token_proxy("\n".join(m.content for m in messages))),
        )


class Memory:
    def __init__(self, trip: TripProfile):
        self.trip = trip
        self.recent = [
            LLMMessage(
                role="user" if i % 2 == 0 else "assistant",
                content=f"Prior trip exchange {i}: scenic roads and quiet hotels",
            )
            for i in range(10)
        ]

    def load_facts(self, user_id):
        return []

    def load_conversation(self, user_id, chat_id):
        return ConversationMemory(
            chat_id=chat_id, summary="Traveler prefers scenic roads and quiet hotels."
        )

    def load_recent_turns(self, user_id, chat_id, limit=10):
        return self.recent[-limit:]

    def load_trip_profile(self, user_id, chat_id):
        return self.trip.to_json()

    def save_conversation(self, user_id, chat_id, conversation):
        pass


class Tools:
    def specs(self):
        return []

    async def dispatch(self, call, ctx):
        if call.name == "get_initial_route":
            value = {"route_handle": "initial_route_1", "summary": "Initial route ready"}
        elif call.name == "generate_final_route":
            value = {
                "action": "route_updated",
                "route_handle": "route_1",
                "summary": "Trip planned",
                "route": {"geometry": "G" * 3000},
            }
        elif call.name == "generate_itinerary":
            value = {"action": "itinerary_updated", "itinerary": [{"day": "D" * 3000}]}
        else:
            value = {"action": "trip_profile_updated", "trip_profile": {"num_stops": 3}}
        return ToolResult(name=call.name, ok=True, result=value)


def baseline_builder():
    source = subprocess.check_output(
        ["git", "show", f"{BASELINE_REF}:backend/app/agent/prompt.py"],
        cwd=ROOT,
        text=True,
    )
    module = ModuleType("baseline_prompt")
    exec(compile(source, "baseline_prompt.py", "exec"), module.__dict__)
    return module.build_messages


def cases():
    complete = TripProfile(
        start_address="Denver",
        start_coords=[39.7, -105.0],
        destination_address="Moab",
        destination_coords=[38.6, -109.5],
        num_stops=3,
        budget=150,
        start_date="2099-10-10T09:00:00",
        car_status="skipped",
    )
    return [
        ("collecting", TripProfile(), "Plan a scenic trip", False, ["Where are you starting?"]),
        (
            "correcting",
            complete,
            "Actually make it three stops",
            False,
            [
                tool_block("update_trip_profile", {"num_stops": 3}),
                "Updated to three stops.",
            ],
        ),
        (
            "completing",
            complete,
            "Finish my trip",
            False,
            [
                tool_block("get_initial_route"),
                tool_block("generate_final_route", {"route_handle": "initial_route_1"}),
                tool_block("generate_itinerary", {"route_handle": "route_1"}),
                "Your trip is ready.",
            ],
        ),
        (
            "revising",
            complete,
            "Revise this trip for three stops",
            True,
            [
                tool_block("update_trip_profile", {"num_stops": 3}),
                tool_block("generate_final_route"),
                tool_block("generate_itinerary", {"route_handle": "route_1"}),
                "Your revised trip is ready.",
            ],
        ),
    ]


async def run_case(name, trip, message, has_route, responses):
    provider = ScriptedProvider(responses)
    result = await agent.run_turn(
        AgentChatRequest(
            partitionKey="fixture",
            chatId="42",
            message=message,
            clientContext=AgentClientContext(hasRoute=has_route),
        ),
        provider,
        Memory(trip),
        Tools(),
    )
    completed = [action.type for action in result.actions][-2:] == [
        "route_updated",
        "itinerary_updated",
    ] and not result.toolErrors
    return {
        "case": name,
        "prompt_token_proxy": result.usage.promptTokens,
        "model_calls": result.modelCalls,
        "trip_completed": completed,
    }


async def main():
    original_builder = agent.build_messages
    original_limit = agent.RECENT_MESSAGE_LIMIT
    original_auth = agent.get_user_id_from_token
    agent.get_user_id_from_token = lambda _: "fixture-user"
    try:
        for label, builder, limit in (
            ("before", baseline_builder(), 10),
            ("after", original_builder, 6),
        ):
            agent.build_messages = builder
            agent.RECENT_MESSAGE_LIMIT = limit
            rows = [await run_case(*case) for case in cases()]
            print(json.dumps({"version": label, "samples": rows}))
    finally:
        agent.build_messages = original_builder
        agent.RECENT_MESSAGE_LIMIT = original_limit
        agent.get_user_id_from_token = original_auth


if __name__ == "__main__":
    asyncio.run(main())
