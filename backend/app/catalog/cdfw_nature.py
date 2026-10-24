"""Offline replay of three reviewed CDFW trail arrivals and dated solar windows.

This is a pinned, scoped review, not an automatic permit to import other reserves.
CDFW supplies destination facts; OSM supplies unchanged road/parking geometry.
No numeric preference ratings are generated here. Freshness expires after 30 days.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from astral import Observer
from astral.sun import sun
from lxml.html import fromstring

from app.catalog import admission
from app.catalog.calendar_enrichment import Reader, _receipt
from app.catalog.kaggle_coastal import driving_destination
from app.catalog.kaggle_cultural import distance

REVIEW_SHA256 = "5199f6ee04d050c362e8b380a520a0779ba7a239cb1bec1fc87bc0a687afef9b"
FACTS_DATASET = "Roadtrips reviewed destination facts"
FACTS_VERSION = "roadtrips-reviewed-destination-facts/1"
ATTRIBUTION = (
    "California Department of Fish and Wildlife factual public-domain information; "
    "© OpenStreetMap contributors, ODbL 1.0 (https://www.openstreetmap.org/copyright). "
    "Solar windows calculated with Astral 3.2; AI traits are separate estimates."
)


def solar_windows(lat, lon, first_date, days, timezone, clock=None):
    """Round inward to minutes; never extrapolate beyond the reviewed date horizon."""
    if (
        type(days) is not int
        or not 1 <= days <= 30
        or any(type(v) not in {int, float} or not math.isfinite(v) for v in (lat, lon))
        or not -90 <= lat <= 90
        or not -180 <= lon <= 180
    ):
        raise ValueError("invalid solar coordinates or review horizon")
    zone, first = ZoneInfo(timezone), date.fromisoformat(first_date)
    result = []
    for offset in range(days):
        day = first + timedelta(days=offset)
        times = sun(Observer(lat, lon), date=day, tzinfo=zone)
        sunrise, sunset = times["sunrise"], times["sunset"]
        start = (
            (sunrise + timedelta(seconds=59, microseconds=999999))
            .replace(second=0, microsecond=0)
            .strftime("%H:%M")
        )
        end = sunset.replace(second=0, microsecond=0).strftime("%H:%M")
        if clock:
            start, end = max(start, clock[0]), min(end, clock[1])
        if start >= end:
            raise ValueError("solar and source hours have no same-day intersection")
        result.append(
            {
                "date": day.isoformat(),
                "windows": [{"opens": start, "closes": end, "end_day_offset": 0}],
            }
        )
    return result


def native_arrival(profile, bodies):
    """Resolve the exact reviewed node on a drivable way near public parking."""
    nodes, ways, scanned = {}, {}, 0
    for number in profile["ways"]:
        root = ElementTree.fromstring(bodies[f"osm-way-{number}.xml"])
        if root.tag != "osm":
            raise ValueError("native OSM response missing")
        for el in root:
            scanned += 1
            if el.tag == "node":
                nodes[int(el.attrib["id"])] = (float(el.attrib["lat"]), float(el.attrib["lon"]))
            elif el.tag == "way":
                ways[int(el.attrib["id"])] = (
                    [int(n.attrib["ref"]) for n in el.findall("nd")],
                    {t.attrib["k"]: t.attrib["v"] for t in el.findall("tag")},
                )
    refs, tags = ways[profile["road"]]
    parking_refs, parking_tags = ways[profile["parking"]]
    lat, lon = nodes[profile["node"]]
    if (
        profile["node"] not in refs
        or tags.get("highway") not in {"service", "tertiary", "unclassified"}
        or any(tags.get(k) in {"no", "private"} for k in ("access", "vehicle", "motor_vehicle"))
        or parking_tags.get("amenity") != "parking"
        or parking_tags.get("access") in {"no", "private"}
        or any(not math.isfinite(v) for v in (lat, lon))
        or not 32 <= lat <= 35
        or not -119 <= lon <= -116
        or min(distance((lat, lon), nodes[n]) for n in parking_refs) > 75
    ):
        raise ValueError("reviewed native public driving/parking arrival differs")
    return lat, lon, scanned


def prepare(path, manifest=None, *, max_rows=50_000, max_bytes=104_857_600):
    path = Path(path)
    if path.stat().st_size > max_bytes:
        raise ValueError("review exceeds byte ceiling")
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != REVIEW_SHA256:
        raise ValueError("CDFW reviewed identities and source bindings differ")
    review = json.loads(body)
    reader = Reader(path.parent, max_bytes - len(body))
    bodies = {}
    reviewed = datetime.fromisoformat(review["reviewed_at"])
    for name, receipt in review["receipts"].items():
        _receipt(receipt, reader)
        checked = datetime.fromisoformat(receipt["checked_at"])
        if not 0 <= (reviewed - checked).total_seconds() < 86400:
            raise ValueError("review source acquisition freshness differs")
        bodies[name] = reader.read(name, receipt["snapshot_sha256"])
    text = {
        k: " ".join(fromstring(v).text_content().split())
        for k, v in bodies.items()
        if k.endswith(".html")
    }
    if (
        "public domain" not in text["wildlife-terms.html"]
        or "Open Database License" not in text["osm-copyright.html"]
    ):
        raise ValueError("reviewed source rights are missing")
    if any(
        word in text["wildlife-closures.html"].lower()
        for word in ("bolsa chica", "batiquitos", "upper newport")
    ):
        raise ValueError("reserve mentioned in emergency closures; new review required")
    rows, entries, scanned = [], [], 0
    for p in review["profiles"]:
        page = p["page"] + ".html"
        if any(fact not in text[page] for fact in p["checks"]):
            raise ValueError("official trail access/hours evidence differs")
        gis = json.loads(bodies[p["gis"] + ".json"])["features"]
        if (
            len(gis) != 1
            or gis[0]["attributes"]["GlobalID"].strip("{}").lower() != p["global_id"]
            or not gis[0]["attributes"]["ACCESS"].startswith("Open;")
        ):
            raise ValueError("CDFW native property identity/access differs")
        lat, lon, consumed = native_arrival(p, bodies)
        scanned += consumed + 1
        # Reuse the existing native-coordinate road-response validator.
        _, snap = driving_destination(
            {"LOCATION": repr({"latitude": lat, "longitude": lon})},
            {"url": review["receipts"][p["key"] + "-road.json"]["source_url"]},
            bodies[p["key"] + "-road.json"],
        )
        if snap > 75:
            raise ValueError("native destination is too far from the drivable network")
        receipts = [
            review["receipts"][key]
            for key in (
                page,
                p["gis"] + ".json",
                "cdfw-regulations.pdf",
                "wildlife-closures.html",
                f"osm-way-{p['road']}.xml",
                f"osm-way-{p['parking']}.xml",
                p["key"] + "-road.json",
                "wildlife-terms.html",
                "osm-copyright.html",
            )
        ]
        windows = solar_windows(
            lat, lon, review["first_date"], review["days"], review["timezone"], p["clock"]
        )
        calendar = {
            "schema_version": "roadtrips-source-visit-calendar/1",
            "weekly_windows": [],
            "seasons": [],
            "date_overrides": windows,
            "annual_closures": [],
            "fixed_starts": [],
            "source_receipts": receipts,
            "unknown_reasons": [],
        }
        entries.append(
            {
                "source_id": p["source_id"],
                "source_visit_calendar": calendar,
                "source_constraints": [
                    {
                        "rule": "CDFW section 550(c)(2)(C): ordinary visitor access sunrise to sunset; posted closures override access.",
                        "page": 61,
                    },
                    {
                        "component": p["description"],
                        "additional_clock": p["clock"],
                        "bolsa_rule_page": 112 if p["clock"] else None,
                    },
                ],
                "transformation": {
                    "method": "Astral 3.2 sunrise/sunset, zero observer elevation, local timezone; ceil opening and floor closing to minutes, intersect any published fixed hours",
                    "timezone": review["timezone"],
                    "first_date": review["first_date"],
                    "days": review["days"],
                    "coordinates": [lat, lon],
                    "derived_not_published_clock": True,
                    "terrain_and_weather_not_modeled": True,
                },
                "source_attribution": ATTRIBUTION,
            }
        )
        rows.append(
            {
                "source_id": p["source_id"],
                "name": p["name"],
                "latitude": lat,
                "longitude": lon,
                "region": "CA",
                "categories": ["daytime", "nature_reserve", "trailhead", "wildlife_viewing"],
                "address": p["address"],
                "url": review["receipts"][page]["source_url"],
                "source_updated_at": review["receipts"][page]["checked_at"],
                "provenance": [
                    {
                        "dataset": "CDFW/OSM reviewed trail arrival",
                        "review_sha256": REVIEW_SHA256,
                        "source_attribution": ATTRIBUTION,
                        "global_id": p["global_id"],
                        "osm_node": p["node"],
                        "osm_road_way": p["road"],
                        "osm_parking_way": p["parking"],
                        "native_coordinates_unchanged": True,
                        "road_snap_metres": snap,
                        "receipts": receipts,
                    },
                    {
                        "dataset": FACTS_DATASET,
                        "schema_version": FACTS_VERSION,
                        "description": p["description"],
                        "activities": ["Hiking on designated trails", "Wildlife viewing"],
                    },
                    {
                        "dataset": admission.DATASET,
                        "catalog_admission": {
                            "schema_version": admission.SCHEMA,
                            "tier": "T3",
                            "source_id": p["source_id"],
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
