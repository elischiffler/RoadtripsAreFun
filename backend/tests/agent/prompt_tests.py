"""The stage-specific prompt uses validated trip state and bounded history."""

from __future__ import annotations

from app.agent.memory import ConversationMemory, MemoryFact
from app.agent.prompt import (
    RECENT_MESSAGE_CHARS,
    RECENT_MESSAGE_LIMIT,
    SUMMARY_CHARS,
    _stage,
    build_messages,
)
from app.agent.schemas import AgentClientContext, LLMMessage
from app.agent.trip_profile import TripProfile


def _complete_trip() -> TripProfile:
    return TripProfile(
        start_address="Denver",
        start_coords=[39.7, -105.0],
        destination_address="Moab",
        destination_coords=[38.6, -109.5],
        num_stops=3,
        budget=150,
        start_date="2099-10-10T09:00:00-06:00",
        car_status="skipped",
    )


def _messages(trip=None, text="Plan a trip", hint=None, recent=None, summary=""):
    return build_messages(
        facts=[],
        trip=trip,
        user_message=text,
        client_context=hint,
        recent_turns=recent or [],
        conversation=ConversationMemory(chat_id="42", summary=summary),
    )


def test_stage_uses_validated_profile_and_change_intent():
    trip = _complete_trip()
    assert _stage(TripProfile(), "Plan a trip", None) == "collecting"
    assert _stage(trip, "Go ahead", None) == "completing"
    assert _stage(trip, "Actually make it four stops", None) == "correcting"
    assert _stage(trip, "Change my budget", AgentClientContext(hasRoute=True)) == "revising"
    assert _stage(TripProfile(), "Continue", AgentClientContext(hasRoute=True)) == "collecting"


def test_stage_instructions_are_selected_and_other_stages_omitted():
    scenarios = (
        (TripProfile(), "Plan a trip", None, "Stage: collect details."),
        (_complete_trip(), "Actually change the stops", None, "Stage: correct input."),
        (_complete_trip(), "Finish it", None, "Stage: complete the trip."),
        (
            _complete_trip(),
            "Revise this",
            AgentClientContext(hasRoute=True),
            "Stage: revise an existing trip.",
        ),
    )
    for trip, message, hint, expected in scenarios:
        system = _messages(trip, message, hint)[0].content
        assert expected in system
        assert (
            sum(
                system.count(marker)
                for marker in (
                    "Stage: collect",
                    "Stage: correct",
                    "Stage: complete",
                    "Stage: revise",
                )
            )
            == 1
        )
        assert "Never recite internal context" in system
        assert "ok:false" in system


def test_profile_is_authoritative_and_ui_defaults_are_not_sent():
    system = _messages(
        _complete_trip(),
        "Continue",
        AgentClientContext(hasRoute=False, stops=1, hotelBudget=0),
    )[0].content
    assert "num_stops: 3" in system
    assert "budget: 150.0" in system
    assert "hotelBudget=0" not in system
    assert "stops=1" not in system
    assert "INTERNAL" in system


def test_optional_car_and_departure_instructions_are_present_without_completing_early():
    assert _stage(_complete_trip().model_copy(update={"car_status": "unanswered"}), "Go", None) == (
        "collecting"
    )
    collecting = _messages(TripProfile(), "Plan")[0].content
    assert "departure time" in collecting
    assert "9:00 AM" in collecting
    assert "year, make, and model" in collecting
    assert '"skip" or "no car"' in collecting
    assert "correction or offer to skip" in collecting
    skipped = _messages(TripProfile(car_status="skipped"), "Continue")[0].content
    assert "car_status: skipped" in skipped


def test_facts_and_history_are_bounded_and_summary_is_conditional():
    recent = [LLMMessage(role="user", content=f"turn {i} " + "x" * 1000) for i in range(10)]
    short = _messages(recent=recent[:2], summary="earlier preference")
    assert not any("Summary of earlier conversation" in m.content for m in short)
    long = _messages(recent=recent, summary="z" * 2000)
    history = [m for m in long if m.role == "user"][:-1]
    assert len(history) == RECENT_MESSAGE_LIMIT
    assert all(len(m.content) <= RECENT_MESSAGE_CHARS for m in history)
    assert not any("turn 0" in m.content for m in history)
    summary = next(m.content for m in long if "Summary of earlier conversation" in m.content)
    assert len(summary) <= SUMMARY_CHARS + 100

    messages = build_messages(
        facts=[MemoryFact(key="home_city", value="Boston")],
        trip=None,
        conversation=None,
        recent_turns=[],
        user_message="Hello",
    )
    assert "home_city: Boston" in messages[0].content
    assert messages[-1].content == "Hello"
