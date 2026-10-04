"""Deterministic receipts from persisted changes, never model recollection."""

import re
from datetime import datetime

from app.agent.schemas import TripDetailPresentation
from app.agent.trip_profile import TripProfile
from app.models.scheduling_policy import SchedulingPolicy
from app.routing.occupancy import COUNT_QUESTION, OCCUPANCY_QUESTION

QUESTIONS = {
    "traveler_count": COUNT_QUESTION,
    "hotel_rooms": OCCUPANCY_QUESTION,
    "start_address": "What city or address are you starting from?",
    "destination_address": "What city or address are you traveling to?",
    "num_stops": "How many attraction stops would you like (1–10)?",
    "budget": "What is your hotel budget per night in dollars?",
    "departure_date": "What date would you like to leave?",
    "departure_time": "What time would you like to leave? You can choose 9:00 AM.",
    "car": "Optional car: would you like to provide a car for this trip, or skip it?",
}
LABELS = {
    "traveler_count": "Travelers (including you)",
    "hotel_rooms": "Hotel occupancy",
    "persona_weights": "Trip personality",
    "start_address": "Starting location",
    "destination_address": "Destination",
    "num_stops": "Attraction stops",
    "budget": "Hotel budget",
    "departure_date": "Departure date",
    "departure_time": "Departure time",
    "start_timezone": "Starting location timezone",
    "car": "Optional car",
    "scheduling_policy": "Hotel and driving times",
    "evening_interests": "Evening suggestions",
}


def detail_request(message: str) -> str | None:
    """Recognize explicit summary/collection requests without replacing general chat."""
    if re.search(
        r"^(?:summary|recap|summarize)(?: please)?[.!?]?$|"
        r"\b(summary|summarize|recap|show|list)\b.*\b(trip|details)\b",
        message,
        re.I,
    ):
        return "summary"
    if re.search(
        r"\b(what (else )?do you (still )?need|what (trip )?details are missing|"
        r"what('s| is) (still )?(next|missing|needed)|"
        r"plan (my |a )?(trip|road trip)|ready to plan)\b",
        message,
        re.I,
    ):
        return "collect"
    return None


def collection_fields(profile: TripProfile) -> list[str]:
    missing = profile.missing_details()
    if "departure_date" in missing and not profile.departure_time:
        missing.insert(missing.index("departure_date") + 1, "departure_time")
    return missing


def present_details(
    before: TripProfile,
    after: TripProfile,
    issues: dict[str, str],
    *,
    full: bool = False,
    notes: list[str] | None = None,
) -> TripDetailPresentation:
    updated = []
    for field in (
        "start_address",
        "destination_address",
        "num_stops",
        "traveler_count",
        "hotel_rooms",
        "persona_weights",
        "budget",
        "start_date",
        "departure_time",
        "car_status",
        "scheduling_policy",
        "evening_interests",
    ):
        value = getattr(after, field)
        changed = value != getattr(before, field)
        if field == "car_status":
            changed |= after.car != before.car
        if not full and not changed:
            continue
        if value is None or field in issues or field in after.pending_locations:
            continue
        if field == "scheduling_policy":
            if full and not changed and value == SchedulingPolicy():
                continue
            late = f"until {value.late_cutoff}" if value.late_driving else "off"
            text = f"Hotel arrival: prefer {value.preferred_hotel_arrival}, latest {value.latest_hotel_arrival}; morning restart: {value.morning_restart}; late driving: {late}; final destination latest: {value.arrival_cutoff(final=True)}"
        elif field == "evening_interests":
            text = "Evening suggestions: " + (", ".join(value) if value else "off")
        elif field == "start_date":
            try:
                departure = datetime.fromisoformat(value)
                text = "Departure: " + departure.isoformat(sep=" ")
            except ValueError:
                continue  # Legacy malformed dates must not become confirmed receipts.
            if after.start_timezone:
                text += " (" + after.start_timezone + ")"
        elif field == "departure_time":
            if after.start_date:
                continue  # The canonical departure above already includes the time.
            text = "Departure time: " + value
            if after.start_timezone:
                text += " (" + after.start_timezone + ")"
        elif field == "car_status":
            if "car" in issues or value == "unanswered":
                continue
            car = after.car
            text = "Optional car: " + (f"{car.year} {car.make} {car.model}" if car else "skipped")
        elif field == "hotel_rooms":
            text = "Hotel rooms: " + "; ".join(
                f"Room {i + 1}: {room.adults} adults, "
                + (
                    "children aged " + ", ".join(map(str, room.child_ages))
                    if room.child_ages
                    else "no children"
                )
                for i, room in enumerate(value)
            )
        elif field == "persona_weights":
            text = "Trip personality: " + ", ".join(
                f"{key} {weight:g}" for key, weight in value.items()
            )
        elif field == "budget":
            text = f"Hotel budget: ${value:g} per room per night"
        else:
            text = f"{LABELS[field]}: {value}"
        updated.append(text)

    if after.pending_departure and (full or after.pending_departure != before.pending_departure):
        updated.append("Departure date (awaiting validation): " + after.pending_departure.date)
    issues = dict(issues)
    if (
        after.start_address
        and not after.start_timezone
        and not after.start_date
        and "start_address" not in after.pending_locations
    ):
        issues["start_timezone"] = (
            "The selected starting location has no usable timezone. Please enter a different city or address."
        )
    if after.pending_departure:
        if "start_address" in after.pending_locations or not after.start_timezone:
            issues["departure_date"] = (
                "Your date is saved; confirm the starting location to finish setting it."
            )
        else:
            try:
                after.pending_departure.resolve(after.departure_time, after.start_timezone)
            except ValueError as exc:
                issues["departure_date"] = str(exc)
    if (
        after.traveler_count is not None
        and after.hotel_rooms
        and "hotel_rooms" in after.missing_details()
    ):
        issues["hotel_rooms"] = "Room occupants must equal the total travelers including you."
    for field, pending in after.pending_locations.items():
        issues[field] = (
            f"Confirm the suggested address: {pending.candidates[0].address}. If it is wrong, type a different city or address."
            if pending.candidates
            else f"No match found for '{pending.query}'. Please enter a city and state or address."
        )
    needed = [
        f"{LABELS.get(field, 'Trip detail')}: "
        + (
            (
                "Car verification is unavailable. Would you like to retry verification, or skip the car?"
                if "verification is unavailable" in question
                else "Would you like to correct the car details, or skip the car?"
            )
            if field == "car"
            else question
        )
        for field, question in issues.items()
    ]
    # Finish the address choices before introducing the next collection questions.
    missing = [] if after.pending_locations else collection_fields(after)
    # Prioritize validation questions; then ask at most two actionable details.
    for field in missing:
        if len(needed) >= 2:
            break
        if field in issues:
            continue
        if field == "departure_date" and "start_timezone" in issues:
            continue
        needed.append(QUESTIONS[field])
    return TripDetailPresentation(
        title="Trip details" if full else "Updated trip details",
        updated=updated,
        needed=needed[:2],
        notes=notes or [],
    )
