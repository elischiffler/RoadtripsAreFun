"""Official NPS heritage-unit identities with reviewed visitor facility arrivals.

The inspected public map inventory supplies identities/designations only. It
supplies no arrival geometry or facility jurisdiction. Those require current
structured visitor records, explicit facility state and auto parking. No network
or database operations; no photographs or descriptions imported.
"""

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

from app.catalog import nps, roadside
from app.catalog.nps_access import dated_closure

SCHEMA = "nps-heritage-arrivals/1"
SOURCE_URL = "https://www.nps.gov/subjects/digital/structured-data.htm"
INDEX_URL = "https://carto.nps.gov/user/parktiles/api/v2/sql"
INDEX_SHA256 = "dcd341fb86cd4b6a8604ed0807f773d05e028ced4948e8f71285a6c0ab951b93"
ATTRIBUTION = "National Park Service factual heritage-unit and visitor-arrival data. No claim to original U.S. Government works. No NPS endorsement."
DESIGNATIONS = {
    "National Historical Park",
    "National Historic Site",
    "National Monument",
    "National Memorial",
    "National Battlefield",
    "National Military Park",
    "National Battlefield Site",
    "National Battlefield Park",
    "National Historic Park",
    "National Monument and Historic Shrine",
}
NON_DRIVING_UNITS = {"ania", "cakr", "kala"}
RESTRICTED_CAR_ACCESS = re.compile(
    r"mandatory shuttle|closed to (?:private|public) vehicles|no public vehic|staff (?:car )?parking only",
    re.I,
)


def prepare(path, manifest, *, max_rows, max_bytes):
    if (
        manifest.get("source_url") != SOURCE_URL
        or manifest.get("attribution") != ATTRIBUTION
        or not re.fullmatch(r"nps-heritage-\d{4}-\d{2}-\d{2}", manifest.get("release", ""))
    ):
        raise ValueError("NPS heritage requires the reviewed publisher and dated release")
    path = Path(path)
    if not 0 < path.stat().st_size <= 32_768:
        raise ValueError("NPS heritage bundle missing or exceeds 32 KiB")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest.get("sha256"):
        raise ValueError("NPS heritage bundle checksum mismatch")
    bundle = json.loads(raw)
    index = bundle.get("inventory", {})
    if index.get("url") != INDEX_URL or index.get("sha256") != INDEX_SHA256:
        raise ValueError("NPS heritage inventory differs from the inspected public index")
    inventory_raw = roadside.retained(index, url=INDEX_URL, ceiling=1024 * 1024)
    inventory = json.loads(inventory_raw).get("rows", [])
    if not 0 < len(inventory) <= 600:
        raise ValueError("NPS heritage inventory row ceiling")
    units = {}
    for item in inventory:
        code = item.get("unit_code")
        if code in units:
            raise ValueError("duplicate NPS inventory identity")
        units[code] = item
    inputs, selections = bundle.get("inputs"), bundle.get("selections")
    if (
        not isinstance(inputs, dict)
        or not isinstance(selections, dict)
        or not 1 <= len(selections) <= min(max_rows, 500)
        or set(selections) != set(inputs)
    ):
        raise ValueError("NPS heritage requires explicit bounded facility selections")
    rows, rejects, regions, categories = [], Counter(), Counter(), Counter()
    seen_facilities = set()
    driving_raw = roadside.retained(bundle["driving"])
    driving = json.loads(driving_raw)
    if not isinstance(driving, list) or len(driving) > 500:
        raise ValueError("NPS heritage driving evidence ceiling")
    size = len(raw) + len(inventory_raw) + len(driving_raw)
    for code, selection in selections.items():
        unit = units.get(code, {})
        if unit.get("designation") not in DESIGNATIONS:
            raise ValueError("unit is not an inspected heritage designation")
        evidence = inputs[code]
        data, checked, nbytes = nps.read_snapshot(evidence, code)
        size += nbytes
        if size > max_bytes:
            raise ValueError("NPS heritage aggregate byte ceiling")
        if roadside.compact(data.get("name", "").replace("&", "and")) != roadside.compact(
            unit.get("fullname", "").replace("&", "and")
        ):
            raise ValueError("NPS heritage current unit name and inventory identity differ")
        facilities = [
            v
            for v in data.get("visitorCenters", [])
            if v.get("visitorCenterID") == selection.get("visitor_center_id")
        ]
        if len(facilities) != 1:
            raise ValueError("heritage visitor facility missing or ambiguous")
        facility = facilities[0]
        if code in NON_DRIVING_UNITS or RESTRICTED_CAR_ACCESS.search(
            facility.get("directions", "")
        ):
            rejects["general_car_arrival_unverified"] += 1
            continue
        if dated_closure(facility, checked):
            rejects["active_or_uncertain_dated_closure"] += 1
            continue
        address = facility.get("physical_address", {})
        if not address.get("state_code") or address.get("country_code") not in {None, "", "US"}:
            rejects["explicit_facility_us_state_required"] += 1
            continue
        if "Parking - Auto" not in facility.get("amenities", []):
            rejects["public_auto_parking_unverified"] += 1
            continue
        # A cartographic label's state or park HQ address is not facility-state
        # evidence. Empty fallback makes the shared facility guard fail closed.
        row, reason = nps.normalize_arrival(
            {"Park Code": code.upper(), "State": ""},
            data,
            selection,
            evidence,
            checked,
            source_kind="nps-heritage",
        )
        if reason:
            rejects[reason] += 1
            continue
        native_id = facility["visitorCenterID"]
        if native_id in seen_facilities:
            raise ValueError("duplicate NPS visitor facility requires reviewed parent mapping")
        seen_facilities.add(native_id)
        checks = [x for x in driving if x.get("source_id") == row["source_id"]]
        if len(checks) != 1:
            raise ValueError("NPS heritage driving identity missing or ambiguous")
        check = checks[0]
        roadside.checked_time(check["checked_at"])
        distance = check.get("snap_distance_m")
        if (
            check.get("checked_waypoint") != "destination"
            or check.get("http_status") != 200
            or check.get("code") != "Ok"
            or check.get("source_coordinates") != [row["latitude"], row["longitude"]]
            or isinstance(distance, bool)
            or not isinstance(distance, (int, float))
            or not math.isfinite(distance)
            or not 0 <= distance <= 75
        ):
            rejects["driving_destination_unverified"] += 1
            continue
        row["provenance"][-1].update(
            {
                "driving_evidence_sha256": bundle["driving"]["sha256"],
                "driving_snap_distance_m": distance,
                "driving_road": check.get("road_name", ""),
                "coordinate_source": "original NPS visitor-facility point; unchanged",
            }
        )
        row["provenance"].insert(
            0,
            {
                "dataset": "National Park Service public unit inventory",
                "record_id": code,
                "designation": unit["designation"],
                "source_url": INDEX_URL,
                "snapshot_sha256": INDEX_SHA256,
                "license": "LicenseRef-US-Government-Work",
                "cartographic_geometry_used": False,
                "cartographic_label_state_used_for_facility": False,
            },
        )
        rows.append(row)
        regions[row["region"]] += 1
        categories[selection.get("primary_category", "landmarks")] += 1
    return rows, {
        "scanned": len(selections),
        "accepted": len(rows),
        "bytes": size,
        "rejects": dict(rejects),
        "regions": dict(regions),
        "primary_categories": dict(categories),
    }
