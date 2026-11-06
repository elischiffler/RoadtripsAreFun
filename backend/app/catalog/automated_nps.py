"""Replay bounded official NPS facility/parking facts without venue profiles.

Acquisition is a separate command. Admission is offline: original coordinates,
calendar clocks and their exceptions remain source facts. Ambiguous prose,
solar boundaries and missing public-car access produce explicit holds.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from threading import Lock
from urllib.parse import urlsplit

from app.catalog import calendar_enrichment, nps_visit_calendar
from app.catalog.kaggle_markets import driving
from app.catalog.mixed import distance
from app.catalog.normalize import US_REGIONS
from app.routing.visit_calendar import source_calendar

SCHEMA = "roadtrips-automated-nps-facilities/1"
SOURCE_URL = "https://www.nps.gov/subjects/digital/structured-data.htm"
ATTRIBUTION = "National Park Service factual visitor-facility and parking data. No claim to original U.S. Government works. No NPS endorsement. Driving evidence: OSRM, © OpenStreetMap contributors (ODbL)."
MAX_ROWS, MAX_BYTES = 50_000, 100 * 1024 * 1024
GENERIC = {
    "visitor",
    "center",
    "centre",
    "parking",
    "lot",
    "the",
    "and",
    "national",
    "park",
    "main",
    "contact",
    "station",
}
AMBIGUOUS = re.compile(
    r"\bsunrise\b|\bsunset\b|\bdawn\b|\bdusk\b|\bseason\w*\b|\bsummer\b|\bwinter\b|\bspring\b|\bautumn\b|fall hours|"
    r"last (?:entry|admission|tour)|by appointment|\breservations?\b|"
    r"timed.entry|ferry|shuttle|closed to private vehicles|staff.only|\bpermits?\b|"
    r"no (?:car |public |visitor )?parking\b(?!\s+(?:fees?|charges?))|parking (?:is )?(?:not available|prohibited)|"
    r"no (?:public )?vehic|closed to public vehicles|pedestrian.only|not accessible by car|walk.in.only|boat.access.only|"
    r"temporarily closed|closed until|closed due|closure|construction|renovation|"
    r"subject to change|may (?:close|vary)|occasionally|weather permitting|"
    r"lunch|noon|midday|mid-day|except|holiday|closed|\b20\d{2}\b",
    re.I,
)


class Hold(ValueError):
    """Source facts do not establish a schedulable visitor arrival."""


def _words(value):
    return re.findall(r"[a-z0-9]+", str(value).casefold())


def _plain(value):
    return re.sub(r"<[^>]+>", " ", str(value))


_HOLIDAYS = {
    "thanksgiving": "Thanksgiving Day",
    "thanksgiving day": "Thanksgiving Day",
    "christmas": "Christmas Day",
    "christmas day": "Christmas Day",
    "new years": "New Year’s Day",
    "new years day": "New Year’s Day",
    "new year s day": "New Year’s Day",
    "new year day": "New Year’s Day",
    "nyd": "New Year’s Day",
    "veterans day": "Veterans Day",
    "veteran s day": "Veterans Day",
    "memorial day": "Memorial Day",
    "labor day": "Labor Day",
    "independence day": "Independence Day",
    "juneteenth": "Juneteenth National Independence Day",
    "christmas eve": "12-24",
    "new years eve": "12-31",
}


def _holiday_list(value):
    values = re.split(r",|\band\b|\bor\b|;", value, flags=re.I)
    result = []
    for item in values:
        normalized = " ".join(_words(item))
        if not normalized:
            continue
        if normalized not in _HOLIDAYS:
            return None
        result.append(_HOLIDAYS[normalized])
    return result or None


def _prose_guard(value, closures=None):
    text = _plain(value)
    # A small source grammar accepts explicit named holiday closures. Unknown
    # selectors, observed-day claims and relative dates remain holds.
    text = re.sub(r"\bincluding holidays\b", "", text, flags=re.I)
    pattern = r"(?:closed(?:\s+on|\s+for)?|except(?:\s+for)?|with\s+(?:the\s+)?exception\s+of)\s+([^.!?\n]+)"
    for match in reversed(list(re.finditer(pattern, text, flags=re.I))):
        selected = _holiday_list(match[1].strip(" ()"))
        if selected:
            if closures is not None:
                closures.update(selected)
            text = text[: match.start()] + text[match.end() :]
    text = re.sub(r"\bclosed-caption(?:ed)?\b", "captioned", text, flags=re.I)
    if AMBIGUOUS.search(text):
        raise Hold("unresolved_access_or_calendar_prose")
    # Negative/special time qualifications cannot silently disappear behind a
    # native weekday table. This first adapter deliberately holds them.
    if re.search(
        r"\b(?:only open|open only|limited (?:hours|basis|access|services?)|restricted access|access (?:is )?restricted|gate (?:closes?|opens?|is closed)|closes? at|opens? at)\b",
        text,
        re.I,
    ):
        raise Hold("qualified_access_requires_review")


def _clock_guard(texts, schedules):
    bounds = []
    for text in texts:
        clocks = []
        for match in re.finditer(
            r"\b(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\.?", _plain(text), re.I
        ):
            hour, minute = int(match[1]), int(match[2] or 0)
            if not 1 <= hour <= 12 or not 0 <= minute < 60:
                raise Hold("invalid_prose_clock")
            clock = hour % 12 * 60 + minute + (720 if match[3].lower() == "p" else 0)
            clocks.append(clock)
        if clocks:
            # Only a literal single forward pair can constrain a native table.
            # Never infer AM/PM, bridge split sessions or use union membership.
            if len(clocks) != 2 or clocks[1] <= clocks[0]:
                raise Hold("prose_clock_interval_requires_review")
            bounds.append((clocks[0], clocks[1]))
    return bounds


def _point(value):
    try:
        lat, lon = value["latitude"], value["longitude"]
        if isinstance(lat, bool) or isinstance(lon, bool):
            raise ValueError
        lat, lon = float(lat), float(lon)
        if (
            not math.isfinite(lat)
            or not math.isfinite(lon)
            or not -90 <= lat <= 90
            or not -180 <= lon <= 180
        ):
            raise ValueError
        return {"latitude": lat, "longitude": lon}
    except (KeyError, ValueError, TypeError) as exc:
        raise Hold("invalid_native_coordinates") from exc


def _parking_schedule(value):
    """Parking uses camel-case fields; preserve every explicit flag and clock."""
    result = dict(value)
    result["hours"] = [
        {
            "dayOfWeek": row.get("dayOfWeek"),
            "is_closed": row.get("isClosed"),
            "sunrise_open": row.get("sunriseOpen"),
            "sunset_close": row.get("sunsetClose"),
            "time_open": row.get("timeOpen"),
            "time_close": row.get("timeClose"),
        }
        for row in value.get("hours", [])
    ]
    # Unknown parking exception schema must not be ignored.
    if value.get("exceptions"):
        raise Hold("parking_exceptions_require_review")
    return result


def _fact(receipt, pointer, value, scope):
    return {**receipt, "native_json_pointer": pointer, "native_value": value, "scope": scope}


def transform(data, code, index, receipt, *, horizon_days=30, car_arrival=None):
    facility = data["visitorCenters"][index]
    ident = facility.get("visitorCenterID")
    if type(ident) is not int or ident <= 0:
        raise Hold("native_facility_identity_missing")
    sid = f"nps-public:facility:{code}:{ident}"
    name = str(facility.get("name", "")).strip()
    if (
        not name
        or "Parking - Auto" not in facility.get("amenities", [])
        or (not str(facility.get("directions", "")).strip() and car_arrival is None)
    ):
        raise Hold("published_public_auto_arrival_missing")
    point = _point(facility.get("location", {}))
    address = facility.get("physical_address", {})
    if address.get("state_code") not in US_REGIONS or address.get("country_code") not in {
        None,
        "",
        "US",
    }:
        raise Hold("explicit_facility_us_state_missing")
    selected = facility.get("operatingHours")
    if not isinstance(selected, dict) or len(selected) != 1:
        raise Hold("exact_single_facility_schedule_required")
    key, schedule = next(iter(selected.items()))
    if not isinstance(schedule, dict) or not schedule.get("operatingScheduleID"):
        raise Hold("native_schedule_identity_missing")
    closures = set()
    texts = [
        facility.get("description", ""),
        facility["directions"],
        schedule.get("description", ""),
        schedule.get("label", ""),
    ]
    for value in texts:
        _prose_guard(value, closures)
    pointer = f"/visitorCenters/{index}"
    constraints = [
        _fact(
            receipt,
            pointer,
            {
                k: facility.get(k)
                for k in (
                    "visitorCenterID",
                    "name",
                    "location",
                    "physical_address",
                    "amenities",
                    "directions",
                    "description",
                    "operatingHours",
                )
            },
            "selected_facility",
        )
    ]
    # All native parent schedules are restrictive intersections. No classifier
    # guesses that a closure applies to a different component and discards it.
    schedules = [schedule]
    for number, parent in enumerate(data.get("operatingHours", [])):
        if parent is None:
            continue  # Empty serialized slot contains no native schedule facts.
        if not isinstance(parent, dict):
            raise Hold("malformed_parent_schedule")
        # Native typed campground hours and other native visitor-facility
        # schedules are different components. Their full facts are retained;
        # no prose classifier decides this relationship.
        parent_name = " ".join(_words(parent.get("name", "")))
        selected_name = " ".join(_words(schedule.get("name", name)))
        same_named_facility = bool(selected_name) and (
            parent_name == selected_name or parent_name == "visitor center " + selected_name
        )
        other_component = parent.get("type") == "Campground" or (
            parent.get("type") == "Visitor Center"
            and parent.get("operatingScheduleID") != schedule["operatingScheduleID"]
            and not same_named_facility
        )
        constraints.append(
            _fact(
                receipt,
                f"/operatingHours/{number}",
                parent,
                "other_native_typed_component"
                if other_component
                else "conservative_all_parent_access_intersection",
            )
        )
        if other_component:
            continue
        texts.extend((parent.get("description", ""), parent.get("label", "")))
        _prose_guard(parent.get("description", ""), closures)
        _prose_guard(parent.get("label", ""), closures)
        schedules.append(parent)
    # The amenity explicitly establishes auto parking. Named lot + proximity
    # establishes its relationship; proximity alone never grants public access.
    anchors = set(_words(name)) - GENERIC
    lots, nearby_lots = [], []
    for number, lot in enumerate(data.get("parkingLots", [])):
        try:
            nearby = distance(point, _point(lot)) <= 250
        except Hold:
            continue
        words = set(_words(lot.get("name", "") + " " + lot.get("description", "")))
        if nearby:
            nearby_lots.append(lot)
        if nearby and anchors and anchors <= words:
            lots.append((number, lot))
    if not lots and nearby_lots:
        raise Hold("nearby_parking_relationship_unresolved")
    if (
        not lots
        and car_arrival is None
        and not re.search(
            r"\b(?:driv(?:e|ing)|by car|parking|highway|interstate)\b", facility["directions"], re.I
        )
    ):
        raise Hold("public_car_frontage_directions_missing")
    for number, lot in lots:
        spaces = lot.get("totalParkingSpaces")
        if (
            isinstance(spaces, bool)
            or not isinstance(spaces, (int, float))
            or not math.isfinite(spaces)
            or spaces <= 0
        ):
            raise Hold("positive_native_car_parking_required")
        _prose_guard(lot.get("description", ""), closures)
        _prose_guard(lot.get("name", ""), closures)
        native = lot.get("schedule", {})
        if not native.get("operatingScheduleID"):
            raise Hold("parking_schedule_missing")
        _prose_guard(native.get("description", ""), closures)
        _prose_guard(native.get("label", ""), closures)
        texts.extend(
            (lot.get("description", ""), native.get("description", ""), native.get("label", ""))
        )
        schedules.append(_parking_schedule(native))
        constraints.append(
            _fact(
                receipt,
                f"/parkingLots/{number}",
                {
                    k: lot.get(k)
                    for k in (
                        "lotID",
                        "name",
                        "latitude",
                        "longitude",
                        "totalParkingSpaces",
                        "description",
                        "schedule",
                    )
                },
                "named_selected_arrival_parking",
            )
        )
    for native in schedules:
        for exception in native.get("exceptions", []):
            text = exception.get("description", "")
            _prose_guard(text, closures)
            texts.append(text)
    prose_bounds = _clock_guard(texts, schedules)
    start = datetime.fromisoformat(receipt["checked_at"].replace("Z", "+00:00")).date()
    overrides, withheld = [], []
    for offset in range(horizon_days):
        day = start + timedelta(days=offset)
        try:
            windows = [(0, 1440)]
            for native in schedules:
                windows = nps_visit_calendar._intersect(
                    windows, nps_visit_calendar._schedule_windows(native, day)
                )
            for bound in prose_bounds:
                windows = nps_visit_calendar._intersect(windows, [bound])
            if any(
                day
                == (
                    date(day.year, int(value[:2]), int(value[3:]))
                    if re.fullmatch(r"\d{2}-\d{2}", value)
                    else nps_visit_calendar._holiday(value, day.year)
                )
                for value in closures
            ):
                windows = []
            overrides.append(
                {
                    "date": day.isoformat(),
                    "windows": [
                        {
                            "opens": f"{a // 60:02d}:{a % 60:02d}",
                            "closes": f"{b // 60:02d}:{b % 60:02d}",
                            "end_day_offset": 0,
                        }
                        for a, b in windows
                    ],
                }
            )
        except (ValueError, KeyError, TypeError) as exc:
            withheld.append({"date": day.isoformat(), "reason": str(exc)})
    if not any(row["windows"] for row in overrides):
        raise Hold("no_unambiguous_positive_calendar_window")
    url = facility.get("siteURL", "")
    if urlsplit(url).hostname not in {"nps.gov", "www.nps.gov"}:
        url = data.get("url", "")
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"nps.gov", "www.nps.gov"}
        or parsed.username
        or parsed.password
        or parsed.query
    ):
        raise Hold("official_facility_page_missing")
    url = parsed._replace(scheme="https").geturl()
    row = {
        "source_id": sid,
        "name": f"{data['name']} — {name}"[:300],
        **point,
        "region": address["state_code"],
        "categories": ["daytime", "visitor_center", "public_destination"],
        "address": ", ".join(
            str(address.get(k, "")).strip()
            for k in ("line_1", "line_2", "city", "state_code", "postal_code")
            if str(address.get(k, "")).strip()
        )
        or None,
        "url": url,
        "source_updated_at": None,
        "provenance": [
            {
                "dataset": "National Park Service automated factual visitor facility",
                "record_id": str(ident),
                "park_code": code,
                **receipt,
                "license": "LicenseRef-US-Government-Work",
                "arrival_type": "documented_auto_parking_visitor_facility",
                "auto_parking_listed": True,
                "native_coordinates_replaced": False,
                "parking_lot_ids": [lot["lotID"] for _, lot in lots],
                "limitations": "Published visitor-facility point with facility-specific auto-parking amenity and car directions. Named parking restrictions apply when present. Venue hours do not invent separate parking clocks, parking capacity or surveyed entrance geometry. Fees and future availability are unknown.",
            }
        ],
    }
    entry = {
        "source_id": sid,
        "source_visit_calendar": {
            "schema_version": nps_visit_calendar.SCHEMA,
            "weekly_windows": [],
            "date_overrides": overrides,
            "seasons": [
                {
                    "kind": "dated",
                    "start": start.isoformat(),
                    "end": (start + timedelta(days=horizon_days - 1)).isoformat(),
                }
            ],
            "annual_closures": [],
            "unknown_reasons": [],
            "source_receipts": [receipt],
        },
        "source_constraints": constraints,
        "transformation": {
            "adapter": SCHEMA,
            "native_facility_id": ident,
            "native_schedule_id": schedule["operatingScheduleID"],
            "native_facility_pointer": pointer,
            "all_parent_schedules_intersected": True,
            "review_horizon_days": horizon_days,
            "horizon_basis": "Finite extraction scope after acquisition, not source-published expiry or annual recurrence",
            "withheld_dates": withheld,
        },
    }
    if source_calendar({"source_provenance": [entry]}) is None:
        raise Hold("source_calendar_contract_invalid")
    return row, entry


def prepare(path, manifest, *, max_rows=MAX_ROWS, max_bytes=MAX_BYTES):
    """Typed incremental-source adapter; replay facts and retain every hold."""
    if (
        type(max_rows) is not int
        or not 1 <= max_rows <= MAX_ROWS
        or type(max_bytes) is not int
        or not 1 <= max_bytes <= MAX_BYTES
    ):
        raise ValueError("NPS import cannot raise resource ceilings")
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= min(32768, max_bytes):
        raise ValueError("NPS configuration missing or oversized")
    raw = path.read_bytes()
    if (
        manifest.get("schema_version") != SCHEMA
        or manifest.get("source_url") != SOURCE_URL
        or manifest.get("attribution") != ATTRIBUTION
        or not re.fullmatch(r"nps-facilities-\d{4}-\d{2}-\d{2}", manifest.get("release", ""))
        or hashlib.sha256(raw).hexdigest() != manifest.get("sha256")
    ):
        raise ValueError("NPS source manifest identity/checksum differs")
    bundle = json.loads(raw)
    reader = calendar_enrichment.Reader(path.parent, max_bytes - len(raw))
    if bundle.get("schema_version") == SCHEMA and "index" in bundle:
        index = bundle["index"]
        indexed_raw = reader.read(index["path"], index["sha256"])
        if len(indexed_raw) > 1024 * 1024:
            raise ValueError("NPS acquisition index exceeds 1MiB")
        bundle = json.loads(indexed_raw)
    if (
        bundle.get("schema_version") != SCHEMA
        or not isinstance(bundle.get("inputs"), dict)
        or not 1 <= len(bundle["inputs"]) <= 500
    ):
        raise ValueError("NPS source requires bounded native inputs")
    if set(manifest.get("licenses", {})) != {"LicenseRef-US-Government-Work", "ODbL-1.0"}:
        raise ValueError("NPS requires retained factual reuse and routing rights")
    for identifier, receipt in manifest["licenses"].items():
        expected = (
            "https://www.nps.gov/aboutus/disclaimer.htm"
            if identifier == "LicenseRef-US-Government-Work"
            else "https://opendatacommons.org/licenses/odbl/1-0/"
        )
        if receipt.get("url") != expected or receipt.get("status") != 200:
            raise ValueError("NPS factual/routing rights URL or acquisition differs")
        reader.read(receipt["path"], receipt["sha256"])
    rows, entries, ledger, scanned = [], [], [], 0
    native_counts = Counter()
    for code, evidence in bundle["inputs"].items():
        if (
            not re.fullmatch("[a-z]{4}", code)
            or evidence.get("url") != f"https://www.nps.gov/{code}/structured_data_{code}.json"
            or evidence.get("status") != 200
        ):
            raise ValueError("NPS input URL/HTTP identity differs")
        checked = datetime.fromisoformat(evidence["retrieved_at"].replace("Z", "+00:00"))
        if checked.tzinfo is None or not datetime.now(UTC) - timedelta(
            days=30
        ) <= checked <= datetime.now(UTC):
            raise ValueError("NPS source acquisition future/stale")
        body = reader.read(evidence["path"], evidence["sha256"])
        if len(body) > 2 * 1024 * 1024 or evidence.get("bytes") != len(body):
            raise ValueError("NPS source body ceiling/receipt length differs")
        data = json.loads(body.decode("utf-8-sig"))
        if data.get("siteCode") != code:
            raise ValueError("NPS source native identity differs")
        counts = {
            "units": 1,
            "parking_lots": len(data.get("parkingLots", [])),
            "parent_schedule_slots": len(data.get("operatingHours", [])),
            "visitor_facilities": len(data.get("visitorCenters", [])),
        }
        native_counts.update(counts)
        scanned += sum(counts.values())
        if scanned > max_rows:
            raise ValueError("NPS scanned source row ceiling")
        receipt = {
            "source_url": evidence["url"],
            "snapshot_sha256": evidence["sha256"],
            "checked_at": evidence["retrieved_at"],
            "evidence_path": evidence["path"],
        }
        if data.get("physicalAddressCountryCode") != "US":
            ledger.append(
                {
                    "source_id": f"nps-public:unit:{code}",
                    "reason": "explicit_us_unit_jurisdiction_missing",
                    **receipt,
                }
            )
            continue
        for index, facility in enumerate(data.get("visitorCenters", [])):
            sid = f"nps-public:facility:{code}:{facility.get('visitorCenterID', 'unknown')}"
            try:
                arrival, arrival_receipt = None, bundle.get("arrival_pages", {}).get(sid)
                if arrival_receipt is not None:
                    from app.catalog.automated_nps_arrivals import match

                    checked_arrival = datetime.fromisoformat(
                        arrival_receipt["retrieved_at"].replace("Z", "+00:00")
                    )
                    if (
                        arrival_receipt.get("status") != 200
                        or checked_arrival.tzinfo is None
                        or not datetime.now(UTC) - timedelta(days=30)
                        <= checked_arrival
                        <= datetime.now(UTC)
                    ):
                        raise Hold("arrival_page_acquisition_failed_future_or_stale")
                    arrival = match(
                        data,
                        facility,
                        reader.read(arrival_receipt["path"], arrival_receipt["sha256"]),
                        arrival_receipt["url"],
                    )
                row, entry = transform(data, code, index, receipt, car_arrival=arrival)
                if arrival is not None:
                    receipt_arrival = {
                        "source_url": arrival_receipt["url"],
                        "snapshot_sha256": arrival_receipt["sha256"],
                        "checked_at": arrival_receipt["retrieved_at"],
                        "evidence_path": arrival_receipt["path"],
                    }
                    entry["source_visit_calendar"]["source_receipts"].append(receipt_arrival)
                    entry["source_constraints"].append(
                        {
                            **receipt_arrival,
                            "scope": "exact_native_facility_address_and_typed_car_approach",
                            **arrival,
                        }
                    )
                    row["provenance"].append(
                        {
                            "dataset": "National Park Service official facility car approach",
                            "record_id": str(facility["visitorCenterID"]),
                            **receipt_arrival,
                            **arrival,
                            "license": "LicenseRef-US-Government-Work",
                        }
                    )
                drive = bundle.get("driving", {}).get(sid)
                if not drive:
                    raise Hold("authentic_driving_destination_receipt_missing")
                reader.read(drive["path"], drive["sha256"])
                _, snap = driving(path.parent, drive, row)
                row["provenance"][-1].update(
                    {
                        "driving_evidence_sha256": drive["sha256"],
                        "driving_checked_at": drive["retrieved_at"],
                        "driving_destination_distance_m": snap,
                    }
                )
                rows.append(row)
                entries.append(entry)
            except (Hold, ValueError, TypeError, KeyError) as exc:
                ledger.append(
                    {
                        "source_id": sid,
                        "name": facility.get("name"),
                        "reason": str(exc),
                        **receipt,
                        "native_json_pointer": f"/visitorCenters/{index}",
                    }
                )
    if len({row["source_id"] for row in rows}) != len(rows):
        raise ValueError("NPS duplicate native facility identity")
    return rows, {
        "scanned": scanned,
        "source_rows": dict(native_counts),
        "accepted": len(rows),
        "bytes": reader.bytes + len(raw),
        "rejects": dict(Counter(item["reason"] for item in ledger)),
        "rejection_ledger": ledger,
        "calendar_entries": entries,
        "regions": dict(Counter(row["region"] for row in rows)),
    }


def acquire(output, codes=None, *, arrival_page_urls=()):
    """Acquire official native bodies and raw route receipts into a new directory.

    This performs public GET requests only. It never reads application secrets,
    changes a database or decides that a downloaded candidate is admitted.
    """
    import requests

    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    acquired_bytes, budget_lock, last_osrm = 0, Lock(), None
    arrival_urls = set(arrival_page_urls)
    if len(arrival_urls) > 16 or any(
        urlsplit(url).scheme != "https"
        or urlsplit(url).netloc != "www.nps.gov"
        or urlsplit(url).query
        or urlsplit(url).fragment
        or not urlsplit(url).path.endswith(".htm")
        for url in arrival_urls
    ):
        raise ValueError("NPS arrival selectors require up to16 official public HTML URLs")

    def fetch(url, relative):
        nonlocal acquired_bytes, last_osrm
        parsed = urlsplit(url)
        endpoint = parsed.scheme + "://" + parsed.netloc + parsed.path
        is_osrm = (
            parsed.scheme == "https"
            and parsed.netloc == "router.project-osrm.org"
            and bool(re.fullmatch(r"/route/v1/driving/[-0-9.,;]+", parsed.path))
        )
        allowed = (
            endpoint == "https://carto.nps.gov/user/parktiles/api/v2/sql"
            or endpoint
            in {
                "https://www.nps.gov/aboutus/disclaimer.htm",
                "https://opendatacommons.org/licenses/odbl/1-0/",
            }
            or (
                parsed.scheme == "https"
                and parsed.netloc == "www.nps.gov"
                and bool(re.fullmatch(r"/([a-z]{4})/structured_data_\1.json", parsed.path))
            )
            or url in arrival_urls
            or is_osrm
        )
        if not allowed or parsed.username or parsed.password or parsed.fragment:
            raise ValueError("NPS acquisition endpoint is outside the reviewed allowlist")
        if is_osrm:
            if last_osrm is not None:
                time.sleep(max(0, 1 - (time.monotonic() - last_osrm)))
            last_osrm = time.monotonic()
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, timeout=(10, 30), stream=True, allow_redirects=False) as response:
            if response.status_code != 200 or getattr(response, "url", url) != url:
                raise ValueError("NPS acquisition redirected or returned unsuccessful HTTP status")
            chunks, size = [], 0
            for chunk in response.iter_content(64 * 1024):
                size += len(chunk)
                if size > 2 * 1024 * 1024:
                    raise ValueError("NPS remote body exceeds 2MiB")
                chunks.append(chunk)
            body = b"".join(chunks)
            with budget_lock:
                if acquired_bytes + len(body) > MAX_BYTES:
                    raise ValueError("NPS acquisition exceeds unchanged 100MiB ceiling")
                acquired_bytes += len(body)
            target.write_bytes(body)
            return {
                "url": url,
                "path": relative,
                "sha256": hashlib.sha256(body).hexdigest(),
                "retrieved_at": datetime.now(UTC).isoformat(),
                "status": response.status_code,
                "bytes": len(body),
            }

    inventory_url = "https://carto.nps.gov/user/parktiles/api/v2/sql?q=SELECT%20parkcode%20AS%20unit_code%2Cfullname%2Cdesignation%20FROM%20parktiles.sd_parks"
    inventory = fetch(inventory_url, "inventory.json")
    if inventory["status"] != 200:
        raise ValueError("NPS current inventory acquisition failed")
    inventory_rows = json.loads((output / "inventory.json").read_bytes())["rows"]
    available = {
        row["unit_code"].lower()
        for row in inventory_rows
        if re.fullmatch("[a-zA-Z]{4}", row.get("unit_code", ""))
    }
    selected = sorted(available if codes is None else set(codes))
    if not selected or len(selected) > 500 or set(selected) - available:
        raise ValueError("NPS acquisition needs current native inventory codes")
    inputs, failures = {}, []

    def fetch_code(code):
        try:
            receipt = fetch(
                f"https://www.nps.gov/{code}/structured_data_{code}.json", f"sources/{code}.json"
            )
            data = json.loads((output / receipt["path"]).read_bytes().decode("utf-8-sig"))
            if receipt["status"] != 200 or data.get("siteCode") != code:
                return (
                    code,
                    None,
                    {
                        "code": code,
                        "receipt": receipt,
                        "reason": "native_acquisition_identity_or_status",
                    },
                )
            return code, receipt, None
        except (requests.RequestException, ValueError, KeyError) as exc:
            return code, None, {"code": code, "reason": type(exc).__name__}

    with ThreadPoolExecutor(max_workers=4) as pool:
        for code, receipt, failure in pool.map(fetch_code, selected):
            if failure:
                failures.append(failure)
            else:
                inputs[code] = receipt
    driving_receipts, preliminary_holds, prequalified, arrival_pages = {}, [], 0, {}
    for code, evidence in inputs.items():
        data = json.loads((output / evidence["path"]).read_bytes().decode("utf-8-sig"))
        receipt = {
            "source_url": evidence["url"],
            "snapshot_sha256": evidence["sha256"],
            "checked_at": evidence["retrieved_at"],
            "evidence_path": evidence["path"],
        }
        for index, facility in enumerate(data.get("visitorCenters", [])):
            sid = f"nps-public:facility:{code}:{facility.get('visitorCenterID', 'unknown')}"
            try:
                try:
                    row, _ = transform(data, code, index, receipt)
                except Hold as exc:
                    if (
                        str(exc)
                        not in {
                            "public_car_frontage_directions_missing",
                            "published_public_auto_arrival_missing",
                        }
                        or "Parking - Auto" not in facility.get("amenities", [])
                        or not arrival_urls
                    ):
                        raise
                    from app.catalog.automated_nps_arrivals import match

                    candidates = []
                    for linked in (data.get("directionsURL", ""), facility.get("siteURL", "")):
                        original = urlsplit(linked)
                        if (
                            original.hostname in {"www.nps.gov", "nps.gov"}
                            and original.scheme in {"http", "https"}
                            and not original.query
                            and not original.fragment
                        ):
                            candidates.append(
                                original._replace(scheme="https", netloc="www.nps.gov").geturl()
                            )
                    page_url = next((url for url in candidates if url in arrival_urls), None)
                    if page_url is None:
                        raise Hold("selected_official_native_arrival_page_unavailable") from exc
                    page = fetch(page_url, f"arrivals/{code}-{facility['visitorCenterID']}.html")
                    arrival = match(data, facility, (output / page["path"]).read_bytes(), page_url)
                    arrival_pages[sid] = page
                    row, _ = transform(data, code, index, receipt, car_arrival=arrival)
                prequalified += 1
                lat, lon = row["latitude"], row["longitude"]
                url = f"https://router.project-osrm.org/route/v1/driving/{lon},{lat + 0.01};{lon},{lat}?overview=false"
                drive = fetch(url, f"driving/{code}-{facility['visitorCenterID']}.json")
                response = json.loads((output / drive["path"]).read_bytes())
                waypoint = response.get("waypoints", [{}])[-1]
                drive.update(
                    {
                        "checked_waypoint": "destination",
                        "source_coordinates": [lat, lon],
                        "snap_distance_m": waypoint.get("distance"),
                        "road_name": waypoint.get("name"),
                    }
                )
                driving_receipts[sid] = drive
            except (Hold, ValueError, KeyError, TypeError, requests.RequestException) as exc:
                preliminary_holds.append({"source_id": sid, "reason": str(exc)})
    licenses = {
        identifier: fetch(url, relative)
        for identifier, url, relative in (
            (
                "LicenseRef-US-Government-Work",
                "https://www.nps.gov/aboutus/disclaimer.htm",
                "rights/nps.html",
            ),
            ("ODbL-1.0", "https://opendatacommons.org/licenses/odbl/1-0/", "rights/odbl.html"),
        )
    }
    index = {
        "schema_version": SCHEMA,
        "inventory": inventory,
        "inputs": inputs,
        "driving": driving_receipts,
        "arrival_pages": arrival_pages,
        "acquisition_failures": failures,
        "preliminary_holds": preliminary_holds,
    }
    index_path = output / "acquisition.json"
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    config = {
        "schema_version": SCHEMA,
        "index": {
            "path": index_path.name,
            "sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
        },
    }
    path = output / "nps.source.json"
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": SCHEMA,
        "source_url": SOURCE_URL,
        "attribution": ATTRIBUTION,
        "release": "nps-facilities-" + datetime.now(UTC).date().isoformat(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "licenses": licenses,
    }
    sidecar = Path(str(path) + ".manifest.json")
    sidecar.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {
        "source_path": str(path),
        "manifest_path": str(sidecar),
        "acquired_units": len(inputs),
        "failed_units": len(failures),
        "prequalified_facilities": prequalified,
        "driving_receipts": len(driving_receipts),
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--codes", nargs="+")
    args = parser.parse_args()
    print(json.dumps(acquire(args.output, args.codes), sort_keys=True))


if __name__ == "__main__":
    main()
