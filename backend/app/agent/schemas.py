"""Pydantic v2 models for the chat agent (contracts 1 and 1b).

This module also owns the **shared tool primitives** (:class:`ToolSpec`,
:class:`ToolCall`, :class:`ToolResult`). The design doc (§5) lists these under
``tools.py``, but :class:`LLMMessage` / :class:`LLMResponse` (§6, defined here)
reference :class:`ToolCall`, and ``tools.py`` also needs them — putting them in
one low-level module avoids an import cycle. ``tools.py`` re-exports them so the
doc's ``tools.py`` surface is preserved. This is the clean decision called for
by the Stream A brief.

Contracts implemented:
- §3  — :class:`AgentClientContext`, :class:`AgentChatRequest`,
        :class:`AgentAction`, :class:`AgentUsage`, :class:`AgentChatResponse`
- §5  — :class:`ToolSpec`, :class:`ToolCall`, :class:`ToolResult`
- §6  — :class:`LLMMessage`, :class:`LLMResponse`
"""

from __future__ import annotations

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------- #
# Shared tool primitives (design doc §5) — live here to avoid an import cycle
# with the provider/message models below. Re-exported from ``tools.py``.
# --------------------------------------------------------------------------- #


class ToolSpec(BaseModel):
    """Advertised tool: name, description, and JSON-Schema parameters.

    This is the shape LLM function-calling APIs expect when told which tools are
    available.
    """

    name: str
    description: str
    parameters: dict  # JSON Schema for the arguments


class ToolCall(BaseModel):
    """A tool invocation requested by the model."""

    name: str
    arguments: dict = Field(default_factory=dict)


class ToolResult(BaseModel):
    """The outcome of dispatching a :class:`ToolCall`.

    Tool failures are captured as ``ok=False`` with an ``error`` string and fed
    back to the model rather than raised — the agent can retry, pick another
    tool, or explain.
    """

    name: str
    ok: bool
    result: dict | None = None
    error: str | None = None


# --------------------------------------------------------------------------- #
# Contract 1 — Agent request/response (backend <-> frontend), design doc §3
# --------------------------------------------------------------------------- #


class AgentClientContext(BaseModel):
    """Best-effort UI hint about current trip state.

    Purely advisory — never trusted for server-side state (the server reads the
    DB as the source of truth).
    """

    hasRoute: bool = False
    stops: int | None = None
    hotelBudget: int | None = None


class AgentChatRequest(BaseModel):
    """``POST /agent/chat`` request body.

    ``partitionKey`` is decoded server-side to ``user_id`` via
    ``app.utils.auth.get_user_id_from_token``. The frontend does not send
    history — the server rehydrates conversation context from persistence.
    """

    partitionKey: str
    chatId: str
    message: str
    clientContext: AgentClientContext | None = None


class AgentAction(BaseModel):
    """A structured side effect the UI may apply (e.g. ``route_updated``)."""

    type: str
    chatId: str | None = None
    payload: dict | None = None


class AgentUsage(BaseModel):
    """Best-effort token accounting; may be ``None`` when a provider omits it."""

    promptTokens: int | None = None
    completionTokens: int | None = None


class AgentToolError(BaseModel):
    """A tool that failed during the turn, surfaced for client-side debugging.

    Tool failures are fed back to the model (not raised), so they don't appear in
    ``actions``. Echoing them here lets the frontend log *why* an attempted tool
    (e.g. ``update_trip_profile``) didn't apply — without digging in server logs.
    """

    name: str
    error: str


class AgentChatResponse(BaseModel):
    """``POST /agent/chat`` response body."""

    reply: str
    toolsUsed: list[str] = Field(default_factory=list)
    toolErrors: list[AgentToolError] = Field(default_factory=list)
    actions: list[AgentAction] = Field(default_factory=list)
    provider: str | None = None
    usage: AgentUsage | None = None


# --------------------------------------------------------------------------- #
# Contract 1b — Provider fallback chain messages (design doc §6)
# --------------------------------------------------------------------------- #


class LLMMessage(BaseModel):
    """One message in a provider conversation.

    ``role`` is one of ``"system" | "user" | "assistant" | "tool"``.
    ``tool_calls`` is set on assistant turns that request tools; ``tool_call_id``
    links a ``tool`` result back to the call that produced it.
    """

    role: str
    content: str = ""
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


class LLMResponse(BaseModel):
    """Normalized provider output — every provider maps its API shape into this."""

    content: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    provider: str = ""
    usage: AgentUsage | None = None
