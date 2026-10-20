"""Traveler collection, room allocation, old-chat and revision regressions."""

import json

import pytest
from pydantic import ValidationError

from app.agent.extraction import EXTRACTION_PROMPT, extract_trip_patch
from app.agent.schemas import LLMMessage
from app.agent.trip_profile import TripProfile, TripProfileUpdate
from app.routing.occupancy import HotelRoom, require_occupancy
from tests.agent.conftest import FakeProvider


@pytest.mark.parametrize(
    "room",
    [
        {"adults": True, "child_ages": []},
        {"adults": 0, "child_ages": [5]},
        {"adults": 6, "child_ages": [5]},
        {"adults": 1, "child_ages": [-1]},
        {"adults": 1, "child_ages": [18]},
        {"adults": 1, "child_ages": [1.5]},
        {"adults": 2},
    ],
)
def test_room_requires_explicit_adults_child_ages_and_provider_bounds(room):
    with pytest.raises(ValidationError):
        TripProfileUpdate(hotel_rooms=[room])


def test_multiple_rooms_count_all_travelers_without_adult_inference():
    rooms = [HotelRoom(adults=2, child_ages=[0, 7]), HotelRoom(adults=1, child_ages=[])]
    assert require_occupancy(5, rooms) == rooms
    with pytest.raises(ValueError, match="equal the total"):
        require_occupancy(4, rooms)
    with pytest.raises(ValidationError):
        TripProfileUpdate(hotel_rooms=rooms * 3)


@pytest.mark.parametrize(
    ("message", "count"),
    [
        ("just me", 1),
        ("me and my partner", 2),
        ("two of us", 2),
        ("two passengers plus me", 3),
    ],
)
def test_explicit_count_extraction_contract(message, count):
    provider = FakeProvider(
        extraction_responses=[json.dumps({"details": {"traveler_count": count}})]
    )
    patch, _ = extract_trip_patch(provider, message, TripProfile())
    assert patch == {"traveler_count": count}
    assert message in EXTRACTION_PROMPT


def test_ambiguous_passengers_and_yes_have_context_without_default_rooms():
    assert 'A bare "two passengers" is ambiguous' in EXTRACTION_PROMPT
    provider = FakeProvider(extraction_responses=['{"details":{}}'])
    recent = [
        LLMMessage(
            role="assistant",
            content="Are all two travelers adults sharing one room, with no children?",
        )
    ]
    patch, _ = extract_trip_patch(
        provider, "yes", TripProfile(traveler_count=2), recent_turns=recent
    )
    assert patch == {}
    assert recent[0] in provider.seen_messages[0]
    assert TripProfile(traveler_count=2).hotel_rooms is None
