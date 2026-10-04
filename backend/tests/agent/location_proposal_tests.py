"""Replay endpoint correction and confirmation without losing supplied details."""

from types import SimpleNamespace

import pytest

import app.agent.tool_dispatcher as td
from app.agent.location_confirmation import confirm_location
from app.agent.presentation import present_details
from app.agent.schemas import ToolCall
from app.agent.tool_dispatcher import AppToolDispatcher
from app.agent.tools import ToolContext
from app.agent.trip_dates import PendingDeparture
from app.agent.trip_profile import TripProfile
from app.utils.location_resolution import LocationConfirmation
from tests.agent.conftest import FakeMemory


def match(address, timezone="America/Los_Angeles"):
    return SimpleNamespace(
        address=address,
        latitude=35.28,
        longitude=-120.66,
        raw={"annotations": {"timezone": {"name": timezone}}},
    )


async def record(memory, **args):
    return await AppToolDispatcher().dispatch(
        ToolCall(name="record_trip_details", arguments=args),
        ToolContext(user_id="owner", chat_id="chat", memory=memory),
    )


def load(memory):
    return TripProfile.from_json(memory.load_trip_profile("owner", "chat"))


def confirm(memory, field):
    candidate = load(memory).pending_locations[field].candidates[0]
    return confirm_location(
        memory, "owner", "chat", LocationConfirmation(field=field, candidateId=candidate.id)
    )


async def test_single_full_address_still_requires_confirmation(monkeypatch):
    monkeypatch.setattr(td, "get_location", lambda **kw: [match("San Luis Obispo, CA, USA")])
    memory = FakeMemory()
    await record(memory, start_address="San Luis Obispo, California")
    pending = load(memory)
    assert pending.start_address is None
    assert (
        pending.pending_locations["start_address"].candidates[0].address
        == "San Luis Obispo, CA, USA"
    )
    receipt = present_details(TripProfile(), pending, {})
    assert "Confirm" in receipt.needed[0]
    assert "San Luis Obispo, CA, USA" in receipt.needed[0]
    assert confirm(memory, "start_address").start_address == "San Luis Obispo, CA, USA"


async def test_full_city_and_state_prefers_city_over_county_without_discarding_alternatives(
    monkeypatch,
):
    monkeypatch.setattr(
        td,
        "get_location",
        lambda **kw: [
            match("San Luis Obispo County, California, USA"),
            match("San Luis Obispo, California, USA"),
            match("California City, California, USA"),
        ],
    )
    memory = FakeMemory()
    await record(memory, start_address="san luis obispo, california")
    candidates = load(memory).pending_locations["start_address"].candidates
    assert candidates[0].address == "San Luis Obispo, California, USA"
    assert len(candidates) == 3
    assert candidates[1].address == "San Luis Obispo County, California, USA"
    assert confirm(memory, "start_address").start_address == candidates[0].address


async def test_corrections_preserve_date_and_time_until_confirmed(monkeypatch):
    monkeypatch.setattr(
        td,
        "get_location",
        lambda **kw: [match(kw["address"] + ", USA"), match("Another location")],
    )
    memory = FakeMemory()
    await record(
        memory,
        start_address="slo",
        destination_address="boulder",
        departure_date="October 10, 2099",
        departure_time="10 am",
        num_stops=2,
        budget=200,
    )
    await record(
        memory, start_address="San Luis Obispo, California", destination_address="Boulder, Colorado"
    )
    pending = load(memory)
    assert pending.start_date is None
    assert pending.pending_departure.date == "October 10, 2099"
    assert pending.departure_time == "10:00"
    confirm(memory, "destination_address")
    saved = confirm(memory, "start_address")
    assert saved.start_date == "2099-10-10T10:00:00-07:00"
    assert saved.pending_departure is None
    assert saved.num_stops == 2
    assert saved.budget == 200
    assert not saved.pending_locations


async def test_same_search_preserves_ids_and_confirmed_canonical_address_is_not_reset(monkeypatch):
    monkeypatch.setattr(td, "get_location", lambda **kw: [match("San Luis Obispo, CA, USA")])
    memory = FakeMemory()
    await record(memory, start_address="San Luis Obispo, California")
    pending = load(memory)
    monkeypatch.setattr(
        td, "get_location", lambda **kw: pytest.fail("Unchanged locations need no lookup")
    )
    await record(memory, start_address="san luis obispo, california", budget=200)
    assert load(memory).pending_locations == pending.pending_locations
    confirm(memory, "start_address")
    await record(memory, start_address="San Luis Obispo, CA, USA")
    assert not load(memory).pending_locations


@pytest.mark.parametrize(
    "timezone,expected",
    [
        ("America/Los_Angeles", "2099-10-10T10:00:00-07:00"),
        ("America/New_York", "2099-10-11T10:00:00-04:00"),
    ],
)
async def test_relative_date_uses_original_request_in_confirmed_timezone(
    monkeypatch, timezone, expected
):
    monkeypatch.setattr(td, "get_location", lambda **kw: [match("Chosen city", timezone)])
    memory = FakeMemory()
    await record(memory, start_address="a city", departure_time="10 am")
    profile = load(memory)
    profile.pending_departure = PendingDeparture(
        date="tomorrow", requested_at="2099-10-10T06:30:00Z"
    )
    memory.save_trip_profile("owner", "chat", profile.to_json())
    saved = confirm(memory, "start_address")
    assert saved.start_date == expected
    assert saved.pending_departure is None


async def test_invalid_date_does_not_prevent_location_confirmation_or_allow_planning(monkeypatch):
    monkeypatch.setattr(td, "get_location", lambda **kw: [match("San Luis Obispo, CA, USA")])
    memory = FakeMemory()
    await record(memory, start_address="SLO", departure_date="February 30, 2099", budget=200)
    before = load(memory)
    saved = confirm(memory, "start_address")
    assert saved.start_address == "San Luis Obispo, CA, USA"
    assert saved.pending_departure.date == "February 30, 2099"
    assert saved.start_date is None
    assert "departure_date" in saved.missing_details()
    assert "valid departure date" in " ".join(present_details(before, saved, {}).needed)
    await record(memory, departure_date="October 10, 2099")
    assert load(memory).start_date == "2099-10-10T09:00:00-07:00"
    assert load(memory).pending_departure is None


async def test_replacing_origin_and_time_does_not_copy_departure_from_old_trip(monkeypatch):
    monkeypatch.setattr(td, "get_location", lambda **kw: [match("New city", "America/New_York")])
    memory = FakeMemory()
    memory.save_trip_profile(
        "owner",
        "chat",
        TripProfile(
            start_address="Old city",
            start_coords=[35, -120],
            start_timezone="America/Los_Angeles",
            start_date="2099-10-10T09:00:00-07:00",
        ).to_json(),
    )
    await record(memory, start_address="New city", departure_time="10 am")
    saved = confirm(memory, "start_address")
    assert saved.start_date is None
    assert saved.pending_departure is None
    assert saved.departure_time == "10:00"
    assert saved.start_timezone == "America/New_York"
