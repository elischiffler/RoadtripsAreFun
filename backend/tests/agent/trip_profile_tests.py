"""Tests for the per-chat TripProfile model + the trip-profile tools + routing defaults."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.agent.trip_profile import Car, TripProfile, TripProfileUpdate

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
    assert t.car_status == "provided"
    assert t.start_coords == [35.28, -120.66]


@pytest.mark.parametrize(
    "bad",
    [
        {"num_stops": 0},
        {"num_stops": 31},
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


def test_car_choice_can_be_skipped_then_selected():
    skipped = TripProfile().merged_with(TripProfileUpdate(car_status="skipped"))
    assert skipped.car is None
    assert skipped.car_status == "skipped"
    selected = skipped.merged_with(
        TripProfileUpdate(car_year=2020, car_make="Mazda", car_model="3")
    )
    assert selected.car == Car(year=2020, make="Mazda", model="3")
    assert selected.car_status == "provided"
    skipped_again = selected.merged_with(TripProfileUpdate(car_status="skipped"))
    assert skipped_again.car is None
    assert skipped_again.car_status == "skipped"


def test_partial_flat_car_surfaces_clear_error():
    # Missing year → Car validation error (not silently dropped).
    with pytest.raises(ValidationError):
        TripProfileUpdate.model_validate({"car_make": "Mazda", "car_model": "CX-3"})


def test_new_updates_reject_stringified_coords():
    with pytest.raises(ValidationError):
        TripProfileUpdate.model_validate({"destination_coords": "[36.1674263, -115.1484131]"})


def test_saved_stringified_coords_remain_readable():
    t = TripProfile.model_validate({"start_coords": "[35.28, -120.66]"})
    assert t.start_coords == [35.28, -120.66]


def test_placeholder_coord_string_is_rejected():
    with pytest.raises(ValidationError):
        TripProfileUpdate.model_validate({"start_coords": "[await result]"})


def test_invalid_coord_update_is_not_partially_applied():
    with pytest.raises(ValidationError):
        TripProfileUpdate.model_validate(
            {"start_address": "482 Luneta Dr", "start_coords": "<coords>"}
        )


def test_stringified_invalid_coord_still_errors_loudly():
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


def test_old_stored_car_is_treated_as_provided():
    old = '{"car": {"year": 2020, "make": "Mazda", "model": "CX-3"}}'
    assert TripProfile.from_json(old).car_status == "provided"


def test_structured_skip_clears_existing_car_and_allows_later_change():
    provided = TripProfile().merged_with(
        TripProfileUpdate(car_year=2020, car_make="Mazda", car_model="CX-3")
    )
    skipped = provided.merged_with(TripProfileUpdate.model_validate({"car_status": "skipped"}))
    assert skipped.car_status == "skipped"
    assert skipped.car is None
    changed = skipped.merged_with(
        TripProfileUpdate(car_year=2022, car_make="Honda", car_model="Civic")
    )
    assert changed.car_status == "provided"
    assert changed.car == Car(year=2022, make="Honda", model="Civic")


@pytest.mark.parametrize("data", [{"car_status": "no car"}, {"car": "skip"}])
def test_unstructured_skip_text_is_rejected(data):
    with pytest.raises(ValidationError):
        TripProfileUpdate.model_validate(data)


def test_inconsistent_or_incomplete_car_is_rejected():
    with pytest.raises(ValidationError):
        TripProfileUpdate.model_validate({"car_status": "skipped", "car_year": 2020})
    with pytest.raises(ValidationError):
        TripProfileUpdate.model_validate({"car_year": 2020, "car_make": "Mazda"})
    with pytest.raises(ValidationError):
        TripProfile(car_status="provided")


def test_from_json_empty_when_none():
    assert TripProfile.from_json(None).is_empty() is True


def test_from_json_survives_corrupt_json():
    assert TripProfile.from_json("{not valid json").is_empty() is True
