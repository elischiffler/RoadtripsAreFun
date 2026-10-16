"""Offline replay of individually reviewed official venue opening facts.

This is a source preparation adapter, not an HTML opening-hours guesser. The
immutable review inventory binds each normalization to complete original bytes,
exact extraction locators and all retained/current source variants. Ordinary
runtime imports do not read research files or perform network requests.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from lxml import html

SCHEMA = "roadtrips-source-visit-calendar/1"
INVENTORY_FILE = "venue-source-inventory.json"
INVENTORY_SHA256 = "d31dbc211d909585f7d20a30bb52af45f6336e92177e75af5070b1353acf8e21"
MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_AGE = timedelta(days=30)
_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
_SHORT_DAYS = {day[:2]: n for n, day in enumerate(_DAYS)}


class VenueCalendarError(ValueError):
    """Pinned originals, reviewed facts or source freshness failed validation."""


def _instant(value: str) -> datetime:
    point = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if point.utcoffset() is None:
        raise VenueCalendarError("Receipt requires an aware acquisition instant")
    return point.astimezone(UTC)


def visible_lines(raw: bytes) -> list[str]:
    """Exact locator normalization: collapse whitespace in individual HTML text nodes."""
    tree = html.fromstring(raw)
    for element in tree.xpath("//script|//style|//noscript"):
        element.drop_tree()
    return [" ".join(text.split()) for text in tree.xpath("//text()") if text.strip()]


def validate_extraction(raw: bytes, extraction: dict) -> None:
    """Validate literal facts against their original body, never a derived text file."""
    kind = extraction["kind"]
    if kind == "visible_lines":
        lines = visible_lines(raw)
        start, end = extraction["start_line"], extraction["end_line"]
        if not (type(start) is int and type(end) is int and 1 <= start <= end <= len(lines)):
            raise VenueCalendarError("Visible-text locator is out of bounds")
        value = "\n".join(lines[start - 1 : end])
        expected = extraction["literal"]
    elif kind == "javascript_json":
        scripts = html.fromstring(raw).xpath("//script")
        script = scripts[extraction["script_index"]].text or ""
        marker = "var " + extraction["assignment"] + " = "
        if script.count(marker) != 1:
            raise VenueCalendarError("Embedded dated JSON assignment must be unique")
        value = json.JSONDecoder().raw_decode(script.split(marker, 1)[1])[0]
        for part in extraction["path"]:
            value = value[part]
        if "html_xpath" in extraction:
            value = html.fromstring(value).xpath(extraction["html_xpath"]).strip()
        expected = extraction["value"]
    elif kind == "jsonld":
        scripts = html.fromstring(raw).xpath('//script[@type="application/ld+json"]')
        index = extraction["script_index"]
        if type(index) is not int or not 0 <= index < len(scripts):
            raise VenueCalendarError("Structured-hours locator is out of bounds")
        value = json.loads(scripts[index].text or "")
        for part in extraction["path"]:
            value = value[part]
        expected = extraction["value"]
    elif kind == "xpath_text":
        elements = html.fromstring(raw).xpath(extraction["xpath"])
        if len(elements) != 1:
            raise VenueCalendarError("Named holiday table locator must be unique")
        value = " ".join(" ".join(elements[0].xpath(".//text()")).split())
        expected = extraction["literal"]
    else:
        raise VenueCalendarError("Unsupported extraction locator")
    if value != expected:
        raise VenueCalendarError("Extracted literal does not match the original body")


def _minutes(clock: str) -> int:
    if not isinstance(clock, str) or re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", clock) is None:
        raise VenueCalendarError("Clock requires literal normalized HH:MM")
    hours, minutes = map(int, clock.split(":"))
    return hours * 60 + minutes


def _clock(minutes: int) -> str:
    return f"{minutes % 1440 // 60:02d}:{minutes % 60:02d}"


def _window(day_numbers: list[int], opens: str, closes: str) -> dict:
    if opens == closes:
        raise VenueCalendarError("Ambiguous equal structured clocks")
    return {
        "weekdays": day_numbers,
        "opens": opens,
        "closes": closes,
        "end_day_offset": int(closes <= opens),
    }


def structured_layer(extraction: dict) -> dict | None:
    """Normalize only complete explicit Schema.org clocks; unknown syntax fails closed."""
    value = extraction["value"]
    if value in ("", []):
        return None
    field = extraction["path"][-1]
    windows = []
    if field == "openingHours":
        values = [value] if isinstance(value, str) else value
        for text in values:
            for token in text.split(","):
                if not token.strip():
                    continue
                found = re.fullmatch(r"\s*([A-Z][a-z]) (\d\d:\d\d)-(\d\d:\d\d)\s*", token)
                if not found or found[1] not in _SHORT_DAYS:
                    raise VenueCalendarError("Unreviewed structured openingHours syntax")
                _minutes(found[2])
                _minutes(found[3])
                windows.append(_window([_SHORT_DAYS[found[1]]], found[2], found[3]))
    elif field in {"openingHoursSpecification", "specialOpeningHoursSpecification"}:
        specs = [value] if isinstance(value, dict) else value
        for item in specs:
            if item.get("validFrom") or item.get("validThrough"):
                raise VenueCalendarError(
                    "Dated structured clocks need an explicit reviewed profile"
                )
            days = item["dayOfWeek"]
            days = [days] if isinstance(days, str) else days
            names = [day.rsplit("/", 1)[-1] for day in days]
            if not names or any(day not in _DAYS for day in names):
                raise VenueCalendarError("Unrecognized structured weekdays")
            _minutes(item["opens"])
            _minutes(item["closes"])
            # Equal clocks can mean a closure or 24-hour opening; never guess.
            if item["opens"] == item["closes"]:
                raise VenueCalendarError("Ambiguous equal structured clocks")
            windows.append(
                _window([_DAYS.index(day) for day in names], item["opens"], item["closes"])
            )
    else:
        raise VenueCalendarError("Unrecognized structured opening-hours field")
    return {"windows": windows}


def _intervals(layer: dict, day: date) -> list[tuple[int, int]]:
    if (
        layer.get("start", "0001-01-01") > day.isoformat()
        or layer.get("end", "9999-12-31") < day.isoformat()
    ):
        return []
    result = []
    windows = (
        layer["date_windows"].get(day.isoformat(), [])
        if "date_windows" in layer
        else layer["windows"]
    )
    for window in windows:
        if day.weekday() not in window["weekdays"] or day.month not in window.get(
            "months", range(1, 13)
        ):
            continue
        if any(type(number) is not int or not 0 <= number <= 6 for number in window["weekdays"]):
            raise VenueCalendarError("Invalid weekday number")
        opens = _minutes(window["opens"])
        closes = _minutes(window["closes"]) + 1440 * window.get("end_day_offset", 0)
        if not 0 < closes - opens <= 1440:
            raise VenueCalendarError("Invalid opening interval")
        if "last_entry" in window:
            # Runtime contract lacks a last-admission field: ending the whole
            # visit by that cutoff is conservative, including the full dwell.
            closes = min(closes, _minutes(window["last_entry"]))
        if opens < closes:
            result.append((opens, closes))
    return result


def intersect_layers(layers: list[dict], day: date) -> list[dict]:
    """Intersect every feed; retain split services rather than merging across gaps."""
    intervals = [(0, 2880)] if layers else []
    for layer in layers:
        intervals = [
            (max(a, c), min(b, d))
            for a, b in intervals
            for c, d in _intervals(layer, day)
            if max(a, c) < min(b, d)
        ]
    return [
        {"opens": _clock(a), "closes": _clock(b), "end_day_offset": int(b >= 1440)}
        for a, b in sorted(set(intervals))
    ]


def compile_calendar(plan: dict, layers: list[dict], start: date, end: date, receipts: list[dict]):
    """Expand literal recurrences into a bounded review scope, without inventing seasons."""
    if not 0 <= (end - start).days < 30:
        raise VenueCalendarError("Review scope must be at most thirty calendar dates")
    known_closed = set(plan.get("dated_closures", []))
    annual = set(plan.get("annual_closures", []))
    overrides, withheld = [], []
    day = start
    while day <= end:
        conditions = []
        for condition in plan.get("omit_conditions", []):
            applies = (condition["kind"] == "date" and condition["date"] == day.isoformat()) or (
                condition["kind"] in {"weekday", "first_weekday"}
                and day.weekday() == condition["weekday"]
                and (condition["kind"] == "weekday" or day.day <= 7)
            )
            if applies:
                conditions.append(condition["reason"])
        if day.isoformat() in known_closed or day.strftime("%m-%d") in annual:
            overrides.append({"date": day.isoformat(), "windows": []})
        elif conditions:
            # Omission with no weekly fallback withholds scheduling; it does
            # not claim the operator physically closes for ineligible parties.
            withheld.append({"date": day.isoformat(), "unknown_reasons": conditions})
        else:
            windows = intersect_layers(layers, day)
            if windows:
                overrides.append({"date": day.isoformat(), "windows": windows})
        day += timedelta(days=1)
    return {
        "schema_version": SCHEMA,
        "weekly_windows": [],
        "seasons": [],
        "date_overrides": overrides,
        "annual_closures": sorted(annual),
        "fixed_starts": [],
        "source_receipts": receipts,
        "unknown_reasons": list(plan.get("holds", [])),
    }, withheld


def _receipt(root: Path, source: dict, now: datetime) -> tuple[dict, list[dict]]:
    parsed = urlsplit(source["source_url"])
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
    ):
        raise VenueCalendarError("Source URL must be an ordinary public HTTP(S) URL")
    acquired = _instant(source["checked_at"])
    if not timedelta(0) <= now - acquired <= MAX_AGE:
        raise VenueCalendarError("Source acquisition is future-dated or older than thirty days")
    body = (root / source["body_path"]).resolve()
    if not body.is_relative_to(root) or not body.is_file():
        raise VenueCalendarError("Original body must exist inside the evidence root")
    if not 0 < source["bytes"] <= MAX_SOURCE_BYTES or body.stat().st_size != source["bytes"]:
        raise VenueCalendarError("Original body length is invalid")
    raw = body.read_bytes()
    if hashlib.sha256(raw).hexdigest() != source["snapshot_sha256"]:
        raise VenueCalendarError("Original body SHA256 mismatch")
    if not source["extractions"]:
        raise VenueCalendarError("Receipt has no exact source extraction")
    structured = []
    for extraction in source["extractions"]:
        validate_extraction(raw, extraction)
        if extraction["kind"] == "jsonld":
            layer = structured_layer(extraction)
            if layer:
                structured.append(layer)
    return {
        "source_url": source["source_url"],
        "snapshot_sha256": source["snapshot_sha256"],
        "checked_at": source["checked_at"],
        "body_path": str(body),
        "extractions": source["extractions"],
        "source_role": source["role"],
    }, structured


def build_entries(research_root: str | Path, *, checked_at: str | None = None):
    """Return validated companion entries and a full held/partial-date ledger.

    A new source/profile requires a separate reviewed inventory and code pin.
    Nothing is written; source rows, native points and original provenance are
    not inputs to mutation. Bare catalog UUID identities are preserved exactly.
    """
    root = Path(research_root).resolve()
    path = root / INVENTORY_FILE
    if not path.is_file() or path.stat().st_size > MAX_SOURCE_BYTES:
        raise VenueCalendarError("Missing or oversized reviewed inventory")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != INVENTORY_SHA256:
        raise VenueCalendarError("Reviewed inventory SHA256 mismatch")
    inventory = json.loads(raw)
    if inventory["schema_version"] != "roadtrips-reviewed-venue-calendar-input/1":
        raise VenueCalendarError("Unsupported reviewed inventory schema")
    now = _instant(checked_at) if checked_at else datetime.now(UTC)
    start, end = (
        date.fromisoformat(inventory["horizon_start"]),
        date.fromisoformat(inventory["horizon_end"]),
    )
    entries, holds, partial, identities = [], [], [], set()
    for item in inventory["items"]:
        identity = item["source_id"]
        if identity in identities or identity.startswith("overture:"):
            raise VenueCalendarError("Duplicate or provider-prefixed catalog identity")
        identities.add(identity)
        receipts, structured = [], []
        for source in item["sources"]:
            receipt, layers = _receipt(root, source, now)
            receipts.append(receipt)
            structured.extend(layers)
        if not receipts:
            raise VenueCalendarError("Venue requires an official original receipt")
        layers = [*item["plan"]["layers"], *structured]
        calendar, withheld = compile_calendar(item["plan"], layers, start, end, receipts)
        constraints = [
            {
                "source_url": r["source_url"],
                "snapshot_sha256": r["snapshot_sha256"],
                "extraction": extraction,
            }
            for r in receipts
            for extraction in r["extractions"]
        ]
        entry = {
            "source_id": identity,
            "source_visit_calendar": calendar,
            "source_constraints": constraints,
            "transformation": {
                "adapter": "reviewed-official-venue-calendar/1",
                "inventory_sha256": INVENTORY_SHA256,
                "profile": item["slug"],
                "scope": item["plan"]["scope"],
                "review_horizon": {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "basis": inventory["horizon_basis"],
                },
                "reviewed_visible_layers": item["plan"]["layers"],
                "structured_layers_intersected": len(structured),
                "all_original_receipts_validated": len(receipts),
                "normalization": "Intersect every reviewed visible and nonempty structured source interval. Expand only dated review scope; no timezone, future season, fixed event start or ticket availability inferred. Last-entry bounds conservatively clip full visits.",
                "party_condition_dates_withheld": withheld,
                "known_dated_closures": item["plan"].get("dated_closures", []),
                "native_place_data_changed": False,
            },
        }
        if calendar["unknown_reasons"] or not any(
            row["windows"] for row in calendar["date_overrides"]
        ):
            holds.append(
                {
                    "source_id": identity,
                    "name": item["name"],
                    "profile": item["slug"],
                    "reasons": calendar["unknown_reasons"]
                    or ["No intersected positive opening window"],
                    "draft_entry": entry,
                }
            )
        else:
            entries.append(entry)
            if withheld:
                partial.append(
                    {"source_id": identity, "profile": item["slug"], "dates_withheld": withheld}
                )
    return entries, {
        "schema_version": "roadtrips-reviewed-venue-calendar-report/1",
        "checked_at": now.isoformat(),
        "inventory_sha256": INVENTORY_SHA256,
        "baseline_sha256": inventory["baseline_sha256"],
        "reviewed_count": len(identities),
        "verified_entry_count": len(entries),
        "held_count": len(holds),
        "holds": holds,
        "partial_party_condition_dates": partial,
        "review_horizon": {"start": start.isoformat(), "end": end.isoformat()},
        "remaining_unknowns": [
            "Provider-resolved IANA timezone required at actual visit",
            "Future ticket, capacity, staffing and parking availability unknown",
            "No automatic scheduling beyond the bounded review horizon",
            "No changed place coordinates, source identity or original provenance",
        ],
    }
