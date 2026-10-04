"""Deterministic receipts from persisted changes, never model recollection."""

import re
from datetime import datetime

from app.agent.schemas import TripDetailPresentation
from app.agent.trip_profile import TripProfile
from app.models.scheduling_policy import SchedulingPolicy

QUESTIONS = {
    "start_address": "What city or address are you starting from?",
    "destination_address": "What city or address are you traveling to?",
    "num_stops": "How many attraction stops would you like (1–10)?",
    "budget": "What is your hotel budget per night in dollars?",
    "departure_date": "What date would you like to leave?",
    "departure_time": "What time would you like to leave? You can choose 9:00 AM.",
    "car": "Optional car: what year, make, and model will you use, or would you like to skip?",
}
LABELS = {
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
            text = f"Hotel arrival: prefer {value.preferred_hotel_arrival}, latest {value.latest_hotel_arrival}; morning restart: {value.morning_restart}; late driving: {late}"
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
        elif field == "budget":
            text = f"Hotel budget: ${value:g} per night"
        else:
            text = f"{LABELS[field]}: {value}"
        updated.append(text)

    issues = dict(issues)
    for field, pending in after.pending_locations.items():
        issues[field] = (
            f"Please choose a match for '{pending.query}' below, or enter a full city and state or address."
        )
    needed = [
        f"{LABELS.get(field, 'Trip detail')}: {question}" for field, question in issues.items()
    ]
    missing = after.missing_details()
    if "departure_date" in missing and not after.departure_time:
        missing.insert(missing.index("departure_date") + 1, "departure_time")
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
