"""Pinned Kaggle park facts with independently reviewed public visitor evidence.

No network or database I/O. A blank source closure year never establishes access.
The immutable review pins every original operator/road/Wikidata receipt and its
component-specific disposition; changed evidence needs another independent review.
"""

import csv
import hashlib
import io
import json
import math
import re
import zipfile
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from lxml import html

from app.catalog import park_visit_calendar

SCHEMA = "kaggle-rideinpark-reviewed-arrivals/1"
SOURCE_URL = "https://www.kaggle.com/datasets/rideinpark/theme-parks-of-the-world/versions/1"
ARCHIVE_SHA256 = "5d611038b0e8ec2c1ed9a75d3e28822e8080eb6f8d6de7c9a0504501c9960059"
METADATA_SHA256 = "34da5c8dc5973ce24b7fbd60c072e36f399252750ba7b04991855492ce2f6bda"
REVIEW_SHA256 = "d133085372caa784c31aa2b6c7b4e86a8c26bee456b3565c1a414db37390b326"
CSV_SHA256 = "6277aac916db10587ad594eb534996cdc388bb24ed9bd96d44aeb1826594ffa8"
CSV_ROWS = 2105
COLUMNS = (
    "wikidata nom_en nom_fr type pays latitude longitude annee_ouverture "
    "annee_fermeture exploitant site_officiel visiteurs_annuels annee_visiteurs "
    "wikipedia_en wikipedia_fr ride_in_park"
).split()
ATTRIBUTION = (
    "Ride in Park, Theme Parks of the World, Kaggle version 1, CC BY 4.0; "
    "filtered to independently reviewed US visitor destinations and normalized. "
    "Wikidata structured-data identity/coordinate corroboration, CC0. "
    "Driving evidence: OSRM and OpenStreetMap contributors / ODbL. "
    "No photographs, reviews, creative descriptions, prices or scheduler hours imported."
)


def now():
    return datetime.now(UTC)


def checked_time(value):
    checked = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if checked.tzinfo is None or not now() - timedelta(days=30) <= checked <= now():
        raise ValueError("park evidence must be genuinely acquired within 30 days")
    return checked.isoformat()


def text(raw):
    document = html.fromstring(raw)
    for element in document.xpath("//script|//style|//noscript"):
        element.drop_tree()
    return " ".join(" ".join(document.itertext()).split())


class Reader:
    """Bound each retained input and count actual unique bytes across the recipe."""

    def __init__(self, ceiling):
        self.ceiling = ceiling
        self.paths = set()
        self.bytes = 0

    def read(self, evidence, *, root=None, ceiling=2 * 1024 * 1024, fresh=True):
        if not isinstance(evidence, dict):
            raise ValueError("park evidence must identify a retained original")
        path = Path(evidence["path"])
        if root is not None:
            if path.is_absolute() or ".." in path.parts or "\\" in evidence["path"]:
                raise ValueError("park review paths must be portable relative paths")
            path = root / path
        if not path.is_file() or not 0 < path.stat().st_size <= ceiling:
            raise ValueError("park evidence missing or oversized")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != evidence["sha256"]:
            raise ValueError("park evidence checksum differs from independent review")
        if fresh:
            checked_time(evidence["retrieved_at"])
        resolved = path.resolve()
        if resolved not in self.paths:
            self.bytes += len(raw)
            self.paths.add(resolved)
            if self.bytes > self.ceiling:
                raise ValueError("park aggregate evidence byte ceiling exceeded")
        return raw


def archive_rows(raw):
    if hashlib.sha256(raw).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("unreviewed Kaggle park archive/version")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if (
            {m.filename for m in members} != {"parcs-du-monde.csv", "parcs-du-monde.json"}
            or len(members) != 2
            or sum(m.file_size for m in members) > 2 * 1024 * 1024
            or any(m.flag_bits & 1 for m in members)
        ):
            raise ValueError("unexpected park archive inventory or decoded byte ceiling")
        csv_raw = archive.read("parcs-du-monde.csv")
    if hashlib.sha256(csv_raw).hexdigest() != CSV_SHA256:
        raise ValueError("park CSV differs from inspected source")
    reader = csv.DictReader(io.StringIO(csv_raw.decode("utf-8-sig")))
    if reader.fieldnames != COLUMNS:
        raise ValueError("unexpected park source schema")
    rows = {}
    for count, row in enumerate(reader, 1):
        if count > CSV_ROWS or not re.fullmatch(r"Q[1-9][0-9]*", row["wikidata"]):
            raise ValueError("park source row ceiling or native identity is invalid")
        if row["wikidata"] in rows:
            raise ValueError("duplicate native park identity")
        rows[row["wikidata"]] = row
    if len(rows) != CSV_ROWS:
        raise ValueError("park source row count differs from pinned version")
    return rows


