"""Replay a bounded, pinned review of walk-in cultural and food destinations.

Official pages supply facts and hours; unchanged OSM points supply location.
This adapter never assigns, updates, or reads attraction ratings. Importing new
venues does not authorize re-rating existing identities.
"""

import hashlib
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from lxml.html import fromstring

from app.catalog import admission
from app.catalog.calendar_enrichment import Reader, _receipt
from app.catalog.cdfw_nature import FACTS_DATASET, FACTS_VERSION
from app.catalog.kaggle_coastal import driving_destination
from app.catalog.venue_visit_calendar import intersect_layers

REVIEW_SHA256 = "1a3c3974f61162e1337b0ac45934d09be2e884f98830e42278609df5b4e58519"
FOODHALLS_REVIEW_SHA256 = "055b857df5ed26fec0e5539d0444fb4df05742e2ed7cdf28d752a38392bc5d8c"
ATTRIBUTION = (
    "Published venue facts from the individually cited operators; descriptions paraphrased "
    "for research. Coordinates © OpenStreetMap contributors, ODbL 1.0 "
    "(https://www.openstreetmap.org/copyright). AI ratings are separate estimates."
)


def calendar_windows(profile, first_date, days):
    """Expand reviewed recurring clocks; omit uncertain holiday access, never infer it."""
    if type(days) is not int or not 1 <= days <= 30:
        raise ValueError("review horizon exceeds thirty dates")
    result = []
    for offset in range(days):
        day = date.fromisoformat(first_date) + timedelta(days=offset)
        if day.isoformat() in profile["omit_dates"]:
            continue
        windows = profile["date_windows"].get(
            day.isoformat(), intersect_layers([{"windows": profile["windows"]}], day)
        )
        result.append({"date": day.isoformat(), "windows": windows})
    return result


def prepare(path, manifest=None, *, max_rows=50_000, max_bytes=104_857_600):
    path = Path(path)
    if not 0 < path.stat().st_size <= max_bytes:
        raise ValueError("review exceeds byte ceiling")
    body = path.read_bytes()
    review_sha = hashlib.sha256(body).hexdigest()
    if review_sha not in {REVIEW_SHA256, FOODHALLS_REVIEW_SHA256}:
        raise ValueError("reviewed entertainment identities or facts differ")
    review = json.loads(body)
    if review["schema_version"] != "roadtrips-reviewed-entertainment/1":
        raise ValueError("unsupported review")
    reader = Reader(path.parent, max_bytes - len(body))
    reviewed = datetime.fromisoformat(review["reviewed_at"])
    bodies = {}
    for name, receipt in review["receipts"].items():
        _receipt(receipt, reader)
        acquired = datetime.fromisoformat(receipt["checked_at"])
        if not 0 <= (reviewed - acquired).total_seconds() < 86400:
            raise ValueError("review acquisition freshness differs")
        bodies[name] = reader.read(name, receipt["snapshot_sha256"])
    rows, entries, scanned = [], [], 0
    for profile in review["profiles"]:
        native_rows = json.loads(bodies[profile["geo"]])
        scanned += len(native_rows) + 1
        native = native_rows[0]
        if (
            native["osm_type"] != profile["native_type"]
            or native["osm_id"] != profile["native_id"]
            or native["address"]["ISO3166-2-lvl4"] != "US-" + profile["region"]
        ):
            raise ValueError("reviewed native destination identity differs")
        text = " ".join(fromstring(bodies[profile["pages"][0]]).text_content().split())
        if any(literal not in text for literal in profile["checks"]):
            raise ValueError("official access or hours evidence differs")
        lat, lon = float(native["lat"]), float(native["lon"])
        road_receipt = review["receipts"][profile["road"]]
        _, snap = driving_destination(
            {"LOCATION": repr({"latitude": lat, "longitude": lon})},
            {"url": road_receipt["source_url"]},
            bodies[profile["road"]],
        )
        if snap > 75:
            raise ValueError("native destination is too far from the driving network")
        receipts = [
            review["receipts"][key]
            for key in [*profile["pages"], profile["geo"], profile["road"], "osm-copyright.html"]
        ]
        constraints = [
            {
                "scope": profile["description"],
                "omitted_dates": profile["omit_dates"],
                "omission_reason": "Major-holiday hours unspecified; no availability claimed",
                "coordinates": "Unchanged OSM venue/address point; not a guaranteed parking space",
            }
        ]
        entries.append(
            {
                "source_id": profile["source_id"],
                "source_visit_calendar": {
                    "schema_version": "roadtrips-source-visit-calendar/1",
                    "weekly_windows": [],
                    "seasons": [],
                    "date_overrides": calendar_windows(
                        profile, review["first_date"], review["days"]
                    ),
                    "annual_closures": [],
                    "fixed_starts": [],
                    "source_receipts": receipts,
                    "unknown_reasons": [],
                },
                "source_constraints": constraints,
                "transformation": {
                    "method": "Reviewed local-clock recurrences expanded to bounded dates; no extrapolation",
                    "review_sha256": review_sha,
                },
                "source_attribution": ATTRIBUTION,
            }
        )
        rows.append(
            {
                "source_id": profile["source_id"],
                "name": profile["name"],
                "latitude": lat,
                "longitude": lon,
                "region": profile["region"],
                "categories": profile["categories"],
                "address": profile["address"],
                "url": review["receipts"][profile["pages"][0]]["source_url"],
                "source_updated_at": review["receipts"][profile["pages"][0]]["checked_at"],
                "provenance": [
                    {
                        "dataset": "Reviewed entertainment destination facts and OSM locations",
                        "review_sha256": review_sha,
                        "source_attribution": ATTRIBUTION,
                        "native_type": profile["native_type"],
                        "native_id": profile["native_id"],
                        "native_coordinates_unchanged": True,
                        "road_snap_metres": snap,
                        "receipts": receipts,
                    },
                    {
                        "dataset": FACTS_DATASET,
                        "schema_version": FACTS_VERSION,
                        "description": profile["description"],
                        "activities": profile["categories"][1:],
                    },
                    {
                        "dataset": admission.DATASET,
                        "catalog_admission": {
                            "schema_version": admission.SCHEMA,
                            "tier": "T3",
                            "source_id": profile["source_id"],
                            "review_status": "approved",
                            "reviewed_at_epoch": int(reviewed.timestamp()),
                            "expires_at_epoch": int(reviewed.timestamp()) + 30 * 86400,
                            "gates": dict.fromkeys(admission.GATES, True),
                        },
                    },
                ],
            }
        )
    if scanned > max_rows:
        raise ValueError("source row ceiling exceeded")
    return rows, {
        "bytes": reader.bytes + len(body),
        "scanned": scanned,
        "calendar_entries": entries,
    }
