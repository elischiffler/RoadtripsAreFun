"""Tests for the per-chat TripProfile model + the trip-profile tools + routing defaults."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.schemas import ToolCall
from app.agent.tool_dispatcher import AppToolDispatcher
from app.agent.tools import ToolContext
from app.agent.trip_profile import Car, TripProfile, TripProfileUpdate

from .conftest import FakeMemory

# --------------------------------------------------------------------------- #
# TripProfile / TripProfileUpdate validation
# --------------------------------------------------------------------------- #


def test_empty_trip_is_empty():
    assert TripProfile().is_empty() is True
    assert TripProfile(start_address="482 Luneta Dr").is_empty() is False


def test_valid_full_trip():
    t = TripProfile(
        start_address="482 Luneta Dr, San Luis Obispo, CA",
        start_coords=[35.28, -120.66],
        destination_address="Denver, CO",
        destination_coords=[39.74, -104.99],
        num_stops=3,
        budget=250.0,
        start_date="2026-07-01T09:00:00",
        car={"year": 2020, "make": "Mazda", "model": "CX-3"},
    )
    assert t.num_stops == 3
    assert t.budget == 250.0
    assert isinstance(t.car, Car)
    assert t.start_coords == [35.28, -120.66]


@pytest.mark.parametrize(
    "bad",
    [
        {"num_stops": 0},
        {"num_stops": 11},
        {"start_coords": [200, 0]},
        {"destination_coords": [0]},
        {"budget": -5},
        {"car": {"year": 1900, "make": "X", "model": "Y"}},
    ],
)
def test_invalid_updates_rejected(bad):
    with pytest.raises(ValidationError):
        TripProfileUpdate.model_validate(bad)


def test_empty_update_rejected():
    with pytest.raises(ValidationError):
        TripProfileUpdate.model_validate({})


def test_flat_car_fields_fold_into_car():
    # Models reliably emit flat car_year/car_make/car_model — accept them.
    u = TripProfileUpdate.model_validate(
        {"car_year": 2020, "car_make": "Mazda", "car_model": "CX-3"}
    )
    assert u.car == Car(year=2020, make="Mazda", model="CX-3")


def test_nested_car_still_accepted():
    u = TripProfileUpdate.model_validate({"car": {"year": 2019, "make": "Honda", "model": "Civic"}})
    assert u.car == Car(year=2019, make="Honda", model="Civic")


def test_partial_flat_car_surfaces_clear_error():
    # Missing year → Car validation error (not silently dropped).
    with pytest.raises(ValidationError):
        TripProfileUpdate.model_validate({"car_make": "Mazda", "car_model": "CX-3"})


def test_stringified_coords_are_coerced_to_list():
    # Models routinely emit coords as a JSON *string* — coerce so the common case
    # works instead of failing with a list_type validation error.
    u = TripProfileUpdate.model_validate({"destination_coords": "[36.1674263, -115.1484131]"})
    assert u.destination_coords == [36.1674263, -115.1484131]


def test_stringified_start_coords_coerced():
    u = TripProfileUpdate.model_validate({"start_coords": "[35.28, -120.66]"})
    assert u.start_coords == [35.28, -120.66]


def test_stringified_coords_coerced_on_trip_profile_too():
    t = TripProfile.model_validate({"start_coords": "[35.28, -120.66]"})
    assert t.start_coords == [35.28, -120.66]


def test_placeholder_coord_string_is_dropped_not_kept():
    # A non-coordinate placeholder (e.g. the model filled coords before it had a
    # validate_location result) is DROPPED, not stored — so it can't poison a
    # route later. Here it's the only field, so the update is empty -> rejected.
    with pytest.raises(ValidationError):
        TripProfileUpdate.model_validate({"start_coords": "[await result]"})


def test_placeholder_coord_dropped_but_sibling_field_survives():
    # The key behavior: a bad coords placeholder must NOT discard a valid sibling
    # field in the same update. The address saves; coords simply aren't recorded.
    u = TripProfileUpdate.model_validate(
        {"start_address": "482 Luneta Dr", "start_coords": "<coords>"}
    )
    assert u.start_address == "482 Luneta Dr"
    assert u.start_coords is None


def test_parseable_but_invalid_coord_still_errors_loudly():
    # A value that PARSES to a list but is an invalid coordinate (out of range) is
    # NOT dropped — it hard-fails so a genuine bug surfaces, not a placeholder.
    with pytest.raises(ValidationError):
        TripProfileUpdate.model_validate({"start_coords": "[200, 0]"})


def test_real_list_coords_unaffected_by_coercion():
    u = TripProfileUpdate.model_validate({"start_coords": [35.28, -120.66]})
    assert u.start_coords == [35.28, -120.66]


def test_blank_address_becomes_none():
    t = TripProfile(start_address="   ")
    assert t.start_address is None


# --------------------------------------------------------------------------- #
# merge semantics
# --------------------------------------------------------------------------- #


def test_merge_overwrites_and_preserves():
    base = TripProfile(start_address="SLO", num_stops=2)
    upd = TripProfileUpdate(num_stops=4, destination_address="Denver")
    merged = base.merged_with(upd)
    assert merged.num_stops == 4  # scalar overwritten
    assert merged.start_address == "SLO"  # untouched field preserved
    assert merged.destination_address == "Denver"  # new field applied


def test_merge_only_touches_provided_fields():
    base = TripProfile(start_address="SLO", num_stops=2, budget=100.0)
    # An update that sets only budget must not clear start_address/num_stops.
    merged = base.merged_with(TripProfileUpdate.model_validate({"budget": 300}))
    assert merged.start_address == "SLO"
    assert merged.num_stops == 2
    assert merged.budget == 300.0


# --------------------------------------------------------------------------- #
# JSON round-trip
# --------------------------------------------------------------------------- #


def test_json_round_trip():
    t = TripProfile(start_address="SLO", num_stops=3, budget=200.0)
    restored = TripProfile.from_json(t.to_json())
    assert restored.start_address == "SLO"
    assert restored.num_stops == 3
    assert restored.budget == 200.0


def test_from_json_empty_when_none():
    assert TripProfile.from_json(None).is_empty() is True


def test_from_json_survives_corrupt_json():
    assert TripProfile.from_json("{not valid json").is_empty() is True


# --------------------------------------------------------------------------- #
# Tools: get_trip_profile / update_trip_profile
# --------------------------------------------------------------------------- #
# (async tests run under pytest-asyncio's auto mode — no explicit marker needed)


def _ctx(memory=None):
    return ToolContext(user_id="u1", chat_id="42", memory=memory)


async def test_get_trip_profile_empty():
    result = await AppToolDispatcher().dispatch(
        ToolCall(name="get_trip_profile"), _ctx(FakeMemory())
    )
    assert result.ok is True
    assert result.result["trip_profile"] == {}


async def test_update_trip_profile_persists_merges_and_emits_action():
    memory = FakeMemory()
    d = AppToolDispatcher()

    r1 = await d.dispatch(
        ToolCall(name="update_trip_profile", arguments={"start_address": "482 Luneta Dr"}),
        _ctx(memory),
    )
    assert r1.ok is True
    # Emits the trip_profile_updated action so the frontend reflects/persists it.
    assert r1.result["action"] == "trip_profile_updated"
    assert r1.result["trip_profile"]["start_address"] == "482 Luneta Dr"

    # A second update merges (adds destination) without clobbering the start.
    r2 = await d.dispatch(
        ToolCall(
            name="update_trip_profile",
            arguments={"destination_address": "Denver, CO", "num_stops": 3},
        ),
        _ctx(memory),
    )
    assert r2.ok is True
    tp = r2.result["trip_profile"]
    assert tp["start_address"] == "482 Luneta Dr"  # preserved
    assert tp["destination_address"] == "Denver, CO"
    assert tp["num_stops"] == 3


async def test_update_trip_profile_is_per_chat():
    """Trip profiles are scoped per (user, chat) — different chats don't share."""
    memory = FakeMemory()
    d = AppToolDispatcher()
    await d.dispatch(
        ToolCall(name="update_trip_profile", arguments={"start_address": "SLO"}),
        ToolContext(user_id="u1", chat_id="A", memory=memory),
    )
    # A different chat starts empty.
    other = await d.dispatch(
        ToolCall(name="get_trip_profile"),
        ToolContext(user_id="u1", chat_id="B", memory=memory),
    )
    assert other.result["trip_profile"] == {}


