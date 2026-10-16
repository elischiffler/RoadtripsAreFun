"""Normalize literal market calendars without inferring opening information.

The output is an intersection of every supported source restriction. Entries in
``weekly_windows`` and ``seasons`` are alternatives within that intersection;
season end dates are inclusive. Weekdays anchor the day a window opens. Clocks
are local wall times and intentionally have no timezone. Runtime scheduling must
resolve an IANA zone and fit the entire visit inside an eligible window.

Unknown text, incomplete official schedules and contradictory restrictions all
produce an empty calendar with explicit reasons. This module never fetches data.
"""

import calendar
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

SCHEMA = "roadtrips-source-visit-calendar/1"
DAYS = {
    form: index
    for index, forms in enumerate(
        (
            "mon monday mondays",
            "tue tues tuesday tuesdays",
            "wed wednesday wednesdays",
            "thu thur thurs thursday thursdays",
            "fri friday fridays",
            "sat saturday saturdays",
            "sun sunday sundays",
        )
    )
    for form in forms.split()
}
MONTHS = {
    name.lower(): month
    for month in range(1, 13)
    for name in (calendar.month_name[month], calendar.month_abbr[month])
} | {"sept": 9}
DAY_PATTERN = "|".join(sorted(DAYS, key=len, reverse=True))
MONTH_PATTERN = "|".join(sorted(MONTHS, key=len, reverse=True))
CLOCK = r"(?:(?:0?[1-9]|1[0-2])(?::[0-5]\d)?\s*[ap]m|(?:[01]\d|2[0-3]):[0-5]\d|noon|midnight)"
CLOCK_RANGE = re.compile(rf"(?<![\w:])({CLOCK})\s*(?:-|to|through)\s*({CLOCK})(?!\w)")
DAY_RANGE = re.compile(rf"\b({DAY_PATTERN})\.?\s*(?:-|to|through)\s*({DAY_PATTERN})\b\.?")
DAY_WORD = re.compile(rf"\b({DAY_PATTERN})\b\.?")
YEAR_ROUND = re.compile(r"\byear\s*-?\s*round\b")
CALENDAR_FIELDS = (
    "season",
    "days",
    "hours",
    "months",
    "start_date",
    "end_date",
    "start_time",
    "end_time",
    "start",
    "end",
    "weather_qualification",
)


def _endpoint(prefix):
    return (
        rf"(?P<{prefix}month>{MONTH_PATTERN})\b"
        rf"(?:\s+(?P<{prefix}day>[0-3]?\d)(?:st|nd|rd|th)?(?!\d))?"
        rf"(?:,?\s+(?P<{prefix}year>(?:19|20)\d{{2}}))?"
    )


MONTH_RANGE = re.compile(rf"\b{_endpoint('a')}\s*(?:-|to|through)\s*{_endpoint('b')}")
ISO_RANGE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\s*(?:-|to|through)\s*(\d{4}-\d{2}-\d{2})\b")


@dataclass
class _Restrictions:
    days: list = field(default_factory=list)
    clocks: list = field(default_factory=list)
    seasons: list = field(default_factory=list)


def _plain(value):
    if not isinstance(value, str):
        raise ValueError("non_text_calendar_field")
    text = unicodedata.normalize("NFKC", value).lower()
    text = text.replace("–", "-").replace("—", "-").replace("−", "-")
    # PDF cells can wrap the letters in an otherwise explicit meridiem.
    text = re.sub(r"([ap])(?:\s+|\.)m\b\.?", r"\1m", text)
    return " ".join(text.split())


def _clock(value):
    if value in {"noon", "midnight"}:
        return 720 if value == "noon" else 0
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*([ap]m)", value)
    if match:
        hour, minute, meridiem = int(match[1]), int(match[2] or 0), match[3]
        return (hour % 12 + (12 if meridiem == "pm" else 0)) * 60 + minute
    hour, minute = value.split(":")
    return int(hour) * 60 + int(minute)


def _month_bound(match, prefix, *, ending):
    month = MONTHS[match[prefix + "month"]]
    year = int(match[prefix + "year"] or 2000)
    day = int(match[prefix + "day"] or (calendar.monthrange(year, month)[1] if ending else 1))
    return date(year, month, day)


