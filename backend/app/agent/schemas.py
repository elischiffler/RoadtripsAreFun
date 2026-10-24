"""Shared AI provider messages, tool descriptions and usage accounting."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    """Advertised tool: name, description, and JSON-Schema parameters.

    This is the shape LLM function-calling APIs expect when told which tools are
    available.
    """

    name: str
    description: str
    parameters: dict


class ToolCall(BaseModel):
    """A tool invocation requested by the model."""

    name: str
    arguments: dict = Field(default_factory=dict)


class AgentUsage(BaseModel):
    """Best-effort token accounting; may be ``None`` when a provider omits it."""

    promptTokens: int | None = None
    completionTokens: int | None = None


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
    model: str | None = None
    usage: AgentUsage | None = None