async def test_update_trip_profile_invalid_returns_error_not_raise():
    result = await AppToolDispatcher().dispatch(
        ToolCall(name="update_trip_profile", arguments={"num_stops": 99}),
        _ctx(FakeMemory()),
    )
    assert result.ok is False
    assert result.error


async def test_update_trip_profile_without_memory_returns_error():
    result = await AppToolDispatcher().dispatch(
        ToolCall(name="update_trip_profile", arguments={"start_address": "X"}),
        _ctx(memory=None),
    )
    assert result.ok is False
    assert "memory" in result.error.lower()


# --------------------------------------------------------------------------- #
# Routing/car tools default from the trip profile
# --------------------------------------------------------------------------- #


async def test_generate_final_route_defaults_from_trip(monkeypatch):
    import app.agent.tool_dispatcher as td

    captured = {}

    async def fake_plan(payload):
        from types import SimpleNamespace

        captured["num_stops"] = payload["num_stops"]
        captured["budget"] = payload["budget"]
        return SimpleNamespace(stops=[], cost=0.0, distance=100000.0, model_dump=lambda: {})

    monkeypatch.setattr(td, "plan_final_route", fake_plan)
    monkeypatch.setattr(td.MapBox.MapBox_Route, "model_validate", classmethod(lambda cls, v: v))
    monkeypatch.setattr(td.Route_Payload, "model_validate", classmethod(lambda cls, v: v))

    # Trip profile supplies num_stops + budget gathered earlier in the chat.
    memory = FakeMemory()
    await AppToolDispatcher().dispatch(
        ToolCall(name="update_trip_profile", arguments={"num_stops": 4, "budget": 150}),
        _ctx(memory),
    )

    # Call generate_final_route with NO num_stops/budget — must default from trip.
    result = await AppToolDispatcher().dispatch(
        ToolCall(name="generate_final_route", arguments={"initial_route": {}}),
        _ctx(memory),
    )
    assert result.ok is True, result.error
    assert captured["num_stops"] == 4
    assert captured["budget"] == 150.0


