"""Mandatory structured trip-detail extraction for each user turn.

The model identifies only what the latest message supplies. Backend tools own
geocoding, normalization, validation, and the persisted profile.
"""

from __future__ import annotations

import json

from app.agent.providers import LLMProvider
from app.agent.schemas import LLMMessage, LLMResponse
from app.agent.trip_profile import TripProfile

TRIP_DETAIL_FIELDS = frozenset(
    {
        "start_address",
        "destination_address",
        "num_stops",
        "budget",
        "departure_date",
        "departure_time",
        "car_year",
        "car_make",
        "car_model",
        "car_status",
    }
)

EXTRACTION_PROMPT = """Extract trip details supplied by the LATEST user message. Return only one JSON object with a `details` object, such as {"details":{"start_address":"Tampa","destination_address":"Houston","budget":150}}. Omit fields the latest message does not supply. Do not copy saved profile fields into details. For no trip details, return {"details":{}}. Never invent a value.

Allowed details keys: start_address, destination_address, num_stops, budget, departure_date, departure_time, car_year, car_make, car_model, car_status. Use departure_date for date wording such as "tomorrow" or "November 10th" and departure_time for time wording such as "11 am". Extract both independently. Use car_status="skipped" only when the user explicitly skips or declines a car. Extract numeric stop count and nightly hotel budget as numbers when clear. Car year, make, and model are independent fields. Check each clause of the latest message before returning JSON so every supplied field appears. The backend validates every value. No prose, markdown, tool blocks, or extra keys."""


class ExtractionFormatError(Exception):
    """The provider responded, but neither attempt contained parseable JSON."""

    def __init__(self, responses: list[LLMResponse]):
        self.responses = responses
        super().__init__("The model did not return valid trip-detail JSON")


def parse_trip_patch(content: str) -> dict:
    """Parse strict model JSON; never interpret prose as data."""
    try:
        payload = json.loads(content)
    except (TypeError, ValueError) as exc:
        raise ValueError("Trip extraction was not valid JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("details"), dict):
        raise ValueError("Trip extraction must contain a details object")
    details = payload["details"]
    return {
        key: value
        for key, value in details.items()
        if key in TRIP_DETAIL_FIELDS and value is not None
    }


def extract_trip_patch(
    provider: LLMProvider, message: str, trip: TripProfile
) -> tuple[dict, list[LLMResponse]]:
    """Require a machine-readable patch, with one JSON-format retry."""
    saved = trip.model_dump(mode="json", exclude_none=True)
    messages = [
        LLMMessage(role="system", content=EXTRACTION_PROMPT),
        LLMMessage(
            role="system", content="Saved validated profile for context: " + json.dumps(saved)
        ),
        LLMMessage(role="user", content=message),
    ]
    responses: list[LLMResponse] = []
    for attempt in range(2):
        response = provider.complete(messages, [])
        responses.append(response)
        try:
            return parse_trip_patch(response.content), responses
        except ValueError as exc:
            if attempt:
                raise ExtractionFormatError(responses) from exc
            messages.append(LLMMessage(role="assistant", content=response.content))
            messages.append(
                LLMMessage(role="system", content="Return only the required JSON object. No prose.")
            )
    raise AssertionError("unreachable")
