from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import app.agent.tool_dispatcher as td
from app.agent.agent import run_turn
from app.agent.location_confirmation import confirm_location, confirm_locations
from app.agent.providers import FallbackChain
from app.agent.schemas import AgentChatRequest, LLMResponse, ToolCall
from app.agent.tool_dispatcher import AppToolDispatcher
from app.agent.tools import ToolContext
from app.agent.trip_profile import TripProfile
from app.utils.location_resolution import LocationConfirmation, needs_confirmation, resolve_location
from tests.agent.conftest import FakeMemory, FakeProvider


def location(address="Salem-Leckrone Airport, Illinois", lat=38.64, timezone="America/Chicago"):
    return SimpleNamespace(
        address=address,
        latitude=lat,
        longitude=-88.96,
        raw={"annotations": {"timezone": {"name": timezone}}},
    )


@pytest.mark.parametrize("field", ["start_address", "destination_address"])
async def test_abbreviation_persists_pending_and_human_choice_is_exact(monkeypatch, field):
    monkeypatch.setattr(td, "get_location", lambda **kw: [location()])
    memory = FakeMemory()
    ctx = ToolContext(user_id="owner", chat_id="chat", memory=memory)
    dispatcher = AppToolDispatcher()
    result = await dispatcher.dispatch(
        ToolCall(name="record_trip_details", arguments={field: "SLO", "budget": 180}), ctx
    )
    profile = TripProfile.from_json(memory.load_trip_profile("owner", "chat"))
    assert getattr(profile, field) is None
    assert profile.budget == 180
    assert field in result.result["clarifications"]
    candidate = profile.pending_locations[field].candidates[0]
    choice = LocationConfirmation(field=field, candidateId=candidate.id)
    for user, chat in [("other", "chat"), ("owner", "other")]:
        with pytest.raises(ValueError, match="expired"):
            confirm_location(memory, user, chat, choice)
    confirmed = confirm_location(memory, "owner", "chat", choice)
    assert getattr(confirmed, field) == candidate.address
    assert getattr(confirmed, field.replace("address", "coords")) == [38.64, -88.96]
    assert not confirmed.pending_locations
    if field == "start_address":
        assert confirmed.start_timezone == "America/Chicago"
    with pytest.raises(ValueError, match="expired"):
        confirm_location(memory, "owner", "chat", choice)


async def test_failed_replacement_expires_choices_preserves_old_endpoint_and_blocks_all_tools(
    monkeypatch,
):
    memory = FakeMemory()
    memory.save_trip_profile(
        "owner",
        "chat",
        TripProfile(
            start_address="Denver",
            start_coords=[39.74, -104.99],
            start_timezone="America/Denver",
            start_date="2099-10-17T11:00:00-06:00",
        ).to_json(),
    )
    ctx = ToolContext(user_id="owner", chat_id="chat", memory=memory)
    dispatcher = AppToolDispatcher()
    monkeypatch.setattr(td, "get_location", lambda **kw: [location()])
    await dispatcher.dispatch(
        ToolCall(name="record_trip_details", arguments={"start_address": "SLO"}), ctx
    )
    profile = TripProfile.from_json(memory.load_trip_profile("owner", "chat"))
    old_id = profile.pending_locations["start_address"].candidates[0].id
    for name in [
        "complete_trip",
        "get_initial_route",
        "generate_final_route",
        "generate_itinerary",
    ]:
        blocked = await dispatcher.dispatch(
            ToolCall(name=name, arguments={"initial_route": {}, "start_lat": 0}), ctx
        )
        assert not blocked.ok
        assert "pending locations" in blocked.error
    monkeypatch.setattr(td, "get_location", lambda **kw: None)
    result = await dispatcher.dispatch(
        ToolCall(
            name="record_trip_details",
            arguments={
                "start_address": "unknown",
                "budget": 190,
                "departure_date": "October 17, 2099",
            },
        ),
        ctx,
    )
    assert "departure_date" in result.result["clarifications"]
    assert result.result["trip_profile"]["start_address"] == "Denver"
    assert result.result["trip_profile"]["budget"] == 190
    with pytest.raises(ValueError):
        confirm_location(
            memory, "owner", "chat", LocationConfirmation(field="start_address", candidateId=old_id)
        )


def test_candidate_policy_multiple_dedup_invalid_and_finite():
    lookup = Mock(
        return_value=[
            location(),
            location(),
            location("Other city", 40),
            location("Bad", float("nan")),
            location("", 38),
        ]
    )
    result = resolve_location(None, "Springfield", lookup=lookup)
    assert len(result.candidates) == 2
    assert needs_confirmation(result)
    lookup.assert_called_once_with(geocoder=None, address="Springfield", exactly_one=False)
    assert not needs_confirmation(
        resolve_location(None, "Salem, Illinois", lookup=lambda **kw: [location()])
    )


def test_old_saved_route_profile_remains_compatible_with_new_pending_default():
    memory = FakeMemory()
    profile = TripProfile(start_address="Denver", start_coords=[39.74, -104.99])
    memory.save_trip_profile("owner", "chat", profile.to_json())
    older = profile.model_dump()
    older.pop("pending_locations")
    memory.save_planned_route("owner", "chat", {"profile": older, "route": {"stops": []}})
    ctx = ToolContext(user_id="owner", chat_id="chat", memory=memory)
    assert AppToolDispatcher()._resolve_route_for_itinerary({}, ctx) == {"stops": []}


