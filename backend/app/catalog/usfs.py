"""Pinned public USFS facility records, independently cross-checked before import.

The construction-site point is preserved verbatim. The older public recreation
point is an identity/access corroboration, never a replacement coordinate. Only
selected factual fields are emitted; publisher prose stays in retained receipts.
"""

import hashlib
import json
import math
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse, urlsplit

from app.catalog import mixed, roadside
from app.catalog.normalize import US_REGIONS

SCHEMA = "usfs-public-facilities/1"
SOURCE_URL = "https://data.fs.usda.gov/geodata/edw/datasets.php?xmlKeyword=recreation"
ATTRIBUTION = (
    "USDA Forest Service public recreation facility facts; U.S. Census Bureau ACS 2025 "
    "cartographic state boundaries; original U.S. Government works; no agency endorsement; "
    "driving evidence: OSRM, © OpenStreetMap contributors (ODbL)"
)
RELEASE = "usfs-2026-10-15"
# The reviewed immutable acquisition inventory, not a blanket arbitrary-row adapter.
INDEX_SHA256 = "cc24c5f3474c5f27f742a148fb9164a52d59425ac51b0eb81b7e3fd4e240bf6b"
SELECTION_SHA256 = "4213c90bbce960d418b6a6c2b09e1370aeb35c18816c8bf14e12286790a43854"
FACILITY_URL = "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0/query"
PUBLIC_URL = "https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecreationOpportunities_01/MapServer/0/query"
STATE_URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/Generalized_ACS2025/State_County/MapServer/7/query"
TYPES = {
    "TRAILHEAD": ["trailhead", "nature", "daytime", "public_parking_arrival"],
    "PICNIC SITE": ["picnic_site", "nature", "daytime", "public_parking_arrival"],
    "DAY USE AREA": ["day_use_area", "nature", "daytime", "public_parking_arrival"],
    "OBSERVATION SITE": ["viewpoint", "nature", "daytime", "public_parking_arrival"],
    "INTERPRETIVE SITE": ["interpretive_site", "landmark", "culture", "daytime"],
    "WILDLIFE VIEWING SITE": ["wildlife_viewing", "nature", "daytime"],
    "SWIMMING SITE": ["swimming_site", "nature", "daytime"],
    "INTERPRETIVE VISITOR CENTER (MAJOR)": ["visitor_center", "nature", "culture", "daytime"],
    "INTERPRETIVE VISITOR CENTER (MINOR)": ["visitor_center", "nature", "culture", "daytime"],
}
ACCESS_FIELDS = (
    "directions",
    "recarea_description",
    "service_type_list",
    "important_info",
    "restrictions",
    "season_description",
    "operational_hours",
    "site_contact_notes",
)
PUBLIC_ACCESS_FIELDS = (
    "recareadescription",
    "operational_hours",
    "restrictions",
    "reservation_info",
    "accessibility",
)
CONTRADICTION = re.compile(
    r"clos(?:ed|ure)|4[- ]?wheel|high[- ]clearance|4wd|boat[- ]access[- ]only|"
    r"accessible only by|no parking",
    re.I,
)
VEHICLE_WARNING = re.compile(
    r"(?:four|all)[- ]wheel drive|low[- ]clearance|high[- ]clearance|"
    r"(?:road|roads)[^.\n]{0,100}\b(?:rough|rocky|rutted|bumpy|impassable)\b|"
    r"\b(?:rough|rocky|rutted|bumpy)\b[^.\n]{0,50}\broads?\b|"
    r"human powered snow access only",
    re.I,
)
# These are dated exceptions found by inspecting the actual immutable feed,
# rather than assuming its OPEN enum resolves conflicting source statements.
REVIEW_HOLDS = {
    "5061.000601": "published season ends in September",
    "5318.001561": "conflicting September/October season ends and snow warning",
    "6738209010602": "winter ski arrival has no reviewed ordinary fall use",
    "11865010344": "private-road approach asks visitors to call for access information",
    "6471.003621": "published parking is half a mile from the native trailhead point",
}


