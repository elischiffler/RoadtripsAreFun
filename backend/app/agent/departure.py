"""Normalize a trip departure before route and itinerary planning."""

from datetime import UTC, datetime


def is_upcoming_departure(value: datetime, *, now: datetime | None = None) -> bool:
    """Compare the departure instant, including its offset, against UTC now."""
    candidate = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return candidate > (now or datetime.now(UTC))


def normalize_departure(value: str, *, now: datetime | None = None) -> datetime:
    """Require an unambiguous upcoming ISO-8601 datetime with a UTC offset."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("An upcoming departure date and time with a UTC offset is required.")
    try:
        departure = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError("Departure must be an ISO-8601 date and time with a UTC offset.") from exc
    if departure.tzinfo is None or departure.utcoffset() is None:
        raise ValueError("Departure needs a UTC offset, such as -07:00 or Z.")
    if not is_upcoming_departure(departure, now=now):
        raise ValueError("Departure must be in the future.")
    return departure
