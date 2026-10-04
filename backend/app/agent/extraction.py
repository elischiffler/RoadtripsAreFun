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
        "traveler_count",
        "hotel_rooms",
        "budget",
        "departure_date",
        "departure_time",
        "car_year",
        "car_make",
        "car_model",
        "car_status",
        "scheduling_policy",
        "evening_interests",
    }
)

EXTRACTION_PROMPT = """Extract trip details supplied by the LATEST user message. Return only one JSON object with a `details` object, such as {"details":{"start_address":"Tampa","destination_address":"Houston","budget":150}}. Omit fields the latest message does not supply. Do not copy saved profile fields into details. For no trip details, return {"details":{}}. Never invent a value.

Allowed details keys: traveler_count, hotel_rooms, start_address, destination_address, num_stops, budget, departure_date, departure_time, car_year, car_make, car_model, car_status, scheduling_policy, evening_interests. Copy location wording exactly as supplied; never expand an abbreviation such as SLO or LA into a city. A bare yes or a location-choice response does not supply a new address. Use departure_date for date wording such as "tomorrow" or "November 10th" and departure_time for time wording such as "11 am". Extract both independently. Use car_status="skipped" only when the user explicitly skips or declines a car. Extract numeric stop count and nightly hotel budget as numbers when clear. Car year, make, and model are independent fields. Optional scheduling_policy is a partial object with preferred_hotel_arrival, latest_hotel_arrival, morning_restart, late_driving (boolean), late_cutoff, using HH:MM local clocks. "I can drive until midnight" explicitly supplies {"late_driving":true,"late_cutoff":"24:00"}; do not turn it on otherwise. "No late driving" supplies late_driving=false. Only extract explicitly stated timing preferences. evening_interests is an array of food, culture, nightlife for optional evening requests, or [] when declined. These are optional and never new planning blockers. Check each clause of the latest message before returning JSON so every supplied field appears. traveler_count is total people INCLUDING the typing person/driver: "just me"=1, "me and my partner"=2, "two of us"=2, "two passengers plus me"=3. A bare "two passengers" is ambiguous: do not guess whether the driver is included; return traveler_count=null and ask the total including the user. Never infer count from car, budget, interests, or persona. Keep invalid explicitly supplied counts as supplied so backend validation can clarify. hotel_rooms is an array of {"adults": integer, "child_ages": [integer ages]} describing the explicit allocation for EACH room. For example "two adults and a child aged 5 in one room" gives [{"adults":2,"child_ages":[5]}]; "3 adults, two rooms: two in one, one in the other, no children" gives [{"adults":2,"child_ages":[]},{"adults":1,"child_ages":[]}]. Count alone, "partner", and "just me" do not confirm adults or rooms. Do not infer room allocation from total headcount or assume children are adults. When the latest message changes occupancy but ages, adult counts or room allocation are incomplete, return hotel_rooms=null to invalidate the old allocation and request clarification. Otherwise omit hotel_rooms when not mentioned. A bare yes confirms a room allocation ONLY if the immediately preceding question explicitly proposed that exact allocation including adults and child ages/no children. The backend validates every value. No prose, markdown, tool blocks, or extra keys."""


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
        if key in TRIP_DETAIL_FIELDS
        and (value is not None or key in {"traveler_count", "hotel_rooms"})
    }


def extract_trip_patch(
    provider: LLMProvider,
    message: str,
    trip: TripProfile,
    *,
    recent_turns: list[LLMMessage] | None = None,
) -> tuple[dict, list[LLMResponse]]:
    """Require a machine-readable patch, with one JSON-format retry."""
    saved = trip.model_dump(mode="json", exclude_none=True)
    messages = [
        LLMMessage(role="system", content=EXTRACTION_PROMPT),
        LLMMessage(
            role="system", content="Saved validated profile for context: " + json.dumps(saved)
        ),
        *[m for m in (recent_turns or [])[-2:]],
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