def retained(root, evidence, *, ceiling=20 * 1024 * 1024, endpoint=None):
    name = evidence.get("path", "")
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.\-/]+", name):
        raise ValueError("invalid USFS receipt path")
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("USFS receipt escapes or is missing from source root")
    if not 0 < path.stat().st_size <= ceiling:
        raise ValueError("USFS receipt byte ceiling exceeded")
    with path.open("rb") as stream:
        raw = stream.read(ceiling + 1)
    if len(raw) > ceiling:
        raise ValueError("USFS receipt byte ceiling exceeded")
    if hashlib.sha256(raw).hexdigest() != evidence.get("sha256"):
        raise ValueError("USFS receipt checksum mismatch")
    roadside.checked_time(evidence["retrieved_at"])
    if evidence.get("status") != 200:
        raise ValueError("USFS source acquisition was not successful")
    if endpoint:
        url = urlparse(evidence.get("url", ""))
        if url.scheme + "://" + url.netloc + url.path != endpoint or url.fragment:
            raise ValueError("USFS receipt is not from the inspected publisher endpoint")
    return raw


def ring_contains(lon, lat, ring):
    inside = False
    for a, b in zip(ring, ring[1:] + ring[:1]):
        if (a[1] > lat) != (b[1] > lat) and lon < (
            (b[0] - a[0]) * (lat - a[1]) / (b[1] - a[1]) + a[0]
        ):
            inside = not inside
    return inside


def state_shapes(data):
    shapes = []
    if data.get("type") != "FeatureCollection" or len(data.get("features", [])) != 56:
        raise ValueError("expected the retained 56 Census state/territory features")
    for feature in data["features"]:
        geom = feature["geometry"]
        if geom["type"] not in {"Polygon", "MultiPolygon"}:
            raise ValueError("Census state geometry must contain polygons")
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        for poly in polys:
            points = [point for ring in poly for point in ring]
            shapes.append(
                (
                    feature["properties"]["STUSAB"],
                    min(p[0] for p in points),
                    max(p[0] for p in points),
                    min(p[1] for p in points),
                    max(p[1] for p in points),
                    poly,
                )
            )
    return shapes


def state_for(point, shapes):
    lat, lon = point
    matches = {
        code
        for code, x0, x1, y0, y1, poly in shapes
        if x0 <= lon <= x1
        and y0 <= lat <= y1
        and ring_contains(lon, lat, poly[0])
        and not any(ring_contains(lon, lat, ring) for ring in poly[1:])
    }
    return next(iter(matches)) if len(matches) == 1 and matches <= US_REGIONS else None


def qualification(facility, public, shapes):
    """Return a rejection reason or the unchanged, source-backed compact facts."""
    a, b = facility, public
    if a.get("site_cn") in REVIEW_HOLDS:
        return None, "review_hold: " + REVIEW_HOLDS[a["site_cn"]]
    if a.get("site_type") not in TYPES or a.get("development_status") != "EXISTING":
        return None, "ineligible_facility_type_or_development"
    if a.get("recarea_enable") != "Y" or a.get("seasonal_operational_status") != "OPEN":
        return None, "not_published_open"
    if not b or b.get("openstatus") != "open":
        return None, "public_status_not_open_or_missing"
    if str(a.get("usda_portal_id")) != str(b.get("recareaid")):
        return None, "public_identity_mismatch"
    text = " ".join(str(a.get(key) or "") for key in ACCESS_FIELDS)
    if not a.get("directions") or not re.search(r"\bparking\b|\bcars?\b", text, re.I):
        return None, "parking_or_directions_not_documented"
    other = " ".join(str(b.get(key) or "") for key in PUBLIC_ACCESS_FIELDS)
    if CONTRADICTION.search(text) or CONTRADICTION.search(other):
        return None, "contradictory_access_text"
    if VEHICLE_WARNING.search(text) or VEHICLE_WARNING.search(other):
        return None, "published_vehicle_access_warning"
    try:
        lat, lon = a["latitude"], a["longitude"]
        if any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
            for v in (lat, lon)
        ) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError
        old = {"latitude": float(b["latitude"]), "longitude": float(b["longitude"])}
        if mixed.distance(a, old) > 500:
            return None, "public_identity_point_more_than_500m_away"
    except (KeyError, ValueError, TypeError):
        return None, "coordinates"
    state = state_for([lat, lon], shapes)
    if not state:
        return None, "state_not_established"
    # Only a one-state source field is authoritative corroboration. Nearby-town
    # names are not the facility's jurisdiction and never supply its state.
    if a.get("states_spanned") in US_REGIONS and a["states_spanned"] != state:
        return None, "published_state_conflict"
    name = a.get("public_site_name") or a.get("recarea_name") or a.get("site_name")
    url = b.get("recareaurl")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 300:
        return None, "name"
    parsed = urlparse(url or "")
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in {
        "www.fs.usda.gov",
        "fs.usda.gov",
    }:
        return None, "publisher_url"
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", a.get("site_cn", "")):
        return None, "native_identity"
    return {
        "source_id": "usfs:" + str(b["recareaid"]),
        "name": name.strip(),
        "latitude": lat,
        "longitude": lon,
        "region": state,
        "categories": TYPES[a["site_type"]],
        "address": None,
        "url": url,
        "source_updated_at": (
            datetime.fromtimestamp(a["infra_last_update"] / 1000, UTC).isoformat()
            if isinstance(a.get("infra_last_update"), (float, int))
            else None
        ),
    }, None


