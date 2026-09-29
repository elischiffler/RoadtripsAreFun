"""Resolve a traveler's departure wording in the geocoded start timezone."""

from __future__ import annotations

import calendar
import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_MONTHS = {name.lower(): number for number, name in enumerate(calendar.month_name) if name}
_MONTHS.update({name.lower(): number for number, name in enumerate(calendar.month_abbr) if name})
_MONTHS["sept"] = 9
_MONTH_DAY = re.compile(r"([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?", re.I)


def timezone_from_location(location: object) -> str | None:
    """Use OpenCage's IANA name; never infer an offset from coordinates."""
    raw = getattr(location, "raw", None)
    annotations = raw.get("annotations", {}) if isinstance(raw, dict) else {}
    timezone = annotations.get("timezone", {}) if isinstance(annotations, dict) else {}
    name = timezone.get("name") if isinstance(timezone, dict) else None
    if not isinstance(name, str) or not name or re.fullmatch(r"GMT[+-]\d+", name):
        return None
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return None
    return name


def _localize(naive: datetime, zone: ZoneInfo) -> datetime:
    first = naive.replace(tzinfo=zone, fold=0)
    second = naive.replace(tzinfo=zone, fold=1)
    if first.utcoffset() != second.utcoffset():
        raise ValueError(
            "That departure time is ambiguous or does not exist locally; please choose another time"
        )
    if first.astimezone(UTC).astimezone(zone).replace(tzinfo=None) != naive:
        raise ValueError("That departure time does not exist locally; please choose another time")
    return first


def resolve_departure(wording: str, timezone: str, now: datetime | None = None) -> str:
    """Return an upcoming ISO datetime with offset, or explain what needs clarification."""
    try:
        zone = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("The starting location has no usable timezone; please clarify it") from exc
    local_now = (now or datetime.now(UTC)).astimezone(zone)
    text = wording.strip().rstrip(".") if isinstance(wording, str) else ""
    if not text:
        raise ValueError("Please provide a departure date")

    if re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d", text):
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Please provide a valid departure date and time") from exc
        departure = parsed.astimezone(zone) if parsed.tzinfo else _localize(parsed, zone)
        if departure <= local_now:
            raise ValueError("Departure must be in the future; please choose a later date or time")
        return departure.isoformat()

    time_match = re.search(r"(?:\s+at\s+|\s+)(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s*$", text, re.I)
    hour, minute = 9, 0
    if time_match:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        meridiem = time_match.group(3).lower()
        if not 1 <= hour <= 12 or minute > 59:
            raise ValueError("Please provide a valid departure time")
        hour = hour % 12 + (12 if meridiem == "pm" else 0)
        text = text[: time_match.start()].strip()
    elif match := re.search(r"\s+at\s+(noon|midnight)$", text, re.I):
        hour = 12 if match.group(1).lower() == "noon" else 0
        text = text[: match.start()].strip()
    elif re.search(r"\s+at\s+\d", text, re.I):
        time_match = re.search(r"\s+at\s+(\d{1,2}):(\d{2})$", text, re.I)
        if not time_match:
            raise ValueError("Please clarify the departure time, for example 2:30 PM")
        hour, minute = int(time_match.group(1)), int(time_match.group(2))
        if hour > 23 or minute > 59:
            raise ValueError("Please provide a valid departure time")
        text = text[: time_match.start()].strip()
    elif time_match := re.search(r"\s+(\d{1,2}):(\d{2})$", text):
        hour, minute = int(time_match.group(1)), int(time_match.group(2))
        if hour > 23 or minute > 59:
            raise ValueError("Please provide a valid departure time")
        text = text[: time_match.start()].strip()

    yearless = False
    if text.lower() in {"today", "tomorrow"}:
        day = local_now.date() + timedelta(days=text.lower() == "tomorrow")
    elif match := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text):
        try:
            day = datetime(int(match.group(1)), int(match.group(2)), int(match.group(3))).date()
        except ValueError as exc:
            raise ValueError("Please provide a valid departure date") from exc
    elif match := _MONTH_DAY.fullmatch(text):
        month = _MONTHS.get(match.group(1).lower())
        if month is None:
            raise ValueError("Please spell out the departure month")
        day_number = int(match.group(2))
        yearless = match.group(3) is None
        year = local_now.year if yearless else int(match.group(3))
        for candidate_year in range(year, year + (9 if yearless else 1)):
            try:
                candidate = datetime(candidate_year, month, day_number, hour, minute)
            except ValueError:
                continue
            if not yearless or _localize(candidate, zone) > local_now:
                day = candidate.date()
                break
        else:
            raise ValueError("Please provide a valid departure date")
    else:
        raise ValueError(
            "Please clarify the departure date with a month name and day, or YYYY-MM-DD"
        )

    departure = _localize(datetime(day.year, day.month, day.day, hour, minute), zone)
    if departure <= local_now:
        raise ValueError("Departure must be in the future; please choose a later date or time")
    return departure.isoformat()
