"""Thin router: ``POST /agent/chat`` (design doc §3, §7).

Keeps the controller thin — it validates the request, builds the injected
dependencies (provider chain + memory + tools) via a dependency function, calls
``run_turn``, and maps errors. All logic lives in ``app/agent/``.

For Stream A the memory and tool dependencies are placeholders: an in-memory
no-op ``MemoryStore`` and an empty ``ToolDispatcher``. Stream B swaps in the
Postgres-backed ``memory_crud`` store and Stream A-tools swaps in the real
dispatcher — neither requires a change to this router.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from app.agent.agent import run_turn
from app.agent.memory import ConversationMemory, MemoryFact, MemoryStore
from app.agent.providers import ProvidersExhausted, build_default_chain
from app.agent.schemas import AgentChatRequest, AgentChatResponse
from app.agent.tool_dispatcher import AppToolDispatcher
from app.agent.tools import ToolCall, ToolContext, ToolDispatcher, ToolResult, ToolSpec
from app.crud.memory_crud import MemoryCrudStore

router = APIRouter()
logger = logging.getLogger(__name__)


class _NullMemory:
    """Placeholder ``MemoryStore``: no facts, empty conversation, no writes.

    Real persistence arrives with Stream B (``crud/memory_crud.py``).
    """

    def load_facts(self, user_id: str) -> list[MemoryFact]:
        return []

    def upsert_facts(self, user_id: str, facts: list[MemoryFact]) -> None:
        return None

    def load_conversation(self, user_id: str, chat_id: str) -> ConversationMemory:
        return ConversationMemory(chat_id=chat_id, updated_at=datetime.now(timezone.utc))

    def save_conversation(self, user_id: str, chat_id: str, mem: ConversationMemory) -> None:
        return None


class _EmptyTools:
    """Placeholder ``ToolDispatcher``: advertises no tools.

    Real tool bodies arrive with Stream A-tools (``agent/tools.py`` dispatcher).
    """

    def specs(self) -> list[ToolSpec]:
        return []

    async def dispatch(self, call: ToolCall, ctx: ToolContext) -> ToolResult:
        return ToolResult(name=call.name, ok=False, error="No tools are wired yet.")


def get_agent_dependencies() -> tuple[object, MemoryStore, ToolDispatcher]:
    """Build the injected loop dependencies.

    Uses the real provider chain, the Postgres-backed ``MemoryCrudStore``
    (Stream B), and the real ``AppToolDispatcher`` (Stream A-tools). Still
    overridable in tests via FastAPI's ``dependency_overrides`` to inject fakes;
    the ``_NullMemory`` / ``_EmptyTools`` placeholders remain for that purpose.
    """
    return build_default_chain(), MemoryCrudStore(), AppToolDispatcher()


@router.post("/agent/chat", response_model=AgentChatResponse)
async def agent_chat(
    request: AgentChatRequest,
    deps: tuple = Depends(get_agent_dependencies),
) -> AgentChatResponse:
    """Handle one conversational turn."""
    providers, memory, tools = deps
    try:
        return await run_turn(request, providers, memory, tools)
    except ProvidersExhausted as exception:
        logger.error("All LLM providers exhausted: %s", exception)
        raise HTTPException(
            status_code=503, detail="No language model provider is available right now."
        )
    except ValidationError as exception:
        raise HTTPException(status_code=422, detail=f"Error validating request: {exception}")
    except Exception:  # noqa: BLE001
        # A turn should fail gracefully (tool errors are already captured inside
        # the loop), but never leak a raw 500. Map any unexpected fault to a 503
        # so the client shows "try again" instead of an Internal Server Error.
        logger.exception("agent_chat: unexpected failure serving the turn")
        raise HTTPException(
            status_code=503, detail="The assistant hit a temporary problem. Please try again."
        )