def driving(root, entry, row, *, max_distance=75):
    raw = retained(root, entry, ceiling=1024 * 1024)
    data = json.loads(raw)
    result = data.get("waypoints", [])
    if (
        entry.get("checked_waypoint") != "destination"
        or data.get("code") != "Ok"
        or len(result) != 2
    ):
        raise ValueError("USFS arrival lacks a successful two-waypoint driving destination")
    lat, lon = row["latitude"], row["longitude"]
    if entry.get("source_coordinates") != [lat, lon]:
        raise ValueError("USFS driving check changed the native facility point")
    url = urlsplit(entry.get("url", ""))
    expected = f"/route/v1/driving/{lon},{lat + 0.01};{lon},{lat}"
    if url.scheme != "https" or url.netloc != "router.project-osrm.org" or url.path != expected:
        raise ValueError("USFS driving receipt URL differs from the checked native point")
    waypoint = result[-1]
    distance = waypoint.get("distance")
    if (
        isinstance(distance, bool)
        or not isinstance(distance, (int, float))
        or not math.isfinite(distance)
        or not 0 <= distance <= max_distance
    ):
        raise ValueError("USFS driving destination is too distant or invalid")
    if entry.get("snap_distance_m") != distance or entry.get("road_name") != waypoint.get("name"):
        raise ValueError("USFS driving summary disagrees with the retained raw response")
    return len(raw), distance, waypoint.get("name")