def access_allowed(rule, pages):
    """Admission-date gate, separate from unknown future scheduler intervals."""
    today = now().date()
    kind = rule["kind"]
    if kind == "daily":
        return
    if kind == "weekdays" and today.weekday() in rule["days"]:
        return
    if kind == "snapshot-day" and today.isoformat() == rule["date"]:
        return
    if kind == "date-range" and rule["start"] <= today.isoformat() <= rule["end"]:
        return
    if kind == "belmont-calendar":
        dated = []
        for page, raw in pages:
            if page["url"] == "https://www.belmontpark.com/park-hours":
                document = html.fromstring(raw)
                dated.extend(
                    document.xpath(
                        "//div[@data-date=$day]/@data-hours", day=today.strftime("%m/%d/%Y")
                    )
                )
        if dated and all(re.fullmatch(r"[0-9:apm\s]+ - [0-9:apm\s]+", x) for x in dated):
            return
    raise ValueError("park current day/season lacks reviewed positive visitor access")


def wiki_identity(raw, qid, lat, lon):
    entity = json.loads(raw).get("entities", {}).get(qid)
    if not entity or entity.get("id") != qid:
        raise ValueError("park Wikidata native identity missing")
    claims = entity.get("claims", {})
    # No missing-closing-year inference: these are independent negative vetoes.
    if claims.get("P576") or claims.get("P3999"):
        raise ValueError("park Wikidata reports dissolution/permanent closure")
    points = [
        claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        for claim in claims.get("P625", [])
    ]
    if not any(
        isinstance(point, dict)
        and point.get("globe") == "http://www.wikidata.org/entity/Q2"
        and isinstance(point.get("latitude"), (int, float))
        and isinstance(point.get("longitude"), (int, float))
        and math.hypot(
            (lat - point["latitude"]) * 111_195,
            (lon - point["longitude"]) * 111_195 * math.cos(math.radians(lat)),
        )
        <= 2
        for point in points
    ):
        raise ValueError("Kaggle native park point differs from structured upstream")
    return entity.get("lastrevid")


def driving(raw, evidence, lat, lon):
    url = urlsplit(evidence["url"])
    expected = f"/route/v1/driving/{lon + 0.002},{lat + 0.002};{lon},{lat}"
    if (
        url.scheme != "https"
        or url.netloc != "router.project-osrm.org"
        or url.path != expected
        or url.query != "overview=false&steps=false"
    ):
        raise ValueError("park driving query is not the unchanged native destination")
    response = json.loads(raw)
    points = response.get("waypoints", [])
    if response.get("code") != "Ok" or len(points) != 2 or not response.get("routes"):
        raise ValueError("park raw destination route did not succeed")
    destination = points[-1]
    distance = destination.get("distance")
    location = destination.get("location")
    if (
        isinstance(distance, bool)
        or not isinstance(distance, (int, float))
        or not math.isfinite(distance)
        or not 0 <= distance <= 75
        or not isinstance(location, list)
        or len(location) != 2
        or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in location)
        or any(not math.isfinite(v) for v in location)
    ):
        raise ValueError("park native point lacks bounded real driving destination")
    return distance, destination.get("name", "")


def geometry_distance(lat, lon, geometry):
    """Local metre distance and polygon containment; geometry is evidence only."""
    points = [
        ((p["lon"] - lon) * 111_195 * math.cos(math.radians(lat)), (p["lat"] - lat) * 111_195)
        for p in geometry
    ]
    best, inside = math.inf, False
    for (ax, ay), (bx, by) in zip(points, points[1:]):
        if (ay > 0) != (by > 0) and 0 < ax + (bx - ax) * (-ay) / (by - ay):
            inside = not inside
        denominator = (bx - ax) ** 2 + (by - ay) ** 2
        fraction = (
            max(0, min(1, (-ax * (bx - ax) - ay * (by - ay)) / denominator)) if denominator else 0
        )
        best = min(best, math.hypot(ax + fraction * (bx - ax), ay + fraction * (by - ay)))
    return best, inside