async def test_generate_final_route_explicit_args_win(monkeypatch):
    from types import SimpleNamespace

    import app.agent.tool_dispatcher as td

    captured = {}

    async def fake_plan(payload):
        captured["num_stops"] = payload["num_stops"]
        return SimpleNamespace(stops=[], cost=0.0, distance=100000.0, model_dump=lambda: {})

    monkeypatch.setattr(td, "plan_final_route", fake_plan)
    monkeypatch.setattr(td.MapBox.MapBox_Route, "model_validate", classmethod(lambda cls, v: v))
    monkeypatch.setattr(td.Route_Payload, "model_validate", classmethod(lambda cls, v: v))

    memory = FakeMemory()
    await AppToolDispatcher().dispatch(
        ToolCall(name="update_trip_profile", arguments={"num_stops": 4, "budget": 150}),
        _ctx(memory),
    )
    await AppToolDispatcher().dispatch(
        ToolCall(
            name="generate_final_route",
            arguments={"initial_route": {}, "num_stops": 1, "budget": 300},
        ),
        _ctx(memory),
    )
    assert captured["num_stops"] == 1  # explicit arg beat the trip default of 4


async def test_generate_final_route_missing_stops_no_trip_errors(monkeypatch):
    import app.agent.tool_dispatcher as td

    monkeypatch.setattr(td.MapBox.MapBox_Route, "model_validate", classmethod(lambda cls, v: v))
    result = await AppToolDispatcher().dispatch(
        ToolCall(name="generate_final_route", arguments={"initial_route": {}, "budget": 300}),
        _ctx(FakeMemory()),
    )
    assert result.ok is False
    assert "num_stops" in result.error


async def test_get_car_budget_defaults_car_from_trip(monkeypatch):
    import app.agent.tool_dispatcher as td

    seen = {}

    async def fake_details(model, make, year):
        seen.update({"model": model, "make": make, "year": year})
        return {"combination_mpg": 30.0}

    async def fake_gas():
        return 3.0

    monkeypatch.setattr(td, "get_car_details", fake_details)
    monkeypatch.setattr(td, "get_gas_price", fake_gas)

    memory = FakeMemory()
    await AppToolDispatcher().dispatch(
        ToolCall(
            name="update_trip_profile",
            arguments={"car": {"year": 2020, "make": "Mazda", "model": "CX-3"}},
        ),
        _ctx(memory),
    )
    result = await AppToolDispatcher().dispatch(
        ToolCall(name="get_car_budget", arguments={}), _ctx(memory)
    )
    assert result.ok is True, result.error
    assert seen == {"model": "CX-3", "make": "Mazda", "year": 2020}