async def test_yes_does_not_confirm_and_selection_never_uses_model_coordinates(monkeypatch):
    monkeypatch.setattr("app.agent.agent.get_user_id_from_token", lambda token: "owner")
    monkeypatch.setattr(td, "get_location", lambda **kw: [location()])
    memory = FakeMemory()
    provider = FakeProvider(
        extraction_responses=['{"details":{"start_address":"SLO"}}'],
        responses=[LLMResponse(content="Your trip is ready")],
    )

    def request(message, **kw):
        return AgentChatRequest(partitionKey="owner", chatId="chat", message=message, **kw)

    first = await run_turn(request("SLO"), FallbackChain([provider]), memory, AppToolDispatcher())
    assert provider.calls == 0
    assert "confirm the suggested address" in first.reply.lower()
    assert first.presentation.updated == []
    assert "Starting location: Confirm the suggested address" in first.presentation.needed[0]
    candidate = first.tripProfile["pending_locations"]["start_address"]["candidates"][0]
    yes = await run_turn(
        request("yes"), FallbackChain([FakeProvider(fail=True)]), memory, AppToolDispatcher()
    )
    assert yes.modelCalls == 0
    assert yes.tripProfile["pending_locations"]
    selected = await run_turn(
        request(
            "Use a fake city",
            locationConfirmation={"field": "start_address", "candidateId": candidate["id"]},
        ),
        FallbackChain([FakeProvider(fail=True)]),
        memory,
        AppToolDispatcher(),
    )
    assert candidate["address"] in selected.reply
    assert selected.presentation.updated == ["Starting location: " + candidate["address"]]
    assert selected.tripProfile["start_coords"] == [38.64, -88.96]
    assert not selected.tripProfile["pending_locations"]


async def test_confirmed_start_clears_date_and_retains_selected_time(monkeypatch):
    memory = FakeMemory()
    monkeypatch.setattr(td, "get_location", lambda **kw: [location()])
    memory.save_trip_profile(
        "owner",
        "chat",
        TripProfile(
            start_address="Denver",
            start_coords=[39.74, -104.99],
            start_timezone="America/Denver",
            start_date="2099-10-17T11:00:00-06:00",
        ).to_json(),
    )
    ctx = ToolContext(user_id="owner", chat_id="chat", memory=memory)
    await AppToolDispatcher().dispatch(
        ToolCall(name="record_trip_details", arguments={"start_address": "SLO"}), ctx
    )
    before = TripProfile.from_json(memory.load_trip_profile("owner", "chat"))
    candidate = before.pending_locations["start_address"].candidates[0]
    after = confirm_location(
        memory,
        "owner",
        "chat",
        LocationConfirmation(field="start_address", candidateId=candidate.id),
    )
    assert after.start_date is None
    assert after.departure_time == "11:00"
    assert after.start_timezone == "America/Chicago"


async def test_batch_confirmation_saves_both_in_one_turn_without_model_calls(monkeypatch):
    monkeypatch.setattr("app.agent.agent.get_user_id_from_token", lambda token: "owner")
    monkeypatch.setattr(td, "get_location", lambda **kw: [location(address=kw["address"])])
    memory = FakeMemory()
    await AppToolDispatcher().dispatch(
        ToolCall(
            name="record_trip_details",
            arguments={"start_address": "Boulder", "destination_address": "Minneapolis"},
        ),
        ToolContext(user_id="owner", chat_id="chat", memory=memory),
    )
    profile = TripProfile.from_json(memory.load_trip_profile("owner", "chat"))
    choices = [
        LocationConfirmation(field=field, candidateId=pending.candidates[0].id)
        for field, pending in profile.pending_locations.items()
    ]
    before = profile.to_json()
    stale = choices[1].model_copy(update={"candidateId": "expired"})
    with pytest.raises(ValueError, match="expired"):
        confirm_locations(memory, "owner", "chat", [choices[0], stale])
    assert memory.load_trip_profile("owner", "chat") == before
    memory.save_trip_profile = Mock(wraps=memory.save_trip_profile)
    response = await run_turn(
        AgentChatRequest(
            partitionKey="owner",
            chatId="chat",
            message="Confirm both",
            locationConfirmations=choices,
        ),
        FallbackChain([FakeProvider(fail=True)]),
        memory,
        AppToolDispatcher(),
    )
    memory.save_trip_profile.assert_called_once()
    assert response.modelCalls == 0
    assert not response.tripProfile["pending_locations"]
    assert response.tripProfile["start_address"] == "Boulder"
    assert response.tripProfile["destination_address"] == "Minneapolis"
    assert response.presentation.updated == [
        "Starting location: Boulder",
        "Destination: Minneapolis",
    ]
    assert len(response.actions) == 1


@pytest.mark.parametrize(
    "extra",
    [
        {"locationConfirmations": []},
        {"locationConfirmations": [{"field": "start_address", "candidateId": "a"}] * 2},
        {
            "locationConfirmation": {"field": "start_address", "candidateId": "a"},
            "locationConfirmations": [{"field": "destination_address", "candidateId": "b"}],
        },
    ],
)
def test_batch_confirmation_rejects_empty_duplicate_and_mixed_selections(extra):
    with pytest.raises(ValueError):
        AgentChatRequest(partitionKey="owner", chatId="chat", message="Confirm", **extra)
