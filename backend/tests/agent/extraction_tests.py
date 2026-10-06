"""The model's per-turn patch is strict JSON and never writes profile state itself."""

import pytest

from app.agent.extraction import ExtractionFormatError, extract_trip_patch, parse_trip_patch
from app.agent.providers import FallbackChain
from app.agent.trip_profile import TripProfile

from .conftest import FakeProvider


def test_patch_keeps_supplied_fields_and_ignores_unknowns():
    assert parse_trip_patch(
        '{"details":{"budget":150,"departure_time":"11 am","unrelated":"ignore"}}'
    ) == {"budget": 150, "departure_time": "11 am"}
    assert parse_trip_patch('{"details":{}}') == {}


@pytest.mark.parametrize("content", ["hello", "[]", '{"details":null}'])
def test_patch_rejects_non_json_or_wrong_shape(content):
    with pytest.raises(ValueError):
        parse_trip_patch(content)


def test_extraction_retries_bad_json_once():
    provider = FakeProvider(extraction_responses=["not JSON", '{"details":{"num_stops":8}}'])
    patch, responses = extract_trip_patch(FallbackChain([provider]), "8 stops", TripProfile())
    assert patch == {"num_stops": 8}
    assert len(responses) == 2
    assert provider.extraction_calls == 2


def test_extraction_fails_closed_after_two_bad_json_responses():
    provider = FakeProvider(extraction_responses=["not JSON", "still not JSON"])
    with pytest.raises(ExtractionFormatError):
        extract_trip_patch(FallbackChain([provider]), "8 stops", TripProfile())
