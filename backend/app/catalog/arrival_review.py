"""Explicit current-arrival reviews layered on original licensed Overture rows.

This optional manifest evidence does not replace the source normalizer or permit
arbitrary normalized places. Profiles are added only after inspecting the actual
publisher pages and original venue point. No downloads or database operations.
"""

import json
import math
from collections import Counter
from urllib.parse import urlparse

from app.catalog import expansion_venue_profiles, roadside, venue_profiles

SCHEMA = "roadtrips-arrival-review/1"
PROFILES = {
    "03f811cd-0401-40ad-b75c-1ae7328cf6b7": {
        "profile": "wing-luke/1",
        "name": "Wing Luke Museum",
        "region": "WA",
        "address": "719 S King St",
        "host": "wingluke.org",
        "pages": {
            "https://www.wingluke.org/visit": [
                "719 South King Street",
                "GETTING TO THE MUSEUMBY CAR",
                "museum does not have on-site parking",
                "public pay parking lots",
            ]
        },
        "roads": {"South King Street"},
        "distance_m": 20,
        "primary_category": "museums",
        "arrival_type": "venue frontage at published visitor address",
        "limitations": "No on-site parking; nearby paid lots and metered streets require a walk. Check the museum's current weekly and holiday schedule before travel. Future access and parking availability are unknown.",
    },
    "57193dd5-6aa9-4857-98bc-60e2097c3af0": {
        "profile": "waikiki-aquarium/1",
        "name": "Waikiki Aquarium",
        "region": "HI",
        "address": "2777 Kalakaua Ave",
        "host": "waikikiaquarium.org",
        "pages": {
            "https://www.waikikiaquarium.org/visit/directions-parking/": [
                "2777 Kalakaua Avenue",
                "free parking stalls",
                "Aquarium entrance",
                "Driving from the West",
                "open while undergoing vital renovations",
            ],
            "https://www.waikikiaquarium.org/visit/hours/": [
                "Open daily, 7 days a week",
                "Scheduled Closures",
            ],
        },
        # The checked link is unnamed. Admission relies on the publisher's
        # entrance parking, a small venue and <=10 m driving-destination check;
        # it is not a claim that an unnamed link is Kalakaua Avenue.
        "roads": {"", "Kalakaua Avenue", "Kalākaua Avenue"},
        "distance_m": 10,
        "primary_category": "entertainment",
        "arrival_type": "visitor frontage beside published entrance parking",
        "limitations": "Entrance parking is very limited and visitor-only; street parking is metered. The aquarium reports remaining open during renovations and publishes dated closures and special hours. Check these before travel; future access and parking availability are unknown.",
    },
}
PROFILES.update(venue_profiles.PROFILES)
PROFILES.update(expansion_venue_profiles.PROFILES)


def apply(rows, evidence, *, max_bytes):
    if evidence.get("schema_version") != SCHEMA:
        raise ValueError("unknown arrival-review schema")
    if not rows or len(rows) > len(PROFILES):
        raise ValueError("arrival review requires inspected venue profiles")
    entries = evidence.get("entries")
    if not isinstance(entries, dict) or set(entries) != {r["source_id"] for r in rows}:
        raise ValueError("arrival review must cover exactly the selected source identities")
    size, categories = 0, Counter()
    for row in rows:
        entry = entries[row["source_id"]]
        profile = PROFILES.get(row["source_id"])
        if (
            not profile
            or entry.get("profile") != profile["profile"]
            or row["name"] != profile["name"]
            or row["region"] != profile["region"]
            or not roadside.compact(row["address"]).startswith(roadside.compact(profile["address"]))
            or (urlparse(row["url"]).hostname or "").removeprefix("www.") != profile["host"]
            or (
                "coordinates" in profile
                and [row["latitude"], row["longitude"]] != profile["coordinates"]
            )
        ):
            raise ValueError("arrival review does not match the inspected source venue")
        pages = entry.get("pages", {})
        if set(pages) != set(profile["pages"]):
            raise ValueError("arrival review requires all inspected publisher pages")
        for url, phrases in profile["pages"].items():
            raw = roadside.retained(pages[url], url=url)
            size += len(raw)
            text = roadside.text(raw)
            if roadside.CLOSURE.search(text) or any(
                roadside.compact(phrase) not in roadside.compact(text) for phrase in phrases
            ):
                raise ValueError("publisher access evidence changed or reports closure")
        raw = roadside.retained(entry["driving"])
        size += len(raw)
        checks = [x for x in json.loads(raw) if x.get("source_id") == row["source_id"]]
        if len(checks) != 1:
            raise ValueError("arrival driving-destination evidence missing or ambiguous")
        check = checks[0]
        roadside.checked_time(check["checked_at"])
        distance = check.get("snap_distance_m")
        if (
            check.get("checked_waypoint") != "destination"
            or check.get("http_status") != 200
            or check.get("code") != "Ok"
            or check.get("source_coordinates") != [row["latitude"], row["longitude"]]
            or check.get("road_name") not in profile["roads"]
            or isinstance(distance, bool)
            or not isinstance(distance, (int, float))
            or not math.isfinite(distance)
            or not 0 <= distance <= profile["distance_m"]
        ):
            raise ValueError("arrival point lacks the reviewed driving destination")
        if profile.get("require_raw_driving"):
            raw_response = roadside.retained(entry["raw_driving"])
            size += len(raw_response)
            response = json.loads(raw_response)
            waypoints = response.get("waypoints", [])
            if (
                response.get("code") != "Ok"
                or len(waypoints) != 2
                or waypoints[-1].get("name") != check["road_name"]
                or waypoints[-1].get("distance") != distance
                or check.get("response_sha256") != entry["raw_driving"]["sha256"]
            ):
                raise ValueError("raw venue driving receipt differs from the inspected destination")
        if size > max_bytes:
            raise ValueError("arrival evidence exceeds the aggregate byte ceiling")
        row["provenance"].append(
            {
                "dataset": "Roadtrips current publisher arrival review",
                "record_id": row["source_id"],
                "profile": profile["profile"],
                "publisher_evidence": [
                    {k: pages[url][k] for k in ("url", "sha256", "retrieved_at")}
                    for url in profile["pages"]
                ],
                "checked_at": check["checked_at"],
                "driving_evidence_sha256": entry["driving"]["sha256"],
                "driving_snap_distance_m": distance,
                "driving_road": check["road_name"],
                "coordinate_source": "licensed Overture point; unchanged",
                "arrival_type": profile["arrival_type"],
                "primary_category": profile["primary_category"],
                "limitations": profile["limitations"],
                "opening_hours_imported": False,
            }
        )
        if profile.get("additional_categories"):
            extra = profile["additional_categories"]
            if set(extra) - {"food", "culture", "nightlife"}:
                raise ValueError("unsupported inspected publisher category")
            row["categories"] = sorted(set(row["categories"]) | set(extra))
            row["provenance"][-1]["additional_publisher_categories"] = extra
        if profile.get("require_raw_driving"):
            row["provenance"][-1]["raw_driving_response_sha256"] = entry["raw_driving"]["sha256"]
        categories[profile["primary_category"]] += 1
    return {"bytes": size, "arrival_reviewed": len(rows), "primary_categories": dict(categories)}