def prepare(path, manifest, *, max_rows, max_bytes):
    if (manifest.get("source_url"), manifest.get("release"), manifest.get("attribution")) != (
        SOURCE_URL,
        RELEASE,
        ATTRIBUTION,
    ):
        raise ValueError("USFS source/release/attribution differs from the reviewed acquisition")
    path = Path(path)
    with path.open("rb") as stream:
        raw = stream.read(32_769)
    if len(raw) > 32_768 or hashlib.sha256(raw).hexdigest() != manifest.get("sha256"):
        raise ValueError("USFS bundle checksum/size mismatch")
    bundle = json.loads(raw)
    root = path.parent
    index_bytes = retained(root, bundle["index"], ceiling=1024 * 1024)
    if hashlib.sha256(index_bytes).hexdigest() != INDEX_SHA256:
        raise ValueError("USFS acquisition inventory is not the reviewed immutable snapshot")
    index = json.loads(index_bytes)
    size = len(raw) + len(index_bytes)
    facilities, public = {}, {}
    evidence_by_site, evidence_by_public = {}, {}
    scanned = 0
    for kind, endpoint, key, target, receipts in (
        ("facilities", FACILITY_URL, "site_cn", facilities, evidence_by_site),
        ("public", PUBLIC_URL, "recareaid", public, evidence_by_public),
    ):
        for evidence in index[kind]:
            payload = retained(root, evidence, endpoint=endpoint)
            size += len(payload)
            if size > max_bytes:
                raise ValueError("USFS aggregate evidence byte ceiling exceeded")
            data = json.loads(payload)
            if data.get("error") or data.get("exceededTransferLimit") and kind == "public":
                raise ValueError("USFS source query failed or truncated an identity lookup")
            for feature in data.get("features", []):
                scanned += 1
                if scanned > 10_000:
                    raise ValueError("USFS source scan exceeds 10,000 records")
                item = feature["attributes"]
                ident = str(item[key])
                if ident in target:
                    raise ValueError("USFS source contains duplicate native records")
                target[ident], receipts[ident] = item, evidence
    state_raw = retained(root, index["states"], endpoint=STATE_URL)
    drive_raw = retained(root, index["driving"], ceiling=1024 * 1024)
    shapes = state_shapes(json.loads(state_raw))
    checks = {item["site_cn"]: item for item in json.loads(drive_raw)}
    size += len(state_raw) + len(drive_raw)
    for evidence in index["rights"]:
        size += len(retained(root, evidence, ceiling=2 * 1024 * 1024))
    selected = bundle.get("selection")
    if (
        not isinstance(selected, list)
        or not 1 <= len(selected) <= max_rows
        or len(set(selected)) != len(selected)
    ):
        raise ValueError("USFS selection must contain bounded, distinct native facility IDs")
    if (
        hashlib.sha256(json.dumps(selected, separators=(",", ":")).encode()).hexdigest()
        != SELECTION_SHA256
    ):
        raise ValueError("USFS selection differs from the frozen reviewed batch")
    rows, seen, regions, categories = [], set(), Counter(), Counter()
    for site in selected:
        a = facilities.get(site)
        b = public.get(str(a.get("usda_portal_id"))) if a else None
        row, reason = qualification(a or {}, b, shapes)
        if reason:
            raise ValueError("selected USFS site is no longer eligible: " + reason)
        if row["source_id"] in seen:
            raise ValueError("multiple USFS arrivals cannot inflate one destination")
        seen.add(row["source_id"])
        check = checks[site]
        nbytes, distance, road = driving(root, check, row)
        size += nbytes
        if size > max_bytes:
            raise ValueError("USFS aggregate evidence byte ceiling exceeded")
        origin = evidence_by_site[site]
        corroboration = evidence_by_public[str(b["recareaid"])]
        row["provenance"] = [
            {
                "dataset": "USDA Forest Service public recreation facilities",
                "record_id": site,
                "global_id": a["globalid"],
                "public_record_id": b["recareaid"],
                "source_url": origin["url"],
                "snapshot_sha256": origin["sha256"],
                "checked_at": origin["retrieved_at"],
                "public_evidence_url": corroboration["url"],
                "public_snapshot_sha256": corroboration["sha256"],
                "public_checked_at": corroboration["retrieved_at"],
                "license": "LicenseRef-US-Agency-Factual-Data",
                "coordinate_source": "unchanged USFS constructed recreation-site latitude/longitude",
                "point_role": a["site_type"],
                "arrival_type": "published visitor facility with documented parking and driving directions",
                "published_operational_status": "OPEN; public recreation feed: open",
                "published_open_season": a.get("open_season"),
                "published_season_qualification": a.get("season_description"),
                "published_restrictions": a.get("restrictions"),
                "published_fee_charged": a.get("fee_charged"),
                "primary_category": "landmarks"
                if a["site_type"] == "INTERPRETIVE SITE"
                else "nature",
                "state_source": "point-in-polygon against retained Census ACS 2025 States 500K; not a nearby town or forest headquarters",
                "state_snapshot_sha256": index["states"]["sha256"],
                "driving_evidence_sha256": check["sha256"],
                "driving_checked_at": check["retrieved_at"],
                "driving_snap_distance_m": distance,
                "driving_road": road,
                "opening_hours_imported": False,
                "limitations": "Dated published access only. Verify current road, weather, seasonal, fee, reservation and parking restrictions. The native facility point is not a surveyed parking entrance. Walking from parking may be required. Local Alaska road networks may require a ferry or flight to reach; lower-48 road connectivity is not asserted. Hours, prices, future access and parking availability remain unknown.",
            }
        ]
        rows.append(row)
        regions[row["region"]] += 1
        categories.update(row["categories"])
    return rows, {
        "scanned": scanned,
        "accepted": len(rows),
        "bytes": size,
        "duplicates": 0,
        "rejects": {},
        "regions": dict(regions),
        "categories": dict(categories),
        "unselected_source_records": len(facilities) - len(selected),
    }
