"""Shared fixtures/fakes for chat-agent tests.

Mirrors ``tests/routing/conftest.py``: the agent loop reaches providers, memory,
and tools only through injected interfaces, so these fakes let every test run
with no network and no DB. This is the fake-injection template for the agent.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.agent.memory import ConversationMemory, MemoryFact
from app.agent.schemas import (
    AgentUsage,
    LLMMessage,
    LLMResponse,
    ToolCall,
    ToolResult,
    ToolSpec,
)
from app.agent.tools import ToolContext


@pytest.fixture(autouse=True)
def _routing_local(monkeypatch):
    """Force the routing tools onto the LOCAL path for all agent tests.

    ``ROUTING_REMOTE_URL`` may be set in the developer's real ``.env`` (B1 remote
    proxy). Without pinning it off, tests that monkeypatch the *local* routing
    functions would silently hit the real deployed backend instead. Tests that
    specifically exercise the remote path (``routing_remote_tests.py``) set the
    URL explicitly, overriding this default.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "ROUTING_REMOTE_URL", None, raising=False)


class FakeProvider:
    """Returns canned :class:`LLMResponse` objects.

    Pass a list of responses to script a multi-step tool loop (one response per
    provider call). ``configured`` and ``fail`` let tests exercise the fallback
    chain's skip / advance behavior.
    """

    def __init__(
        self,
        name: str = "fake",
        responses: list[LLMResponse] | None = None,
        configured: bool = True,
        fail: bool = False,
        error: Exception | None = None,
    ):
        self.name = name
        self._responses = list(responses or [LLMResponse(content="Hi there!")])
        self._configured = configured
        self._fail = fail
        self._error = error
        self.calls = 0
        # Capture the message list passed to each provider call so tests can
        # assert what context (recent turns, summary, facts) was assembled.
        self.seen_messages: list[list[LLMMessage]] = []

    def configured(self) -> bool:
        return self._configured

    def complete(self, messages: list[LLMMessage], tools: list[ToolSpec]) -> LLMResponse:
        self.calls += 1
        self.seen_messages.append(list(messages))
        if self._fail:
            from app.agent.providers import ProviderError

            raise self._error or ProviderError(f"{self.name} failed")
        # Serve the next scripted response; repeat the last one after exhaustion.
        idx = min(self.calls - 1, len(self._responses) - 1)
        response = self._responses[idx].model_copy(deep=True)
        if not response.provider:
            response.provider = self.name
        return response


class FakeMemory:
    """In-memory :class:`MemoryStore`."""

    def __init__(
        self,
        facts: list[MemoryFact] | None = None,
        recent_turns: list[LLMMessage] | None = None,
        raise_on_save: bool = False,
    ):
        self._facts: dict[str, list[MemoryFact]] = {}
        if facts:
            self._facts["_seed"] = facts
        self._conversations: dict[tuple[str, str], ConversationMemory] = {}
        self.saved_conversations: list[ConversationMemory] = []
        self.upserted: list[MemoryFact] = []
        # Per-chat trip-profile JSON strings, keyed by (user_id, chat_id).
        self._trip_profiles: dict[tuple[str, str], str] = {}
        self._seed = facts or []
        # Optional short-term window (verbatim recent turns). When set, this fake
        # satisfies the loop's duck-typed ``load_recent_turns`` probe.
        self._recent_turns = list(recent_turns) if recent_turns is not None else None
        self._raise_on_save = raise_on_save

    def load_facts(self, user_id: str) -> list[MemoryFact]:
        return list(self._facts.get(user_id, self._seed))

    def upsert_facts(self, user_id: str, facts: list[MemoryFact]) -> None:
        self._facts.setdefault(user_id, list(self._seed)).extend(facts)
        self.upserted.extend(facts)

    def load_conversation(self, user_id: str, chat_id: str) -> ConversationMemory:
        return self._conversations.get(
            (user_id, chat_id),
            ConversationMemory(chat_id=chat_id, updated_at=datetime.now(UTC)),
        )

    def save_conversation(self, user_id: str, chat_id: str, mem: ConversationMemory) -> None:
        if self._raise_on_save:
            raise RuntimeError("simulated save_conversation failure")
        self._conversations[(user_id, chat_id)] = mem
        self.saved_conversations.append(mem)

    def load_trip_profile(self, user_id: str, chat_id: str) -> str | None:
        return self._trip_profiles.get((user_id, chat_id))

    def save_trip_profile(self, user_id: str, chat_id: str, profile_json: str) -> None:
        self._trip_profiles[(user_id, chat_id)] = profile_json

    def load_recent_turns(self, user_id: str, chat_id: str, limit: int = 10) -> list[LLMMessage]:
        if self._recent_turns is None:
            return []
        return list(self._recent_turns[-limit:])


class FakeTools:
    """In-memory :class:`ToolDispatcher`.

    Records dispatched calls and returns a canned result per tool name. Unknown
    tools return ``ok=True`` with a generic echo so the loop keeps progressing.
    """

    def __init__(
        self,
        specs: list[ToolSpec] | None = None,
        results: dict[str, ToolResult] | None = None,
    ):
        self._specs = list(specs or [])
        self._results = dict(results or {})
        self.dispatched: list[ToolCall] = []

    def specs(self) -> list[ToolSpec]:
        return list(self._specs)

    async def dispatch(self, call: ToolCall, ctx: ToolContext) -> ToolResult:
        self.dispatched.append(call)
        if call.name in self._results:
            return self._results[call.name]
        return ToolResult(name=call.name, ok=True, result={"echo": call.arguments})


def make_usage(prompt: int = 100, completion: int = 20) -> AgentUsage:
    return AgentUsage(promptTokens=prompt, completionTokens=completion)


@pytest.fixture
def fake_memory():
    return FakeMemory()


@pytest.fixture
def fake_tools():
    return FakeTools()
