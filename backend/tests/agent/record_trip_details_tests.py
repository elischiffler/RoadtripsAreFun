"""Trip detail recording keeps valid fields when another needs clarification."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import app.agent.tool_dispatcher as td
from app.agent.schemas import ToolCall
from app.agent.tool_dispatcher import AppToolDispatcher
from app.agent.tools import ToolContext
from app.agent.trip_dates import resolve_departure
from app.agent.trip_profile import TripProfile
from tests.agent.conftest import FakeMemory


def _location(address, lat, lon, timezone="America/Los_Angeles"):
    annotations = {"timezone": {"name": timezone}} if timezone else {}
    return SimpleNamespace(
        address=address, latitude=lat, longitude=lon, raw={"annotations": annotations}
    )


def _ctx(memory):
    return ToolContext(user_id="owner", chat_id="trip", memory=memory)


async def _record(memory, **arguments):
    return await AppToolDispatcher().dispatch(
        ToolCall(name="record_trip_details", arguments=arguments), _ctx(memory)
    )


async def test_complete_message_geocodes_and_saves_every_field(monkeypatch):
    calls = []
    locations = {
        "San Francisco": _location("San Francisco, CA", 37.77, -122.42),
        "Denver": _location("Denver, CO", 39.74, -104.99, "America/Denver"),
    }

    def geocode(*, geocoder, address):
        calls.append(address)
        return locations[address]

    monkeypatch.setattr("app.agent.tool_dispatcher.get_location", geocode)
    memory = FakeMemory()
    result = await _record(
        memory,
        start_address="San Francisco",
        destination_address="Denver",
        num_stops=3,
        budget="$250",
        departure="October 3, 2099 at 2:30 PM",
    )
    assert result.ok
    assert calls == ["San Francisco", "Denver"]
    assert result.result["clarifications"] == {}
    profile = TripProfile.from_json(memory.load_trip_profile("owner", "trip"))
    assert profile.start_coords == [37.77, -122.42]
    assert profile.destination_coords == [39.74, -104.99]
    assert profile.start_timezone == "America/Los_Angeles"
    assert profile.num_stops == 3
    assert profile.budget == 250
    assert profile.start_date == "2099-10-03T14:30:00-07:00"


async def test_bad_date_and_stop_count_preserve_valid_locations_and_budget(monkeypatch):
    monkeypatch.setattr(
        "app.agent.tool_dispatcher.get_location",
        lambda *, geocoder, address: _location(address, 35.0, -120.0),
    )
    memory = FakeMemory()
    result = await _record(
        memory,
        start_address="SLO",
        destination_address="LA",
        num_stops=99,
        budget=180,
        departure="sometime next season",
    )
    assert result.ok
    assert set(result.result["clarifications"]) == {"num_stops", "departure"}
    profile = TripProfile.from_json(memory.load_trip_profile("owner", "trip"))
    assert profile.start_address == "SLO"
    assert profile.destination_address == "LA"
    assert profile.budget == 180
    assert profile.num_stops is None
    assert profile.start_date is None


async def test_partial_update_preserves_existing_fields_and_changes_date(monkeypatch):
    memory = FakeMemory()
    existing = TripProfile(
        start_address="SLO",
        start_coords=[35.0, -120.0],
        start_timezone="America/Los_Angeles",
        destination_address="LA",
        destination_coords=[34.0, -118.0],
        num_stops=2,
        budget=100,
        start_date="2099-09-30T09:00:00-07:00",
    )
    memory.save_trip_profile("owner", "trip", existing.to_json())
    monkeypatch.setattr(
        "app.agent.tool_dispatcher.get_location",
        lambda **kwargs: pytest.fail("No geocode needed for a budget/date update"),
    )
    result = await _record(memory, budget=220, departure="October 3, 2099 at 4 PM")
    assert result.ok
    profile = TripProfile.from_json(memory.load_trip_profile("owner", "trip"))
    assert profile.start_coords == existing.start_coords
    assert profile.destination_coords == existing.destination_coords
    assert profile.num_stops == 2
    assert profile.budget == 220
    assert profile.start_date == "2099-10-03T16:00:00-07:00"


async def test_missing_timezone_requests_clarification_without_guessing(monkeypatch):
    monkeypatch.setattr(
        "app.agent.tool_dispatcher.get_location",
        lambda *, geocoder, address: _location(address, 35.0, -120.0, None),
    )
    memory = FakeMemory()
    result = await _record(memory, start_address="Unclear", budget=90, departure="tomorrow")
    assert result.ok
    assert set(result.result["clarifications"]) == {"start_timezone", "departure"}
    profile = TripProfile.from_json(memory.load_trip_profile("owner", "trip"))
    assert profile.start_timezone is None
    assert profile.start_date is None
    assert profile.budget == 90


async def test_failed_geocode_preserves_existing_location_and_saves_other_fields(monkeypatch):
    memory = FakeMemory()
    memory.save_trip_profile(
        "owner",
        "trip",
        TripProfile(destination_address="Denver", destination_coords=[39.74, -104.99]).to_json(),
    )
    monkeypatch.setattr("app.agent.tool_dispatcher.get_location", lambda **kwargs: None)
    result = await _record(memory, destination_address="???", num_stops=4)
    assert result.ok
    assert "destination_address" in result.result["clarifications"]
    profile = TripProfile.from_json(memory.load_trip_profile("owner", "trip"))
    assert profile.destination_address == "Denver"
    assert profile.destination_coords == [39.74, -104.99]
    assert profile.num_stops == 4


async def test_invalid_budget_does_not_discard_valid_stop_count():
    memory = FakeMemory()
    result = await _record(memory, num_stops=5, budget="-20")
    assert result.ok
    assert "budget" in result.result["clarifications"]
    assert result.result["trip_profile"]["num_stops"] == 5
    assert "budget" not in result.result["trip_profile"]


async def test_car_skip_then_provide_or_change_uses_provider_validation(monkeypatch):
    memory = FakeMemory()
    calls = []

    async def verify_car(*, model, make, year):
        calls.append((year, make, model))
        return {"combination_mpg": 30}

    monkeypatch.setattr(td, "get_car_details", verify_car)
    skipped = await _record(memory, car_status="no car", budget=180)
    assert skipped.ok
    assert skipped.result["clarifications"] == {}
    assert skipped.result["trip_profile"]["car_status"] == "skipped"
    assert "car" not in skipped.result["trip_profile"]
    assert calls == []

    provided = await _record(memory, car_year=2020, car_make="Mazda", car_model="CX-3")
    assert provided.ok
    assert provided.result["trip_profile"]["car_status"] == "provided"
    assert calls == [(2020, "Mazda", "CX-3")]

    changed = await _record(memory, car_year=2022, car_make="Honda", car_model="Civic")
    assert changed.ok
    assert changed.result["trip_profile"]["car"]["model"] == "Civic"
    assert TripProfile.from_json(memory.load_trip_profile("owner", "trip")).budget == 180


async def test_invalid_car_requests_correction_or_skip_and_saves_valid_sibling(monkeypatch):
    from fastapi import HTTPException

    async def no_match(*, model, make, year):
        raise HTTPException(status_code=404, detail="No matching car")

    monkeypatch.setattr(td, "get_car_details", no_match)
    memory = FakeMemory()
    result = await _record(memory, car_year=2020, car_make="Unknown", car_model="X", num_stops=3)
    assert result.ok
    assert result.result["trip_profile"]["num_stops"] == 3
    assert result.result["trip_profile"]["car_status"] == "unanswered"
    assert "correct" in result.result["clarifications"]["car"].lower()
    assert "skip" in result.result["clarifications"]["car"].lower()

    partial = await _record(memory, car_year=2020, car_make="Mazda")
    assert partial.ok
    assert "car" in partial.result["clarifications"]
    assert TripProfile.from_json(memory.load_trip_profile("owner", "trip")).car is None


async def test_recorded_skip_permits_agent_planning(monkeypatch):
    memory = FakeMemory()
    skipped = await _record(memory, car_status="skip", num_stops=2, budget=150)
    assert skipped.ok

    async def fake_plan(payload, *, user_id):
        return SimpleNamespace(stops=[], cost=0.0, distance=100000.0, model_dump=lambda: {})

    monkeypatch.setattr(td, "plan_final_route", fake_plan)
    monkeypatch.setattr(td.MapBox.MapBox_Route, "model_validate", classmethod(lambda cls, v: v))
    monkeypatch.setattr(td.Route_Payload, "model_validate", classmethod(lambda cls, v: v))
    result = await AppToolDispatcher().dispatch(
        ToolCall(name="generate_final_route", arguments={"initial_route": {}}), _ctx(memory)
    )
    assert result.ok, result.error


async def test_invalid_geocode_coordinates_are_not_saved(monkeypatch):
    monkeypatch.setattr(
        "app.agent.tool_dispatcher.get_location",
        lambda **kwargs: _location("Bad", float("nan"), -120.0),
    )
    memory = FakeMemory()
    result = await _record(memory, start_address="Bad", budget=75)
    assert result.ok
    assert "start_address" in result.result["clarifications"]
    assert "start_address" not in result.result["trip_profile"]
    assert result.result["trip_profile"]["budget"] == 75


async def test_changing_start_clears_old_date_and_timezone(monkeypatch):
    memory = FakeMemory()
    memory.save_trip_profile(
        "owner",
        "trip",
        TripProfile(
            start_address="SLO",
            start_coords=[35.0, -120.0],
            start_timezone="America/Los_Angeles",
            start_date="2099-10-03T09:00:00-07:00",
        ).to_json(),
    )
    monkeypatch.setattr(
        "app.agent.tool_dispatcher.get_location",
        lambda *, geocoder, address: _location("Boston, MA", 42.36, -71.06, "America/New_York"),
    )
    result = await _record(memory, start_address="Boston")
    assert result.ok
    profile = TripProfile.from_json(memory.load_trip_profile("owner", "trip"))
    assert profile.start_timezone == "America/New_York"
    assert profile.start_date is None


def test_tomorrow_uses_start_timezone_at_utc_boundary():
    now = datetime(2026, 9, 30, 6, 30, tzinfo=UTC)  # Still September 29 in LA.
    assert resolve_departure("tomorrow", "America/Los_Angeles", now) == (
        "2026-09-30T09:00:00-07:00"
    )
    assert resolve_departure("tomorrow at 4 PM", "America/New_York", now) == (
        "2026-10-01T16:00:00-04:00"
    )


def test_yearless_date_uses_next_occurrence_and_default_time():
    now = datetime(2026, 10, 4, 18, 0, tzinfo=UTC)
    assert resolve_departure("October 3", "America/Los_Angeles", now) == (
        "2027-10-03T09:00:00-07:00"
    )
    assert resolve_departure("February 29", "America/Los_Angeles", now) == (
        "2028-02-29T09:00:00-08:00"
    )


def test_yearless_today_after_nine_uses_next_year():
    now = datetime(2026, 9, 29, 20, 0, tzinfo=UTC)
    assert resolve_departure("September 29", "America/Los_Angeles", now) == (
        "2027-09-29T09:00:00-07:00"
    )


def test_ambiguous_dst_hour_requests_clarification():
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_departure(
            "November 1, 2026 at 1:30 AM",
            "America/Los_Angeles",
            datetime(2026, 9, 29, 20, 0, tzinfo=UTC),
        )


def test_iso_datetime_is_normalized_to_start_timezone():
    assert (
        resolve_departure(
            "2099-10-03T21:30:00Z",
            "America/Los_Angeles",
            datetime(2026, 9, 29, tzinfo=UTC),
        )
        == "2099-10-03T14:30:00-07:00"
    )


def test_explicit_noon_and_24_hour_times_are_preserved():
    now = datetime(2026, 9, 29, tzinfo=UTC)
    assert resolve_departure("October 3, 2099 at noon", "America/Los_Angeles", now) == (
        "2099-10-03T12:00:00-07:00"
    )
    assert resolve_departure("October 3, 2099 17:45", "America/Los_Angeles", now) == (
        "2099-10-03T17:45:00-07:00"
    )


@pytest.mark.parametrize("wording", ["2025-01-01", "February 30, 2099", "3/4", "today"])
def test_invalid_ambiguous_or_past_date_requests_clarification(wording):
    with pytest.raises(ValueError):
        resolve_departure(wording, "America/Los_Angeles", datetime(2026, 9, 29, 20, 0, tzinfo=UTC))
