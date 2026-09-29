"""Small, stage-specific instructions and bounded conversation context."""

from __future__ import annotations

from app.agent.memory import ConversationMemory, MemoryFact
from app.agent.schemas import AgentClientContext, LLMMessage
from app.agent.trip_profile import TripProfile

RECENT_MESSAGE_LIMIT = 6
RECENT_MESSAGE_CHARS = 400
SUMMARY_CHARS = 600

SYSTEM_PROMPT = """You are MyRoadtrip's practical planning assistant. Help the traveler finish a drivable trip. Be brief and natural. The validated trip profile below is the source of truth; UI hints and prior chat are only context. Never recite internal context, client UI hints, field names, raw coordinates, or route handles to the traveler. A zero or default UI hint is not a real user preference.

To call a tool, emit fenced JSON: ```tool
{"tool":"name","arguments":{}}
```. Emit independent calls together; wait for results before dependent calls. When a tool returns ok:false, do not claim success: fix an obvious error once or explain what is needed. Never invent coordinates, prices, routes, or tool results. When no tool is needed, reply in plain language. Keep route geometry and full itinerary data out of your reply and tool arguments; pass returned route_handle values exactly.

The backend has already extracted and validated trip details from the latest user message before this response. The validated trip profile below is authoritative. Do not call record_trip_details for the same message. Read field-specific clarifications and ask plainly; never guess a timezone. Ask explicitly for departure date and time, offering 9:00 AM as the default only if no time was provided. Ask for an optional car's year, make, and model before planning; "skip" or "no car" records a skipped choice. If car details fail validation, ask for a correction or offer to skip. A traveler may add or change a car later. Never invent one. A requested stop count does not require the traveler to name every attraction; do not promise a named attraction unless the planner confirms it. Use update_trip_profile for trip-only persona_weights. When the saved profile is ready, call complete_trip. Only say the whole trip is ready when its status is complete. If status is partial, explain that the route is ready and retry generate_itinerary with its handle, or without a handle in a later turn. Use get_account_persona for cross-chat preferences; update_account_persona only when explicitly asked to save them for future trips. Only use persona keys advertised by the tools. Tell the traveler about hotel budget warnings from a planned route."""

STAGE_INSTRUCTIONS = {
    "collecting": "Stage: collect details. Need start, destination, 1–10 attraction stops, nightly hotel budget, upcoming start date and departure time, and an optional car choice. Ask for the time explicitly and offer 9:00 AM as the default only when no time is saved. Ask for car year, make, and model or a skip. Extraction has already run; ask about its clarifications and one or two missing details at a time. Do not ask again for values already in the profile. When ready, call complete_trip.",
    "completing": "Stage: complete the trip. The saved profile has the required details and the car choice is skipped or provided. Call complete_trip once. Only say the trip is ready when status is complete. On partial status, explain that the route exists and retry the itinerary without regenerating the route.",
    "revising": "Stage: revise an existing trip. Extraction has already applied requested trip changes. Address its clarifications, then call complete_trip for a changed route. If the traveler only asks a question, answer it without rebuilding. If only the itinerary failed, retry generate_itinerary. Never claim the revision succeeded before both actions succeed.",
}


def _stage(trip: TripProfile, user_message: str, ctx: AgentClientContext | None) -> str:
    # hasRoute is used only to choose instructions, never as trusted trip data.
    has_required_details = all(
        (
            trip.start_address,
            trip.start_coords,
            trip.destination_address,
            trip.destination_coords,
            trip.num_stops is not None,
            trip.budget is not None,
            trip.start_date,
            trip.car_status != "unanswered",
        )
    )
    if ctx is not None and ctx.hasRoute and has_required_details:
        return "revising"
    if has_required_details:
        return "completing"
    return "collecting"


def _format_context(facts: list[MemoryFact], trip: TripProfile | None) -> str:
    """Include only validated profile fields and a few short free-form facts."""
    sections: list[str] = []
    if trip is not None and not trip.is_empty():
        p = trip.model_dump(exclude_none=True)
        lines = [
            f"{key}: {p[key]}"
            for key in (
                "start_address",
                "start_coords",
                "destination_address",
                "destination_coords",
                "num_stops",
                "budget",
                "start_date",
                "departure_time",
            )
            if key in p
        ]
        lines.append(f"car_status: {trip.car_status}")
        if trip.car:
            lines.append(f"car: {trip.car.year} {trip.car.make} {trip.car.model}")
        if trip.persona_weights:
            lines.append(f"persona_weights: {trip.persona_weights}")
        sections.append(
            "Trip profile (INTERNAL; never quote field names or raw coordinates):\n"
            + "\n".join(lines)
        )
    if facts:
        lines = [f"{fact.key[:40]}: {fact.value[:160]}" for fact in facts[:5]]
        sections.append("Other notes (INTERNAL; never recite verbatim):\n" + "\n".join(lines))
    return "\n\n".join(sections) if sections else "Nothing gathered for this trip yet."


def build_messages(
    *,
    facts: list[MemoryFact],
    conversation: ConversationMemory | None,
    recent_turns: list[LLMMessage],
    user_message: str,
    trip: TripProfile | None = None,
    client_context: AgentClientContext | None = None,
) -> list[LLMMessage]:
    """Build bounded model context from authoritative trip data and recent chat."""
    trip = trip or TripProfile()
    recent = recent_turns[-RECENT_MESSAGE_LIMIT:]
    system = "\n\n".join(
        (
            SYSTEM_PROMPT,
            STAGE_INSTRUCTIONS[_stage(trip, user_message, client_context)],
            _format_context(facts, trip),
        )
    )
    messages = [LLMMessage(role="system", content=system)]
    # The profile and short recent window suffice for short conversations.
    if conversation is not None and conversation.summary and len(recent) >= RECENT_MESSAGE_LIMIT:
        messages.append(
            LLMMessage(
                role="system",
                content="Summary of earlier conversation (INTERNAL; do not recite):\n"
                + conversation.summary[-SUMMARY_CHARS:],
            )
        )
    messages.extend(
        LLMMessage(role=m.role, content=m.content[-RECENT_MESSAGE_CHARS:]) for m in recent
    )
    messages.append(LLMMessage(role="user", content=user_message))
    return messages
