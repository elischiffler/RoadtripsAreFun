"""Offline admission of pinned Kaggle-native New York public market destinations.

The current state roster corroborates street/city/ZIP and independent published
points; it does not survey entrances. All source seasons constrain a bounded
visit calendar. Driving destination proximity never verifies parking.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import zipfile
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from itertools import product
from pathlib import Path
from urllib.parse import urlsplit

from app.catalog import kaggle_markets as markets
from app.catalog import market_visit_calendar, roadside
from app.routing.visit_calendar import Season

SCHEMA = "kaggle-usda-markets-ny-reviewed-arrivals/1"
SOURCE_URL = markets.SOURCE_URL
RELEASE = "kaggle-usda-markets-v4+ny-review-2026-10-15"
ATTRIBUTION = (
    "Harvestly Markets (CC BY 4.0), derived from USDA AMS Local Food Portal; "
    "New York State Department of Agriculture and Markets via OPEN-NY, "
    "independent agency point corroboration; driving evidence: OSRM, "
    "© OpenStreetMap contributors (ODbL). No endorsement."
)
INDEX_SHA256 = "cfbc844363ddbb7c59667dc84c59f282c1f882b7497441e87de602fe8a41fec1"
NY_SHA256 = "e0a4b8b72db5b58439035c6347a9dedaa29957955caf6107e2d42c2b4a0a7429"
NY_URL = "https://data.ny.gov/resource/qq4h-8p86.json?$limit=5000"
TERMS_SHA256 = "9437c849705d58df008f01fc23f404444becce6b86676adc3974f9160a4cb650"
BASELINE_SHA256 = "f09f0a85a5dbf0cf586c637ffeb99b1472a2098e75127fdc8ee7fb1b4ccf0ce2"
MAX_POINT_DISTANCE_M = 100
COLLISION_DISTANCE_M = 250
_REQUIRED_LICENSES = {"CC-BY-4.0", "LicenseRef-NY-Open-Data", "ODbL-1.0"}
_LICENSE_PINS = {
    "CC-BY-4.0": "d557539df68e771cc1eedcc91d13f70fca930e508d11eedcafa4b15db49e3744",
    "LicenseRef-NY-Open-Data": "61c83743627582696baf7b6fddd04f16ae3ab5d9211a41b0fd4cab8cdc4bc870",
    "ODbL-1.0": "77d2692c3d64efdd4db18dce2407699baf62930e2b50d6e5ed90b48acf16b7c1",
}
_STREET_TYPES = {
    "street",
    "road",
    "avenue",
    "boulevard",
    "highway",
    "drive",
    "parkway",
    "lane",
    "place",
    "court",
    "way",
    "terrace",
}


def name_city(row, *, official=False):
    return (
        markets.core(row["market_name"] if official else row["name"]),
        tuple(markets.words(row["city"])),
    )


def exact_numbered_street(native: str, official: str) -> bool:
    """Complete address-token equality preserves direction, numbers and qualifiers."""
    native_tokens, official_tokens = markets.address_words(native), markets.address_words(official)
    return bool(
        native_tokens == official_tokens
        and any(token.isdigit() and 1 <= len(token) <= 6 for token in native_tokens)
        and native_tokens & _STREET_TYPES
    )


def roster_index(officials):
    result = {}
    for ordinal, official in enumerate(officials):
        if official.get("state") != "NY":
            raise ValueError("New York roster contains an unreviewed state")
        result.setdefault(name_city(official, official=True), []).append((ordinal, official))
    return result


def _point(latitude, longitude):
    latitude, longitude = float(latitude), float(longitude)
    if not (
        math.isfinite(latitude)
        and math.isfinite(longitude)
        and -90 <= latitude <= 90
        and -180 <= longitude <= 180
    ):
        raise ValueError("invalid source coordinates")
    return latitude, longitude


def _fact(feed, record_id, receipt, fields):
    return {
        "feed": feed,
        "record_id": record_id,
        "source_url": receipt["url"],
        "snapshot_sha256": receipt["sha256"],
        "checked_at": receipt["retrieved_at"],
        "fields": fields,
    }


def qualification(native, canonical, roster, receipts, *, as_of: date):
    """Ordinary rows pass identical deterministic source, location and season gates."""
    if native["state"] != "NY":
        return None, "outside_new_york_roster"
    if canonical is None:
        return None, "missing_current_canonical_membership"
    if any(
        native[key] != canonical[key] for key in ("name", "street", "city", "state", "lat", "lng")
    ):
        return None, "canonical_identity_or_native_coordinates_changed"
    try:
        native_point = _point(native["lat"], native["lng"])
    except (TypeError, ValueError):
        return None, "invalid_native_coordinates"
    matches = roster.get(name_city(native), [])
    if len(matches) != 1:
        return None, "no_unique_exact_normalized_market_name_and_city"
    ordinal, official = matches[0]
    if not exact_numbered_street(native["street"], official.get("address_line_1", "")):
        return None, "no_exact_complete_numbered_street_match"
    road_tokens = {
        token for token in markets.address_words(native["street"]) if not token.isdigit()
    }
    visitor_tokens = markets.address_words(official.get("market_location", ""))
    if not road_tokens <= visitor_tokens:
        return None, "official_visitor_location_conflicts_with_native_street"
    if native["zip"] != official.get("zip") or canonical["zip"] != official.get("zip"):
        return None, "native_canonical_official_zip_conflict"
    try:
        agency_point = _point(official["latitude"], official["longitude"])
        geometry = official["georeference_1"]
        if geometry["type"] != "Point" or list(reversed(geometry["coordinates"])) != list(
            agency_point
        ):
            raise ValueError("agency coordinate fields conflict")
    except (TypeError, ValueError, KeyError):
        return None, "invalid_or_conflicting_independent_agency_coordinates"
    distance = markets.point_distance(native_point, agency_point)
    if distance > MAX_POINT_DISTANCE_M:
        return None, "native_point_more_than_100m_from_independent_agency_point"
    ident = native["listing_id"]
    groups = [
        _fact(
            "kaggle_feed",
            ident,
            receipts["archive"],
            {
                "season": native["season"] or None,
                "source_updated_at_raw": native["updated"] or None,
                "location": native["street"],
                "city": native["city"],
            },
        ),
        _fact(
            "canonical_feed",
            ident,
            receipts["canonical"],
            {
                "season": canonical["season"] or None,
                "source_updated_at_raw": canonical["updated"] or None,
                "location": canonical["street"],
                "city": canonical["city"],
            },
        ),
        _fact(
            "official_visitor_facts",
            str(ordinal),
            receipts["ny"],
            {
                "season": official.get("operation_season"),
                "hours": official.get("operation_hours"),
                "location": official["address_line_1"],
                "city": official["city"],
            },
        ),
    ]
    calendar = market_visit_calendar.build(groups)
    if calendar["unknown_reasons"]:
        return None, "unresolved_all_source_calendar:" + ";".join(calendar["unknown_reasons"])
    if not any(Season.model_validate(season).includes(as_of) for season in calendar["seasons"]):
        return None, "outside_all_source_season_intersection"
    return {
        "source_id": "usda-market:" + ident,
        "name": native["name"].strip(),
        "latitude": native_point[0],
        "longitude": native_point[1],
        "region": "NY",
        "address": native["street"],
        "categories": ["farmers_market", "food_destination", "daytime", "public_destination"],
        "source_updated_at": None,
        "official": official,
        "official_row_index": ordinal,
        "agency_native_point_distance_m": distance,
        "fact_groups": groups,
        "unbounded_calendar_research": calendar,
    }, None


def bounded_calendar(calendar, start: date, end: date):
    """Expand literal weekday/clock/season intersections within reviewed dates only."""
    if not 0 <= (end - start).days < 30 or calendar["unknown_reasons"]:
        raise ValueError("NY calendar review scope is unresolved or exceeds thirty dates")
    seasons = [Season.model_validate(value) for value in calendar["seasons"]]
    overrides = []
    day = start
    while day <= end:
        if any(season.includes(day) for season in seasons):
            windows = [
                {key: item[key] for key in ("opens", "closes", "end_day_offset")}
                for item in calendar["weekly_windows"]
                if day.weekday() in item["weekdays"]
            ]
            if windows:
                overrides.append({"date": day.isoformat(), "windows": windows})
        day += timedelta(days=1)
    return {**calendar, "weekly_windows": [], "seasons": [], "date_overrides": overrides}


def collision_holds(rows, baseline):
    """Linear spatial-grid screening of new arrivals against one another/full parent."""
    size = COLLISION_DISTANCE_M / 6_371_000
    buckets, held = {}, {}
    for row, is_new in [*((row, False) for row in baseline), *((row, True) for row in rows)]:
        lat, lon = math.radians(row["latitude"]), math.radians(row["longitude"])
        vector = (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))
        cell = tuple(math.floor(value / size) for value in vector)
        for offset in product((-1, 0, 1), repeat=3):
            nearby = tuple(a + b for a, b in zip(cell, offset))
            for other, other_new in buckets.get(nearby, ()):
                if not (is_new or other_new):
                    continue
                if (
                    markets.point_distance(
                        [row["latitude"], row["longitude"]], [other["latitude"], other["longitude"]]
                    )
                    < COLLISION_DISTANCE_M
                ):
                    if is_new:
                        held.setdefault(row["source_id"], []).append(other["source_id"])
                    if other_new:
                        held.setdefault(other["source_id"], []).append(row["source_id"])
        buckets.setdefault(cell, []).append((row, is_new))
    return held


def _retained(root, evidence, *, ceiling=15 * 1024 * 1024):
    """Local replay inputs have no invented HTTP response or retrieval status."""
    if evidence.get("kind") != "retained-local-artifact":
        return markets.retained(root, evidence, ceiling=ceiling)
    path = (root / evidence["path"]).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("NY local evidence path escapes or is missing")
    if not 0 < path.stat().st_size <= ceiling:
        raise ValueError("NY local evidence exceeds byte ceiling")
    raw = path.read_bytes()
    if len(raw) != evidence["bytes"] or hashlib.sha256(raw).hexdigest() != evidence["sha256"]:
        raise ValueError("NY local evidence checksum/length mismatch")
    roadside.checked_time(evidence["checked_at"])
    return raw


def _source_bytes(root, index):
    data, unique = {}, {}
    for key in (
        "archive",
        "canonical",
        "ny",
        "ny_metadata",
        "ny_terms",
        "baseline",
        "harvestly_rights",
        "kaggle_metadata",
    ):
        receipt = index[key]
        raw = _retained(root, receipt)
        unique[receipt["sha256"]] = len(raw)
        data[key] = raw
    pins = {
        "archive": markets.ARCHIVE_SHA256,
        "canonical": markets.CANONICAL_SHA256,
        "ny": NY_SHA256,
        "ny_terms": TERMS_SHA256,
        "baseline": BASELINE_SHA256,
    }
    if any(hashlib.sha256(data[key]).hexdigest() != digest for key, digest in pins.items()):
        raise ValueError("NY source bytes differ from the reviewed authentic originals")
    with zipfile.ZipFile(io.BytesIO(data["archive"])) as archive:
        info = archive.getinfo(markets.MEMBER)
        if info.file_size > 15 * 1024 * 1024:
            raise ValueError("NY native source member exceeds byte ceiling")
        raw = archive.read(info)
    if hashlib.sha256(raw).hexdigest() != markets.CSV_SHA256:
        raise ValueError("NY native CSV differs from Kaggle version four")
    native = markets.csv_rows(raw, markets.CSV_ROWS)
    canonical = markets.csv_rows(data["canonical"], markets.CANONICAL_ROWS)
    officials = json.loads(data["ny"])
    if not isinstance(officials, list) or len(officials) != 675:
        raise ValueError("NY official roster count/schema changed")
    baseline = [json.loads(line) for line in data["baseline"].splitlines() if line.strip()]
    if len(baseline) != 557 or len({row["source_id"] for row in baseline}) != 557:
        raise ValueError("NY dedup parent is not the exact released 557")
    for evidence in index["driving"]:
        raw = markets.retained(root, evidence, ceiling=1024 * 1024)
        unique[evidence["sha256"]] = len(raw)
    return native, canonical, officials, baseline, unique


def prepare(path, manifest, *, max_rows=50_000, max_bytes=104_857_600):
    """Replay source evidence before returning normalized rows and separate overlays."""
    if (
        manifest.get("schema_version"),
        manifest.get("source_url"),
        manifest.get("release"),
        manifest.get("attribution"),
    ) != (SCHEMA, SOURCE_URL, RELEASE, ATTRIBUTION):
        raise ValueError("NY manifest differs from exact reviewed source/release")
    if set(manifest.get("licenses", {})) != _REQUIRED_LICENSES:
        raise ValueError("NY markets require exact retained CC BY, Open NY and ODbL notices")
    if any(
        manifest["licenses"][key].get("sha256") != digest for key, digest in _LICENSE_PINS.items()
    ):
        raise ValueError("NY market license notices differ from reviewed exact texts")
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= 32768:
        raise ValueError("NY source configuration missing or oversized")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest.get("sha256"):
        raise ValueError("NY source configuration checksum mismatch")
    bundle, root = json.loads(raw), path.parent
    index_raw = _retained(root, bundle["index"], ceiling=1024 * 1024)
    if hashlib.sha256(index_raw).hexdigest() != INDEX_SHA256:
        raise ValueError("NY source acquisition index is not the frozen review")
    index = json.loads(index_raw)
    start, end = date.fromisoformat(index["review_start"]), date.fromisoformat(index["review_end"])
    if not 0 <= (datetime.now(UTC).date() - start).days <= 30:
        raise ValueError("NY reviewed admission date is future or stale")
    native, canonical, officials, baseline, unique_bytes = _source_bytes(root, index)
    scanned = len(native) + len(canonical) + len(officials) + len(baseline)
    if scanned > max_rows:
        raise ValueError("NY aggregate scanned row ceiling exceeded")
    roster = roster_index(officials)
    parent_ids = {row["source_id"] for row in baseline}
    checks = {entry["listing_id"]: entry for entry in index["driving"]}
    if len(checks) != len(index["driving"]):
        raise ValueError("Duplicate NY driving source identity")
    provisional, ledger = [], []
    for ident, source in native.items():
        row, reason = qualification(source, canonical.get(ident), roster, index, as_of=start)
        if not reason and row["source_id"] in parent_ids:
            reason = "source_identity_already_in_released_parent"
        if not reason:
            check = checks.get(ident)
            if check is None:
                reason = "no_authentic_driving_destination_proof"
            else:
                try:
                    nbytes, distance = markets.driving(root, check, row)
                    roadside.checked_time(check["retrieved_at"])
                    unique_bytes[check["sha256"]] = nbytes
                    row["driving_distance_m"] = distance
                except (ValueError, TypeError, KeyError):
                    reason = "driving_destination_proof_failed"
        if reason:
            ledger.append({"source_id": "usda-market:" + ident, "reason": reason})
        else:
            provisional.append(row)
    collisions = collision_holds(provisional, baseline)
    rows, overlays = [], []
    for row in provisional:
        ident = row["source_id"].split(":", 1)[1]
        if row["source_id"] in collisions:
            ledger.append(
                {
                    "source_id": row["source_id"],
                    "reason": "unresolved_arrival_within_250m",
                    "nearby_source_ids": sorted(set(collisions[row["source_id"]])),
                }
            )
            continue
        official = row.pop("official")
        ordinal = row.pop("official_row_index")
        calendar = row.pop("unbounded_calendar_research")
        normalized_seasons = calendar["seasons"]
        visit = bounded_calendar(calendar, start, end)
        for receipt in visit["source_receipts"]:
            source = next(
                index[key]
                for key in ("archive", "canonical", "ny")
                if index[key]["sha256"] == receipt["snapshot_sha256"]
            )
            receipt["body_path"] = str((root / source["path"]).resolve())
        if not any(item["windows"] for item in visit["date_overrides"]):
            ledger.append(
                {
                    "source_id": row["source_id"],
                    "reason": "no_positive_visit_date_in_review_horizon",
                }
            )
            continue
        distance = row.pop("agency_native_point_distance_m")
        driving_distance = row.pop("driving_distance_m")
        facts = row.pop("fact_groups")
        check = checks[ident]
        provenance = {
            "dataset": "kaggle-usda-markets",
            "record_id": ident,
            "source_url": SOURCE_URL,
            "license": "CC-BY-4.0",
            "snapshot_sha256": markets.ARCHIVE_SHA256,
            "checked_at": index["archive"]["retrieved_at"],
            "coordinate_source": "Unchanged native Kaggle v4 latitude/longitude strings; current publisher identity/location agrees exactly",
            "native_source_point": {
                "latitude_raw": native[ident]["lat"],
                "longitude_raw": native[ident]["lng"],
                "archive_member": markets.MEMBER,
                "csv_sha256": markets.CSV_SHA256,
            },
            "point_role": "Published recurring public market destination, not surveyed entrance or parking",
            "arrival_type": "Independent current state roster point within 100 m of native point and OSRM driving destination within 75 m; parking unknown",
            "primary_category": "food_destination",
            "coordinate_corroboration": {
                "dataset": "New York State Department of Agriculture and Markets via OPEN-NY",
                "source_url": NY_URL,
                "license": "LicenseRef-NY-Open-Data",
                "snapshot_sha256": NY_SHA256,
                "checked_at": index["ny"]["retrieved_at"],
                "row_index": ordinal,
                "official_address": official["address_line_1"],
                "official_location": official["market_location"],
                "official_city": official["city"],
                "official_zip": official["zip"],
                "native_zip": native[ident]["zip"],
                "official_latitude_raw": official["latitude"],
                "official_longitude_raw": official["longitude"],
                "native_point_distance_m": distance,
                "native_coordinates_replaced": False,
                "point_role": "Independent agency-published location corroboration; precision and surveyed arrival role unknown",
            },
            "published_access_facts": facts,
            "parking": None,
            "price": None,
            "opening_hours_imported": False,
            "scheduler_hours": "unknown; separate source calendar required",
            "normalized_source_updated_at": "unknown; raw historical source updated string retained in attributed facts",
            "driving_evidence_sha256": check["sha256"],
            "driving_checked_at": check["retrieved_at"],
            "driving_snap_distance_m": driving_distance,
            "driving_road": check["road_name"],
            "limitations": "Only published market weekdays/clocks within every source season are schedulable. Separate dated review calendar required. Future operation, ticket/capacity, weather, price, parking and actual market-day vehicle access unknown. Road proximity does not prove an entrance.",
        }
        link = canonical[ident]["website"]
        url = urlsplit(link)
        row["url"] = (
            link
            if url.scheme in {"http", "https"}
            and url.hostname
            and not url.username
            and not url.password
            else NY_URL
        )
        row["provenance"] = [provenance]
        rows.append(row)
        overlays.append(
            {
                "source_id": row["source_id"],
                "source_visit_calendar": visit,
                "source_constraints": facts,
                "transformation": {
                    "adapter": SCHEMA,
                    "inventory_sha256": INDEX_SHA256,
                    "source_season_intersection_research": normalized_seasons,
                    "review_horizon": {
                        "start": start.isoformat(),
                        "end": end.isoformat(),
                        "basis": "Conservative thirty-date review scope; not a new source season or annual recurrence",
                    },
                    "all_source_weekdays_clocks_and_seasons_intersected": True,
                    "native_coordinates_replaced": False,
                },
            }
        )
    actual = sorted(row["source_id"] for row in rows)
    if actual != index["selection"] or actual != bundle["selection"]:
        raise ValueError("Replayed NY admitted identities differ from frozen selection")
    if len(rows) > max_rows or len(raw) + len(index_raw) + sum(unique_bytes.values()) > max_bytes:
        raise ValueError("NY source evidence row/byte ceiling exceeded")
    ledger_by_id = {entry["source_id"]: entry["reason"] for entry in ledger}
    prospect_report = []
    for source_id in index["research_prospect_ids"]:
        source = native[source_id.split(":", 1)[1]]
        ordinal, official = roster[name_city(source)][0]
        prospect_report.append(
            {
                "source_id": source_id,
                "name": source["name"],
                "native_street": source["street"],
                "native_city": source["city"],
                "native_zip": source["zip"],
                "native_latitude_raw": source["lat"],
                "native_longitude_raw": source["lng"],
                "official_row_index": ordinal,
                "official_address": official["address_line_1"],
                "official_visitor_location": official["market_location"],
                "official_city": official["city"],
                "official_zip": official["zip"],
                "official_latitude_raw": official["latitude"],
                "official_longitude_raw": official["longitude"],
                "native_agency_point_distance_m": markets.point_distance(
                    [float(source["lat"]), float(source["lng"])],
                    [float(official["latitude"]), float(official["longitude"])],
                ),
                "disposition": ledger_by_id.get(source_id, "accepted"),
                "native_coordinates_replaced": False,
            }
        )
    return rows, {
        "scanned": scanned,
        "source_rows": {
            "native_kaggle": len(native),
            "canonical": len(canonical),
            "official_ny": len(officials),
            "dedup_parent": len(baseline),
        },
        "accepted": len(rows),
        "bytes": len(raw) + len(index_raw) + sum(unique_bytes.values()),
        "unique_evidence_raw_bytes": sum(unique_bytes.values()),
        "unique_evidence_body_count": len(unique_bytes),
        "duplicates": 0,
        "rejects": dict(Counter(row["reason"] for row in ledger)),
        "rejection_ledger": ledger,
        "regions": {"NY": len(rows)},
        "categories": {"food_destination": len(rows), "daytime": len(rows)},
        "calendar_entries": overlays,
        "source_inventory_sha256": INDEX_SHA256,
        "reviewed_prospect_report": prospect_report,
        "review_horizon": {"start": start.isoformat(), "end": end.isoformat()},
    }
