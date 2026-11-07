"""Pinned, exact-row exceptions to acquisition holds; never issue admission.

An exception resolves named historical causes for one immutable payload. It does
not approve new facts, renew admission clocks, or qualify routing. Append new
payload versions instead of replacing old versions needed for frozen rollback.
The shipped registry pins individually reviewed payloads. Only an affirmative
per-ID evidence review and an independently calculated PostgreSQL payload
fingerprint may add a version; an empty registry remains fail-closed.
"""

import hashlib
import json
import math
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.catalog import browse_quarantine
from app.catalog.identity import identity

SCHEMA = "roadtrips-row-bound-hold-resolutions/1"
MARKER_SCHEMA = "roadtrips-row-bound-hold-resolution/1"
DATASET = "Roadtrips row-bound source hold resolution"
REGISTRY_SHA256 = "e928ab09951ffd8d1fccfec8aff5453a59ddffcc3ddba3766297afe110bcdead"
ORIGINAL_HOLDS_SHA256 = "0d29c5d527be6d08f018e4ee1cd9598dc8048b944e1c67aa42f2c29c190bb2ec"
FIELDS = (
    "source_id",
    "name",
    "latitude",
    "longitude",
    "region",
    "categories",
    "address",
    "url",
    "source_updated_at",
    "provenance",
)
_ENTRY_KEYS = {
    "source_id",
    "resolved_held_ids",
    "approved_payload",
    "payload_sha256",
    "payload_pg_md5",
    "marker",
    "review",
}
_ADMISSION_KEYS = {
    "schema_version",
    "tier",
    "source_id",
    "review_status",
    "reviewed_at_epoch",
    "expires_at_epoch",
    "gates",
}
_BASE_GATES = {"rights", "identity", "location", "public_access", "local_duplicate_review"}
_HEX64 = re.compile(r"[0-9a-f]{64}\Z")
_SID = re.compile(r"[A-Za-z0-9_:./~-]{1,512}\Z")
_RUNTIME_KEYS = {
    "provider_id",
    "coordinates",
    "source_provenance",
    "source",
    "provider_rank",
    "source_release",
    "source_attribution",
    "description",
    "activities",
    "type",
    "rank",
    "utility",
    "contributions",
    "attribute_ratings",
    "timezone",
    "availability",
    "visit_duration",
    "arrival",
    "departure",
    # Existing discovery, road-check and saved-trip annotations are not source
    # facts. They may accompany the exact canonical payload without changing it.
    "section_id",
    "source_query_ids",
    "route_progress_seconds",
    "distance_meters",
    "segment_index",
    "detour_seconds",
    "detour_raw_seconds",
    "detour_provenance",
    "road_check_status",
    "duration",
    "distance",
    "road_arrival_time",
    "wait_seconds",
    "arrival_time",
    "departure_time",
    "travel_day",
    "deadline",
    "meal_breaks",
}


def _json(value):
    """Canonical, JSON-type-sensitive encoding (False never equals zero)."""
    if isinstance(value, dict):
        if any(type(key) is not str for key in value):
            raise ValueError("JSON object keys must be strings")
        for item in value.values():
            _json(item)
    elif isinstance(value, list):
        for item in value:
            _json(item)
    elif value is not None and type(value) not in (str, bool, int, float):
        raise ValueError("payload is not JSON typed")
    return json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False)


