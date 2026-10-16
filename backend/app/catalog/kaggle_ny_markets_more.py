"""Pinned alternative-address NY market admissions, preserving unknown native fields.

The current consumer-facing government roster and regional publication must agree.
Every genuine successful address form constrains the unchanged native point. Neither
an address-range interpolation nor a nearby driving road surveys an entrance.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlsplit

from app.catalog import kaggle_markets as markets
from app.catalog import kaggle_ny_markets as ny
from app.catalog import market_visit_calendar
from app.catalog.kaggle_ca_markets import EvidenceReader, _canonical_rows_sha
from app.routing.visit_calendar import Season

SCHEMA = "kaggle-usda-markets-ny-alternative-address-reviewed-arrivals/1"
SOURCE_URL = markets.SOURCE_URL
RELEASE = "kaggle-usda-markets-v4+ny-alternative-address-review-2026-10-15"
ATTRIBUTION = (
    "Harvestly Markets (CC BY 4.0), derived from USDA AMS Local Food Portal; "
    "New York State Department of Agriculture and Markets via OPEN-NY and "
    "current regional consumer market schedules; independent Census address-range "
    "interpolation; driving evidence: OSRM, © OpenStreetMap contributors (ODbL). "
    "Native points unchanged; no surveyed entrance or parking claim. No endorsement."
)
INDEX_SHA256 = "1895e7b8dd6091e3722961b117675929587b6e56a16ee6e633f29bed2af7acff"
PARENT_SHA256 = "003ddd7c72307f6844af11ff1df970bfb791f67dda57b143ca317c7f0c501a71"
PARENT_RAW_SHA256 = "7d8992babb4c9acd530a0f6b794f17f91994c5a1e90d344c8987560ea6ae2c1c"
REVIEW_START, REVIEW_END = date(2026, 10, 15), date(2026, 11, 13)
MAX_ROWS, MAX_BYTES = 50_000, 104_857_600
LICENSE_PINS = {
    **ny._LICENSE_PINS,
    "LicenseRef-US-Census-Geocoder": (
        "1ec78b37e4b4da2ce1cd2f8b67a946424c7a1a08c83faae4d43aad0ba56db364"
    ),
}
PDF_PINS = {
    "agency-counties-a-g-pdf": "c31fb0d978ff4ad4a0ab5f831f8aa5dd709d776d63ebd598143340b23af0b160",
    "agency-counties-h-r-pdf": "6c5c17b9cee1ed28bc27ff54df29a822df1643cfaaaf3c5b083794fb70619538",
    "agency-counties-s-y-pdf": "f4c5b31505fc12907f43e954f95a98f3ef90b571fe1e69cb688c588e37157c72",
    "agency-nyc-pdf": "3c04db2786a084fd16c27fd9a72fc50ec5f354d8923f278c20fe96a45ccba7a4",
}
_IDENTITY = ("listing_id", "name", "street", "city", "state", "zip", "lat", "lng")
_PHONE = re.compile(r"\(\d{3}\)\s*\d{3}-\d{4}(?:\s*x\d+)?")
_NUMBERED = re.compile(
    r"\b\d{1,6}\s+[A-Za-z0-9.'-]+(?:\s+[A-Za-z0-9.'-]+){0,5}?\s+"
    r"(?:Street|St|Road|Rd|Avenue|Ave|Parkway|Pkwy|Lane|Ln|Drive|Dr|Plaza|Boulevard|Blvd|Court|Ct)"
    r"\b(?:\s+(?:North|South|East|West|N|S|E|W)\b)?",
    re.I,
)


def address_tokens(value):
    """Literal street tokens, with explicit ordinary USPS abbreviation expansion."""
    return {
        "plaza" if x == "plz" else "court" if x == "ct" else x for x in markets.address_words(value)
    }


def regional_block(official, all_officials, columns):
    """Extract one complete published market block without emitting contact columns."""
    name = official["market_name"]
    pattern = re.escape(name).replace(r"\ ", r"\s+")
    matches = []
    for col in columns:
        text = col["literal_text"]
        for match in re.finditer(pattern, text):
            end = len(text)
            for other in {o["market_name"] for o in all_officials} - {name}:
                next_title = re.search(re.escape(other).replace(r"\ ", r"\s+"), text[match.end() :])
                if next_title:
                    end = min(end, match.end() + next_title.start())
            block = text[match.start() : end].split("• SNAP accepted")[0].split("Farm Stand")[0]
            lines = [x.strip() for x in block.splitlines() if x.strip() not in {"•", "+", "♦"}]
            block = _PHONE.sub("", "\n".join(lines)).strip()
            headers = re.findall(
                r"(?m)^(Farmers' Market|Farm Stand|Mobile Market)$", text[: match.start()]
            )
            matches.append(
                {
                    **{
                        k: col[k]
                        for k in (
                            "source_key",
                            "snapshot_sha256",
                            "pdf_page",
                            "column_index",
                            "bbox",
                        )
                    },
                    "literal_block_without_phone": block,
                    "published_market_type": headers[-1] if headers else None,
                }
            )
    if len(matches) != 1:
        return None, "regional_publication_identity_missing_or_ambiguous"
    block = matches[0]
    if block["published_market_type"] != "Farmers' Market":
        return None, "not_a_published_fixed_consumer_farmers_market"
    text = " ".join(block["literal_block_without_phone"].split())
    if re.search(
        r"\b(private|residents?[- ]only|members?[- ]only|appointment|restricted|tickets?)\b",
        text,
        re.I,
    ):
        return None, "public_party_access_unresolved"
    for key in ("operation_hours", "operation_season"):
        if not official.get(key) or " ".join(official[key].split()) not in text:
            return None, "regional_and_open_ny_calendar_conflict_or_incomplete_clock"
    remainder = text.replace(name, "", 1)
    for key in ("operation_hours", "operation_season"):
        remainder = remainder.replace(" ".join(official[key].split()), "", 1)
    if re.search(
        r"\b(closed|except|holiday|winter|summer|last|entry|call|am|pm|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b",
        remainder,
        re.I,
    ):
        return None, "additional_regional_schedule_or_access_restriction_unparsed"
    # The remaining text is a separately attributed literal visitor-location field.
    block["visitor_location"] = " ".join(remainder.split()).strip(" •+♦,")
    api = address_tokens(official.get("market_location", ""))
    pdf = address_tokens(block["visitor_location"])
    if not api or not pdf or api != pdf:
        return None, "regional_and_open_ny_visitor_location_conflict"
    return block, None


def address_queries(ident, official, block):
    """All genuine full forms and literal numbered substrings, never an invented native address."""
    forms = [
        ("official_api_postal", official["address_line_1"]),
        ("official_api_visitor", official["market_location"]),
        ("official_pdf_visitor", block["visitor_location"]),
    ]
    for role, value in list(forms):
        forms.extend(
            ("literal_numbered_fragment:" + role, hit[0]) for hit in _NUMBERED.finditer(value)
        )
    queries, seen = [], set()
    for role, value in forms:
        value = " ".join(value.split())
        if not value or (role, value) in seen:
            continue
        seen.add((role, value))
        queries.append(
            {
                "query_id": f"{ident}-{len(seen)}",
                "listing_id": ident,
                "address_role": role,
                "street": value,
                **{k: official[k] for k in ("city", "state", "zip")},
            }
        )
    return queries


def parse_census(request_raw, response_raw, document):
    """Validate exact unmodified request/result pairs, allowing several attributed forms per ID."""
    if (document.get("benchmark"), document.get("benchmark_name")) != (
        markets.CENSUS_BENCHMARK,
        markets.CENSUS_BENCHMARK_NAME,
    ):
        raise ValueError("NY Census benchmark differs")
    queries = document.get("queries", [])
    if not 1 <= len(queries) <= 150:
        raise ValueError("NY Census bounded query count differs")
    submitted = list(csv.reader(io.StringIO(request_raw.decode(), newline="")))
    if submitted != [
        [q[k] for k in ("query_id", "street", "city", "state", "zip")] for q in queries
    ]:
        raise ValueError("NY Census actual request bytes differ from query fields")
    by_id = {q["query_id"]: q for q in queries}
    if len(by_id) != len(queries):
        raise ValueError("NY Census duplicate submitted ID")
    results = {}
    for fields in csv.reader(io.StringIO(response_raw.decode(), newline="")):
        if len(fields) not in {3, 8} or fields[0] not in by_id or fields[0] in results:
            raise ValueError("NY Census response identity/schema differs")
        query = by_id[fields[0]]
        if fields[1] != ", ".join(query[k] for k in ("street", "city", "state", "zip")):
            raise ValueError("NY Census response does not preserve submitted address")
        result = {"query": query, "status": fields[2]}
        if fields[2] == "Match":
            if len(fields) != 8:
                raise ValueError("NY Census successful result is incomplete")
            parts = [p.strip() for p in fields[4].split(",")]
            if fields[3] not in {"Exact", "Non_Exact"} or len(parts) != 4:
                raise ValueError("NY Census successful result is incomplete")
            longitude, latitude = map(float, fields[5].split(","))
            ny._point(latitude, longitude)
            result.update(
                match_type=fields[3],
                matched_address=fields[4],
                matched_street=parts[0],
                matched_city=parts[1],
                matched_state=parts[2],
                matched_zip=parts[3],
                coordinates=[latitude, longitude],
                tiger_line_id=fields[6] or None,
                tiger_line_side=fields[7] or None,
            )
        elif fields[2] not in {"No_Match", "Tie"} or len(fields) != 3:
            raise ValueError("NY Census unknown response status")
        results[fields[0]] = result
    if set(results) != set(by_id):
        raise ValueError("NY Census omitted submitted identities")
    return results


def coordinate_facts(native, official, block, census):
    expected_zip = official.get("zip")
    if not isinstance(expected_zip, str) or not re.fullmatch(r"\d{5}", expected_zip):
        return None, "official_zip_unknown_or_malformed"
    if native["zip"] and native["zip"] != expected_zip:
        return None, "native_official_zip_conflict"
    expected_queries = address_queries(native["listing_id"], official, block)
    entries = [v for v in census.values() if v["query"]["listing_id"] == native["listing_id"]]
    if sorted((v["query"] for v in entries), key=lambda q: q["query_id"]) != sorted(
        expected_queries, key=lambda q: q["query_id"]
    ):
        return None, "not_every_genuine_published_address_form_was_queried"
    facts, positive = [], False
    for entry in entries:
        query = entry["query"]
        fact = {
            "query_id": query["query_id"],
            "address_role": query["address_role"],
            "submitted_address": {k: query[k] for k in ("street", "city", "state", "zip")},
            "status": entry["status"],
        }
        if entry["status"] == "Match":
            if (
                tuple(markets.words(entry["matched_city"])),
                entry["matched_state"],
                entry["matched_zip"],
            ) != (tuple(markets.words(native["city"])), native["state"], expected_zip):
                return None, "one_successful_census_city_state_or_zip_conflicts"
            if not address_tokens(entry["matched_street"]) <= address_tokens(query["street"]):
                return None, "one_successful_census_street_is_not_literal"
            distance = markets.point_distance(
                [float(native["lat"]), float(native["lng"])], entry["coordinates"]
            )
            if distance > 100:
                return None, "one_genuine_successful_address_form_exceeds_100m"
            fact.update({k: v for k, v in entry.items() if k not in {"query", "status"}})
            fact["native_point_distance_m"] = distance
            positive = True
        elif entry["status"] not in {"No_Match", "Tie"}:
            return None, "unrecognized_independent_address_status"
        facts.append(fact)
    return (facts, None) if positive else (None, "no_positive_literal_independent_address_point")


def qualification(native, canonical, roster, officials, columns, receipts, census):
    """The same conservative identity, public-listing, address and calendar gates for every row."""
    if not isinstance(native, dict) or any(not isinstance(native.get(k), str) for k in _IDENTITY):
        return None, "native_identity_schema_incomplete"
    if native["state"] != "NY":
        return None, "outside_new_york"
    if (
        not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", native["listing_id"])
        or not markets.core(native["name"])
        or not markets.words(native["city"])
    ):
        return None, "native_identity_incomplete"
    if native["street"].strip():
        return None, "outside_reviewed_unknown_native_street_profile"
    if canonical is None:
        return None, "missing_canonical_membership"
    if any(native[k] != canonical.get(k) for k in _IDENTITY):
        return None, "native_canonical_identity_point_or_zip_conflict"
    matches = roster.get(ny.name_city(native), [])
    if len(matches) != 1:
        return None, "no_unique_exact_all_source_name_city_membership"
    ordinal, official = matches[0]
    try:
        point = ny._point(native["lat"], native["lng"])
        agency = ny._point(official["latitude"], official["longitude"])
        if official["georeference_1"] != {"type": "Point", "coordinates": [agency[1], agency[0]]}:
            raise ValueError
    except (ValueError, KeyError, TypeError):
        return None, "native_or_independent_agency_point_invalid_or_conflicting"
    agency_distance = markets.point_distance(point, agency)
    if agency_distance > 100:
        return None, "native_agency_point_exceeds_100m"
    groups = [
        ny._fact(
            feed,
            native["listing_id"],
            receipts[key],
            {
                "season": record.get("season") or None,
                "source_updated_at_raw": record.get("updated") or None,
                "location": None,
                "city": record["city"],
            },
        )
        for feed, record, key in [
            ("kaggle_feed", native, "archive"),
            ("canonical_feed", canonical, "canonical"),
        ]
    ]
    groups.append(
        ny._fact(
            "official_visitor_facts",
            str(ordinal),
            receipts["ny"],
            {
                "season": official.get("operation_season"),
                "hours": official.get("operation_hours"),
                "location": official.get("market_location"),
                "postal_address": official.get("address_line_1"),
                "city": official["city"],
                "zip": official.get("zip"),
            },
        )
    )
    calendar = market_visit_calendar.build(groups)
    if calendar["unknown_reasons"]:
        return None, "unresolved_all_source_calendar:" + ";".join(calendar["unknown_reasons"])
    if not any(Season.model_validate(s).includes(REVIEW_START) for s in calendar["seasons"]):
        return None, "outside_all_source_season_intersection"
    if not any(
        (int(w["closes"][:2]) * 60 + int(w["closes"][3:]) + w["end_day_offset"] * 1440)
        - (int(w["opens"][:2]) * 60 + int(w["opens"][3:]))
        >= 120
        for w in calendar["weekly_windows"]
    ):
        return None, "no_complete_two_hour_source_visit_window"
    block, reason = regional_block(official, officials, columns)
    if reason:
        return None, reason
    pdf_fact = ny._fact(
        "official_visitor_facts",
        str(ordinal),
        receipts[block["source_key"]],
        {
            "season": official["operation_season"],
            "hours": official["operation_hours"],
            "location": block["visitor_location"],
            "published_market_type": block["published_market_type"],
            "literal_source_block": block["literal_block_without_phone"],
        },
    )
    pdf_fact.update({k: block[k] for k in ("pdf_page", "column_index", "bbox")})
    groups.append(pdf_fact)
    calendar = market_visit_calendar.build(groups)
    if calendar["unknown_reasons"]:
        return None, "regional_calendar_intersection_unresolved"
    geocodes, reason = coordinate_facts(native, official, block, census)
    if reason:
        return None, reason
    return {
        "row": {
            "source_id": "usda-market:" + native["listing_id"],
            "name": native["name"].strip(),
            "latitude": point[0],
            "longitude": point[1],
            "region": "NY",
            "address": None,
            "categories": ["farmers_market", "food_destination", "daytime", "public_destination"],
            "source_updated_at": None,
        },
        "official": official,
        "official_row_index": ordinal,
        "regional": block,
        "agency_distance_m": agency_distance,
        "facts": groups,
        "calendar": calendar,
        "geocodes": geocodes,
    }, None


def original_pdf_columns(bodies):
    """Optional source replay parses all authentic PDF bytes; runtime import stays dependency-free."""
    import pdfplumber

    columns = []
    for key in sorted(PDF_PINS):
        if hashlib.sha256(bodies[key]).hexdigest() != PDF_PINS[key]:
            raise ValueError("NY regional original PDF checksum differs")
        with pdfplumber.open(io.BytesIO(bodies[key])) as pdf:
            for ordinal, page in enumerate(pdf.pages, 1):
                bboxes = [
                    (17.978857142857144, 90.11883714285705, 306.08, page.height - 28),
                    (306.08, 90.11883714285705, 600.0, page.height - 28),
                ]
                if key == "agency-nyc-pdf":
                    x = [
                        17.978857142857144,
                        263.45784615384616,
                        508.8723076923077,
                        754.255,
                        999.7400000000001,
                    ]
                    bboxes = [
                        (x[i], 90.11883714285705, x[i + 1], page.height - 28) for i in range(4)
                    ]
                for ci, bbox in enumerate(bboxes):
                    columns.append(
                        {
                            "source_key": key,
                            "snapshot_sha256": PDF_PINS[key],
                            "pdf_page": ordinal,
                            "column_index": ci,
                            "bbox": list(bbox),
                            "literal_text": page.crop(bbox).extract_text(layout=False) or "",
                        }
                    )
    return columns


def verify_original_pdfs(path):
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= min(32768, MAX_BYTES):
        raise ValueError("NY PDF source configuration missing or oversized")
    control_raw = path.read_bytes()
    bundle = json.loads(control_raw)
    reader = EvidenceReader(path.parent, MAX_BYTES - len(control_raw))
    raw = reader.read(bundle["index"])
    if hashlib.sha256(raw).hexdigest() != INDEX_SHA256:
        raise ValueError("NY PDF source inventory differs")
    inputs = json.loads(raw)["source_inputs"]
    actual = original_pdf_columns({k: reader.read(inputs[k]) for k in PDF_PINS})
    expected = json.loads(reader.read(inputs["regional_columns"]))
    if actual != expected:
        raise ValueError("NY original PDF extraction disagrees with retained columns")
    return {
        "pages": len({(c["source_key"], c["pdf_page"]) for c in actual}),
        "columns": len(actual),
        "original_pdf_sha256": PDF_PINS,
        "literal_column_json_sha256": inputs["regional_columns"]["sha256"],
    }


def _sources(reader, index):
    inputs = index["source_inputs"]
    bodies = {k: reader.read(v) for k, v in inputs.items()}
    for key, expected in {
        "archive": markets.ARCHIVE_SHA256,
        "canonical": markets.CANONICAL_SHA256,
        "ny": ny.NY_SHA256,
        "ny_terms": ny.TERMS_SHA256,
        "parent576": PARENT_RAW_SHA256,
        **PDF_PINS,
    }.items():
        if hashlib.sha256(bodies[key]).hexdigest() != expected:
            raise ValueError("NY authentic source/reuse/parent pin differs")
    with zipfile.ZipFile(io.BytesIO(bodies["archive"])) as archive:
        if not 0 < archive.getinfo(markets.MEMBER).file_size <= 5 * 1024 * 1024:
            raise ValueError("NY native archive member byte ceiling exceeded")
        raw = archive.read(markets.MEMBER)
    if hashlib.sha256(raw).hexdigest() != markets.CSV_SHA256:
        raise ValueError("NY native member checksum differs")
    metadata = json.loads(bodies["kaggle_metadata"])
    if metadata.get("currentVersionNumber") != 4 or "CC BY 4.0" not in metadata.get(
        "description", ""
    ):
        raise ValueError("NY exact version or license evidence differs")
    native = markets.csv_rows(raw, markets.CSV_ROWS)
    canonical = markets.csv_rows(bodies["canonical"], markets.CANONICAL_ROWS)
    official, parent, columns = (
        json.loads(bodies[k]) for k in ("ny", "parent576", "regional_columns")
    )
    if (
        len(official) != 675
        or len(parent) != 576
        or len({r["source_id"] for r in parent}) != 576
        or _canonical_rows_sha(parent) != PARENT_SHA256
    ):
        raise ValueError("NY complete government roster or verified576 parent differs")
    if len(columns) != 132 or any(
        c["source_key"] not in PDF_PINS or c["snapshot_sha256"] != PDF_PINS[c["source_key"]]
        for c in columns
    ):
        raise ValueError("NY extracted regional columns are incomplete or unbound")
    receipt = inputs["census_response"]
    if (receipt["url"], receipt["method"], receipt["benchmark"], receipt["benchmark_name"]) != (
        markets.CENSUS_URL,
        "POST",
        markets.CENSUS_BENCHMARK,
        markets.CENSUS_BENCHMARK_NAME,
    ) or hashlib.sha256(bodies["census_request"]).hexdigest() != receipt["request_sha256"]:
        raise ValueError("NY Census receipt does not bind the actual request/benchmark")
    census = parse_census(
        bodies["census_request"], bodies["census_response"], json.loads(bodies["census_queries"])
    )
    if not any(
        row["id"] == markets.CENSUS_BENCHMARK
        and row["benchmarkName"] == markets.CENSUS_BENCHMARK_NAME
        for row in json.loads(bodies["census_benchmarks"])["benchmarks"]
    ):
        raise ValueError("NY Census benchmark is absent from retained official metadata")
    return native, canonical, official, parent, columns, census


def prepare(path, manifest=None, *, max_rows=MAX_ROWS, max_bytes=MAX_BYTES):
    """Replay original typed sources, return normalized rows and separate dated calendars."""
    if (
        type(max_rows) is not int
        or not 1 <= max_rows <= MAX_ROWS
        or type(max_bytes) is not int
        or not 1 <= max_bytes <= MAX_BYTES
    ):
        raise ValueError("NY may not raise unchanged hard resource ceilings")
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= min(32768, max_bytes):
        raise ValueError("NY typed configuration missing or oversized")
    raw = path.read_bytes()
    if manifest is None:
        sidecar = Path(str(path) + ".manifest.json")
        if not sidecar.is_file() or not 0 < sidecar.stat().st_size <= 32768:
            raise ValueError("NY source sidecar missing or oversized")
        manifest_raw = sidecar.read_bytes()
        manifest = json.loads(manifest_raw)
    else:
        manifest_raw = json.dumps(manifest, sort_keys=True, allow_nan=False).encode()
    if len(manifest_raw) > 32768 or len(raw) + len(manifest_raw) > max_bytes:
        raise ValueError("NY source headers exceed byte ceiling")
    if (
        manifest.get("schema_version"),
        manifest.get("source_url"),
        manifest.get("release"),
        manifest.get("attribution"),
        manifest.get("sha256"),
    ) != (SCHEMA, SOURCE_URL, RELEASE, ATTRIBUTION, hashlib.sha256(raw).hexdigest()):
        raise ValueError("NY source manifest/release/checksum differs")
    if set(manifest.get("licenses", {})) != set(LICENSE_PINS) or any(
        manifest["licenses"][k].get("sha256") != v for k, v in LICENSE_PINS.items()
    ):
        raise ValueError("NY requires exact source reuse notices")
    reader = EvidenceReader(path.parent, max_bytes - len(raw) - len(manifest_raw))
    config = json.loads(raw)
    if config.get("schema_version") != SCHEMA:
        raise ValueError("NY alternative-address schema differs")
    index_raw = reader.read(config["index"], ceiling=1024 * 1024)
    if hashlib.sha256(index_raw).hexdigest() != INDEX_SHA256:
        raise ValueError("NY exact source inventory differs")
    index = json.loads(index_raw)
    if (
        index.get("schema_version") != "roadtrips-ny-alternative-address-source-inputs/1"
        or index.get("parent_canonical_rows_sha256") != PARENT_SHA256
        or not 0 <= (datetime.now(UTC).date() - REVIEW_START).days <= 30
    ):
        raise ValueError("NY source parent binding or admission freshness differs")
    for key, digest in LICENSE_PINS.items():
        if index["licenses"][key]["sha256"] != digest:
            raise ValueError("NY source notice pin differs")
        reader.read(index["licenses"][key], freshness=False, ceiling=1024 * 1024)
    native, canonical, officials, parent, columns, census = _sources(reader, index)
    inputs = index["source_inputs"]
    source_rows = {
        "native_kaggle": len(native),
        "canonical": len(canonical),
        "official_open_ny": len(officials),
        "regional_pdf_text_columns": len(columns),
        "regional_pdf_literal_lines": sum(len(c["literal_text"].splitlines()) for c in columns),
        "dedup_parent": len(parent),
        "address_queries": len(census),
        "address_results": len(census),
        "driving_destinations": sum(k.startswith("driving-") for k in inputs),
    }
    scanned = sum(source_rows.values())
    if scanned > max_rows:
        raise ValueError("NY aggregate scanned source row ceiling exceeded")
    roster, parent_ids = ny.roster_index(officials), {r["source_id"] for r in parent}
    qualified, ledger = [], []
    for ident, n in native.items():
        value, reason = qualification(
            n, canonical.get(ident), roster, officials, columns, inputs, census
        )
        if not reason and value["row"]["source_id"] in parent_ids:
            reason = "already_in_verified576_parent"
        if not reason:
            evidence = inputs.get("driving-" + ident)
            if evidence is None:
                reason = "actual_driving_destination_receipt_missing"
            else:
                try:
                    _, distance = markets.driving(path.parent, evidence, value["row"])
                    value.update(driving=evidence, driving_distance_m=distance)
                except (ValueError, KeyError, TypeError):
                    reason = "actual_driving_destination_proof_failed"
        if reason:
            ledger.append({"source_id": "usda-market:" + ident, "reason": reason})
        else:
            qualified.append(value)
    collisions = ny.collision_holds([v["row"] for v in qualified], parent)
    rows, entries = [], []
    for item in qualified:
        row, ident = item["row"], item["row"]["source_id"].removeprefix("usda-market:")
        if row["source_id"] in collisions:
            ledger.append(
                {
                    "source_id": row["source_id"],
                    "reason": "source_or_parent_arrival_conflict_within250m",
                    "nearby_ids": collisions[row["source_id"]],
                }
            )
            continue
        visit = ny.bounded_calendar(item["calendar"], REVIEW_START, REVIEW_END)
        if not any(d["windows"] for d in visit["date_overrides"]):
            ledger.append(
                {
                    "source_id": row["source_id"],
                    "reason": "no_positive_dated_visit_window_in_review_horizon",
                }
            )
            continue
        for receipt in visit["source_receipts"]:
            original = next(v for v in inputs.values() if v["sha256"] == receipt["snapshot_sha256"])
            receipt["body_path"] = str((path.parent / original["path"]).resolve())
        url = item["official"].get("market_link", {}).get("url", "")
        parsed = urlsplit(url)
        row["url"] = (
            url
            if parsed.scheme in {"http", "https"}
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            else ny.NY_URL
        )
        row["provenance"] = [
            {
                "dataset": "kaggle-usda-markets",
                "record_id": ident,
                "source_url": SOURCE_URL,
                "license": "CC-BY-4.0",
                "snapshot_sha256": markets.ARCHIVE_SHA256,
                "checked_at": inputs["archive"]["retrieved_at"],
                "native_source_point": {
                    "latitude_raw": native[ident]["lat"],
                    "longitude_raw": native[ident]["lng"],
                    "csv_sha256": markets.CSV_SHA256,
                    "archive_member": markets.MEMBER,
                },
                "native_coordinates_replaced": False,
                "native_street": None,
                "canonical_street": None,
                "native_zip": native[ident]["zip"] or None,
                "canonical_zip": canonical[ident]["zip"] or None,
                "published_access_facts": item["facts"],
                "official_row_index": item["official_row_index"],
                "public_destination_basis": "Current consumer-facing agency publication explicitly classifies this exact name as Farmers' Market, with a fixed visitor location and dated weekly schedule; no private/mobile/party restriction inferred away",
                "agency_coordinate_corroboration": {
                    "source_url": ny.NY_URL,
                    "license": "LicenseRef-NY-Open-Data",
                    "checked_at": inputs["ny"]["retrieved_at"],
                    "latitude_raw": item["official"]["latitude"],
                    "longitude_raw": item["official"]["longitude"],
                    "native_point_distance_m": item["agency_distance_m"],
                    "snapshot_sha256": ny.NY_SHA256,
                },
                "independent_census_address_forms": item["geocodes"],
                "census_source_url": markets.CENSUS_URL,
                "census_license": "LicenseRef-US-Census-Geocoder",
                "census_checked_at": inputs["census_response"]["retrieved_at"],
                "census_request_sha256": inputs["census_response"]["request_sha256"],
                "census_point_role": "Independent address-range interpolation, not surveyed entrance or parking",
                "census_snapshot_sha256": inputs["census_response"]["sha256"],
                "census_benchmark": markets.CENSUS_BENCHMARK_NAME,
                "driving_source_url": item["driving"]["url"],
                "driving_license": "ODbL-1.0",
                "driving_evidence_sha256": item["driving"]["sha256"],
                "driving_checked_at": item["driving"]["retrieved_at"],
                "driving_destination_distance_m": item["driving_distance_m"],
                "parking": None,
                "price": None,
                "source_updated_at_normalized": "unknown; raw source historical strings retained separately",
                "limitations": "Native address/ZIP unknown fields remain unknown. Independent government points and address-range interpolation corroborate native points; road proximity is not surveyed entrance, parking or market-day vehicle access. Weather, actual staffing/capacity and future operation unknown.",
            }
        ]
        rows.append(row)
        entries.append(
            {
                "source_id": row["source_id"],
                "source_visit_calendar": visit,
                "source_constraints": item["facts"],
                "transformation": {
                    "adapter": SCHEMA,
                    "inventory_sha256": INDEX_SHA256,
                    "native_address_remains_unknown": True,
                    "native_coordinates_replaced": False,
                    "all_source_seasons_weekdays_and_clocks_intersected": True,
                    "review_horizon": {
                        "start": REVIEW_START.isoformat(),
                        "end": REVIEW_END.isoformat(),
                        "basis": "Conservative source review interval, not an invented annual recurrence",
                    },
                },
            }
        )
    actual = sorted(row["source_id"] for row in rows)
    if actual != index["selection"] or actual != config["selection"]:
        raise ValueError("NY deterministic originals replay differs from exact reviewed selection")
    return rows, {
        "scanned": scanned,
        "source_rows": source_rows,
        "accepted": len(rows),
        "bytes": reader.bytes + len(raw) + len(manifest_raw),
        "unique_raw_source_body_bytes": sum(
            {v["sha256"]: v["bytes"] for v in inputs.values()}.values()
        ),
        "unique_evidence_body_count": len(reader.cache),
        "duplicates": 0,
        "rejects": dict(Counter(r["reason"] for r in ledger)),
        "rejection_ledger": ledger,
        "regions": {"NY": len(rows)},
        "categories": {"food_destination": len(rows), "daytime": len(rows)},
        "calendar_entries": entries,
        "source_inventory_sha256": INDEX_SHA256,
        "parent_canonical_rows_sha256": PARENT_SHA256,
        "native_street_unknown_count": len(rows),
        "native_zip_unknown_count": sum(
            not native[r["source_id"].removeprefix("usda-market:")]["zip"] for r in rows
        ),
        "independent_original_pdf_replay_required": True,
    }