def public_arrival(profile, road_raw, roads, features, pages, lat, lon):
    """A car snap on a service/private/interior road is not visitor access proof."""
    proof = profile["arrival_review"]
    road = roads.get(proof["road_way_id"])
    if not road or road.get("type") != "way":
        raise ValueError("park practical arrival road missing from reviewed source")
    tags = road.get("tags", {})
    forbidden = {"private", "no", "delivery", "agricultural", "forestry"}
    if (
        tags.get("highway")
        not in {
            "service",
            "residential",
            "unclassified",
            "primary",
            "secondary",
            "tertiary",
            "trunk",
        }
        or any(
            tags.get(key) in forbidden for key in ("access", "motor_vehicle", "motorcar", "vehicle")
        )
        or float(tags.get("layer", 0)) < 0
        or geometry_distance(lat, lon, road["geometry"])[0] > 75
    ):
        raise ValueError("park practical arrival road is private, internal-only or unsuitable")
    snap = json.loads(road_raw)["waypoints"][-1]["location"]
    if geometry_distance(snap[1], snap[0], road["geometry"])[0] > 3:
        raise ValueError("park public arrival proof differs from actual snapped destination road")
    method = proof["method"]
    parking_id = proof.get("parking_way_id")
    if parking_id is not None:
        parking = features.get(parking_id, {})
        ptags = parking.get("tags", {})
        distance, contains = geometry_distance(lat, lon, parking.get("geometry", []))
        if (
            ptags.get("amenity") != "parking"
            or ptags.get("access") in forbidden
            or (not contains and distance > 75)
        ):
            raise ValueError("park practical arrival lacks reviewed guest parking")
        if method == "public-parking" and not contains:
            raise ValueError("park native point is outside the reviewed public guest parking")
    elif method in {"public-parking", "visitor-parking-frontage"}:
        raise ValueError("park practical arrival parking identity missing")
    if method == "public-street-frontage":
        if tags.get("highway") == "service" or not tags.get("name"):
            raise ValueError("park street frontage cannot use an unnamed internal service road")
    elif method == "visitor-building-frontage":
        building = features.get(proof.get("building_way_id"), {})
        if (
            not building.get("tags", {}).get("building")
            or not geometry_distance(lat, lon, building.get("geometry", []))[1]
        ):
            raise ValueError("park native point is not at the reviewed visitor building")
        entrance_id = proof.get("entrance_node_id")
        if entrance_id:
            entrance = features.get(entrance_id, {})
            if (
                entrance.get("tags", {}).get("entrance") != "main"
                or math.hypot(
                    (lat - entrance["lat"]) * 111_195,
                    (lon - entrance["lon"]) * 111_195 * math.cos(math.radians(lat)),
                )
                > 40
            ):
                raise ValueError("park visitor building lacks its reviewed public main entrance")
        elif not proof["operator_map_evidence"]:
            raise ValueError("park visitor building requires its reviewed operator entrance map")
    elif method == "public-entry-frontage":
        # Parse the operator-published place marker, without calling Google.
        markers = []
        for _, raw in pages:
            for link in html.fromstring(raw).xpath("//a/@href"):
                markers.extend(
                    (float(a), float(b))
                    for a, b in re.findall(r"!3d(-?[0-9.]+)!4d(-?[0-9.]+)", link)
                )
        if not proof["operator_map_evidence"] or not any(
            math.hypot((lat - a) * 111_195, (lon - b) * 111_195 * math.cos(math.radians(lat))) <= 75
            for a, b in markers
        ):
            raise ValueError("park public entry lacks operator coordinate and entrance-map binding")
    elif method not in {"public-parking", "visitor-parking-frontage"}:
        raise ValueError("unreviewed park practical arrival method")
    return {
        "method": method,
        "road_way_id": road["id"],
        "assessment": proof["assessment"],
        "coordinate_replaced": False,
        "evidence_attribution": "OpenStreetMap contributors / ODbL; separate current operator directions and maps",
        "osm_elements": [
            {
                "source_snapshot": snapshot,
                "type": kind,
                "id": proof[field],
                "role": role,
                "source_url": f"https://www.openstreetmap.org/{kind}/{proof[field]}",
            }
            for field, snapshot, kind, role in (
                ("road_way_id", "roads", "way", "arrival-road"),
                ("parking_way_id", "features", "way", "visitor-parking"),
                ("building_way_id", "features", "way", "visitor-building"),
                ("entrance_node_id", "features", "node", "main-visitor-entrance"),
            )
            if proof.get(field) is not None
        ],
    }