def _parse(value):
    """Consume the entire supported calendar grammar, or fail closed."""
    text, result = _plain(value), _Restrictions()
    if not text:
        return result
    if re.search(r"\b(?:and|every)\s*[.,;]*$", text):
        raise ValueError("incomplete_calendar_clause")

    def iso_range(match):
        start, end = date.fromisoformat(match[1]), date.fromisoformat(match[2])
        if end < start:
            raise ValueError("reversed_dated_season")
        result.seasons.append(("dated", start, end))
        return " "

    text = ISO_RANGE.sub(iso_range, text)

    def month_range(match):
        if bool(match["ayear"]) != bool(match["byear"]):
            raise ValueError("incomplete_dated_season")
        start, end = _month_bound(match, "a", ending=False), _month_bound(match, "b", ending=True)
        kind = "dated" if match["ayear"] else "annual"
        if kind == "dated" and end < start:
            raise ValueError("reversed_dated_season")
        result.seasons.append((kind, start, end))
        return " "

    text = MONTH_RANGE.sub(month_range, text)
    if len(result.seasons) > 1:
        raise ValueError("multiple_season_ranges")
    if YEAR_ROUND.search(text):
        if result.seasons:
            raise ValueError("qualified_year_round")
        result.seasons.append(("annual", date(2000, 1, 1), date(2000, 12, 31)))
        text = YEAR_ROUND.sub(" ", text)

    def clock_range(match):
        first, last = match[1], match[2]
        # Never carry a meridiem from one endpoint to the other.
        meridiems = [bool(re.search(r"[ap]m$|noon$|midnight$", part)) for part in (first, last)]
        if meridiems[0] != meridiems[1]:
            raise ValueError("mixed_or_missing_meridiem")
        if not any(meridiems) and not any(
            int(part.split(":")[0]) == 0 or int(part.split(":")[0]) > 12 for part in (first, last)
        ):
            raise ValueError("ambiguous_unqualified_clock_format")
        start, end = _clock(first), _clock(last)
        if start == end:
            raise ValueError("zero_or_unspecified_full_day_window")
        result.clocks.append((start, end + (1440 if end < start else 0)))
        return " "

    text = CLOCK_RANGE.sub(clock_range, text)
    if len(result.clocks) > 1:
        # Pairing multiple day/time clauses requires a richer grammar. Flattening
        # their weekdays and clocks could incorrectly widen a particular day.
        raise ValueError("multiple_clock_ranges")

    def day_range(match):
        start, end = DAYS[match[1]], DAYS[match[2]]
        result.days.append({(start + offset) % 7 for offset in range((end - start) % 7 + 1)})
        return " "

    text = DAY_RANGE.sub(day_range, text)
    days = {DAYS[match[1]] for match in DAY_WORD.finditer(text)}
    if days:
        result.days.append(days)
    text = DAY_WORD.sub(" ", text)
    if result.days:
        # Within a literal day list/range, the listed days are alternatives.
        result.days = [set().union(*result.days)]

    # These exact nonrestrictive phrases appear in the immutable originals.
    # Any additional words, qualifiers or numbers remain unsupported.
    text = re.sub(r"\bavailable products:\s*fresh fruits\s*\.?$", " ", text)
    text = re.sub(r"\brain or shine\b\.?", " ", text)
    text = re.sub(r"\b(?:every|and)\b", " ", text)
    text = re.sub(r"[\s,;:.()·&/]+", "", text)
    if text:
        raise ValueError("unsupported_or_ambiguous_calendar_text")
    return result


def _receipt(fact):
    fields = fact.get("fields", {})
    if not isinstance(fields, dict):
        raise ValueError("invalid_source_fields")
    url = urlsplit(fact.get("source_url", ""))
    if url.scheme not in {"http", "https"} or not url.netloc:
        raise ValueError("missing_source_url")
    if not re.fullmatch(r"[0-9a-f]{64}", fact.get("snapshot_sha256", "")):
        raise ValueError("missing_snapshot_hash")
    checked = datetime.fromisoformat(fact.get("checked_at", ""))
    if checked.utcoffset() is None:
        raise ValueError("missing_aware_acquisition_time")
    return {
        **{
            key: fact[key]
            for key in (
                "feed",
                "record_id",
                "source_url",
                "snapshot_sha256",
                "checked_at",
                "pdf_page",
                "table_index",
                "row_index",
            )
            if key in fact
        },
        "fields": {key: fields[key] for key in CALENDAR_FIELDS if key in fields},
    }


def _segments(values):
    """Consecutive inclusive integer intervals in stable ascending order."""
    segments = []
    for value in sorted(values):
        if segments and value == segments[-1][1] + 1:
            segments[-1][1] = value
        else:
            segments.append([value, value])
    return segments


