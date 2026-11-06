"""Replay current official USFS facility clocks and visitor arrivals, failing closed.

The primary feed explicitly publishes visitor-facing facility facts. The legacy
recreation feed is joined by native ID: known negatives prevent admission and
missing records remain unknown. Without that retained publication contract, both
feeds must publish OPEN. Literal clocks are intersected; unresolved season,
closure and access prose is held. The bounded review period is our policy, never
an agency expiry or guaranteed access.
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import re
import time
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlsplit

from app.catalog import calendar_enrichment, usfs, usfs_parking_pdf
from app.routing.visit_calendar import Calendar

SCHEMA = "roadtrips-usfs-current-facilities/1"
SOURCE_URL = usfs.SOURCE_URL
ATTRIBUTION = (
    "USDA Forest Service factual recreation-facility and visitor-arrival data. "
    "No claim to original U.S. Government works. No agency endorsement. "
    "State boundaries: U.S. Census Bureau ACS 2025. "
    "Driving evidence: OSRM, © OpenStreetMap contributors (ODbL)."
)
MAX_ROWS = 10_000
MAX_BYTES = 64 * 1024 * 1024
LICENSE_PINS = {
    "LicenseRef-US-Agency-Factual-Data": "c66718549e68a3275abad375fa5e35a03dc8b09a31b7772e1cadbd52611560b1",
    "ODbL-1.0": "77d2692c3d64efdd4db18dce2407699baf62930e2b50d6e5ed90b48acf16b7c1",
}
LICENSE_URLS = {
    "LicenseRef-US-Agency-Factual-Data": SOURCE_URL,
    "ODbL-1.0": "https://opendatacommons.org/licenses/odbl/1-0/",
}
_ALL_YEAR = {"", "open year-round", "year-round", "year round", "open year round", "all year"}
PUBLICATION_ENDPOINTS = (
    usfs.FACILITY_URL.rsplit("/0/query", 1)[0],
    usfs.FACILITY_URL.rsplit("/query", 1)[0],
)
PUBLICATION_STATEMENT = "used to populate the public facing web pages"
_ACCESS = (
    "directions",
    "recarea_description",
    "restrictions",
    "important_info",
    "season_description",
    "site_contact_notes",
    "permit_information",
    "open_season",
    "op_status_reason",
    "fee_description",
    "passes",
    "passes_accepted",
)
# These qualifications affect access, not ordinary fire/animal/conservation rules.
_AMBIGUOUS = re.compile(
    r"weather (?:dependent|permitting)|inaccessible|snow|winter|seasonal|"
    r"reservations? (?:are |is )?(?:required|only)|permits? (?:are |is )?(?:required|only)|"
    r"requires? (?:an? )?(?:reservation|permit)|"
    r"\bmust (?:have|obtain|purchase|carry)\b[^.]{0,80}\b(?:permit|reservation|ticket)\b|"
    r"\b(?:shuttle|ferry|walk[- ]in|hike[- ]in|foot[- ]access[- ]only|pedestrian[- ]only)\b|"
    r"\bGPS\b|\b(?:latitude|longitude)\s*[:=]|"
    r"\bclos(?:e[sd]?|ures?)\b|not (?:accessible|open)|gates? (?:shut|lock)|"
    r"no (?:car |vehicle |public )parking|parking (?:is not available|prohibited)|"
    r"(?:check|call)[^.]{0,70}(?:open|access|restriction)|"
    r"(?:daylight|sunrise|sunset|dawn|dusk)|no overnight use",
    re.I,
)
_EXACT_HOURS = {
    "open 24 hours/day",
    "24 hours/day",
    "open 24 hours/day.",
    "open 24 hours/ day",
    "open 24 hours/day, year-round",
    "all year, all hours",
}


def visible(value):
    return " ".join(re.sub(r"<[^>]*>", " ", html.unescape(value or "")).split())


def clock_windows(literal):
    """Accept only complete unqualified daily statements, never free-text guesses."""
    value = visible(literal).lower()
    if value in _EXACT_HOURS:
        return (0, 1440)
    value = value.replace("a.m.", "am").replace("p.m.", "pm")
    value = value.replace("a.m", "am").replace("p.m", "pm")
    value = re.sub(r"^open year[- ]round[, .]*", "", value)
    value = re.sub(
        r"^(?:day[- ]use only: open|day[- ]use hours (?:are|from)|open 7 days a week from|open daily from|daily,|open)\s*",
        "",
        value,
    )
    match = re.fullmatch(
        r"(\d{1,2})(?::([0-5]\d))?\s*(am|pm)\s*(?:-|–|to)\s*"
        r"(\d{1,2})(?::([0-5]\d))?\s*(am|pm)(?:\s+daily)?\.?",
        value,
    )
    if not match:
        return None
    a, am, ap, b, bm, bp = match.groups()
    if not 1 <= int(a) <= 12 or not 1 <= int(b) <= 12:
        return None
    start = (int(a) % 12 + (12 if ap == "pm" else 0)) * 60 + int(am or 0)
    end = (int(b) % 12 + (12 if bp == "pm" else 0)) * 60 + int(bm or 0)
    return (start, end) if start < end else None


def _receipt(value, root, max_bytes, seen, reviewed_on, *, endpoint=None):
    raw = usfs.retained(root, value, ceiling=max_bytes, endpoint=endpoint)
    checked = datetime.fromisoformat(value["retrieved_at"].replace("Z", "+00:00"))
    if not 0 <= (reviewed_on - checked.astimezone(UTC).date()).days <= 1:
        raise ValueError("USFS evidence is outside the one-day acquisition review policy")
    path = (root / value["path"]).resolve()
    if path not in seen:
        seen[path] = len(raw)
    if sum(seen.values()) > max_bytes:
        raise ValueError("USFS aggregate evidence exceeds byte ceiling")
    return raw


def _source_receipt(value):
    return {
        "source_url": value["url"],
        "snapshot_sha256": value["sha256"],
        "checked_at": value["retrieved_at"],
        "evidence_path": value["path"],
    }


def _window(minutes):
    start, end = minutes
    return {
        "opens": f"{start // 60:02d}:{start % 60:02d}",
        "closes": "00:00" if end == 1440 else f"{end // 60:02d}:{end % 60:02d}",
        "end_day_offset": 1 if end == 1440 else 0,
        "weekdays": list(range(7)),
    }


def primary_qualification(a, public, shapes, reviewed_on, *, parking_corroboration=None):
    """Separate public-visitor source path, never a fabricated legacy-feed OPEN."""
    if a.get("site_cn") in usfs.REVIEW_HOLDS:
        return None, "existing_review_hold"
    if a.get("site_type") not in usfs.TYPES or a.get("development_status") != "EXISTING":
        return None, "ineligible_facility_type_or_development"
    if a.get("recarea_enable") != "Y" or a.get("seasonal_operational_status") != "OPEN":
        return None, "primary_visitor_status_not_open"
    if public is not None:
        if str(a.get("usda_portal_id")) != str(public.get("recareaid")):
            return None, "public_identity_mismatch"
        if public.get("openstatus") not in {None, "none", "open"}:
            return None, "known_public_negative_or_unrecognized_status"
        if usfs.public_season_conflict(public, reviewed_on):
            return None, "public_season_outside_dated_admission"
    text = " ".join(visible(a.get(key)) for key in usfs.ACCESS_FIELDS)
    corroborated = (
        parking_corroboration is not None
        and parking_corroboration.get("record_id") == a.get("site_cn")
        and parking_corroboration.get("single_vehicle_spaces", 0) > 0
    )
    if not a.get("directions") or not (
        re.search(r"\bparking\b|\bcars?\b", text, re.I) or corroborated
    ):
        return None, "parking_or_directions_not_documented"
    other = " ".join(visible((public or {}).get(key)) for key in usfs.PUBLIC_ACCESS_FIELDS)
    if usfs.CONTRADICTION.search(text) or usfs.CONTRADICTION.search(other):
        return None, "contradictory_access_text"
    if usfs.VEHICLE_WARNING.search(text) or usfs.VEHICLE_WARNING.search(other):
        return None, "published_vehicle_access_warning"
    lat, lon = a.get("latitude"), a.get("longitude")
    if any(
        type(value) not in {float, int} or not math.isfinite(value) for value in (lat, lon)
    ) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None, "coordinates"
    if public is not None:
        try:
            if any(isinstance(public[key], bool) for key in ("latitude", "longitude")):
                raise ValueError
            point = {"latitude": float(public["latitude"]), "longitude": float(public["longitude"])}
            if not (
                math.isfinite(point["latitude"])
                and math.isfinite(point["longitude"])
                and -90 <= point["latitude"] <= 90
                and -180 <= point["longitude"] <= 180
            ):
                raise ValueError
            if usfs.mixed.distance(a, point) > 500:
                return None, "public_identity_point_more_than_500m_away"
        except (KeyError, TypeError, ValueError):
            return None, "public_coordinates_missing"
    region = usfs.state_for([lat, lon], shapes)
    if not region or (a.get("states_spanned") in usfs.US_REGIONS and a["states_spanned"] != region):
        return None, "published_state_missing_or_conflicting"
    name = a.get("public_site_name") or a.get("recarea_name") or a.get("site_name")
    if (
        not isinstance(name, str)
        or not 1 <= len(name.strip()) <= 300
        or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", a.get("site_cn", ""))
    ):
        return None, "native_identity"
    url = a.get("usda_portal_url") or (public or {}).get("recareaurl")
    if not url:
        url = (
            usfs.FACILITY_URL
            + "?"
            + urlencode({"f": "json", "where": "site_cn='" + a["site_cn"] + "'", "outFields": "*"})
        )
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "www.fs.usda.gov",
        "fs.usda.gov",
        "apps.fs.usda.gov",
    }:
        return None, "publisher_url"
    return {
        "source_id": "usfs:facility:" + a["site_cn"],
        "name": name.strip(),
        "latitude": lat,
        "longitude": lon,
        "region": region,
        "categories": usfs.TYPES[a["site_type"]],
        "address": None,
        "url": url,
        "source_updated_at": datetime.fromtimestamp(a["infra_last_update"] / 1000, UTC).isoformat()
        if type(a.get("infra_last_update")) in {float, int}
        else None,
    }, None


def qualify(
    a, public, shapes, reviewed_on, *, primary_publication=False, parking_corroboration=None
):
    row, reason = (
        primary_qualification(
            a, public, shapes, reviewed_on, parking_corroboration=parking_corroboration
        )
        if primary_publication
        else usfs.qualification(a, public, shapes, as_of=reviewed_on)
    )
    if reason:
        return None, reason
    public = public or {}
    primary_hours = clock_windows(a.get("operational_hours"))
    if primary_hours is None:
        return None, "literal_daily_clocks_missing_or_qualified"
    if any(
        a.get(key) not in {None, ""}
        for key in ("season_name", "site_season_start_date", "site_season_end_date")
    ):
        return None, "native_season_requires_separate_review"
    # A positive source status does not erase contradictory qualification text.
    for key in _ACCESS:
        text = visible(a.get(key))
        if key == "open_season" and text.lower() in _ALL_YEAR:
            continue
        if key in {"open_season", "season_description"} and text:
            return None, "season_not_complete_literal_year_round"
        if _AMBIGUOUS.search(text):
            return None, "unresolved_published_access_qualification"
    for key in ("restrictions", "reservation_info", "accessibility", "recareadescription"):
        if _AMBIGUOUS.search(visible(public.get(key))):
            return None, "unresolved_public_access_qualification"
    other = visible(public.get("operational_hours"))
    if other:
        public_hours = clock_windows(other)
        if public_hours is None:
            return None, "public_hours_not_complete_literal_daily_clocks"
        primary_hours = (
            max(primary_hours[0], public_hours[0]),
            min(primary_hours[1], public_hours[1]),
        )
        if primary_hours[0] >= primary_hours[1]:
            return None, "published_clock_windows_do_not_intersect"
    # Complete published seasonal dates cannot be discarded after today's check.
    start, end = public.get("open_season_start"), public.get("open_season_end")
    if any(visible(value).lower() not in _ALL_YEAR for value in (start, end)):
        return None, "public_season_requires_separate_review"
    row["source_id"] = "usfs:facility:" + a["site_cn"]
    return (row, primary_hours), None


def prepare(path, manifest=None, *, max_rows=MAX_ROWS, max_bytes=MAX_BYTES):
    path = Path(path)
    max_bytes = min(max_bytes, MAX_BYTES)
    with path.open("rb") as stream:
        raw = stream.read(128 * 1024 + 1)
    if not raw or len(raw) > 128 * 1024:
        raise ValueError("USFS bundle exceeds bounded manifest size")
    if manifest is None:
        with Path(str(path) + ".manifest.json").open("rb") as stream:
            manifest_raw = stream.read(32_769)
        if len(manifest_raw) > 32_768:
            raise ValueError("USFS source sidecar exceeds byte ceiling")
        manifest = json.loads(manifest_raw)
    if (
        manifest.get("schema_version") != SCHEMA
        or manifest.get("sha256") != hashlib.sha256(raw).hexdigest()
        or manifest.get("source_url") != SOURCE_URL
        or manifest.get("attribution") != ATTRIBUTION
        or not re.fullmatch(r"usfs-current-\d{4}-\d{2}-\d{2}", manifest.get("release", ""))
    ):
        raise ValueError("USFS source manifest checksum/identity mismatch")
    persona_version = manifest.get("persona_enrichment")
    if persona_version is not None and persona_version != "roadtrips-source-persona/1":
        raise ValueError("unsupported deterministic source persona version")
    bundle = json.loads(raw)
    if bundle.get("schema_version") != SCHEMA:
        raise ValueError("unsupported USFS current bundle schema")
    reviewed_on = date.fromisoformat(bundle["reviewed_on"])
    release = "usfs-current-" + reviewed_on.isoformat()
    if manifest["release"] != release:
        raise ValueError("USFS dated release differs from review policy date")
    selected = bundle.get("selected_site_ids")
    if (
        not isinstance(selected, list)
        or not 1 <= len(selected) <= min(max_rows, MAX_ROWS)
        or any(
            not isinstance(item, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", item)
            for item in selected
        )
        or len(set(selected)) != len(selected)
    ):
        raise ValueError("USFS selection must contain bounded distinct native facility IDs")
    root, seen = path.parent, {path.resolve(): len(raw)}
    reviewed = None
    review = manifest.get("arrival_review")
    if review is not None:
        reader = calendar_enrichment.Reader(root, min(max_bytes, 256 * 1024))
        body = reader.read(review.get("path"), review.get("sha256"))
        ledger = json.loads(body)
        if (
            ledger.get("schema_version") != "roadtrips-usfs-arrival-review/1"
            or ledger.get("source_bundle_sha256") != manifest["sha256"]
        ):
            raise ValueError("independent arrival review differs from original source bundle")
        reviewed = {}
        for item in ledger.get("records", []):
            sid = item.get("source_id")
            if (
                not isinstance(sid, str)
                or sid in reviewed
                or item.get("decision") not in {"hold", "reviewed_no_additional_conflict_observed"}
            ):
                raise ValueError("invalid or conflicting independent arrival review")
            reviewed[sid] = item
        if not 1 <= len(reviewed) <= 250:
            raise ValueError("independent arrival review exceeds bounded scope")
        seen[(root / review["path"]).resolve()] = len(body)
    if set(manifest.get("licenses", {})) != set(LICENSE_PINS):
        raise ValueError("USFS requires exact factual-data and ODbL reuse notices")
    for key, expected in LICENSE_PINS.items():
        evidence = manifest["licenses"][key]
        relative = evidence.get("path")
        if (
            evidence.get("sha256") != expected
            or evidence.get("url") != LICENSE_URLS[key]
            or not calendar_enrichment.portable_relative(relative)
        ):
            raise ValueError("USFS reuse notice differs from reviewed source contract")
        target = (root / relative).resolve()
        if not target.is_relative_to(root.resolve()):
            raise ValueError("USFS rights evidence escapes source directory")
        with target.open("rb") as stream:
            body = stream.read(1024 * 1024 + 1)
        if not body or len(body) > 1024 * 1024 or hashlib.sha256(body).hexdigest() != expected:
            raise ValueError("USFS retained reuse notice checksum/size mismatch")
        seen[target] = len(body)
    if sum(seen.values()) > max_bytes:
        raise ValueError("USFS source headers exceed byte ceiling")
    publication_receipts = []
    publication = bundle.get("publication_contract", [])
    if publication:
        if not isinstance(publication, list) or len(publication) != 2:
            raise ValueError("USFS primary publication requires service and layer contracts")
        for evidence, endpoint in zip(publication, PUBLICATION_ENDPOINTS):
            body = _receipt(evidence, root, max_bytes, seen, reviewed_on, endpoint=endpoint)
            data = json.loads(body)
            purpose = visible(
                data.get("serviceDescription", "") + " " + data.get("description", "")
            ).lower()
            if PUBLICATION_STATEMENT not in purpose or "Query" not in data.get(
                "capabilities", ""
            ).split(","):
                raise ValueError("USFS source no longer establishes public visitor publication")
            if endpoint == PUBLICATION_ENDPOINTS[1] and not {
                "site_cn",
                "latitude",
                "longitude",
                "operational_hours",
                "directions",
                "seasonal_operational_status",
                "recarea_enable",
            } <= {field.get("name") for field in data.get("fields", [])}:
                raise ValueError("USFS published visitor facility field contract changed")
            publication_receipts.append(_source_receipt(evidence))
    rows_by_id, receipt_by_id, publics, public_receipts, public_lookups = {}, {}, {}, {}, {}
    scanned = 0
    for key, endpoint, identity, target, receipts in (
        ("facilities", usfs.FACILITY_URL, "site_cn", rows_by_id, receipt_by_id),
        ("public", usfs.PUBLIC_URL, "recareaid", publics, public_receipts),
    ):
        for evidence in bundle[key]:
            data = json.loads(
                _receipt(evidence, root, max_bytes, seen, reviewed_on, endpoint=endpoint)
            )
            if data.get("error") or (key == "public" and data.get("exceededTransferLimit")):
                raise ValueError("USFS source query failed or truncated public identity lookup")
            query_ids = None
            if key == "public":
                query = parse_qs(urlsplit(evidence["url"]).query, keep_blank_values=True)
                allowed = {
                    "f",
                    "where",
                    "outFields",
                    "returnGeometry",
                    "outSR",
                    "orderByFields",
                    "resultOffset",
                    "resultRecordCount",
                }
                if (
                    set(query) - allowed
                    or any(len(values) != 1 for values in query.values())
                    or query.get("outFields") != ["*"]
                    or query.get("f") != ["json"]
                    or query.get("returnGeometry") != ["true"]
                    or query.get("outSR") != ["4326"]
                    or query.get("resultOffset", ["0"]) != ["0"]
                ):
                    raise ValueError("USFS public query may not omit status fields or add filters")
                where = query.get("where", [""])[0]
                match = re.fullmatch(
                    r"recareaid\s+IN\s*\(\s*(\d+(?:\s*,\s*\d+)*)\s*\)", where, re.I
                )
                if not match:
                    raise ValueError(
                        "USFS public absence requires complete unfiltered identity lookups"
                    )
                query_ids = set(re.findall(r"\d+", match[1]))
                count = query.get("resultRecordCount", ["1000"])[0]
                if not count.isdigit() or not len(query_ids) <= int(count) <= 1000:
                    raise ValueError(
                        "USFS public lookup cannot truncate requested native identities"
                    )
                for native_id in query_ids:
                    if native_id in public_lookups:
                        raise ValueError("USFS public lookup repeats selected identity")
                    public_lookups[native_id] = evidence
            for feature in data.get("features", []):
                item = feature["attributes"]
                ident = str(item[identity])
                if ident in target:
                    raise ValueError("USFS source repeats a native identity")
                if query_ids is not None and ident not in query_ids:
                    raise ValueError("USFS public source returned an identity outside its query")
                target[ident], receipts[ident] = item, evidence
                scanned += 1
                if scanned > min(max_rows, MAX_ROWS):
                    raise ValueError("USFS source scan exceeds unchanged ceiling")
    state_raw = _receipt(
        bundle["states"], root, max_bytes, seen, reviewed_on, endpoint=usfs.STATE_URL
    )
    shapes = usfs.state_shapes(json.loads(state_raw))
    parking_publications = bundle.get("parking_publications", [])
    if parking_publications and not publication_receipts:
        raise ValueError("parking publication cannot replace the primary visitor source contract")
    parking_documents = (
        usfs_parking_pdf.extract(
            parking_publications,
            lambda evidence: _receipt(evidence, root, max_bytes, seen, reviewed_on),
        )
        if parking_publications
        else []
    )
    parking_joins = usfs_parking_pdf.joins(
        {ident: value for ident, value in rows_by_id.items() if ident in selected},
        parking_documents,
    )
    checks = {item["site_cn"]: item["receipt"] for item in bundle.get("driving", [])}
    if len(checks) != len(bundle.get("driving", [])):
        raise ValueError("USFS driving evidence repeats a facility")
    rows, entries, ledger, rejects = [], [], [], Counter()
    for ident in selected:
        a = rows_by_id.get(ident)
        if a is None:
            raise ValueError("selected native facility absent from source snapshot")
        portal = str(a.get("usda_portal_id"))
        if publication_receipts and portal.isdigit() and portal not in public_lookups:
            raise ValueError("USFS primary admission omitted a linked public status lookup")
        b = publics.get(portal)
        qualified, reason = qualify(
            a,
            b,
            shapes,
            reviewed_on,
            primary_publication=bool(publication_receipts),
            parking_corroboration=parking_joins.get(ident),
        )
        if reason is None:
            row, hours = qualified
            check = checks.get(ident)
            if check is None:
                reason = "native_arrival_driving_check_missing"
            else:
                _receipt(check, root, max_bytes, seen, reviewed_on)
                try:
                    usfs.driving(root, check, row)
                except ValueError:
                    reason = "native_arrival_not_within_75m_of_driving_destination"
        if reason is None and reviewed is not None:
            review_item = reviewed.get(row["source_id"])
            if review_item is None:
                reason = "independent_arrival_review_missing"
            elif review_item["decision"] == "hold":
                reason = "independent_arrival_review_hold: " + str(
                    review_item.get("reason", "unresolved arrival")
                )
        ledger.append(
            {
                "site_cn": ident,
                "source_id": "usfs:facility:" + ident,
                "name": a.get("public_site_name"),
                "status": "accepted" if reason is None else "held",
                "reason": reason,
            }
        )
        if reason:
            rejects[reason] += 1
            continue
        lookup = public_lookups.get(portal)
        receipts = [_source_receipt(receipt_by_id[ident]), *publication_receipts]
        parking_fact = parking_joins.get(ident)
        if parking_fact:
            receipts.append(_source_receipt(parking_fact["receipt"]))
        if lookup is not None:
            receipts.append(_source_receipt(lookup))
        public_fields = b or {}
        calendar = {
            "schema_version": "roadtrips-source-visit-calendar/1",
            "weekly_windows": [_window(hours)],
            "seasons": [
                {
                    "kind": "dated",
                    "start": reviewed_on.isoformat(),
                    "end": (reviewed_on + timedelta(days=29)).isoformat(),
                }
            ],
            "source_receipts": receipts,
            "unknown_reasons": [],
        }
        Calendar.model_validate(calendar)
        constraints = [
            {
                "source": "USFS construction facility",
                "source_record_id": ident,
                "source_url": receipts[0]["source_url"],
                "fields": {
                    key: a.get(key)
                    for key in (
                        *_ACCESS,
                        "operational_hours",
                        "seasonal_operational_status",
                        "site_type",
                        "latitude",
                        "longitude",
                    )
                },
            },
            {
                "source": "USFS public recreation",
                "source_record_id": portal,
                "source_url": lookup["url"] if lookup else None,
                "published_status": public_fields.get("openstatus")
                if b
                else "record missing; not asserted open",
                "fields": {
                    key: public_fields.get(key)
                    for key in (
                        "openstatus",
                        "operational_hours",
                        "open_season_start",
                        "open_season_end",
                        "restrictions",
                        "reservation_info",
                        "accessibility",
                    )
                },
            },
        ]
        if parking_fact:
            constraints.append(
                {
                    "source": "USFS official publication vehicle parking",
                    "source_record_id": ident,
                    "source_url": parking_fact["receipt"]["url"],
                    "snapshot_sha256": parking_fact["receipt"]["sha256"],
                    "evidence_path": parking_fact["receipt"]["path"],
                    "page": parking_fact["page"],
                    "matched_native_title": parking_fact["matched_native_title"],
                    "single_vehicle_spaces": parking_fact["single_vehicle_spaces"],
                    "literal_parking_statement": parking_fact["literal_parking_statement"],
                    "literal_camping_restrictions": parking_fact["literal_camping_restrictions"],
                    "capacity_is_current_inventory": False,
                    "hours_or_coordinates_imported_from_pdf": False,
                }
            )
        entry = {
            "source_id": row["source_id"],
            "source_visit_calendar": calendar,
            "source_constraints": constraints,
            "transformation": {
                "rule": "Official primary public visitor facility publication; retain independent legacy-public unknowns and respect known negatives; intersect every published complete literal daily clock; no estimated daylight hours"
                if publication_receipts
                else "Intersect complete literal daily clocks from dual-open official feeds; retain native documented visitor-facility arrival; no estimated daylight hours",
                "policy_date_start": reviewed_on.isoformat(),
                "policy_date_end": (reviewed_on + timedelta(days=29)).isoformat(),
                "policy_scope_is_source_publication_or_expiry_claim": False,
            },
            "source_release": release,
            "source_attribution": ATTRIBUTION,
        }
        row["provenance"] = [
            {
                "dataset": "USDA Forest Service current public recreation facilities",
                "record_id": ident,
                "public_record_id": portal,
                "source_url": receipts[0]["source_url"],
                "snapshot_sha256": receipts[0]["snapshot_sha256"],
                "checked_at": receipts[0]["checked_at"],
                "license": "LicenseRef-US-Agency-Factual-Data",
                "point_role": a["site_type"],
                "coordinate_source": "unchanged USFS constructed recreation-site latitude/longitude",
                "arrival_type": "published visitor facility with documented parking and driving directions",
                "published_access_facts": usfs.access_facts(
                    a, b, receipt_by_id[ident], public_receipts[portal]
                )
                if b
                else {
                    "construction_feed": {
                        "record_id": ident,
                        **receipts[0],
                        "fields": {
                            key: a.get(key)
                            for key in (
                                *_ACCESS,
                                "operational_hours",
                                "seasonal_operational_status",
                            )
                        },
                    },
                    "public_feed": {
                        "record_id": a.get("usda_portal_id"),
                        "status": "record missing; not asserted open",
                        "source_url": lookup["url"] if lookup else None,
                    },
                },
                "publication_contract": publication_receipts,
                "legacy_public_status": public_fields.get("openstatus")
                if b
                else "record missing; not asserted open",
                "driving_evidence_sha256": check["sha256"],
                "driving_checked_at": check["retrieved_at"],
                "driving_snap_distance_m": check["snap_distance_m"],
                "source_release": release,
                "source_attribution": ATTRIBUTION,
                "limitations": "Dated published access only; parking capacity, ticket availability, admission price and future road/weather access are not established. Native facility point is not a surveyed parking entrance; walking may be required.",
                **(
                    {"independent_arrival_review_sha256": review["sha256"]}
                    if review is not None
                    else {}
                ),
            }
        ]
        if parking_fact:
            row["provenance"][0]["parking_corroboration"] = {
                **parking_fact,
                "receipt": _source_receipt(parking_fact["receipt"]),
            }
        if persona_version is not None:
            from app.catalog.personas import build, stored

            row["provenance"].append(
                stored(build(row, entry, release=release, attribution=ATTRIBUTION))
            )
        rows.append(row)
        entries.append(entry)
    return rows, {
        "scanned": scanned,
        "accepted": len(rows),
        "bytes": sum(seen.values()),
        "rejects": dict(rejects),
        "calendar_entries": entries,
        "admission_ledger": ledger,
    }


def _load_routes(index_path, route_root):
    """Verify retained OSRM road geometry; endpoint chords never replace roads."""
    index_path, route_root = Path(index_path), Path(route_root)
    if not index_path.is_file() or index_path.stat().st_size > 1024 * 1024:
        raise ValueError("missing or oversized route inventory")
    index = json.loads(index_path.read_bytes())
    if not 1 <= len(index.get("routes", [])) <= 16:
        raise ValueError("route inventory requires one to sixteen actual road routes")
    receipts = {item["path"]: item for item in index["receipts"]}
    reader = calendar_enrichment.Reader(route_root, 16 * 1024 * 1024)
    routes = []
    for item in index["routes"]:
        name = item["response_path"]
        receipt = receipts[name]
        parsed = urlsplit(receipt["url"])
        if (
            receipt.get("status") != 200
            or parsed.scheme != "https"
            or parsed.hostname != "router.project-osrm.org"
            or not parsed.path.startswith("/route/v1/driving/")
        ):
            raise ValueError("corridor geometry must come from successful retained OSRM driving")
        data = json.loads(reader.read(name, receipt["sha256"]))
        if data.get("code") != "Ok" or len(data.get("routes", [])) != 1:
            raise ValueError("corridor response does not establish one successful road route")
        geometry = data["routes"][0].get("geometry", {})
        points = geometry.get("coordinates")
        if (
            geometry.get("type") != "LineString"
            or not isinstance(points, list)
            or not 2 <= len(points) <= 100_000
        ):
            raise ValueError("corridor needs bounded full road LineString geometry")
        if any(
            not isinstance(point, list)
            or len(point) != 2
            or any(type(x) not in {int, float} or not math.isfinite(x) for x in point)
            or not (-180 <= point[0] <= 180 and -90 <= point[1] <= 90)
            for point in points
        ):
            raise ValueError("corridor geometry contains invalid coordinates")
        routes.append((item["id"], points))
    return routes


def corridor_grid(routes):
    """Index every road segment, including long segments between sparse vertices."""
    grid = {}
    for ident, points in routes:
        for a, b in zip(points, points[1:]):
            x0, x1 = sorted((math.floor(a[0] * 4), math.floor(b[0] * 4)))
            y0, y1 = sorted((math.floor(a[1] * 4), math.floor(b[1] * 4)))
            if (x1 - x0 + 1) * (y1 - y0 + 1) > 4096:
                raise ValueError("route segment exceeds bounded geographic index")
            for x in range(x0, x1 + 1):
                for y in range(y0, y1 + 1):
                    grid.setdefault((x, y), []).append((ident, a, b))
    return grid


def nearby_corridors(lat, lon, grid, *, radius_m=8046.72):
    """Continuous five-mile road buffer, never a promise of runtime sample coverage."""
    if not (math.isfinite(lat) and math.isfinite(lon) and 24 <= lat <= 50 and -125 <= lon <= -66):
        return []
    scale = math.cos(math.radians(lat))
    margin_y, margin_x = radius_m / 111_195, radius_m / (111_195 * scale)
    found = set()
    for x in range(math.floor((lon - margin_x) * 4), math.floor((lon + margin_x) * 4) + 1):
        for y in range(math.floor((lat - margin_y) * 4), math.floor((lat + margin_y) * 4) + 1):
            for ident, a, b in grid.get((x, y), []):
                px, py = (lon - a[0]) * scale, lat - a[1]
                dx, dy = (b[0] - a[0]) * scale, b[1] - a[1]
                fraction = (
                    max(0, min(1, (px * dx + py * dy) / (dx * dx + dy * dy))) if dx or dy else 0
                )
                if math.hypot(px - fraction * dx, py - fraction * dy) * 111_195 <= radius_m:
                    found.add(ident)
    return sorted(found)


def acquire(
    output,
    *,
    parent_rows,
    routes_index,
    route_root,
    parking_publication_urls=(),
    site_ids=None,
):
    """Acquire reproducible official inputs and arrival checks; no database writes.

    Parent rows seed refreshes; new candidate facilities must fall within a
    continuous five-mile buffer of verified road geometry. An explicit shortlist
    of up to 250 native identities permits bounded regional gap filling instead;
    it changes selection only, never source admission or arrival checks.
    Every remote body and
    discovery decision is retained. OSRM requests are serialized at <=1/second.
    """
    import requests

    if site_ids is not None and (
        not isinstance(site_ids, list)
        or not 1 <= len(site_ids) <= 250
        or any(
            not isinstance(item, str) or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", item)
            for item in site_ids
        )
        or len(set(site_ids)) != len(site_ids)
    ):
        raise ValueError("explicit USFS shortlist requires 1..250 distinct native IDs")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    if isinstance(parent_rows, (str, Path)):
        parent_path = Path(parent_rows)
        if not parent_path.is_file() or parent_path.stat().st_size > MAX_BYTES:
            raise ValueError("parent catalog snapshot missing or oversized")
        parent_rows = json.loads(parent_path.read_bytes())
    if not isinstance(parent_rows, list) or len(parent_rows) > 50_000:
        raise ValueError("parent catalog exceeds unchanged row ceiling")
    parent_ids = set()
    for row in parent_rows:
        for item in row.get("provenance", []):
            if not isinstance(item, dict):
                continue
            facts = item.get("published_access_facts")
            if isinstance(facts, dict) and isinstance(facts.get("construction_feed"), dict):
                ident = facts["construction_feed"].get("record_id")
                if isinstance(ident, str) and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", ident):
                    parent_ids.add(ident)
    routes = _load_routes(routes_index, route_root)
    grid = corridor_grid(routes)
    budget, last_osrm = 0, None
    reviewed_on = datetime.now(UTC).date()

    def fetch(url, relative, *, ceiling=16 * 1024 * 1024):
        nonlocal budget, last_osrm
        parsed = urlsplit(url)
        endpoint = parsed.scheme + "://" + parsed.netloc + parsed.path
        is_osrm = (
            parsed.scheme == "https"
            and parsed.netloc == "router.project-osrm.org"
            and re.fullmatch(r"/route/v1/driving/[-0-9.,;]+", parsed.path)
        )
        if (
            endpoint
            not in {usfs.FACILITY_URL, usfs.PUBLIC_URL, usfs.STATE_URL, *PUBLICATION_ENDPOINTS}
            and not is_osrm
            and not usfs_parking_pdf.official_publication(url)
        ):
            raise ValueError("unapproved USFS acquisition endpoint")
        if is_osrm:
            if last_osrm is not None:
                time.sleep(max(0, 1 - (time.monotonic() - last_osrm)))
            last_osrm = time.monotonic()
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=(10, 40), allow_redirects=False) as response:
            chunks, size = [], 0
            for chunk in response.iter_content(64 * 1024):
                size += len(chunk)
                if size > ceiling or budget + size > MAX_BYTES:
                    raise ValueError("USFS remote body or aggregate acquisition exceeds ceiling")
                chunks.append(chunk)
            body = b"".join(chunks)
            budget += size
            target.write_bytes(body)
            result = {
                "path": relative,
                "url": url,
                "sha256": hashlib.sha256(body).hexdigest(),
                "retrieved_at": datetime.now(UTC).isoformat(),
                "status": response.status_code,
                "bytes": len(body),
            }
        if result["status"] != 200:
            raise ValueError("USFS acquisition returned unsuccessful HTTP status")
        return result

    def query(endpoint, where, relative, *, offset=0, count=2000, geojson=False):
        params = {
            "f": "geojson" if geojson else "json",
            "where": where,
            "outFields": "STUSAB" if geojson else "*",
            "returnGeometry": "true",
            "outSR": 4326,
            "resultRecordCount": count,
        }
        if not geojson:
            params.update(
                orderByFields="objectid" if endpoint == usfs.FACILITY_URL else "recareaid",
                resultOffset=offset,
            )
        evidence = fetch(endpoint + "?" + urlencode(params), relative)
        data = json.loads((output / relative).read_bytes())
        if data.get("error"):
            raise ValueError("official ArcGIS source rejected bounded query")
        return evidence, data

    publication = []
    for label, endpoint in zip(("service", "layer"), PUBLICATION_ENDPOINTS):
        evidence = fetch(
            endpoint + "?f=json", "sources/publication-" + label + ".json", ceiling=1024 * 1024
        )
        data = json.loads((output / evidence["path"]).read_bytes())
        if (
            PUBLICATION_STATEMENT
            not in visible(
                data.get("serviceDescription", "") + " " + data.get("description", "")
            ).lower()
        ):
            raise ValueError("official USFS publication no longer establishes visitor-use purpose")
        publication.append(evidence)
    if (
        not isinstance(parking_publication_urls, (list, tuple))
        or len(parking_publication_urls) > 16
        or len(set(parking_publication_urls)) != len(parking_publication_urls)
    ):
        raise ValueError("parking publication acquisition requires bounded distinct official URLs")
    parking_publications = [
        fetch(
            url, f"sources/parking-publication-{index}.pdf", ceiling=usfs_parking_pdf.MAX_PDF_BYTES
        )
        for index, url in enumerate(parking_publication_urls)
    ]
    parking_documents = (
        usfs_parking_pdf.extract(
            parking_publications, lambda evidence: (output / evidence["path"]).read_bytes()
        )
        if parking_publications
        else []
    )
    discovered, discovery = {}, []
    for page in range(6):
        evidence, data = query(
            usfs.FACILITY_URL,
            "recarea_enable='Y' AND seasonal_operational_status='OPEN' AND operational_hours IS NOT NULL",
            f"discovery/facilities-{page}.json",
            offset=page * 2000,
        )
        discovery.append(evidence)
        features = data.get("features", [])
        for feature in features:
            a = feature["attributes"]
            if a["site_cn"] in discovered or len(discovered) >= MAX_ROWS:
                raise ValueError("USFS discovery repeats identity or exceeds 10,000 records")
            discovered[a["site_cn"]] = a
        if not data.get("exceededTransferLimit"):
            break
        if len(features) != 2000:
            raise ValueError("USFS paginated source truncated before expected page boundary")
    else:
        raise ValueError("USFS discovery exceeded bounded page count")
    selected, corridor_matches = set(), {}
    if site_ids is not None and set(site_ids) - discovered.keys():
        raise ValueError("explicit USFS shortlist identities missing from current discovery")
    for ident, a in discovered.items():
        if a.get("site_type") not in usfs.TYPES:
            continue
        lat, lon = a.get("latitude"), a.get("longitude")
        if type(lat) not in {float, int} or type(lon) not in {float, int}:
            continue
        matches = nearby_corridors(lat, lon, grid)
        if ident in parent_ids or (ident in site_ids if site_ids is not None else matches):
            selected.add(ident)
            corridor_matches[ident] = matches
    if not selected:
        raise ValueError("USFS discovery found no parent refreshes or corridor candidates")
    facilities, facility_receipts, public, public_receipts = {}, [], {}, []
    for batch, offset in enumerate(range(0, len(selected), 100)):
        ids = sorted(selected)[offset : offset + 100]
        evidence, data = query(
            usfs.FACILITY_URL,
            "site_cn IN (" + ",".join("'" + ident + "'" for ident in ids) + ")",
            f"sources/facilities-{batch}.json",
            count=1000,
        )
        if data.get("exceededTransferLimit"):
            raise ValueError("USFS selected native identity query truncated")
        values = {a["attributes"]["site_cn"]: a["attributes"] for a in data.get("features", [])}
        if set(values) != set(ids):
            raise ValueError("USFS selected identity set changed between discovery and acquisition")
        facilities.update(values)
        facility_receipts.append(evidence)
    portal_ids = sorted(
        {
            str(a["usda_portal_id"])
            for a in facilities.values()
            if a.get("usda_portal_id") and re.fullmatch(r"[0-9]+", str(a["usda_portal_id"]))
        }
    )
    for batch, offset in enumerate(range(0, len(portal_ids), 100)):
        ids = portal_ids[offset : offset + 100]
        evidence, data = query(
            usfs.PUBLIC_URL,
            "recareaid IN (" + ",".join(ids) + ")",
            f"sources/public-{batch}.json",
            count=1000,
        )
        if data.get("exceededTransferLimit"):
            raise ValueError("USFS public corroboration query truncated")
        for feature in data.get("features", []):
            item = feature["attributes"]
            if str(item["recareaid"]) in public:
                raise ValueError("USFS public corroboration repeats native identity")
            public[str(item["recareaid"])] = item
        public_receipts.append(evidence)
    states_receipt, state_data = query(usfs.STATE_URL, "1=1", "sources/states.json", geojson=True)
    shapes = usfs.state_shapes(state_data)
    driving, preliminary_holds = [], []
    parking_joins = usfs_parking_pdf.joins(facilities, parking_documents)
    for ident, a in sorted(facilities.items()):
        qualified, reason = qualify(
            a,
            public.get(str(a.get("usda_portal_id"))),
            shapes,
            reviewed_on,
            primary_publication=True,
            parking_corroboration=parking_joins.get(ident),
        )
        if reason:
            preliminary_holds.append({"site_cn": ident, "reason": reason})
            continue
        row, _ = qualified
        lat, lon = row["latitude"], row["longitude"]
        url = f"https://router.project-osrm.org/route/v1/driving/{lon},{lat + 0.01};{lon},{lat}?overview=false&steps=false&alternatives=false"
        try:
            receipt = fetch(url, f"driving/{ident.replace('.', '_')}.json", ceiling=1024 * 1024)
            data = json.loads((output / receipt["path"]).read_bytes())
            waypoint = (data.get("waypoints") or [{}])[-1]
            receipt.update(
                checked_waypoint="destination",
                source_coordinates=[lat, lon],
                snap_distance_m=waypoint.get("distance"),
                road_name=waypoint.get("name"),
            )
            driving.append({"site_cn": ident, "receipt": receipt})
        except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
            preliminary_holds.append(
                {"site_cn": ident, "reason": "driving_acquisition_" + type(exc).__name__}
            )
    licenses = {}
    for identifier, digest in LICENSE_PINS.items():
        source = (
            Path(__file__).resolve().parents[3]
            / "frontend"
            / "public"
            / "licenses"
            / (identifier + ".txt")
        )
        body = source.read_bytes()
        if hashlib.sha256(body).hexdigest() != digest:
            raise ValueError("repository factual or ODbL reuse notice changed")
        budget += len(body)
        if budget > MAX_BYTES:
            raise ValueError("USFS rights evidence exceeds aggregate acquisition ceiling")
        relative = "licenses/" + identifier + ".txt"
        (output / "licenses").mkdir(exist_ok=True)
        (output / relative).write_bytes(body)
        licenses[identifier] = {"path": relative, "sha256": digest, "url": LICENSE_URLS[identifier]}
    bundle = {
        "schema_version": SCHEMA,
        "publication_contract": publication,
        "parking_publications": parking_publications,
        "reviewed_on": reviewed_on.isoformat(),
        "selected_site_ids": sorted(selected),
        "facilities": facility_receipts,
        "public": public_receipts,
        "states": states_receipt,
        "driving": driving,
    }
    path = output / "bundle.json"
    path.write_text(json.dumps(bundle, indent=2, allow_nan=False) + "\n")
    manifest = {
        "schema_version": SCHEMA,
        "source_url": SOURCE_URL,
        "attribution": ATTRIBUTION,
        "release": "usfs-current-" + reviewed_on.isoformat(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "licenses": licenses,
    }
    Path(str(path) + ".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    report = {
        "source_path": str(path),
        "manifest_path": str(path) + ".manifest.json",
        "discovered_facilities": len(discovered),
        "selected_facilities": len(selected),
        "parent_refresh_candidates": len(selected & parent_ids),
        "selection_scope": "explicit_bounded_native_identity_shortlist"
        if site_ids is not None
        else "parent_and_continuous_five_mile_corridors",
        "continuous_five_mile_corridors": corridor_matches,
        "discovery_receipts": discovery,
        "preliminary_holds": preliminary_holds,
        "driving_receipts": len(driving),
        "acquired_bytes": budget,
        "database_write": False,
    }
    (output / "acquisition.json").write_text(json.dumps(report, indent=2) + "\n")
    # Replay uses only retained bodies, and catches mutated/truncated bytes before
    # this source can be passed to the outer incremental importer.
    rows, replay = prepare(path, manifest)
    (output / "admission-ledger.json").write_text(
        json.dumps(replay["admission_ledger"], indent=2) + "\n"
    )
    return {**report, "accepted": len(rows), "calendar_entries": len(replay["calendar_entries"])}
