"""Small, stage-specific instructions and bounded conversation context."""

from __future__ import annotations

import re

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

Use update_trip_profile to record details the traveler gives. Validate a location before recording its coordinates; copy only numeric coordinates returned by validate_location. For a finished trip, get_initial_route with validated endpoints, then generate_final_route with its handle, then generate_itinerary with the new handle. Use get_account_persona for cross-chat preferences; update_account_persona only when explicitly asked to save them for future trips. For this trip, use update_trip_profile with persona_weights. Only use persona keys advertised by the tools. Tell the traveler about hotel budget warnings from a planned route."""

STAGE_INSTRUCTIONS = {
    "collecting": "Stage: collect details. Need start, destination, 1–10 attraction stops, nightly hotel budget, and an upcoming start date (9 AM departure by default). Ask for one or two missing details at a time. Validate each new location first, then save its address and returned coordinates with update_trip_profile. Save other supplied details immediately. Do not ask again for values already in the profile. When complete, proceed to the route tools.",
    "correcting": "Stage: correct input. Apply the traveler's change with update_trip_profile. If a location changed, validate it first and record the returned coordinates; never reuse coordinates from the old location. Ask only for missing or ambiguous information. If the trip is complete, continue planning with the corrected profile.",
    "completing": "Stage: complete the trip. The profile has the required details. Call get_initial_route with both validated coordinate pairs, then generate_final_route with its route_handle, then generate_itinerary with the new route_handle. Calls are sequential. Only say the trip is ready after the itinerary succeeds. If a tool fails, explain the blocker.",
    "revising": "Stage: revise an existing trip. Record requested changes in the profile, validating changed locations first. Then regenerate the route with generate_final_route (it can rebuild the initial route from profile coordinates) and call generate_itinerary with the new route_handle. If the traveler only asks a question, answer it without rebuilding. Never claim the revision succeeded before both tools succeed.",
}

_CORRECTION = re.compile(
    r"\b(?:actually|instead|change|correct|make it|switch|rather than|update)\b", re.I
)


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
        )
    )
    if ctx is not None and ctx.hasRoute and has_required_details:
        return "revising"
    if _CORRECTION.search(user_message):
        return "correcting"
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
            )
            if key in p
        ]
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
