"""Pinned California markets with genuinely missing native street fields.

A blank address never supplies an exact street match. Current government visitor
facts plus every genuine Census result independently corroborate native points;
no agency/geocoder value overwrites a native field. Ordinary replay is offline
and uses the immutable PDF extraction. Full PDF parsing is a separate source gate.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import re
import zipfile
from collections import Counter, defaultdict
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlsplit

from app.catalog import kaggle_markets as markets
from app.catalog import market_visit_calendar, roadside
from app.catalog.kaggle_ny_markets import bounded_calendar, collision_holds
from app.routing.visit_calendar import Season

SCHEMA = "kaggle-usda-markets-ca-alternative-address-reviewed-arrivals/1"
SOURCE_URL = markets.SOURCE_URL
RELEASE = "kaggle-usda-markets-v4+ca-alternative-address-review-2026-10-15"
ATTRIBUTION = (
    "Harvestly Markets (CC BY 4.0), derived from USDA AMS Local Food Portal; "
    "California Department of Food and Agriculture current visitor facts; "
    "U.S. Census Bureau Public_AR_ACS2026 address-range corroboration; "
    "driving evidence: OSRM, © OpenStreetMap contributors (ODbL). No endorsement."
)
INDEX_SHA256 = "0d585fc58f5672795a30dd501ee271f7b5a5a8ae540cc240fe972e0bc65bedcd"
PRIOR_PROPOSAL_SHA256 = "3cb18279d8010286edff9e18c93d862e8e3c165acbc561f5596bbea5a69f8f69"
PARENT_SHA256 = "003ddd7c72307f6844af11ff1df970bfb791f67dda57b143ca317c7f0c501a71"
PARENT_RAW_SHA256 = "7d8992babb4c9acd530a0f6b794f17f91994c5a1e90d344c8987560ea6ae2c1c"
PDF_SHA256 = "846d121f3e38ec1ee5f83c95c2260a6ae3857b11b3ad88d31ba9dc548fb06742"
TABLE_SHA256 = "59475ba6d047af8944d99a1c1aa8dcd8297ccfdc5e49dff27f1ff972edff8163"
LICENSE_PINS = {
    "CC-BY-4.0": "d557539df68e771cc1eedcc91d13f70fca930e508d11eedcafa4b15db49e3744",
    "LicenseRef-US-Census-Geocoder": "1ec78b37e4b4da2ce1cd2f8b67a946424c7a1a08c83faae4d43aad0ba56db364",
    "ODbL-1.0": "77d2692c3d64efdd4db18dce2407699baf62930e2b50d6e5ed90b48acf16b7c1",
}
REVIEW_START, REVIEW_END = date(2026, 10, 15), date(2026, 11, 13)
MAX_ROWS, MAX_BYTES = 50_000, 100 * 1024 * 1024
_OFFICIAL_FIELDS = (
    "county",
    "name",
    "location",
    "days",
    "hours",
    "months",
    "pdf_page",
    "table_index",
    "row_index",
)
_IDENTITY_FIELDS = ("listing_id", "name", "street", "city", "state", "zip", "lat", "lng")


def _portable(value):
    return (
        isinstance(value, str)
        and bool(value)
        and not PurePosixPath(value).is_absolute()
        and not PureWindowsPath(value).drive
        and not re.search(r'[<>:"|?*\\\x00-\x1f]', value)
        and all(
            part not in {"", ".", ".."}
            and not part.endswith((".", " "))
            and not re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part, re.I)
            for part in value.split("/")
        )
    )


class EvidenceReader:
    """Count every unique retained body, rejecting before an oversized read."""

    def __init__(self, root, max_bytes):
        self.root = Path(root).resolve()
        self.max_bytes, self.bytes, self.cache = max_bytes, 0, {}

    def read(self, evidence, *, ceiling=15 * 1024 * 1024, freshness=True):
        if not isinstance(evidence, dict) or not _portable(evidence.get("path")):
            raise ValueError("CA evidence requires a portable relative path")
        path = (self.root / evidence["path"]).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ValueError("CA evidence escapes or is missing")
        size = path.stat().st_size
        if not 0 < size <= ceiling:
            raise ValueError("CA evidence body exceeds byte ceiling")
        if path not in self.cache:
            if self.bytes + size > self.max_bytes:
                raise ValueError("CA aggregate evidence byte ceiling exceeded")
            raw = path.read_bytes()
            self.bytes += len(raw)
            self.cache[path] = raw
        raw = self.cache[path]
        if self.bytes > self.max_bytes or hashlib.sha256(raw).hexdigest() != evidence.get("sha256"):
            raise ValueError("CA evidence checksum or aggregate byte ceiling failed")
        if evidence.get("bytes", len(raw)) != len(raw):
            raise ValueError("CA evidence length differs from authentic receipt")
        if freshness:
            local = evidence.get("kind") == "retained-local-artifact"
            roadside.checked_time(evidence["checked_at"] if local else evidence["retrieved_at"])
            if not local and evidence.get("status") != 200:
                raise ValueError("CA remote evidence acquisition did not succeed")
        return raw


def official_city(location):
    """Use the actual terminal city component, never a street-name coincidence."""
    text = re.sub(r"\s*\b\d{5}(?:-\d{4})?\s*$", "", markets.plain(location)).strip(" ,")
    text = re.sub(r",?\s+\b(?:CA|California)$", "", text, flags=re.I).strip(" ,")
    return tuple(markets.words(text.rsplit(",", 1)[-1]))


def roster_index(rows):
    index = defaultdict(list)
    for row in rows:
        index[markets.core(row["name"])].append(row)
    return index


def _fact(feed, record, receipt, fields, **locator):
    return {
        "feed": feed,
        "record_id": record,
        "source_url": receipt["url"],
        "snapshot_sha256": receipt["sha256"],
        "checked_at": receipt["retrieved_at"],
        "fields": fields,
        **locator,
    }


def coordinate_facts(native, officials, results):
    """All successful native/official forms participate; one good point cannot excuse another."""
    zips = [
        match[1]
        for row in officials
        if (match := re.search(r"\b(\d{5})(?:-\d{4})?\s*$", markets.plain(row["location"])))
    ]
    if len(zips) != len(officials) or len(set(zips)) != 1:
        return None, "official_postal_zip_unknown_or_conflicting"
    raw_zip = native["zip"]
    if raw_zip and not re.fullmatch(r"\d{5}(?:-\d{4})?", raw_zip):
        return None, "native_postal_zip_malformed"
    expected_zip = raw_zip[:5] if raw_zip else zips[0]
    if expected_zip != zips[0]:
        return None, "native_official_zip_conflict"
    entries = [value for value in results if value["query"]["listing_id"] == native["listing_id"]]
    if not entries:
        return None, "independent_address_evidence_missing"
    facts, positive = [], False
    for entry in entries:
        query = entry["query"]
        if (query["city"], query["state"]) != (native["city"], native["state"]):
            return None, "submitted_city_or_state_changed"
        if query["address_role"] == "native_kaggle":
            if not native["street"].strip() or any(
                query[key] != native[key] for key in ("street", "city", "state", "zip")
            ):
                return None, "unknown_native_address_cannot_be_queried_as_known"
        elif query["address_role"] == "official_roster":
            if (
                not query["street"].strip()
                or query["zip"] != zips[0]
                or not any(
                    markets.address_words(query["street"]) <= markets.address_words(row["location"])
                    for row in officials
                )
            ):
                return None, "official_query_is_not_a_literal_published_address"
        else:
            return None, "unrecognized_address_role"
        fact = {
            "submitted_address": {key: query[key] for key in ("street", "city", "state", "zip")},
            "address_role": query["address_role"],
            "query_id": query["query_id"],
            "status": entry["status"],
        }
        if entry["status"] == "Match":
            if (
                markets.plain(entry["matched_city"]).casefold(),
                entry["matched_state"],
                entry["matched_zip"],
            ) != (markets.plain(native["city"]).casefold(), native["state"], expected_zip):
                return None, "census_matched_city_state_or_zip_conflict"
            distance = markets.point_distance(
                [float(native["lat"]), float(native["lng"])], entry["coordinates"]
            )
            if distance > 100:
                return None, "one_genuine_address_form_exceeds_100m"
            if not markets.address_words(entry["matched_street"]) <= markets.address_words(
                query["street"]
            ):
                return None, "one_matched_street_is_not_literal"
            fact.update(
                {
                    key: entry[key]
                    for key in (
                        "match_type",
                        "matched_address",
                        "coordinates",
                        "tiger_line_id",
                        "tiger_line_side",
                    )
                }
            )
            fact["native_point_distance_m"] = distance
            positive = True
        elif entry["status"] not in {"No_Match", "Tie"}:
            return None, "unrecognized_geocode_status"
        facts.append(fact)
    return (facts, None) if positive else (None, "no_literal_independent_point_within_100m")


def qualification(native, canonical, roster, receipts, census, *, as_of=REVIEW_START):
    """Exact source identity and independent official-address proof, with missing native fields."""
    if not isinstance(native, dict) or any(
        not isinstance(native.get(k), str) for k in _IDENTITY_FIELDS
    ):
        return None, "native_identity_schema_incomplete"
    if (
        not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", native["listing_id"])
        or not markets.core(native["name"])
        or not markets.words(native["city"])
    ):
        return None, "native_identity_incomplete"
    if native["state"] != "CA":
        return None, "outside_california"
    if native["street"].strip():
        return None, "outside_reviewed_missing_native_street_profile"
    if not isinstance(canonical, dict):
        return None, "missing_canonical_membership"
    if any(native[k] != canonical.get(k) for k in _IDENTITY_FIELDS):
        return None, "native_canonical_identity_location_or_zip_conflict"
    if native["listing_id"] in markets.REVIEW_HOLDS:
        return None, "unresolved_previous_independent_review_hold"
    try:
        latitude, longitude = float(native["lat"]), float(native["lng"])
        if not (
            math.isfinite(latitude)
            and math.isfinite(longitude)
            and -90 <= latitude <= 90
            and -180 <= longitude <= 180
        ):
            raise ValueError
    except (ValueError, TypeError):
        return None, "native_coordinates_invalid"
    officials = [
        row
        for row in roster.get(markets.core(native["name"]), [])
        if official_city(row["location"]) == tuple(markets.words(native["city"]))
    ]
    if not officials:
        return None, "no_exact_official_market_name_and_actual_city"
    if len({markets.plain(row["location"]) for row in officials}) != 1:
        return None, "ambiguous_multiple_official_visitor_locations"
    facts = [
        _fact(
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
        for feed, record, key in (
            ("kaggle_feed", native, "archive"),
            ("canonical_feed", canonical, "canonical"),
        )
    ]
    for official in officials:
        facts.append(
            _fact(
                "official_visitor_facts",
                native["listing_id"],
                receipts["cdfa"],
                {key: official[key] for key in ("name", "location", "days", "hours", "months")},
                **{key: official[key] for key in ("pdf_page", "table_index", "row_index")},
            )
        )
    calendar = market_visit_calendar.build(facts)
    if calendar["unknown_reasons"]:
        return None, "unresolved_all_source_calendar:" + ";".join(calendar["unknown_reasons"])
    if not any(Season.model_validate(value).includes(as_of) for value in calendar["seasons"]):
        return None, "outside_all_source_season_intersection"
    geocodes, reason = coordinate_facts(native, officials, census)
    if reason:
        return None, reason
    return {
        "row": {
            "source_id": "usda-market:" + native["listing_id"],
            "name": native["name"].strip(),
            "latitude": latitude,
            "longitude": longitude,
            "region": "CA",
            "address": None,
            "categories": ["farmers_market", "food_destination", "daytime", "public_destination"],
            "source_updated_at": None,
        },
        "official_rows": [{key: value[key] for key in _OFFICIAL_FIELDS} for value in officials],
        "facts": facts,
        "calendar": calendar,
        "geocodes": geocodes,
    }, None


def _canonical_rows_sha(rows):
    return hashlib.sha256(
        "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows).encode()
    ).hexdigest()


def _sources(reader, index):
    inputs = index["source_inputs"]
    bodies = {key: reader.read(value) for key, value in inputs.items()}
    for key, expected in {
        "archive": markets.ARCHIVE_SHA256,
        "canonical": markets.CANONICAL_SHA256,
        "cdfa": PDF_SHA256,
        "cdfa_rows": TABLE_SHA256,
        "parent576": PARENT_RAW_SHA256,
    }.items():
        if hashlib.sha256(bodies[key]).hexdigest() != expected:
            raise ValueError("CA source original differs from exact review pin")
    with zipfile.ZipFile(io.BytesIO(bodies["archive"])) as archive:
        member = archive.getinfo(markets.MEMBER)
        if not 0 < member.file_size <= 5 * 1024 * 1024:
            raise ValueError("CA native source archive member byte ceiling")
        native_raw = archive.read(member)
    if hashlib.sha256(native_raw).hexdigest() != markets.CSV_SHA256:
        raise ValueError("CA native source member checksum differs")
    metadata = json.loads(bodies["kaggle_metadata"])
    if metadata.get("currentVersionNumber") != 4 or "CC BY 4.0" not in metadata.get(
        "description", ""
    ):
        raise ValueError("CA original Kaggle version/license evidence differs")
    native = markets.csv_rows(native_raw, markets.CSV_ROWS)
    canonical = markets.csv_rows(bodies["canonical"], markets.CANONICAL_ROWS)
    table = json.loads(bodies["cdfa_rows"])
    if (
        table.get("sha256") != PDF_SHA256
        or table.get("anomalies")
        or len(table.get("rows", [])) != 768
    ):
        raise ValueError("CA PDF extraction is not bound to original")
    parent = json.loads(bodies["parent576"])
    if (
        not isinstance(parent, list)
        or len(parent) != 576
        or len({r["source_id"] for r in parent}) != 576
        or _canonical_rows_sha(parent) != PARENT_SHA256
    ):
        raise ValueError("CA parent576 canonical rows differ from verified parent")
    census, query_rows = [], 0
    for prefix in ("retained-census", "new-census"):
        request, response, queries = (
            bodies[prefix + "-" + key] for key in ("request", "response", "queries")
        )
        receipt = inputs[prefix + "-response"]
        if (receipt["url"], receipt["method"], receipt["benchmark"], receipt["benchmark_name"]) != (
            markets.CENSUS_URL,
            "POST",
            markets.CENSUS_BENCHMARK,
            markets.CENSUS_BENCHMARK_NAME,
        ) or hashlib.sha256(request).hexdigest() != receipt["request_sha256"]:
            raise ValueError("CA Census response is not bound to authentic request/benchmark")
        result = markets.parse_census(request, response, json.loads(queries))
        census.extend(result.values())
        query_rows += len(result)
    benchmarks = json.loads(bodies["retained-census-benchmarks"])
    if not any(
        row["id"] == markets.CENSUS_BENCHMARK
        and row["benchmarkName"] == markets.CENSUS_BENCHMARK_NAME
        for row in benchmarks["benchmarks"]
    ):
        raise ValueError("CA Census benchmark is not in retained official metadata")
    return native, canonical, table["rows"], parent, census, query_rows


def verify_original_pdf(source_path):
    """Optional independent source replay: parse every authentic PDF cell, lazily."""
    source_path = Path(source_path)
    if not source_path.is_file() or not 0 < source_path.stat().st_size <= min(32768, MAX_BYTES):
        raise ValueError("CA PDF source configuration missing or oversized")
    control_raw = source_path.read_bytes()
    bundle = json.loads(control_raw)
    reader = EvidenceReader(source_path.parent, MAX_BYTES - len(control_raw))
    index_raw = reader.read(bundle["index"], ceiling=1024 * 1024)
    if hashlib.sha256(index_raw).hexdigest() != INDEX_SHA256:
        raise ValueError("CA PDF replay source inventory differs")
    import pdfminer
    import pdfplumber

    if (pdfplumber.__version__, pdfminer.__version__) != ("0.11.8", "20251107"):
        raise ValueError("CA original PDF replay requires pinned source-only extraction versions")
    inputs = json.loads(index_raw)["source_inputs"]
    pdf = reader.read(inputs["cdfa"])
    table_raw = reader.read(inputs["cdfa_rows"])
    table = json.loads(table_raw)
    if (
        hashlib.sha256(pdf).hexdigest() != PDF_SHA256
        or hashlib.sha256(table_raw).hexdigest() != TABLE_SHA256
    ):
        raise ValueError("CA original PDF checksum differs")
    rows, fields = (
        [],
        ["county", "name", "location", "manager", "days", "hours", "months", "market_phone"],
    )
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        pages = len(document.pages)
        for page_number, page in enumerate(document.pages, 1):
            for table_index, cells in enumerate(page.extract_tables()):
                for row_index, values in enumerate(cells):
                    if row_index == 0 and values[0] and "County" in values[0]:
                        continue
                    if len(values) != 8:
                        raise ValueError("CA original PDF table schema changed")
                    row = dict(zip(fields, values))
                    row.update(
                        pdf_page=page_number,
                        table_index=table_index,
                        row_index=row_index,
                        raw_cells=values,
                    )
                    rows.append(row)
    if rows != table["rows"] or len(rows) != 768:
        raise ValueError("CA actual original PDF cells differ from frozen extraction")
    return {
        "pages": pages,
        "rows_verified": len(rows),
        "pdf_sha256": PDF_SHA256,
        "table_sha256": TABLE_SHA256,
    }


def prepare(path, manifest=None, *, max_rows=MAX_ROWS, max_bytes=MAX_BYTES):
    """Return normalized destinations and separate hard calendars after complete offline replay."""
    if (
        type(max_rows) is not int
        or not 1 <= max_rows <= MAX_ROWS
        or type(max_bytes) is not int
        or not 1 <= max_bytes <= MAX_BYTES
    ):
        raise ValueError("CA import may not raise unchanged hard resource ceilings")
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= min(32768, max_bytes):
        raise ValueError("CA source configuration missing or oversized")
    raw = path.read_bytes()
    if manifest is None:
        sidecar = Path(str(path) + ".manifest.json")
        if not sidecar.is_file() or not 0 < sidecar.stat().st_size <= 32768:
            raise ValueError("CA source sidecar missing or oversized")
        manifest_raw = sidecar.read_bytes()
        manifest = json.loads(manifest_raw)
    else:
        manifest_raw = json.dumps(manifest, sort_keys=True, allow_nan=False).encode()
    if len(manifest_raw) > 32768 or len(raw) + len(manifest_raw) > max_bytes:
        raise ValueError("CA source headers exceed byte ceiling")
    if (
        manifest.get("schema_version"),
        manifest.get("source_url"),
        manifest.get("release"),
        manifest.get("attribution"),
        manifest.get("sha256"),
    ) != (SCHEMA, SOURCE_URL, RELEASE, ATTRIBUTION, hashlib.sha256(raw).hexdigest()):
        raise ValueError("CA manifest differs from exact reviewed source/release/checksum")
    if set(manifest.get("licenses", {})) != set(LICENSE_PINS) or any(
        manifest["licenses"][key].get("sha256") != value for key, value in LICENSE_PINS.items()
    ):
        raise ValueError("CA requires exact retained CC BY, Census and ODbL notices")
    reader = EvidenceReader(path.parent, max_bytes - len(raw) - len(manifest_raw))
    bundle = json.loads(raw)
    if bundle.get("schema_version") != SCHEMA:
        raise ValueError("CA source configuration schema differs")
    index_raw = reader.read(bundle["index"], ceiling=1024 * 1024)
    if hashlib.sha256(index_raw).hexdigest() != INDEX_SHA256:
        raise ValueError("CA source acquisition inventory differs from independent review")
    index = json.loads(index_raw)
    if (
        index.get("schema_version") != "roadtrips-ca-alternative-address-source-inputs/1"
        or index.get("prior_proposal_sha256") != PRIOR_PROPOSAL_SHA256
        or index.get("parent_canonical_rows_sha256") != PARENT_SHA256
    ):
        raise ValueError("CA source proposal/parent binding differs")
    if not 0 <= (datetime.now(UTC).date() - REVIEW_START).days <= 30:
        raise ValueError("CA fixed admission review date is future or stale")
    for key, digest in LICENSE_PINS.items():
        if index["licenses"][key]["sha256"] != digest:
            raise ValueError("CA source license text pin differs")
        reader.read(index["licenses"][key], freshness=False, ceiling=1024 * 1024)
    native, canonical, officials, parent, census, query_rows = _sources(reader, index)
    inputs = index["source_inputs"]
    driving_count = sum(key.startswith("driving-") for key in inputs)
    source_rows = {
        "native_kaggle": len(native),
        "canonical": len(canonical),
        "official_cdfa": len(officials),
        "dedup_parent": len(parent),
        "address_queries": query_rows,
        "address_results": query_rows,
        "driving_destinations": driving_count,
    }
    scanned = sum(source_rows.values())
    if scanned > max_rows:
        raise ValueError("CA aggregate scanned source row ceiling exceeded")
    roster, parent_ids = roster_index(officials), {row["source_id"] for row in parent}
    qualified, ledger = [], []
    for ident, source in native.items():
        value, reason = qualification(source, canonical.get(ident), roster, inputs, census)
        if not reason and value["row"]["source_id"] in parent_ids:
            reason = "identity_already_in_verified576_parent"
        if not reason:
            evidence = inputs.get("driving-" + ident)
            if evidence is None:
                reason = "authentic_driving_destination_proof_missing"
            else:
                try:
                    _, distance = markets.driving(path.parent, evidence, value["row"])
                    value["driving"] = evidence
                    value["driving_distance_m"] = distance
                except (ValueError, TypeError, KeyError):
                    reason = "driving_destination_proof_failed"
        if reason:
            ledger.append({"source_id": "usda-market:" + ident, "reason": reason})
        else:
            qualified.append(value)
    collisions = collision_holds([item["row"] for item in qualified], parent)
    rows, entries = [], []
    for item in qualified:
        row, calendar, facts = item["row"], item["calendar"], item["facts"]
        if row["source_id"] in collisions:
            ledger.append(
                {
                    "source_id": row["source_id"],
                    "reason": "unresolved_arrival_within_250m_of_source_or_parent",
                    "nearby_ids": collisions[row["source_id"]],
                }
            )
            continue
        ident = row["source_id"].split(":", 1)[1]
        source, current = native[ident], canonical[ident]
        visit = bounded_calendar(calendar, REVIEW_START, REVIEW_END)
        if not any(day["windows"] for day in visit["date_overrides"]):
            raise ValueError("CA reviewed market has no positive dated visit window")
        for receipt in visit["source_receipts"]:
            input_receipt = next(
                inputs[key]
                for key in ("archive", "canonical", "cdfa")
                if inputs[key]["sha256"] == receipt["snapshot_sha256"]
            )
            receipt["body_path"] = str((path.parent / input_receipt["path"]).resolve())
        link = current.get("website", "")
        parsed = urlsplit(link)
        row["url"] = (
            link
            if parsed.scheme in {"http", "https"}
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            else inputs["cdfa"]["url"]
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
                    "latitude_raw": source["lat"],
                    "longitude_raw": source["lng"],
                    "archive_member": markets.MEMBER,
                    "csv_sha256": markets.CSV_SHA256,
                },
                "native_coordinates_replaced": False,
                "native_street": None,
                "canonical_street": None,
                "native_zip": source["zip"] or None,
                "canonical_zip": current["zip"] or None,
                "identity_evidence": "Exact native/canonical market name and city plus current official market membership and independently corroborated official street; native street unknown",
                "current_official_visitor_facts": item["official_rows"],
                "published_access_facts": facts,
                "coordinate_corroboration": {
                    "source_url": markets.CENSUS_URL,
                    "license": "LicenseRef-US-Census-Geocoder",
                    "benchmark": markets.CENSUS_BENCHMARK_NAME,
                    "results": item["geocodes"],
                    "snapshot_sha256": inputs["new-census-response"]["sha256"],
                    "request_sha256": inputs["new-census-response"]["request_sha256"],
                    "checked_at": inputs["new-census-response"]["retrieved_at"],
                    "point_role": "Independent address-range interpolation, not a surveyed arrival or parking point",
                },
                "driving_evidence_sha256": item["driving"]["sha256"],
                "driving_checked_at": item["driving"]["retrieved_at"],
                "driving_destination_distance_m": item["driving_distance_m"],
                "driving_road": item["driving"]["road_name"],
                "parking": None,
                "price": None,
                "scheduler_hours": "unknown unless the separate dated source calendar is applied",
                "source_updated_at_normalized": "unknown; raw historical native and canonical update strings retained separately",
                "limitations": "Native/canonical streets remain unknown; no agency field overwrites them. Native points corroborated within 100m of every genuine successful source address; road destination within 75m. Surveyed entrance, parking, actual market-day vehicle access, price, staffing/capacity, weather and future operation unknown.",
            }
        ]
        rows.append(row)
        entries.append(
            {
                "source_id": row["source_id"],
                "source_visit_calendar": visit,
                "source_constraints": facts,
                "transformation": {
                    "adapter": SCHEMA,
                    "inventory_sha256": INDEX_SHA256,
                    "native_street_remains_unknown": True,
                    "native_zip_remains_unknown": not bool(source["zip"]),
                    "native_coordinates_replaced": False,
                    "all_source_seasons_weekdays_and_clocks_intersected": True,
                    "source_season_intersection_research": calendar["seasons"],
                    "review_horizon": {
                        "start": REVIEW_START.isoformat(),
                        "end": REVIEW_END.isoformat(),
                        "basis": "Conservative review dates, not an invented source annual recurrence",
                    },
                },
            }
        )
    actual = sorted(row["source_id"] for row in rows)
    if actual != index["selection"] or actual != bundle["selection"] or len(actual) != 11:
        raise ValueError("CA original-source replay differs from exact reviewed eleven identities")
    return rows, {
        "scanned": scanned,
        "source_rows": source_rows,
        "accepted": len(rows),
        "bytes": reader.bytes + len(raw) + len(manifest_raw),
        "unique_raw_source_body_bytes": sum(
            {value["sha256"]: value["bytes"] for value in inputs.values()}.values()
        ),
        "unique_evidence_body_count": len(reader.cache),
        "duplicates": 0,
        "rejects": dict(Counter(row["reason"] for row in ledger)),
        "rejection_ledger": ledger,
        "regions": {"CA": len(rows)},
        "categories": {"food_destination": len(rows), "daytime": len(rows)},
        "calendar_entries": entries,
        "source_inventory_sha256": INDEX_SHA256,
        "parent_canonical_rows_sha256": PARENT_SHA256,
        "native_street_unknown_count": len(rows),
        "native_zip_unknown_count": sum(
            not native[row["source_id"].split(":", 1)[1]]["zip"] for row in rows
        ),
        "independent_original_pdf_replay_required": True,
    }
