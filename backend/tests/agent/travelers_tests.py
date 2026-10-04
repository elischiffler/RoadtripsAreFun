"""Traveler collection, room allocation, old-chat and revision regressions."""

import json

import pytest
from pydantic import ValidationError

from app.agent.extraction import EXTRACTION_PROMPT, extract_trip_patch
from app.agent.presentation import present_details
from app.agent.schemas import LLMMessage, ToolCall
from app.agent.tool_dispatcher import AppToolDispatcher
from app.agent.tools import ToolContext
from app.agent.trip_profile import TripProfile, TripProfileUpdate
from app.routing.occupancy import COUNT_QUESTION, HotelRoom, require_occupancy
from tests.agent.complete_trip_tests import _profile
from tests.agent.conftest import FakeMemory, FakeProvider


@pytest.mark.parametrize("count", [True, False, 0, -1, 1.5, "2", 25])
async def test_invalid_count_preserves_other_updates_and_blocks_old_prices(count):
    memory = FakeMemory()
    initial = _profile()
    memory.save_trip_profile("u", "c", initial.to_json())
    ctx = ToolContext(user_id="u", chat_id="c", memory=memory)
    result = await AppToolDispatcher().dispatch(
        ToolCall(name="record_trip_details", arguments={"traveler_count": count, "budget": 180}),
        ctx,
    )
    assert result.ok
    assert "traveler_count" in result.result["clarifications"]
    saved = TripProfile.from_json(memory.load_trip_profile("u", "c"))
    assert saved.budget == 180 and saved.traveler_count is None
    assert saved.hotel_rooms is None and saved.persona_weights == initial.persona_weights
    blocked = await AppToolDispatcher().dispatch(ToolCall(name="complete_trip"), ctx)
    assert not blocked.ok and COUNT_QUESTION in blocked.error


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


def test_old_chat_readable_but_count_and_allocation_required():
    old = _profile().model_dump()
    old.pop("traveler_count")
    old.pop("hotel_rooms")
    restored = TripProfile.from_json(json.dumps(old))
    assert restored.start_address == old["start_address"]
    assert restored.missing_details() == ["traveler_count"]
    assert present_details(restored, restored, {}).needed[0] == COUNT_QUESTION


async def test_count_correction_requires_new_allocation_and_invalidates_saved_itinerary():
    memory = FakeMemory()
    initial = _profile(persona_weights={"nature": 2})
    memory.save_trip_profile("u", "c", initial.to_json())
    memory.save_planned_route("u", "c", {"route": {}, "profile": initial.model_dump()})
    ctx = ToolContext(user_id="u", chat_id="c", memory=memory)
    dispatcher = AppToolDispatcher()
    await dispatcher.dispatch(
        ToolCall(name="record_trip_details", arguments={"traveler_count": 3}), ctx
    )
    changed = TripProfile.from_json(memory.load_trip_profile("u", "c"))
    assert changed.traveler_count == 3 and changed.hotel_rooms is None
    assert changed.persona_weights == {"nature": 2}
    assert not memory.upserted
    assert TripProfile.from_json(memory.load_trip_profile("other", "c")).is_empty()
    result = await dispatcher.dispatch(ToolCall(name="generate_itinerary"), ctx)
    assert not result.ok and "child's age" in result.error
    rooms = [{"adults": 2, "child_ages": [5]}]
    await dispatcher.dispatch(
        ToolCall(name="record_trip_details", arguments={"hotel_rooms": rooms}), ctx
    )
    changed = TripProfile.from_json(memory.load_trip_profile("u", "c"))
    assert not changed.missing_details()
    assert COUNT_QUESTION not in present_details(changed, changed, {}).needed
    result = await dispatcher.dispatch(ToolCall(name="generate_itinerary"), ctx)
    assert not result.ok  # The saved profile no longer matches the old route.


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


def test_trip_personality_label_keeps_weight_values_and_room_budget_explicit():
    trip = _profile(persona_weights={"nature": 2, "food": 1})
    presentation = present_details(TripProfile(), trip, {})
    assert "Trip personality: nature 2, food 1" in presentation.updated
    assert "Hotel budget: $200 per room per night" in presentation.updated


async def test_incomplete_child_correction_cannot_reuse_adult_room_at_same_count():
    from app.agent.extraction import parse_trip_patch

    memory = FakeMemory()
    memory.save_trip_profile("u", "c", _profile().to_json())
    patch = parse_trip_patch('{"details":{"traveler_count":2,"hotel_rooms":null,"budget":150}}')
    result = await AppToolDispatcher().dispatch(
        ToolCall(name="record_trip_details", arguments=patch),
        ToolContext(user_id="u", chat_id="c", memory=memory),
    )
    assert result.ok and "hotel_rooms" in result.result["clarifications"]
    saved = TripProfile.from_json(memory.load_trip_profile("u", "c"))
    assert saved.traveler_count == 2 and saved.hotel_rooms is None and saved.budget == 150


@pytest.mark.parametrize("count", [None, 1, 2, 3])
def test_room_collection_depends_on_known_party_size(count):
    from app.routing.occupancy import OCCUPANCY_QUESTION

    trip = _profile().model_dump()
    trip.update(traveler_count=count, hotel_rooms=None)
    profile = TripProfile.model_validate(trip)
    presentation = present_details(profile, profile, {})
    if count is None:
        assert presentation.needed == [COUNT_QUESTION]
        assert "hotel_rooms" not in profile.missing_details()
    elif count == 1:
        assert not profile.missing_details()
        assert profile.hotel_rooms == [HotelRoom(adults=1, child_ages=[])]
        assert require_occupancy(1, profile.hotel_rooms) == profile.hotel_rooms
        assert not presentation.needed
        assert TripProfile.from_json(profile.to_json()).hotel_rooms == profile.hotel_rooms
    else:
        assert presentation.needed == [OCCUPANCY_QUESTION]
        assert profile.hotel_rooms is None


async def test_solo_count_correction_defaults_room_then_group_requires_new_allocation():
    memory = FakeMemory()
    memory.save_trip_profile("u", "c", _profile().to_json())
    ctx = ToolContext(user_id="u", chat_id="c", memory=memory)
    dispatcher = AppToolDispatcher()
    for count in [1, 2]:
        await dispatcher.dispatch(
            ToolCall(name="record_trip_details", arguments={"traveler_count": count}), ctx
        )
        saved = TripProfile.from_json(memory.load_trip_profile("u", "c"))
        if count == 1:
            assert saved.hotel_rooms == [HotelRoom(adults=1, child_ages=[])]
            assert not saved.missing_details()
        else:
            assert saved.hotel_rooms is None
            assert saved.missing_details() == ["hotel_rooms"]


def test_preprovided_rooms_wait_for_count_and_explicit_solo_occupancy_is_preserved():
    rooms = [HotelRoom(adults=2, child_ages=[])]
    trip = _profile().model_dump()
    trip.update(traveler_count=None, hotel_rooms=rooms)
    profile = TripProfile.model_validate(trip)
    assert present_details(profile, profile, {}).needed == [COUNT_QUESTION]
    solo = TripProfile(traveler_count=1, hotel_rooms=rooms)
    assert solo.hotel_rooms == rooms
    assert "hotel_rooms" in solo.missing_details()  # Clarify conflicting explicit details.