def _seasons(restrictions):
    annual_days = set(range(366))
    epoch = date(2000, 1, 1)
    dated = []
    for kind, start, end in restrictions:
        if kind == "dated":
            dated.append((start, end))
            continue
        first, last = (start - epoch).days, (end - epoch).days
        permitted = (
            set(range(first, last + 1))
            if first <= last
            else set(range(first, 366)) | set(range(last + 1))
        )
        annual_days &= permitted
    if dated:
        start, end = max(item[0] for item in dated), min(item[1] for item in dated)
        if (end - start).days > 3660:
            raise ValueError("dated_calendar_span_exceeds_review_bound")
        allowed = set()
        for offset in range(max(0, (end - start).days + 1)):
            candidate = start + timedelta(days=offset)
            annual_day = (date(2000, candidate.month, candidate.day) - epoch).days
            if annual_day in annual_days:
                allowed.add(candidate.toordinal())
        return [
            {
                "kind": "dated",
                "start": date.fromordinal(a).isoformat(),
                "end": date.fromordinal(b).isoformat(),
            }
            for a, b in _segments(allowed)
        ]
    return [
        {
            "kind": "annual",
            "start": (epoch + timedelta(days=a)).strftime("%m-%d"),
            "end": (epoch + timedelta(days=b)).strftime("%m-%d"),
        }
        for a, b in _segments(annual_days)
    ]


def build(fact_groups):
    """Build a source calendar from already authenticated immutable fact groups.

    A blank native field supplies no constraint; it is retained in the receipt.
    Positive official weekdays, clocks and seasons are required. Source receipt
    freshness/checksum validation remains the admitting adapter's responsibility.
    """
    output = {
        "schema_version": SCHEMA,
        "weekly_windows": [],
        "seasons": [],
        "date_overrides": [],
        "fixed_starts": [],
        "source_receipts": [],
        "unknown_reasons": [],
    }
    all_days, all_clocks, all_seasons = set(range(7)), [], []
    official_clock = official_season = False
    for index, fact in enumerate(fact_groups):
        feed = fact.get("feed", "unknown")
        label = f"{feed}[{index}]"
        try:
            receipt = _receipt(fact)
        except (TypeError, ValueError):
            output["unknown_reasons"].append(label + ":unverified_source_receipt")
            continue
        output["source_receipts"].append(receipt)
        if feed not in {"kaggle_feed", "canonical_feed", "official_visitor_facts"}:
            output["unknown_reasons"].append(label + ":unsupported_source_feed")
            continue
        fields, group = receipt["fields"], _Restrictions()
        for key in ("season", "days", "hours", "months"):
            if fields.get(key) in (None, ""):
                continue
            try:
                parsed = _parse(fields[key])
            except (TypeError, ValueError) as exc:
                output["unknown_reasons"].append(f"{label}.{key}:{exc}")
                continue
            group.days.extend(parsed.days)
            group.clocks.extend(parsed.clocks)
            group.seasons.extend(parsed.seasons)
        for first, last in (("start", "end"), ("start_date", "end_date")):
            if fields.get(first) in (None, "") and fields.get(last) in (None, ""):
                continue
            try:
                start, end = date.fromisoformat(fields[first]), date.fromisoformat(fields[last])
                if end < start:
                    raise ValueError
                group.seasons.append(("dated", start, end))
            except (KeyError, TypeError, ValueError):
                output["unknown_reasons"].append(label + ":unresolved_dated_boundaries")
        if fields.get("start_time") or fields.get("end_time"):
            try:
                parsed = _parse(f"{fields.get('start_time', '')} - {fields.get('end_time', '')}")
                if not parsed.clocks:
                    raise ValueError
                group.clocks.extend(parsed.clocks)
            except (TypeError, ValueError):
                output["unknown_reasons"].append(label + ":unresolved_clock_boundaries")
        if fields.get("weather_qualification"):
            try:
                weather = _plain(fields["weather_qualification"]).rstrip(".")
            except ValueError:
                weather = None
            if weather != "rain or shine":
                output["unknown_reasons"].append(label + ":unsupported_weather_qualification")
        for days in group.days:
            all_days &= days
        all_clocks.extend(group.clocks)
        all_seasons.extend(group.seasons)
        if feed == "official_visitor_facts":
            official_clock |= bool(group.days and group.clocks)
            official_season |= bool(group.seasons)
    if not official_clock:
        output["unknown_reasons"].append("missing_positive_official_weekly_clock")
    if not official_season:
        output["unknown_reasons"].append("missing_positive_official_season")
    if not all_days:
        output["unknown_reasons"].append("empty_weekday_intersection")
    if all_clocks:
        opens, closes = max(item[0] for item in all_clocks), min(item[1] for item in all_clocks)
        if opens >= closes:
            output["unknown_reasons"].append("empty_clock_intersection")
    else:
        opens = closes = 0
    try:
        seasons = _seasons(all_seasons)
    except ValueError as exc:
        seasons = []
        output["unknown_reasons"].append(str(exc))
    if not seasons:
        output["unknown_reasons"].append("empty_season_intersection")
    if not output["unknown_reasons"]:
        output["weekly_windows"] = [
            {
                "weekdays": sorted(all_days),
                "opens": f"{opens // 60:02d}:{opens % 60:02d}",
                "closes": f"{closes % 1440 // 60:02d}:{closes % 60:02d}",
                "end_day_offset": closes // 1440,
            }
        ]
        output["seasons"] = seasons
    return output