def payload_sha256(payload):
    return hashlib.sha256(_json(payload).encode()).hexdigest()


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _load_original_ids():
    raw = Path(__file__).with_name("release_holds.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_HOLDS_SHA256:
        raise RuntimeError("original acquisition holds differ from their reviewed pin")
    document = json.loads(raw, object_pairs_hook=_object)
    ids = document.get("source_ids")
    if (
        document.get("schema_version") != "roadtrips-receipt-audit-release-holds/1"
        or type(document.get("count")) is not int
        or document["count"] != 133
        or not isinstance(ids, list)
        or len(ids) != 133
        or any(type(sid) is not str or not _SID.fullmatch(sid) for sid in ids)
        or len(set(ids)) != 133
    ):
        raise RuntimeError("original acquisition hold identities are malformed")
    return frozenset(ids)


ORIGINAL_HELD_IDS = _load_original_ids()


def _marker_like(fact):
    return isinstance(fact, dict) and (
        "source_hold_resolution" in fact or fact.get("dataset") == DATASET
    )


def _held_ids(payload):
    ids = {payload["source_id"]}
    for fact in payload["provenance"]:
        contract = fact.get("catalog_admission")
        if isinstance(contract, dict):
            value = contract.get("source_id")
            if isinstance(value, str):
                ids.add(value)
        aliases = fact.get("aliases", [])
        if not isinstance(aliases, list) or any(type(sid) is not str for sid in aliases):
            raise ValueError("aliases must be an array of string identities")
        ids.update(aliases)
    return ids & ORIGINAL_HELD_IDS


def _timestamp(value):
    if type(value) is not str:
        raise ValueError("review timestamp must be a string")
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise ValueError("review timestamp must include a timezone")
    if stamp > datetime.now(UTC):
        raise ValueError("review timestamp cannot be in the future")
    return stamp


def _valid_payload(payload):
    if type(payload) is not dict or set(payload) != set(FIELDS):
        raise ValueError("approved payload must contain exactly the canonical fields")
    _json(payload)
    if type(payload["source_id"]) is not str or not _SID.fullmatch(payload["source_id"]):
        raise ValueError("invalid canonical source ID")
    for key in ("name", "region"):
        if type(payload[key]) is not str or not payload[key].strip():
            raise ValueError("payload name and region must be nonempty strings")
    for key in ("address", "url", "source_updated_at"):
        if payload[key] is not None and type(payload[key]) is not str:
            raise ValueError("optional canonical text must be string or null")
    for key, limit in (("latitude", 90), ("longitude", 180)):
        value = payload[key]
        if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > limit:
            raise ValueError("coordinates must be finite geographic JSON numbers")
    categories = payload["categories"]
    if (
        not isinstance(categories, list)
        or any(
            type(kind) is not str or not re.fullmatch(r"[a-z0-9_]+", kind) for kind in categories
        )
        or len(categories) != len(set(categories))
        or "catalog_browse" not in categories
    ):
        raise ValueError("resolved payload must retain valid unique browse categories")
    facts = payload["provenance"]
    if (
        not isinstance(facts, list)
        or not facts
        or any(type(fact) is not dict for fact in facts)
        or any(
            _marker_like(fact) or fact.get("dataset") == "Roadtrips active catalog"
            for fact in facts
        )
    ):
        raise ValueError("approved provenance must exclude runtime and resolution markers")
    marks = [
        fact
        for fact in facts
        if "catalog_admission" in fact or fact.get("dataset") == "Roadtrips catalog admission"
    ]
    if len(marks) != 1 or marks[0].get("dataset") != "Roadtrips catalog admission":
        raise ValueError("exactly one explicit catalog admission is required")
    contract = marks[0].get("catalog_admission")
    if (
        type(contract) is not dict
        or set(contract) != _ADMISSION_KEYS
        or contract["schema_version"] != "roadtrips-catalog-admission/1"
        or contract["source_id"] != payload["source_id"]
        or contract["tier"] not in {"T2", "T3"}
        or contract["review_status"] != "approved"
    ):
        raise ValueError("resolution requires an explicit approved T2 or qualified T3 payload")
    reviewed, expires = contract["reviewed_at_epoch"], contract["expires_at_epoch"]
    if (
        type(reviewed) is not int
        or type(expires) is not int
        or not 0 <= reviewed < expires <= 253402300799
        or expires - reviewed > 31 * 24 * 60 * 60
    ):
        raise ValueError("invalid immutable admission clocks")
    gates = contract["gates"]
    if (
        type(gates) is not dict
        or set(gates) != _BASE_GATES | {"arrival", "calendar"}
        or any(type(value) is not bool for value in gates.values())
        or not all(gates[key] for key in _BASE_GATES)
    ):
        raise ValueError("resolution requires the explicit factual review gates")
    if contract["tier"] == "T3":
        _valid_routing_payload(payload, contract)
        return
    if set(categories) & browse_quarantine.ROUTING_CATEGORIES:
        raise ValueError("T2 resolution cannot add routing categories")
    calendars = [fact for fact in facts if "source_visit_calendar" in fact]
    if len(calendars) != 1 or calendars[0].get("dataset") != browse_quarantine.DATASET:
        raise ValueError("exactly one inline project calendar hold is required")
    # Rebuild the deterministic restriction to reject forged windows, receipts,
    # transformation metadata or category-removal claims. No source fact is stripped.
    try:
        rebuilt = browse_quarantine.apply(payload)
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise ValueError("invalid inline browse project hold") from exc
    if _json(rebuilt) != _json(payload):
        raise ValueError("inline browse project hold is not canonical")


def _valid_routing_payload(payload, contract):
    """Validate exact qualified versions without circular admission imports.

    A pinned version is issued only after routing_qualification.build_promotion
    and source review. These import-time structural checks independently retain
    the prior row, original horizon, native facts, positive calendar and arrival.
    """
    facts = payload["provenance"]
    qualification = [f for f in facts if f.get("dataset") == "Roadtrips routing qualification"]
    histories = [
        f for f in facts if f.get("dataset") == "Roadtrips prior routing qualification history"
    ]
    calendars = [f for f in facts if "source_visit_calendar" in f]
    if (
        not all(contract["gates"].values())
        or not set(payload["categories"]) & browse_quarantine.ROUTING_CATEGORIES
        or len(qualification) != 1
        or len(histories) != 1
        or calendars != qualification
        or any(f.get("dataset") == browse_quarantine.DATASET for f in facts)
    ):
        raise ValueError("T3 resolution requires one positive qualification and no browse hold")
    q, history = qualification[0], histories[0]
    previous = history.get("previous_canonical_row")
    if (
        q.get("schema_version") != "roadtrips-routing-qualification/1"
        or history.get("schema_version") != "roadtrips-routing-qualification/1"
        or history.get("selected_for_current_routing") is not False
        or type(previous) is not dict
        or set(previous) != set(FIELDS)
        or payload_sha256(previous) != q.get("original_row_sha256")
        or history.get("original_row_sha256") != q.get("original_row_sha256")
        or not _HEX64.fullmatch(str(q.get("decision_sha256", "")))
        or q.get("native_facts_and_persona_ratings_unchanged") is not True
        or q.get("original_admission_expiry_extended") is not False
    ):
        raise ValueError("T3 resolution must preserve its bound complete prior row")
    stable = ("source_id", "name", "region", "address", "url", "source_updated_at")
    if any(_json(previous[key]) != _json(payload[key]) for key in stable):
        raise ValueError("routing qualification changes stable destination identity fields")
    old_marks = [
        f.get("catalog_admission") for f in previous["provenance"] if "catalog_admission" in f
    ]
    if (
        len(old_marks) != 1
        or old_marks[0].get("tier") != "T2"
        or old_marks[0].get("source_id") != payload["source_id"]
        or old_marks[0].get("expires_at_epoch", 0) < contract["expires_at_epoch"]
        or int(_timestamp(q.get("reviewed_at")).timestamp()) != contract["reviewed_at_epoch"]
        or not isinstance(q.get("reviewer"), str)
        or not q["reviewer"].strip()
    ):
        raise ValueError("T3 resolution renews its original horizon or loses accountable review")
    retained = [
        f
        for f in previous["provenance"]
        if "catalog_admission" not in f
        and "source_hold_resolution" not in f
        and f.get("dataset") != browse_quarantine.DATASET
    ]
    current = [
        f
        for f in facts
        if "catalog_admission" not in f
        and f.get("dataset")
        not in {"Roadtrips routing qualification", "Roadtrips prior routing qualification history"}
    ]
    if _json(retained) != _json(current):
        raise ValueError("T3 resolution alters native facts, credits or persona ratings")
    arrival = q.get("arrival", {})
    if (
        type(arrival) is not dict
        or arrival.get("point_role")
        not in {"visitor_parking", "public_vehicle_entrance", "constructed_facility_arrival"}
        or arrival.get("public_vehicle_access") is not True
        or arrival.get("same_destination_identity_verified") is not True
        or any(_json(arrival.get(k)) != _json(payload[k]) for k in ("latitude", "longitude"))
        or any(
            type(arrival.get(k)) is not str or not arrival[k].strip()
            for k in ("road_approach", "coordinate_basis")
        )
    ):
        raise ValueError("T3 resolution lacks its reviewed public vehicle arrival")
    try:
        ZoneInfo(q["timezone"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("T3 resolution needs a valid IANA timezone") from exc
    if type(q.get("timezone_basis")) is not str or not q["timezone_basis"].strip():
        raise ValueError("T3 timezone has no recorded coordinate or authoritative basis")
    confidence = q.get("confidence", {})
    if set(confidence) != {"calendar", "arrival"} or any(
        v not in {"high", "moderate"} for v in confidence.values()
    ):
        raise ValueError("T3 qualification confidence must be explicit")
    calendar = q["source_visit_calendar"]
    if (
        type(calendar) is not dict
        or calendar.get("schema_version") != "roadtrips-source-visit-calendar/1"
        or calendar.get("unknown_reasons", []) != []
        or not calendar.get("source_receipts")
        or not (
            calendar.get("weekly_windows")
            or any(d.get("windows") for d in calendar.get("date_overrides", []))
        )
    ):
        raise ValueError("T3 resolution has no positive supported visit windows")
    selected = q.get("source_receipts", [])
    if not isinstance(selected, list) or not 1 <= len(selected) <= 100:
        raise ValueError("T3 qualification lacks bounded selected source receipts")

    def receipt_key(receipt):
        if type(receipt) is not dict:
            raise ValueError("malformed T3 source receipt")
        stamp = _timestamp(receipt.get("checked_at"))
        if stamp.timestamp() > _timestamp(q["reviewed_at"]).timestamp() or not _HEX64.fullmatch(
            str(receipt.get("snapshot_sha256", ""))
        ):
            raise ValueError("T3 source timestamp or hash differs")
        url = receipt.get("source_url", "")
        if type(url) is not str or not url.startswith("https://"):
            raise ValueError("T3 source receipt requires its HTTPS source")
        return url, receipt["snapshot_sha256"], receipt["checked_at"]

    keys = {receipt_key(r) for r in selected}
    basis = q.get("calendar_basis", {})
    if basis.get("kind") not in {
        "published_hours",
        "explicit_24_hour",
        "conservative_access_inference",
    } or not basis.get("statement"):
        raise ValueError("T3 calendar lacks its reviewed source or grounded inference basis")
    for group in (
        calendar["source_receipts"],
        arrival.get("evidence", []),
        basis.get("evidence", []),
    ):
        if not group or any(receipt_key(r) not in keys for r in group):
            raise ValueError("T3 arrival/calendar receipts are not selected")
    windows = [
        *calendar.get("weekly_windows", []),
        *(w for d in calendar.get("date_overrides", []) for w in d.get("windows", [])),
    ]
    for window in windows:
        if type(window) is not dict or window.get("end_day_offset", 0) not in {0, 1}:
            raise ValueError("invalid T3 window")
        for key in ("opens", "closes"):
            clock = window.get(key)
            if (
                type(clock) is not str
                or datetime.strptime(clock, "%H:%M").strftime("%H:%M") != clock
            ):
                raise ValueError("invalid T3 clock")
        if not window.get("end_day_offset", 0) and window["closes"] <= window["opens"]:
            raise ValueError("nonpositive T3 window")


def load_registry(path, expected_sha256):
    """Read a byte-pinned, append-only registry; fail startup on any corruption."""
    try:
        raw = Path(path).read_bytes()
        if (
            not isinstance(expected_sha256, str)
            or not _HEX64.fullmatch(expected_sha256)
            or len(raw) > 32 * 1024 * 1024
            or hashlib.sha256(raw).hexdigest() != expected_sha256
        ):
            raise ValueError("resolution registry differs from its reviewed byte pin")
        document = json.loads(raw, object_pairs_hook=_object)
        if (
            type(document) is not dict
            or set(document) != {"schema_version", "count", "entries"}
            or document["schema_version"] != SCHEMA
            or type(document["count"]) is not int
            or not isinstance(document["entries"], list)
            or document["count"] != len(document["entries"])
            or not 0 <= document["count"] <= 4096
        ):
            raise ValueError("invalid resolution registry envelope")
        seen = set()
        for entry in document["entries"]:
            if type(entry) is not dict or set(entry) != _ENTRY_KEYS:
                raise ValueError("invalid resolution entry fields")
            payload = entry["approved_payload"]
            _valid_payload(payload)
            ids = entry["resolved_held_ids"]
            if (
                entry["source_id"] != payload["source_id"]
                or not isinstance(ids, list)
                or not ids
                or any(type(sid) is not str or sid not in ORIGINAL_HELD_IDS for sid in ids)
                or len(ids) != len(set(ids))
                or set(ids) != _held_ids(payload)
                or type(entry["payload_sha256"]) is not str
                or entry["payload_sha256"] != payload_sha256(payload)
                or type(entry["payload_pg_md5"]) is not str
                or not re.fullmatch(r"[0-9a-f]{32}", entry["payload_pg_md5"])
            ):
                raise ValueError("resolution identity, alias coverage or payload digest differs")
            key = (entry["source_id"], entry["payload_sha256"])
            if key in seen:
                raise ValueError("duplicate source/payload resolution version")
            seen.add(key)
            expected = {
                "dataset": DATASET,
                "source_hold_resolution": {
                    "schema_version": MARKER_SCHEMA,
                    "source_id": entry["source_id"],
                    "region": payload["region"],
                    "payload_sha256": entry["payload_sha256"],
                    "resolved_held_ids": ids,
                },
            }
            if _json(entry["marker"]) != _json(expected) or len(_json(expected)) > 4096:
                raise ValueError("resolution marker differs from the exact approved marker")
            review = entry["review"]
            if (
                type(review) is not dict
                or set(review)
                != {
                    "reviewer",
                    "reviewed_at",
                    "original_cause_resolution",
                    "admission_clock_renewed",
                }
                or type(review["reviewer"]) is not str
                or not review["reviewer"].strip()
                or review["admission_clock_renewed"] is not False
                or type(review["original_cause_resolution"]) is not dict
                or set(review["original_cause_resolution"]) != set(ids)
            ):
                raise ValueError("named original-cause review is required for every held alias")
            _timestamp(review["reviewed_at"])
            for cause in review["original_cause_resolution"].values():
                if (
                    type(cause) is not dict
                    or not {"cause", "resolution"} <= set(cause)
                    or any(
                        type(cause[key]) is not str or not cause[key].strip()
                        for key in ("cause", "resolution")
                    )
                ):
                    raise ValueError("original cause and affirmative resolution must be named")
        return tuple(document["entries"])
    except (OSError, ValueError, TypeError, KeyError, OverflowError, RecursionError) as exc:
        raise RuntimeError(f"invalid pinned catalog hold resolution registry: {exc}") from exc


def _runtime_facts(value):
    if not isinstance(value, list) or any(type(fact) is not dict for fact in value):
        raise ValueError("runtime provenance must remain an array of exact source facts")
    runtime = [fact for fact in value if fact.get("dataset") == "Roadtrips active catalog"]
    if runtime:
        if (
            len(runtime) != 1
            or runtime[0] is not value[-1]
            or set(runtime[0]) != {"dataset", "generation", "release"}
            or type(runtime[0]["generation"]) is not str
            or not _HEX64.fullmatch(runtime[0]["generation"])
            or type(runtime[0]["release"]) is not str
            or not runtime[0]["release"].strip()
        ):
            raise ValueError("unknown or misplaced runtime attribution fact")
        return value[:-1]
    return value


def _rating_annotation(value):
    """Recognize only documented rating metadata, never immutable source facts.

    The original three fields remain the uncached projection. Trait discovery
    adds a complete four-field group even when caching is disabled; partial,
    unknown or malformed groups cannot make ambiguous provenance acceptable.
    Version changes require an explicit compatibility review here.
    """
    base = {"identity_source", "ratings_source", "verified_at"}
    cache = {"ratings_cache", "ratings_version", "ratings_created_at", "ratings_provider"}
    if type(value) is not dict or set(value) not in (base, base | cache):
        return False
    if any(type(value[key]) is not str for key in ("identity_source", "ratings_source")):
        return False
    if value["verified_at"] is not None and type(value["verified_at"]) is not str:
        return False
    if set(value) == base:
        return True
    if (
        value["ratings_cache"] not in ("hit", "fresh")
        or value["ratings_version"] != "attraction-traits-v1"
    ):
        return False
    created, provider = value["ratings_created_at"], value["ratings_provider"]
    # Fresh, unstored estimates have neither cache timestamp nor provider label.
    if created is None or provider is None:
        return created is None and provider is None and value["ratings_cache"] == "fresh"
    if (
        type(created) is not str
        or len(created) > 64
        or type(provider) is not str
        or not 1 <= len(provider) <= 256
        or not provider.strip()
    ):
        return False
    try:
        stamp = datetime.fromisoformat(created.replace("Z", "+00:00"))
    except ValueError:
        return False
    return stamp.tzinfo is not None and stamp.utcoffset() is not None


_MEAL_KEYS = {
    "id",
    "kind",
    "meal_type",
    "name",
    "status",
    "optional",
    "arrival_time",
    "departure_time",
    "window_start",
    "window_end",
    "duration_seconds",
    "timezone",
    "notice",
}
_MEAL_WINDOWS = {"breakfast": (7, 9, 1800), "lunch": (12, 14, 2700), "dinner": (18, 20, 3600)}


def _meal_annotation(value):
    """Accept only bounded derived break metadata; it never supplies source facts.

    Final timing and itinerary rebuilding recompute these intervals. Admission
    checks only their shape before discarding them from the canonical payload;
    adding a break cannot resolve an unknown, altered, expired or unreviewed row.
    This module deliberately does not import the routing clock (an import cycle).
    """
    if type(value) is not list or len(value) > 189:
        return False
    seen, previous = set(), None
    for meal in value:
        if type(meal) is not dict or set(meal) != _MEAL_KEYS:
            return False
        kind = meal["meal_type"]
        if type(kind) is not str or kind not in _MEAL_WINDOWS:
            return False
        opening, closing, duration = _MEAL_WINDOWS[kind]
        if (
            meal["kind"] != "meal"
            or meal["status"] != "reserved"
            or meal["optional"] is not False
            or meal["name"] != kind.capitalize()
            or type(meal["duration_seconds"]) is not int
            or meal["duration_seconds"] != duration
            or type(meal["timezone"]) is not str
            or not 1 <= len(meal["timezone"]) <= 128
            or type(meal["notice"]) is not str
            or not 1 <= len(meal["notice"]) <= 1000
            or type(meal["id"]) is not str
        ):
            return False
        try:
            zone = ZoneInfo(meal["timezone"])
            stamps = []
            for key in ("window_start", "window_end", "arrival_time", "departure_time"):
                text = meal[key]
                if type(text) is not str or not 1 <= len(text) <= 64:
                    return False
                stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
                if stamp.tzinfo is None or stamp.utcoffset() is None:
                    return False
                local = stamp.astimezone(zone)
                if (
                    local.replace(tzinfo=None) != stamp.replace(tzinfo=None)
                    or local.utcoffset() != stamp.utcoffset()
                ):
                    return False
                stamps.append(stamp)
            start, end, arrival, departure = stamps
            if (
                start.time().isoformat() != f"{opening:02d}:00:00"
                or end.time().isoformat() != f"{closing:02d}:00:00"
                or end.date() != start.date()
                or meal["id"] != f"meal:{start.date().isoformat()}:{kind}"
                or meal["id"] in seen
                or not start <= arrival < departure <= end
                or (departure.astimezone(UTC) - arrival.astimezone(UTC)).total_seconds() != duration
                or (previous is not None and previous > arrival.astimezone(UTC))
            ):
                return False
        except (ValueError, TypeError, KeyError, OverflowError):
            return False
        seen.add(meal["id"])
        previous = departure.astimezone(UTC)
    return True


def _canonical(record, entry):
    if type(record) is not dict or set(record) - (set(FIELDS) | _RUNTIME_KEYS | {"generation"}):
        raise ValueError("unknown record projection")
    if "meal_breaks" in record and not _meal_annotation(record["meal_breaks"]):
        raise ValueError("invalid derived meal annotation")
    sid = entry["source_id"]
    provider = record.get("provider_id")
    expected_provider, expected_source = identity(sid)
    providers = {sid, expected_provider, "overture:" + sid}
    if "source_id" in record and record["source_id"] != sid:
        raise ValueError("canonical source identity differs")
    if "provider_id" in record and (type(provider) is not str or provider not in providers):
        raise ValueError("runtime provider identity differs")
    if record.get("source_id") != sid and provider is None:
        raise ValueError("complete source identity is required")
    if "source" in record:
        source = "overture" if provider == "overture:" + sid else expected_source
        if record["source"] != source:
            raise ValueError("runtime source/provider disagree")
    if "generation" in record and (
        type(record["generation"]) is not str or not _HEX64.fullmatch(record["generation"])
    ):
        raise ValueError("invalid generation projection")
    for key in ("source_release", "source_attribution", "description"):
        if key in record and record[key] is not None and type(record[key]) is not str:
            raise ValueError("invalid runtime annotation")
    if "provider_rank" in record and type(record["provider_rank"]) is not int:
        raise ValueError("invalid runtime provider rank")
    if "activities" in record and (
        not isinstance(record["activities"], list)
        or any(type(item) is not str for item in record["activities"])
    ):
        raise ValueError("invalid runtime activities")
    facts = _runtime_facts(record.get("source_provenance", record.get("provenance")))
    if "source_provenance" in record and "provenance" in record:
        ratings = record["provenance"]
        if not _rating_annotation(ratings) and _json(_runtime_facts(ratings)) != _json(facts):
            raise ValueError("ambiguous provenance projections")
    marks = [fact for fact in facts if _marker_like(fact)]
    if len(marks) != 1 or _json(marks[0]) != _json(entry["marker"]):
        raise ValueError("exactly one exact resolution marker is required")
    payload = {key: record[key] for key in FIELDS if key in record}
    payload["source_id"] = sid
    payload["provenance"] = [fact for fact in facts if not _marker_like(fact)]
    if "region" not in payload:
        # Region is not projected by repository.nearby. Its value is part of
        # the exact source-provenance marker, never a caller-supplied default.
        if "source_provenance" not in record or "coordinates" not in record:
            raise ValueError("only the documented runtime projection may omit region")
        payload["region"] = marks[0]["source_hold_resolution"]["region"]
    if "coordinates" in record:
        point = record["coordinates"]
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("runtime coordinate projection must be [latitude,longitude]")
        for key, value in zip(("latitude", "longitude"), point, strict=True):
            if key in payload and _json(payload[key]) != _json(value):
                raise ValueError("conflicting coordinate projections")
            payload[key] = value
    if set(payload) != set(FIELDS):
        raise ValueError("partial runtime records cannot resolve a held identity")
    return payload


def resolved(record, held_identities):
    """Resolve only a complete exact pinned row with all held aliases covered.

    The caller supplies all identities that triggered its original hold check.
    Admission freshness remains the responsibility of admission.py; this helper
    binds the original clocks exactly, including for immutable recovery targets.
    """
    if not isinstance(record, Mapping) or isinstance(held_identities, (str, bytes)):
        return False
    try:
        supplied = set(held_identities)
        if not supplied or any(
            type(sid) is not str or sid not in ORIGINAL_HELD_IDS for sid in supplied
        ):
            return False
        for entry in RESOLUTIONS:
            if supplied != set(entry["resolved_held_ids"]):
                continue
            try:
                payload = _canonical(record, entry)
            except (ValueError, TypeError, KeyError):
                continue
            if _held_ids(payload) == supplied and _json(payload) == _json(
                entry["approved_payload"]
            ):
                return True
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return False
    return False


def payload_sql(alias="p"):
    """Canonical PostgreSQL JSONB payload expression for independent MD5 proof."""
    if type(alias) is not str or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", alias):
        raise ValueError("SQL alias must be a literal identifier")
    facts = f"CASE WHEN jsonb_typeof({alias}.provenance)='array' THEN {alias}.provenance ELSE '[]'::jsonb END"
    provenance = f"""COALESCE((SELECT jsonb_agg(fact ORDER BY ord)
        FROM jsonb_array_elements({facts}) WITH ORDINALITY AS src(fact,ord)
        WHERE NOT (fact ? 'source_hold_resolution' OR COALESCE(fact->>'dataset'='{DATASET}',false))), '[]'::jsonb)"""
    pairs = []
    for key in FIELDS:
        pairs.extend((f"'{key}'", provenance if key == "provenance" else f"{alias}.{key}"))
    return "jsonb_build_object(" + ",".join(pairs) + ")"


def sql_resolved(entries):
    """Compact row signatures only; no source bodies or full facts in queries."""
    if not entries:
        return "FALSE"

    def quote(value):
        return "'" + value.replace("'", "''") + "'"

    values = ",".join(
        "("
        + ",".join(
            (
                quote(entry["source_id"]),
                quote(entry["payload_pg_md5"]),
                quote(_json(entry["marker"])) + "::jsonb",
            )
        )
        + ")"
        for entry in entries
    )
    facts = "CASE WHEN jsonb_typeof(p.provenance)='array' THEN p.provenance ELSE '[]'::jsonb END"
    return f"""EXISTS (
      SELECT 1 FROM (VALUES {values}) approved(source_id,payload_pg_md5,marker)
      WHERE p.source_id=approved.source_id
        AND md5(({payload_sql()})::text)=approved.payload_pg_md5
        AND (SELECT count(*) FROM jsonb_array_elements({facts}) fact
             WHERE fact ? 'source_hold_resolution' OR fact->>'dataset'='{DATASET}')=1
        AND (SELECT count(*) FROM jsonb_array_elements({facts}) fact WHERE fact=approved.marker)=1
        AND (SELECT count(*) FROM jsonb_array_elements({facts}) fact
             WHERE fact ? 'catalog_admission' OR fact->>'dataset'='Roadtrips catalog admission')=1
        AND EXISTS (SELECT 1 FROM jsonb_array_elements({facts}) fact
             WHERE fact->>'dataset'='Roadtrips catalog admission'
             AND fact->'catalog_admission'->>'tier' IN ('T2','T3')
             AND fact->'catalog_admission'->>'source_id'=p.source_id)
        AND (SELECT count(*) FROM jsonb_array_elements({facts}) fact WHERE fact ? 'source_visit_calendar')=1
        AND ((NOT (p.categories && ARRAY['daytime','food','culture','nightlife']::text[])
        AND EXISTS (SELECT 1 FROM jsonb_array_elements({facts}) fact
             WHERE fact->>'dataset'='{browse_quarantine.DATASET}'
             AND fact->>'schema_version'='{browse_quarantine.SCHEMA}'
             AND fact->'source_visit_calendar'->'weekly_windows'='[]'::jsonb
             AND fact->'source_visit_calendar'->'date_overrides'='[]'::jsonb
             AND COALESCE(fact->'source_visit_calendar'->'fixed_starts','[]'::jsonb)='[]'::jsonb
             AND COALESCE(fact->'source_visit_calendar'->'seasons','[]'::jsonb)='[]'::jsonb))
        OR (p.categories && ARRAY['daytime','food','culture','nightlife']::text[]
        AND EXISTS (SELECT 1 FROM jsonb_array_elements({facts}) fact
             WHERE fact->>'dataset'='Roadtrips routing qualification'
             AND fact->>'schema_version'='roadtrips-routing-qualification/1'
             AND fact->'source_visit_calendar'->>'schema_version'='roadtrips-source-visit-calendar/1'
             AND COALESCE(fact->'source_visit_calendar'->'unknown_reasons','[]'::jsonb)='[]'::jsonb)
        AND EXISTS (SELECT 1 FROM jsonb_array_elements({facts}) fact
             WHERE fact->'catalog_admission'->>'tier'='T3')))
        AND NOT EXISTS (SELECT 1 FROM public.places_catalog_calendars calendar
             WHERE calendar.generation=p.generation AND calendar.source_id=p.source_id)
    )"""


RESOLUTIONS = load_registry(
    Path(__file__).with_name("source_hold_resolutions.json"), REGISTRY_SHA256
)
SQL_RESOLVED = sql_resolved(RESOLUTIONS)
