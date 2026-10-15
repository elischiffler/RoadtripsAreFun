"""Inspected natural-unit visitor arrivals within nps-public-arrivals/1.

The optional explicit profile adds no database schema or arbitrary-row import.
Public auto parking and current facility evidence supplement unchanged native
facility points; map labels/park centers never supply arrival geometry or state.
"""

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

from app.catalog import nps, nps_heritage, roadside
from app.catalog.nps_access import dated_closure

PROFILE = "nps-nature-visitors/1"
SOURCE_URL = nps_heritage.SOURCE_URL
ATTRIBUTION = "National Park Service factual natural-unit visitor-arrival data. No claim to original U.S. Government works. No NPS endorsement."
REVIEWED_FACILITIES = {
    "amis": 2320,
    "asis": 2369,
    "bica": 2431,
    "bicy": 6000,
    "biso": 42,
    "bith": 98,
    "blri": 1288,
    "buff": 2394,
    "caco": 2522,
    "calo": 2478,
    "cure": 5768,
    "gate": 2536,
    "glca": 1223,
    "goga": 1203,
    "guis": 1317,
    "lake": 103,
    "liri": 64,
    "neri": 2373,
    "niob": 27,
    "obed": 38,
    "ozar": 5983,
    "pais": 2515,
    "piro": 5688,
    "sacn": 2449,
    "samo": 2455,
    "slbe": 2379,
    "tapr": 76,
    "whis": 2409,
    "whsa": 99,
}
DESIGNATIONS = {
    "National Recreation Area",
    "National River & Recreation Area",
    "National Seashore",
    "National Lakeshore",
    "National Preserve",
    "Parkway",
    "National River",
    "National Park",
    "National Park & Preserve",
    "National Scenic River",
    "Wild & Scenic River",
    "National Scenic Riverways",
    "National Scenic Riverway",
}
NOTES = {
    "amis": "Visitor-center purchases require a credit/debit card; no payment or permit is included.",
    "asis": "Mainland Maryland visitor center before the Verrazzano Bridge; not a claim of arrival on the beach.",
    "bica": "The selected gateway facility is in Lovell, Wyoming; park lands also extend into Montana.",
    "bicy": "Published schedule is labeled winter/in-season; reconfirm seasonal visitor-center hours.",
    "blri": "Weather and road-section closures can affect Parkway access; this is the visitor-center arrival, not verified passage along the whole Parkway.",
    "calo": "Public Harkers Island mainland visitor center, picnic area and kayak launch. Offshore islands/light station require separate boat/ferry access; this is not a car arrival there.",
    "cure": "Published winter visitor-center hours are Monday–Friday; verify seasonal hours.",
    "gate": "Jamaica Bay visitor-center building publishes weekend hours; grounds/building hours differ.",
    "glca": "The visitor center is public; the operator reports Glen Canyon Dam tours closed. No dam tour access is included.",
    "guis": "Selected Davis Bayou facility is explicitly in Mississippi; Florida park headquarters is not used as its jurisdiction.",
    "liri": "University/NPS partner visitor center; publisher warns of GPS address variations. Use official directions and the unchanged facility point.",
    "niob": "Summer/off-season visitor-center schedules differ; river outfitters, transport and water access are separate.",
    "ozar": "Big Spring welcome/entrance station has visitor parking; fall/winter building hours exclude weekends and federal holidays.",
    "pais": "Visitor-center deck/ramp provides access toward Malaquite Beach; this record remains a visitor arrival, not a new beach-parking classification.",
    "piro": "Winter/holiday schedules vary; consult current visitor-center and road conditions.",
    "sacn": "Public visitor center operates mid-April–October and closes November 1–mid-April. No winter opening is asserted.",
    "samo": "Visitor-center building publishes Wednesday–Sunday hours. Adjacent parking has a two-hour limit; additional parking may require payment.",
    "tapr": "Summer/winter schedules differ; the visitor center closes Mondays/Tuesdays in winter while some historic buildings have different hours.",
    "whsa": "Visitor-center arrival, not a guarantee that Dunes Drive or US-70 remains accessible during missile testing or other restrictions.",
}


