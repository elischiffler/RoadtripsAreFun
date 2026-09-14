"""Tests for the system prompt + context assembly (``app/agent/prompt.py``).

Focus: internal context (the client UI hint, trip-profile internals, tool
mechanics) must never be presented to the user. These pin the contract so a
regression that reintroduces the leak — e.g. the bot reciting "the client UI
hint had 1 stop and a $0 budget" — fails a test instead of shipping.
"""

from __future__ import annotations

from app.agent.memory import ConversationMemory, MemoryFact
from app.agent.prompt import (
    SYSTEM_PROMPT,
    _format_client_context,
    _format_context,
    build_messages,
)
from app.agent.schemas import AgentClientContext
from app.agent.trip_profile import TripProfile

# --------------------------------------------------------------------------- #
# System prompt carries the non-recitation rule
# --------------------------------------------------------------------------- #


def test_system_prompt_forbids_reciting_internal_context():
    text = SYSTEM_PROMPT.lower()
    # The agent is told never to quote/recite its internal context to the user.
    assert "never recite" in text
    assert "client ui hint" in text
    # A default/zero hint must not be repeated back as if it were a preference.
    assert "not a real user preference" in text


# --------------------------------------------------------------------------- #
# The rendered hint is labelled INTERNAL / do-not-quote
# --------------------------------------------------------------------------- #


def test_client_context_hint_is_labelled_internal():
    hint = _format_client_context(AgentClientContext(hasRoute=True, stops=1, hotelBudget=0))
    assert hint is not None
    assert "INTERNAL" in hint
    # The advisory framing and the actual (advisory) values are still present for
    # the model to weigh — it just may not read them back to the user.
    assert "advisory" in hint.lower()
    assert "stops=1" in hint
    assert "hotelBudget=0" in hint


def test_client_context_none_when_absent():
    assert _format_client_context(None) is None


# --------------------------------------------------------------------------- #
# Trip-profile + facts blocks are labelled INTERNAL / never-recite
# --------------------------------------------------------------------------- #


def test_trip_profile_block_is_labelled_internal():
    trip = TripProfile(start_address="482 Luneta Dr", start_coords=[35.28, -120.66], num_stops=3)
    rendered = _format_context(facts=[], trip=trip)
    # The block that carries field names + raw coordinates is marked internal so
    # the model doesn't read it back verbatim.
    assert "INTERNAL" in rendered
    assert "never quote field names or raw coordinates" in rendered


def test_facts_block_is_labelled_internal():
    facts = [MemoryFact(key="home_city", value="Boston, MA")]
    rendered = _format_context(facts=facts, trip=None)
    assert "INTERNAL" in rendered
    assert "home_city" in rendered  # still present for the model to use


def test_empty_context_is_neutral_and_carries_no_internals():
    rendered = _format_context(facts=[], trip=None)
    assert rendered == "Nothing gathered for this trip yet."


def test_conversation_summary_is_labelled_internal_in_messages():
    conversation = ConversationMemory(chat_id="42", summary="User wants a coastal route.")
    messages = build_messages(
        facts=[],
        conversation=conversation,
        recent_turns=[],
        user_message="continue",
        trip=None,
        client_context=None,
    )
    system = "\n\n".join(m.content for m in messages if m.role == "system")
    assert "Summary of earlier conversation" in system
    assert "INTERNAL" in system
    assert "do not recite this back to the user" in system


# --------------------------------------------------------------------------- #
# The hint is placed in a SYSTEM message, not surfaced as user-visible content
# --------------------------------------------------------------------------- #


def test_hint_lives_in_system_message_only():
    messages = build_messages(
        facts=[],
        conversation=None,
        recent_turns=[],
        user_message="Let's plan a trip",
        trip=None,
        client_context=AgentClientContext(hasRoute=False, stops=1, hotelBudget=0),
    )
    # The hint text rides along in the system prompt...
    system = "\n\n".join(m.content for m in messages if m.role == "system")
    assert "Client UI hint" in system
    assert "INTERNAL" in system
    # ...and never as the user turn the model is answering.
    user_contents = [m.content for m in messages if m.role == "user"]
    assert user_contents == ["Let's plan a trip"]
