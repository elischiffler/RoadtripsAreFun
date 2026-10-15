"""Named beach arrivals from retained official NPS car-parking records only."""

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

from app.catalog import nps

SCHEMA = "nps-public-arrivals/1"
SOURCE_URL = "https://www.nps.gov/subjects/digital/structured-data.htm"
ATTRIBUTION = "National Park Service factual beach-arrival data. No claim to original U.S. Government works. No NPS endorsement."
# Inspected single-state coastal units. Multi-state units need explicit per-lot
# jurisdiction evidence; their headquarters address is not a lot's state.
UNIT_STATES = {"cana": "FL", "pore": "CA", "indu": "IN"}


def beach_name(name):
    if not isinstance(name, str) or not re.search(r"\bbeach\b", name, re.I):
        return None
    name = re.split(
        r"\s+(?:accessible |main |south |north )?(?:parking|trailhead)|\s+lot\s+\d+",
        name,
        flags=re.I,
    )[0].strip()
    if name.casefold() in {"point reyes beach north", "point reyes beach south"}:
        name = "Point Reyes Beach"
    return name


def prepare(path, manifest, *, max_rows, max_bytes):
    if (
        manifest.get("source_url") != SOURCE_URL
        or manifest.get("attribution") != ATTRIBUTION
        or not re.fullmatch(r"nps-public-\d{4}-\d{2}-\d{2}", manifest.get("release", ""))
    ):
        raise ValueError("public NPS arrivals require the reviewed source and dated release")
    with Path(path).open("rb") as stream:
        raw = stream.read(32_769)
    if len(raw) > 32_768 or hashlib.sha256(raw).hexdigest() != manifest.get("sha256"):
        raise ValueError("NPS beach bundle checksum/size mismatch")
    inputs = json.loads(raw).get("inputs")
    if not isinstance(inputs, dict) or not inputs or set(inputs) - UNIT_STATES.keys():
        raise ValueError("NPS beach bundle requires inspected single-state units")
    rows, rejects, regions = [], Counter(), Counter()
    scanned, size, duplicate_lots = 0, len(raw), 0
    for code, evidence in inputs.items():
        data, checked, nbytes = nps.read_snapshot(evidence, code)
        size += nbytes
        if size > max_bytes or data.get("physicalAddressStateCode") != UNIT_STATES[code]:
            raise ValueError("NPS beach state/evidence byte ceiling mismatch")
        grouped = {}
        for lot in data.get("parkingLots", []):
            scanned += 1
            if scanned > max_rows:
                raise ValueError("NPS parking scan row ceiling exceeded")
            label = beach_name(lot.get("name"))
            if not label:
                rejects["not_named_beach_arrival"] += 1
                continue
            if (
                not isinstance(lot.get("totalParkingSpaces"), (int, float))
                or lot["totalParkingSpaces"] <= 0
            ):
                rejects["car_parking_not_established"] += 1
                continue
            if nps.CLOSURE.search(lot.get("description", "")):
                rejects["closure_evidence"] += 1
                continue
            try:
                lat, lon = float(lot["latitude"]), float(lot["longitude"])
                if (
                    not math.isfinite(lat)
                    or not math.isfinite(lon)
                    or not -90 <= lat <= 90
                    or not -180 <= lon <= 180
                ):
                    raise ValueError
            except (ValueError, KeyError, TypeError):
                rejects["coordinates"] += 1
                continue
            if not re.fullmatch(r"[A-Fa-f0-9-]{36}", lot.get("lotID", "")):
                raise ValueError("NPS parking native identity missing")
            grouped.setdefault(label, []).append((lot, lat, lon))
        for label, choices in sorted(grouped.items()):
            # Keep the largest documented lot; other entrances remain native
            # source references rather than additional destination counts.
            choices.sort(key=lambda x: (-x[0]["totalParkingSpaces"], x[0]["lotID"]))
            lot, lat, lon = choices[0]
            duplicate_lots += len(choices) - 1
            key = hashlib.sha256(label.casefold().encode()).hexdigest()[:16]
            rows.append(
                {
                    "source_id": f"nps-public:{code}:{key}",
                    "name": label + " — " + lot["name"],
                    "latitude": lat,
                    "longitude": lon,
                    "region": UNIT_STATES[code],
                    "categories": ["beach", "daytime", "public_parking_arrival"],
                    "address": None,
                    "url": data["url"],
                    "source_updated_at": None,
                    "provenance": [
                        {
                            "dataset": "National Park Service beach parking",
                            "record_id": lot["lotID"],
                            "alternate_lot_ids": [x[0]["lotID"] for x in choices[1:]],
                            "unit_code": code,
                            "source_url": evidence["url"],
                            "snapshot_sha256": evidence["sha256"],
                            "checked_at": checked,
                            "license": "LicenseRef-US-Government-Work",
                            "primary_category": "beaches",
                            "arrival_type": "public_parking",
                            "documented_car_spaces": lot["totalParkingSpaces"],
                            "live_feed_active": lot.get("liveStatusIsActive"),
                            "operating_status": "unknown; live-feed flag is not an open-status claim",
                            "limitations": "Check current NPS beach, road, seasonal and parking restrictions; walking from the arrival may be required.",
                        }
                    ],
                }
            )
            regions[UNIT_STATES[code]] += 1
    return rows, {
        "scanned": scanned,
        "accepted": len(rows),
        "bytes": size,
        "rejects": dict(rejects),
        "duplicate_arrivals": duplicate_lots,
        "regions": dict(regions),
        "primary_categories": {"beaches": len(rows)},
    }