def prepare(path, manifest, *, max_rows, max_bytes):
    if (
        manifest.get("source_url") != SOURCE_URL
        or manifest.get("attribution") != ATTRIBUTION
        or manifest.get("filters", {}).get("arrival_profile") != PROFILE
        or not re.fullmatch(r"nps-public-\d{4}-\d{2}-\d{2}", manifest.get("release", ""))
    ):
        raise ValueError("nature arrivals require the inspected NPS profile and dated source")
    path = Path(path)
    if not 0 < path.stat().st_size <= 32_768:
        raise ValueError("nature source bundle missing or oversized")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest.get("sha256"):
        raise ValueError("nature bundle checksum mismatch")
    bundle = json.loads(raw)
    if bundle.get("profile") != PROFILE:
        raise ValueError("uninspected nature arrival profile")
    index = bundle.get("inventory", {})
    if (
        index.get("url") != nps_heritage.INDEX_URL
        or index.get("sha256") != nps_heritage.EXPANSION_INDEX_SHA256
    ):
        raise ValueError("nature inventory differs from reviewed public identities")
    inventory_raw = roadside.retained(index, url=nps_heritage.INDEX_URL, ceiling=1024 * 1024)
    inventory = json.loads(inventory_raw).get("rows", [])
    if not 0 < len(inventory) <= 600:
        raise ValueError("nature inventory row ceiling")
    units = {u["unit_code"]: u for u in inventory}
    if len(units) != len(inventory):
        raise ValueError("duplicate nature inventory identity")
    inputs, selections = bundle.get("inputs"), bundle.get("selections")
    if (
        not isinstance(inputs, dict)
        or not isinstance(selections, dict)
        or not 1 <= len(selections) <= min(max_rows, 25)
        or set(inputs) != set(selections)
    ):
        raise ValueError("nature arrivals require explicit bounded facility selections")
    driving_raw = roadside.retained(bundle["driving"])
    driving = json.loads(driving_raw)
    if not isinstance(driving, list) or len(driving) > 500:
        raise ValueError("nature driving evidence ceiling")
    size = len(raw) + len(inventory_raw) + len(driving_raw)
    rows, rejects, regions, categories, native_ids = [], Counter(), Counter(), Counter(), set()
    for code, selection in selections.items():
        unit = units.get(code, {})
        if (
            unit.get("designation") not in DESIGNATIONS
            or set(selection) != {"visitor_center_id"}
            or code not in REVIEWED_FACILITIES
            or selection["visitor_center_id"] != REVIEWED_FACILITIES[code]
        ):
            raise ValueError("nature unit/facility is outside the inspected selections")
        data, checked, nbytes = nps.read_snapshot(inputs[code], code)
        size += nbytes
        if roadside.compact(data.get("name", "").replace("&", "and")) != roadside.compact(
            unit.get("fullname", "").replace("&", "and")
        ):
            raise ValueError("current natural-unit name differs from inventory")
        facilities = [
            v
            for v in data.get("visitorCenters", [])
            if v.get("visitorCenterID") == selection["visitor_center_id"]
        ]
        if len(facilities) != 1:
            raise ValueError("selected natural-unit facility missing or ambiguous")
        facility = facilities[0]
        address = facility.get("physical_address", {})
        if not address.get("state_code") or address.get("country_code") not in {None, "", "US"}:
            rejects["explicit_facility_us_state_required"] += 1
            continue
        if "Parking - Auto" not in facility.get("amenities", []):
            rejects["public_auto_parking_unverified"] += 1
            continue
        if dated_closure(facility, checked) or nps_heritage.RESTRICTED_CAR_ACCESS.search(
            facility.get("directions", "")
        ):
            rejects["closed_or_restricted_arrival"] += 1
            continue
        # Reuse the guarded facility decoder (not its heritage identity/labels).
        # Empty fallback forbids substituting an inventory/HQ state.
        row, reason = nps.normalize_arrival(
            {"Park Code": code, "State": ""},
            data,
            selection,
            inputs[code],
            checked,
            source_kind="nps-heritage",
        )
        if reason:
            rejects[reason] += 1
            continue
        native = facility["visitorCenterID"]
        if native in native_ids:
            raise ValueError("shared native facility requires explicit parent review")
        native_ids.add(native)
        row["source_id"] = f"nps-public:{code}:visitor-center"
        checks = [c for c in driving if c.get("source_id") == row["source_id"]]
        if len(checks) != 1:
            raise ValueError("nature driving identity missing or ambiguous")
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
        response_path = Path(check["response_path"])
        if not response_path.is_absolute():
            response_path = Path(bundle["driving"]["path"]).parent / response_path
        response_raw = roadside.retained(
            {
                "path": str(response_path),
                "sha256": check["response_sha256"],
                "retrieved_at": check["checked_at"],
            },
            ceiling=256 * 1024,
        )
        size += len(response_raw)
        response = json.loads(response_raw)
        waypoints = response.get("waypoints", [])
        if (
            response.get("code") != "Ok"
            or len(waypoints) != 2
            or waypoints[1].get("name") != check.get("road_name")
            or not math.isclose(waypoints[1].get("distance", -1), distance, abs_tol=1e-6)
        ):
            raise ValueError("raw driving destination differs from inspected receipt")
        if size > max_bytes:
            raise ValueError("nature aggregate evidence byte ceiling")
        category = (
            "national_parks"
            if unit["designation"] in {"National Park", "National Park & Preserve"}
            else "nature"
        )
        row["categories"] = ["daytime", "nature", "visitor_center"]
        if category == "national_parks":
            row["categories"].append("national_park")
        row["categories"].sort()
        row["provenance"][-1].update(
            {
                "profile": PROFILE,
                "primary_category": category,
                "coordinate_source": "original NPS visitor-facility coordinate; unchanged",
                "driving_evidence_sha256": bundle["driving"]["sha256"],
                "driving_response_sha256": check["response_sha256"],
                "driving_snap_distance_m": distance,
                "driving_road": check.get("road_name", ""),
                "opening_hours_imported": False,
                "limitations": NOTES.get(code, "")
                + " Check current facility hours, seasonal/road closures, reservations, fees and parking restrictions before travel; future access and parking availability are unknown.",
            }
        )
        row["provenance"].insert(
            0,
            {
                "dataset": "National Park Service public unit inventory",
                "record_id": code,
                "designation": unit["designation"],
                "source_url": nps_heritage.INDEX_URL,
                "snapshot_sha256": index["sha256"],
                "license": "LicenseRef-US-Government-Work",
                "cartographic_geometry_used": False,
                "cartographic_label_state_used_for_facility": False,
            },
        )
        rows.append(row)
        regions[row["region"]] += 1
        categories[category] += 1
    if size > max_bytes:
        raise ValueError("nature aggregate evidence byte ceiling")
    return rows, {
        "scanned": len(selections),
        "accepted": len(rows),
        "bytes": size,
        "rejects": dict(rejects),
        "regions": dict(regions),
        "primary_categories": dict(categories),
    }