def prepare(path, manifest, *, max_rows, max_bytes):
    if (
        manifest.get("schema_version") != SCHEMA
        or manifest.get("source_url") != SOURCE_URL
        or manifest.get("attribution") != ATTRIBUTION
        or not re.fullmatch(
            r"kaggle-rideinpark-v1\+review-\d{4}-\d{2}-\d{2}", manifest.get("release", "")
        )
        or set(manifest.get("licenses", {})) != {"CC-BY-4.0", "CC0-1.0", "ODbL-1.0"}
        or not 0 < max_rows <= 50_000
        or not 0 < max_bytes <= 100 * 1024 * 1024
    ):
        raise ValueError("park manifest requires reviewed pinned source/rights/bounds")
    checked_time(manifest["retrieved_at"])
    path = Path(path)
    reader = Reader(max_bytes)
    bundle_raw = reader.read(
        {"path": str(path), "sha256": manifest["sha256"]}, fresh=False, ceiling=32_768
    )
    bundle = json.loads(bundle_raw)
    archive_raw = reader.read(bundle["archive"], ceiling=1024 * 1024)
    source = archive_rows(archive_raw)
    metadata_raw = reader.read(bundle["metadata"])
    metadata = json.loads(metadata_raw)
    if (
        hashlib.sha256(metadata_raw).hexdigest() != METADATA_SHA256
        or metadata.get("ref") != "rideinpark/theme-parks-of-the-world"
        or metadata.get("currentVersionNumber") != 1
        or metadata.get("licenseName") != "Attribution 4.0 International (CC BY 4.0)"
    ):
        raise ValueError("park publisher/source rights metadata differs from review")
    review_raw = reader.read(bundle["review"], ceiling=4 * 1024 * 1024)
    if hashlib.sha256(review_raw).hexdigest() != REVIEW_SHA256:
        raise ValueError("park independent review fingerprint differs")
    review = json.loads(review_raw)
    if (
        review.get("schema_version") != "roadtrips-rideinpark-review/1"
        or review.get("source_url") != SOURCE_URL
    ):
        raise ValueError("park review schema/source differs")
    checked_time(review["reviewed_at"])
    root = Path(bundle["review"]["path"]).parent
    profiles = review["records"]
    if not 1 <= len(profiles) <= max_rows or len({p["qid"] for p in profiles}) != len(profiles):
        raise ValueError("park reviewed selection is empty, duplicated or exceeds row bound")
    arrival_sources = {
        key: {
            element["id"]: element
            for element in json.loads(reader.read(evidence, root=root))["elements"]
        }
        for key, evidence in review["arrival_evidence"].items()
    }
    rows = []
    for profile in profiles:
        qid = profile["qid"]
        original = source.get(qid)
        if (
            not original
            or original != profile["source_row"]
            or original["pays"] != "US"
            or original["annee_fermeture"]
        ):
            raise ValueError("park native source identity/facts/closure differ from review")
        lat, lon = float(original["latitude"]), float(original["longitude"])
        if (
            not all(map(math.isfinite, (lat, lon)))
            or not -90 <= lat <= 90
            or not -180 <= lon <= 180
        ):
            raise ValueError("park native coordinates invalid")
        pages, access = [], []
        for page in profile["pages"]:
            if urlsplit(page["url"]).scheme != "https":
                raise ValueError("park operator evidence requires reviewed HTTPS publisher")
            raw = reader.read(page, root=root)
            visible = text(raw)
            if not page["required_facts"] or any(
                fact not in visible for fact in page["required_facts"]
            ):
                raise ValueError("park positive identity/access or restriction fact missing")
            pages.append((page, raw))
            access.append(
                {
                    "source_url": page["url"],
                    "snapshot_sha256": page["sha256"],
                    "checked_at": page["retrieved_at"],
                    "restrictions": page["restrictions"],
                }
            )
        access_allowed(profile["access_rule"], pages)
        wiki_raw = reader.read(profile["wikidata"], root=root)
        revision = wiki_identity(wiki_raw, qid, lat, lon)
        road_raw = reader.read(profile["driving"], root=root, ceiling=262_144)
        distance, road_name = driving(road_raw, profile["driving"], lat, lon)
        for evidence in profile["arrival_review"]["operator_map_evidence"]:
            reader.read(evidence, root=root)
        practical = public_arrival(
            profile,
            road_raw,
            arrival_sources["roads"],
            arrival_sources["features"],
            pages,
            lat,
            lon,
        )
        provenance = [
            {
                "dataset": "Ride in Park Kaggle Theme Parks of the World",
                "source_url": SOURCE_URL,
                "record_id": qid,
                "release": "1",
                "license": "CC-BY-4.0",
                "archive_sha256": ARCHIVE_SHA256,
                "source_csv_sha256": CSV_SHA256,
                "source_coordinates": [lat, lon],
                "original_category": original["type"],
                "original_closing_year": original["annee_fermeture"] or None,
                "changes": "US filtering, independent access admission and explicit category mapping; native identity, name and coordinates unchanged",
            },
            {
                "dataset": "Wikidata structured identity/coordinate corroboration",
                "source_url": profile["wikidata"]["url"],
                "record_id": qid,
                "license": "CC0-1.0",
                "snapshot_sha256": profile["wikidata"]["sha256"],
                "revision": revision,
                "checked_at": profile["wikidata"]["retrieved_at"],
                "coordinate_replaced": False,
            },
            {
                "dataset": "Independently reviewed park operator visitor evidence",
                "record_id": qid,
                "primary_category": profile["primary_category"],
                "source_facts": access,
                "arrival_type": profile["arrival_type"],
                "practical_arrival": practical,
                "parking": profile["parking"],
                "opening_hours_imported": False,
                "opening_intervals": None,
                "source_visit_calendar": park_visit_calendar.build(profile, pages),
                "prices_imported": False,
                "future_availability": "unknown",
                "review_sha256": REVIEW_SHA256,
                "admission_date": now().date().isoformat(),
            },
            {
                "dataset": "OSRM driving destination proof",
                "source_url": profile["driving"]["url"],
                "snapshot_sha256": profile["driving"]["sha256"],
                "checked_at": profile["driving"]["retrieved_at"],
                "destination_role": "destination",
                "source_coordinates": [lat, lon],
                "snap_distance_m": distance,
                "road_name": road_name,
                "source_point_replaced": False,
                "attribution": "OSRM; OpenStreetMap contributors / ODbL",
            },
            {
                "dataset": "OpenStreetMap practical visitor arrival corroboration",
                "source_url": "https://www.openstreetmap.org/copyright",
                "license": "ODbL-1.0",
                "license_url": "https://opendatacommons.org/licenses/odbl/1-0/",
                "attribution": "OpenStreetMap contributors",
                "elements": practical["osm_elements"],
                "source_snapshots": {
                    key: {
                        "source_url": receipt["url"],
                        "snapshot_sha256": receipt["sha256"],
                        "checked_at": receipt["retrieved_at"],
                    }
                    for key, receipt in review["arrival_evidence"].items()
                },
                "changes": "Selected arrival-road, guest-parking, visitor-building and main-entrance facts; native OSM identity, tags and geometry unchanged",
                "coordinate_replaced": False,
            },
        ]
        rows.append(
            {
                "source_id": "wikidata-park:" + qid,
                "name": original["nom_en"],
                "latitude": lat,
                "longitude": lon,
                "region": profile["region"],
                "categories": profile["categories"],
                "address": profile["address"],
                "url": profile["public_url"],
                "source_updated_at": None,
                "provenance": provenance,
            }
        )
    dispositions = review["source_dispositions"]
    return rows, {
        "scanned": CSV_ROWS,
        "accepted": len(rows),
        "bytes": reader.bytes,
        "primary_categories": dict(Counter(p["primary_category"] for p in profiles)),
        "regions": dict(Counter(p["region"] for p in profiles)),
        "visit_calendars": {
            "supported": sum(
                not row["provenance"][2]["source_visit_calendar"]["unknown_reasons"] for row in rows
            ),
            "unknown": sum(
                bool(row["provenance"][2]["source_visit_calendar"]["unknown_reasons"])
                for row in rows
            ),
            "records": [
                {
                    "source_id": row["source_id"],
                    "unknown_reasons": row["provenance"][2]["source_visit_calendar"][
                        "unknown_reasons"
                    ],
                    "weekly_windows": len(
                        row["provenance"][2]["source_visit_calendar"]["weekly_windows"]
                    ),
                    "date_overrides": len(
                        row["provenance"][2]["source_visit_calendar"]["date_overrides"]
                    ),
                }
                for row in rows
            ],
        },
        "rejects": dict(
            Counter(
                d["disposition"]
                for d in dispositions
                if d["disposition"] != "selected_current_visitor_evidence"
            )
        ),
        "source_dispositions": dispositions,
        "reviewed_holds": review.get("holds", {}),
        "adjacent_destination_review": review.get("adjacent_destination_review"),
        "public_arrival_methods": dict(Counter(p["arrival_review"]["method"] for p in profiles)),
    }
