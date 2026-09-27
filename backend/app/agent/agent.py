"""The agent loop (design doc §7).

``run_turn`` turns one free-text user message into an :class:`AgentChatResponse`.
Every dependency — the provider chain, the memory store, the tool dispatcher —
is injected, so the whole loop is unit-testable with fakes (no network, no DB),
mirroring the routing layer's ``RoutingServices`` pattern.

Stream A owns the loop structure. Memory persistence (``memory_crud``) and real
tool bodies come from other streams; the loop depends only on the
:class:`~app.agent.memory.MemoryStore` and
:class:`~app.agent.tools.ToolDispatcher` Protocols.

The integration pass wires memory write-back (design doc §7 step 6): after the
tool loop produces the reply, the loop extracts durable facts and rolls the
conversation summary through the injected ``MemoryStore``. Write-back is
best-effort — a persistence failure never breaks the user-facing reply. The
verbatim ``ChatLog`` is owned by the frontend and is NOT written here.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.agent import debug
from app.agent.memory import ConversationMemory, MemoryStore
from app.agent.prompt import build_messages
from app.agent.providers import LLMProvider
from app.agent.schemas import (
    AgentAction,
    AgentChatRequest,
    AgentChatResponse,
    AgentToolError,
    LLMMessage,
    ToolResult,
)
from app.agent.toolcall_parser import parse_tool_calls, strip_tool_blocks
from app.agent.tools import ToolContext, ToolDispatcher
from app.agent.trip_profile import TripProfile
from app.utils.auth import get_user_id_from_token

logger = logging.getLogger(__name__)

# Hard cap on the tool loop so a model that keeps requesting tools always
# terminates (design doc §7 step 5).
MAX_TOOL_ITERATIONS = 5

# Substrings that only appear in our INTERNAL system context — if any of these
# surface in the user-facing reply, the model recited internal directions
# instead of talking to the traveler. Used by ``_scan_reply_for_leaks`` as a
# monitor (it logs; it does not rewrite the reply).
_INTERNAL_REPLY_MARKERS = (
    "client ui hint",
    "trip profile",
    "trip_profile",
    "route_handle",
    "start_coords",
    "destination_coords",
    "num_stops",
    "summary of earlier conversation",
    "```tool",
)

# When the verbatim recent window reaches this many turns, roll the conversation
# summary (design doc §7 step 6). The verbatim window itself lives in the
# frontend-owned ``ChatLog``; this only governs when we fold older context into
# the rolling ``ConversationMemory.summary``.
SUMMARY_WINDOW = 10

# Bound the rolling summary so it can never blow the context window. When a new
# note would push past this, the oldest characters are dropped.
_MAX_SUMMARY_CHARS = 2000


def _load_recent_turns(memory: MemoryStore, user_id: str, chat_id: str) -> list[LLMMessage]:
    """Best-effort verbatim recent window.

    The verbatim window comes from the existing ``ChatLog`` (via ``chat_crud``),
    which the real integration will feed in. Stream A depends only on the
    ``MemoryStore`` Protocol, so recent turns are empty here unless a fake
    memory chooses to expose them.
    """
    getter = getattr(memory, "load_recent_turns", None)
    if callable(getter):
        return list(getter(user_id, chat_id))
    return []


def _load_trip(memory: MemoryStore, user_id: str, chat_id: str) -> TripProfile:
    """Best-effort load of this chat's trip profile (empty on any failure).

    Used only for the debug snapshot, so a fake memory without
    ``load_trip_profile`` (or a transient failure) degrades to an empty profile
    rather than breaking the turn.
    """
    getter = getattr(memory, "load_trip_profile", None)
    if not callable(getter):
        return TripProfile()
    try:
        return TripProfile.from_json(getter(user_id, chat_id))
    except Exception:  # debug-only; never break a turn
        return TripProfile()


def _scan_reply_for_leaks(reply: str, trip: TripProfile, chat_id: str = "") -> list[str]:
    """Monitor: detect INTERNAL context that leaked into the user-facing reply.

    "Directions we send to the AI" — the client UI hint, the trip-profile
    internals (field names + raw coordinates), the rolling summary, and the tool
    protocol — are meant for the model, not the traveler. The system prompt tells
    the model never to recite them, but a model may disobey. This is the backstop
    that *notices* when it does: it returns the list of leak markers found (also
    logging a warning) so the leak is observable instead of silent.

    Purely observational — it never rewrites the reply. Detection over mutation:
    quietly editing model output risks corrupting a legitimate answer, so we
    surface the problem for the prompt/tests to address rather than mask it.
    """
    if not reply:
        return []
    lowered = reply.lower()
    hits = [marker for marker in _INTERNAL_REPLY_MARKERS if marker in lowered]

    # Raw coordinates from THIS chat's trip profile are the sharpest signal: an
    # address paraphrase is fine, but echoing "[35.28, -120.66]" is an internal
    # representation the traveler should never see.
    for coords in (trip.start_coords, trip.destination_coords):
        if coords and len(coords) >= 2:
            lat, lon = coords[0], coords[1]
            if str(lat) in reply and str(lon) in reply:
                hits.append(f"raw_coords({lat},{lon})")

    if hits:
        # Log only the detected marker NAMES and the chat correlation id — never
        # the reply text itself, which is user-facing content that may include
        # the very coordinates/PII we're flagging.
        logger.warning(
            "Reply may leak internal context to the user for chat_id=%s (markers=%s). "
            "The model recited directions meant only for it; reply left unchanged.",
            chat_id or "?",
            hits,
        )
    return hits


def _roll_summary(
    conversation: ConversationMemory, user_message: str, reply: str
) -> ConversationMemory:
    """Deterministically roll the rolling conversation summary (design §7 step 6).

    v1 does NOT call the LLM again to summarize — that would be dishonest (a
    fabricated "summary") and out of scope for this integration pass. Instead we
    append a compact, truthful note of the latest exchange, keep the summary
    bounded (dropping the oldest characters past ``_MAX_SUMMARY_CHARS``), bump
    ``summary_turn_count``, and refresh ``updated_at``.

    LLM-based abstractive summarization is a documented future improvement
    (design doc §10). The note is intentionally terse so the bound holds for
    long chats.
    """
    note = f"User: {user_message.strip()} | Assistant: {reply.strip()}"
    summary = (conversation.summary + "\n" + note).strip() if conversation.summary else note
    if len(summary) > _MAX_SUMMARY_CHARS:
        # Drop the oldest characters so the newest exchange always survives.
        summary = summary[-_MAX_SUMMARY_CHARS:]
    return conversation.model_copy(
        update={
            "summary": summary,
            "summary_turn_count": conversation.summary_turn_count + 1,
            "updated_at": datetime.now(UTC),
        }
    )


def _persist_memory(
    *,
    memory: MemoryStore,
    user_id: str,
    chat_id: str,
    user_message: str,
    reply: str,
    conversation: ConversationMemory,
    recent_turns: list[LLMMessage],
) -> None:
    """Best-effort memory write-back after a turn (design doc §7 step 6).

    Two writes, both through the injected ``MemoryStore``:
      a. Fact auto-extraction -> ``upsert_facts`` (extractor is a stub today).
      b. Rolling conversation summary -> ``save_conversation``, but only once the
         verbatim recent window reaches ``SUMMARY_WINDOW`` turns.

    The verbatim ``ChatLog`` is NOT written here — the frontend owns that. Any
    failure is logged and swallowed; the reply is the product.
    """
    try:
        # a. Trip/preference capture is now TOOL-DRIVEN: the agent calls
        #    ``update_trip_profile`` / ``remember_fact`` during the turn (no extra
        #    LLM call). So there is no separate extraction pass here — those writes
        #    already happened through the tool dispatcher.
        #
        # b. Roll the summary once the verbatim window is large enough.
        if len(recent_turns) >= SUMMARY_WINDOW:
            rolled = _roll_summary(conversation, user_message, reply)
            memory.save_conversation(user_id, chat_id, rolled)
    except Exception as exc:  # persistence is best-effort; never break the reply
        logger.warning(
            "memory write-back failed for chat_id=%s (reply still returned): %s",
            chat_id,
            exc,
        )


async def run_turn(
    request: AgentChatRequest,
    providers: LLMProvider,
    memory: MemoryStore,
    tools: ToolDispatcher,
) -> AgentChatResponse:
    """Run one conversational turn.

    Args:
        request: The validated ``POST /agent/chat`` body.
        providers: The provider chain (usually a ``FallbackChain``).
        memory: Injected memory store (facts + conversation summary).
        tools: Injected tool dispatcher.

    Returns:
        The assembled :class:`AgentChatResponse`.

    Raises:
        app.agent.providers.ProvidersExhausted: When no provider can serve the
            request. The router maps this to HTTP 503.
    """
    # 1. Resolve identity.
    user_id = get_user_id_from_token(request.partitionKey)
    chat_id = request.chatId
    debug.turn_start(user_id, chat_id, request.message)

    # 2. Load memory.
    facts = memory.load_facts(user_id)
    conversation = memory.load_conversation(user_id, chat_id)
    recent_turns = _load_recent_turns(memory, user_id, chat_id)
    trip = _load_trip(memory, user_id, chat_id)
    debug.trip_snapshot("before", trip)

    # 3. Assemble messages + advertise tools.
    messages = build_messages(
        facts=facts,
        trip=trip,
        conversation=conversation,
        recent_turns=recent_turns,
        user_message=request.message,
        client_context=request.clientContext,
    )
    specs = tools.specs()

    tools_used: list[str] = []
    tool_errors: list[AgentToolError] = []
    actions: list[AgentAction] = []
    ctx = ToolContext(user_id=user_id, chat_id=chat_id, memory=memory)

    # 4. First provider call.
    response = providers.complete(messages, specs)

    # 5. Tool loop — driven by the TEXT protocol, not response.tool_calls.
    # The gateway has no native function-calling, so tool requests arrive as
    # ```tool JSON blocks inside response.content (see toolcall_parser). We parse
    # them, dispatch, feed results back, and re-ask. Capped to guarantee
    # termination.
    iterations = 0
    calls = parse_tool_calls(response.content)
    while calls and iterations < MAX_TOOL_ITERATIONS:
        iterations += 1
        # Record the assistant turn that requested the tools (verbatim content,
        # so the model sees its own tool blocks in the history).
        messages.append(LLMMessage(role="assistant", content=response.content))
        for call in calls:
            result = await tools.dispatch(call, ctx)
            tools_used.append(call.name)
            debug.tool_fired(call.name, call.arguments, result.ok, result.result, result.error)
            # A failed tool is fed back to the model (not raised) and never becomes
            # an action, so record its error for the client to log/debug.
            if not result.ok and result.error:
                tool_errors.append(AgentToolError(name=call.name, error=result.error))
            _collect_action(result, chat_id, actions)
            messages.append(
                LLMMessage(
                    role="tool",
                    content=_tool_result_content(result),
                    tool_call_id=call.name,
                )
            )
        # Ask the model again now that it has the tool results.
        response = providers.complete(messages, specs)
        calls = parse_tool_calls(response.content)

    if calls:
        # Hit the cap with tool blocks still pending — stop looping and let the
        # model's last prose stand as the reply.
        logger.warning(
            "Tool loop hit the %s-iteration cap for chat_id=%s; %s tool call(s) left unrun.",
            MAX_TOOL_ITERATIONS,
            chat_id,
            len(calls),
        )

    # The user-facing reply is the model's prose with any tool blocks stripped
    # out (raw tool JSON must never surface to the traveler).
    reply = strip_tool_blocks(response.content) or ""

    # Monitor: flag (don't rewrite) any INTERNAL context that leaked into the
    # reply — the client hint, trip-profile internals, raw coords, tool syntax.
    _scan_reply_for_leaks(reply, trip, chat_id)

    # 6. Persist memory (best-effort). Fact extraction + rolling summary go
    # through the injected MemoryStore. We do NOT write the verbatim ChatLog —
    # the frontend owns that write. A persistence failure must never break the
    # reply, so this is wrapped and swallowed with a warning.
    _persist_memory(
        memory=memory,
        user_id=user_id,
        chat_id=chat_id,
        user_message=request.message,
        reply=reply,
        conversation=conversation,
        recent_turns=recent_turns,
    )

    # 7. Return.
    if debug.enabled():
        debug.trip_snapshot("after", _load_trip(memory, user_id, chat_id))
        debug.turn_end(reply, tools_used, actions)
    return AgentChatResponse(
        reply=reply,
        toolsUsed=tools_used,
        toolErrors=tool_errors,
        actions=actions,
        provider=response.provider or None,
        usage=response.usage,
    )


# Bulky result keys that must NEVER be fed back into the LLM context — they hold
# raw geometry / full route / itinerary payloads that would blow the gateway's
# request-size limit (the 413). Tools that produce these also return a
# ``route_handle`` + ``summary`` for the model, and the full data still reaches
# the frontend via the action payload (see ``_collect_action``).
_MODEL_HIDDEN_KEYS = ("route", "stops", "itinerary", "coordinates", "geometry", "legs", "steps")


def _tool_result_content(result: ToolResult) -> str:
    """Serialize a tool result into COMPACT text the model reads next turn.

    Strips the bulky payload keys (kept for the frontend, not the model) so the
    message history stays small. The model still gets the handle + summary +
    scalar fields it needs to chain the next tool.
    """
    trimmed = result.model_copy(deep=True)
    if trimmed.result:
        trimmed.result = {k: v for k, v in trimmed.result.items() if k not in _MODEL_HIDDEN_KEYS}
    return trimmed.model_dump_json()


# Keys a state-mutating tool result carries that the frontend needs to write
# into ChatData so Map/Itinerary render. Since there is no GET-by-chat route
# endpoint, the payload rides back on the action itself (design doc §3).
_ACTION_PAYLOAD_KEYS = ("route", "stops", "cost", "itinerary", "trip_profile")


def _collect_action(result: ToolResult, chat_id: str, actions: list[AgentAction]) -> None:
    """Promote a successful state-mutating tool result into a typed UI action.

    A tool result may hint at a UI-visible side effect via ``result["action"]``.
    The result's trip payload (``route`` / ``itinerary`` / ``stops`` / ``cost``)
    is forwarded on the action so the client can write it into ``ChatData`` —
    there is no GET-by-chat endpoint to re-read it. Only successful results
    contribute an action; failures are fed back to the model instead.
    """
    if not result.ok or not result.result:
        return
    action_type = result.result.get("action")
    if not isinstance(action_type, str) or not action_type:
        return
    payload = {k: result.result[k] for k in _ACTION_PAYLOAD_KEYS if k in result.result}
    actions.append(AgentAction(type=action_type, chatId=chat_id, payload=payload or None))
