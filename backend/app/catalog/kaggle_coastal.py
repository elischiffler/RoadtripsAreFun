"""Bounded offline admission of pinned Kaggle Chicago public shore destinations.

This subsequent artifact does not modify the frozen cultural adapter. It keeps
native Kaggle beach coordinates and resolves official GIS identities without
substituting points. The selected component is shore access, never swimming.
"""

from __future__ import annotations

import ast
import csv
import io
import json
import math
import zipfile
from collections import Counter
from itertools import pairwise
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from xml.etree import ElementTree

from app.catalog.kaggle_cultural import (
    Reader as CulturalReader,
)
from app.catalog.kaggle_cultural import (
    _receipt,
    canonical_rows_digest,
    digest,
    distance,
    osm_elements,
    plain,
)
from app.catalog.kaggle_parks import geometry_distance
from app.routing.visit_calendar import Calendar

SCHEMA = "roadtrips-kaggle-coastal-admission/2"
REVIEW_SHA256 = "83b60b1ed03441689a8e178aa5b1cde66ee49bb8675d4c444592ead5ba3acffd"
ARCHIVE_SHA256 = "236b91c5d636d353720523ceeea860551474a35458d96c9750ca9dd5c333949b"
CSV_SHA256 = "488320a50e44b1cfb762a8463ce0e19d35390570721881a335fd7cf7211de45c"
REF = "chicago/chicago-parks-locations,-facilities-features"
VERSION = 15
MEMBER = "parks-facilities-features-deprecated-november-2016.csv"
BASELINE_COUNT = 576
BASELINE_ROWS_SHA256 = "003ddd7c72307f6844af11ff1df970bfb791f67dda57b143ca317c7f0c501a71"
MAX_ROWS, MAX_BYTES = 50_000, 104_857_600
BEACH_ACCESS = "The beach is open from 6 am to 11 pm, but swimming is only permitted during the beach season when lifeguards are on duty from 11 am to 7 pm, in designated swim areas."
SWIM_SEASON = "The beach season runs from the Friday before Memorial Day, through Labor Day."
CLOSED_SWIM = "The 2026 swim season at Chicago's beaches has ended. No lifeguards are present. Swimming is strictly prohibited."
TRAIL_ALERT = "Please be alert and safe, and avoid these active construction work zones."
WEEKDAYS = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
]


class Reader(CulturalReader):
    """Enforce the aggregate budget before inheriting the receipt validation."""

    def read(self, evidence, *, fresh=True, ceiling=2 * 1024 * 1024):
        if not isinstance(evidence, dict) or not isinstance(evidence.get("path"), str):
            raise ValueError("coastal evidence requires a retained relative path")
        path = (self.root / evidence["path"]).resolve()
        if self.root not in path.parents or not path.is_file():
            raise ValueError("coastal evidence missing or outside portable relative source root")
        if path not in self.paths and self.bytes + path.stat().st_size > self.ceiling:
            raise ValueError("coastal aggregate input byte ceiling exceeded before read")
        return super().read(evidence, fresh=fresh, ceiling=ceiling)


def source_point(row):
    value = ast.literal_eval(row["LOCATION"])
    lat, lon = float(value["latitude"]), float(value["longitude"])
    if (
        not math.isfinite(lat)
        or not math.isfinite(lon)
        or not 24 <= lat <= 50
        or not -126 <= lon <= -66
    ):
        raise ValueError("invalid unchanged native beach coordinate")
    return lat, lon


def source_rows(raw):
    if digest(raw) != ARCHIVE_SHA256:
        raise ValueError("coastal Kaggle archive/version fingerprint differs")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members = z.infolist()
        if (
            len({m.filename for m in members}) != len(members)
            or any(
                m.flag_bits & 1
                or m.file_size > 20 * 1024 * 1024
                or Path(m.filename).is_absolute()
                or ".." in Path(m.filename).parts
                for m in members
            )
            or sum(m.file_size for m in members) > 20 * 1024 * 1024
        ):
            raise ValueError("coastal archive inventory or decoded bounds differ")
        data = z.read(MEMBER)
        metadata = json.loads(
            z.read("socrata_metadata_parks-facilities-features-deprecated-november-2016.json")
        )
        other = list(
            csv.DictReader(
                io.StringIO(
                    z.read("parks-locations-deprecated-november-2016.csv").decode("utf-8-sig")
                )
            )
        )
    if (
        digest(data) != CSV_SHA256
        or metadata.get("id") != "y7qa-tvqx"
        or metadata.get("licenseId") != "PUBLIC_DOMAIN"
        or metadata.get("provenance") != "official"
    ):
        raise ValueError("coastal native CSV/upstream factual public-domain grant differs")
    parser = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
    if parser.fieldnames != [
        "PARK",
        "PARK NUMBER",
        "FACILITY NAME",
        "FACILITY TYPE",
        "X COORDINATE",
        "Y COORDINATE",
        "LOCATION",
    ]:
        raise ValueError("coastal native schema differs")
    rows = list(parser)
    if len(rows) != 4152 or len(other) != 581:
        raise ValueError("coastal pinned source record count differs")
    return {f"chi-facility-{i}": row for i, row in enumerate(rows)}, other


def in_polygon(lon, lat, geometry):
    if len(geometry) < 4 or geometry[0] != geometry[-1]:
        return False
    inside = False
    for a, b in pairwise(geometry):
        x, y, xx, yy = a["lon"], a["lat"], b["lon"], b["lat"]
        if (y > lat) != (yy > lat) and lon < (xx - x) * (lat - y) / (yy - y) + x:
            inside = not inside
    return inside


def driving_destination(row, evidence, raw):
    lat, lon = source_point(row)
    url = urlsplit(evidence["url"])
    if (
        url.scheme != "https"
        or url.netloc != "router.project-osrm.org"
        or url.path != f"/route/v1/driving/{lon + 0.002},{lat + 0.002};{lon},{lat}"
        or url.query != "overview=false&steps=false"
    ):
        raise ValueError("coastal driving query does not target unchanged native point")
    result = json.loads(raw)
    if (
        result.get("code") != "Ok"
        or not result.get("routes")
        or len(result.get("waypoints", [])) != 2
    ):
        raise ValueError("coastal actual destination route failed")
    target = result["waypoints"][-1]
    point, metres = target.get("location"), target.get("distance")
    if (
        type(metres) not in {int, float}
        or not math.isfinite(metres)
        or metres < 0
        or not isinstance(point, list)
        or len(point) != 2
        or any(type(v) not in {int, float} or not math.isfinite(v) for v in point)
    ):
        raise ValueError("coastal destination snap is malformed")
    actual = distance((lat, lon), (point[1], point[0]))
    if abs(actual - metres) > 2:
        raise ValueError("coastal measured snap distance disagrees with native coordinate")
    return target, actual


def calendar_for(profile, beach, parent, global_page):
    beach_text, parent_text, global_text = map(plain, [beach, parent, global_page])
    if (
        BEACH_ACCESS not in beach_text
        or SWIM_SEASON not in beach_text
        or CLOSED_SWIM not in global_text
        or TRAIL_ALERT not in global_text
    ):
        raise ValueError("coastal shore/swim season/access facts differ")
    if any(f"{day}: 6:00 am-11:00 pm" not in parent_text for day in WEEKDAYS):
        raise ValueError(
            "coastal parent park does not independently corroborate daily shore clocks"
        )
    if (
        "The entire beach area is off-limits." in beach_text
        or "is closed indefinitely" in beach_text
        or "The entire park area is off-limits." in parent_text
        or "The park is closed indefinitely" in parent_text
    ):
        raise ValueError("coastal beach closure vetoes parent park hours")
    if profile["name"] not in beach_text or any(
        fact not in beach_text for fact in profile["arrival"]["operator_facts"]
    ):
        raise ValueError("coastal current visitor identity/parking/location is absent")
    if (
        profile["source_row"]["PARK"] == "COLUMBIA BEACH"
        and "renamed Columbia Beach Park in honor of Helen Doria" not in beach_text
    ):
        raise ValueError("coastal changed public name lacks explicit old/new identity evidence")
    if profile["source_row"]["PARK"] == "JARVIS (R.J.) BEACH" and "Jarvis Beach" not in beach_text:
        raise ValueError("coastal renamed Jarvis feature lacks its source-bound identity evidence")
    calendar = {
        "schema_version": "roadtrips-source-visit-calendar/1",
        "weekly_windows": [
            {
                "weekdays": [0, 1, 2, 3, 4, 5, 6],
                "opens": "06:00",
                "closes": "23:00",
                "end_day_offset": 0,
            }
        ],
        "seasons": [],
        "date_overrides": [],
        "annual_closures": [],
        "fixed_starts": [],
        "source_receipts": [
            _receipt(
                profile["beach"],
                extraction="visible Facility Hours explanatory paragraph: beach access independent of swimming",
            ),
            _receipt(profile["parent"], extraction="Park Hours, Sunday through Saturday"),
        ],
        "unknown_reasons": [],
    }
    Calendar.model_validate(calendar)
    return calendar


def arrival_for(profile, row, beach, route_raw, map_raw):
    lat, lon = source_point(row)
    target, actual = driving_destination(row, profile["driving"], route_raw)
    if target["distance"] > 75 or actual > 75:
        raise ValueError("coastal actual native destination exceeds 75 m")
    elements = osm_elements(map_raw)
    proof = profile["arrival"]
    road = elements.get(("way", proof["road_way_id"]))
    if not road:
        raise ValueError("coastal actual snapped road absent from original OSM")
    tags = road["tags"]
    forbidden = {"private", "no", "delivery", "agricultural", "forestry"}
    if (
        tags.get("highway") not in {"residential", "unclassified", "tertiary", "service"}
        or any(tags.get(k) in forbidden for k in ["access", "vehicle", "motor_vehicle", "motorcar"])
        or tags.get("tunnel") in {"yes", "building_passage"}
        or float(tags.get("layer", "0")) < 0
    ):
        raise ValueError("coastal road has incompatible visitor vehicle access")
    x, y = target["location"]
    if (
        geometry_distance(y, x, road["geometry"])[0] > 3
        or geometry_distance(lat, lon, road["geometry"])[0] > 75
    ):
        raise ValueError("coastal original map does not bind actual destination road")
    if not proof["operator_facts"] or any(
        fact not in plain(beach) for fact in proof["operator_facts"]
    ):
        raise ValueError("coastal public parking/directions missing")
    selected = [road]
    method = proof["method"]
    if method == "public-street":
        if (
            tags["highway"] == "service"
            or tags.get("name") != target.get("name")
            or tags.get("name") != proof["connecting_public_street"]
        ):
            raise ValueError("coastal public street frontage is not the documented named street")
    elif method in {"public-park-drive", "public-paid-parking"}:
        park = elements.get(("way", proof["public_park_way_id"]))
        if (
            not park
            or park["tags"].get("leisure") != "park"
            or park["tags"].get("operator") != "Chicago Park District"
            or park["tags"].get("operator:type") != "public"
            or not in_polygon(x, y, park["geometry"])
        ):
            raise ValueError("coastal internal arrival is not within the documented public park")
        selected.append(park)
        if method == "public-park-drive":
            roads = [
                e
                for e in elements.values()
                if e["type"] == "way"
                and e["tags"].get("highway") in {"residential", "unclassified", "tertiary"}
                and e["tags"].get("name") == proof["connecting_public_street"]
                and not any(
                    e["tags"].get(k) in forbidden
                    for k in ["access", "vehicle", "motor_vehicle", "motorcar"]
                )
                and any(a == b for a in e["geometry"] for b in road["geometry"])
            ]
            if len(roads) != 1 or any(
                tags.get(k) in {"customers", "destination", "permit"}
                for k in ["access", "vehicle", "motor_vehicle", "motorcar"]
            ):
                raise ValueError(
                    "coastal public park drive has no unique documented public street connection"
                )
            selected.extend(roads)
        parking_id = proof.get("parking_way_id")
        if parking_id:
            parking = elements.get(("way", parking_id))
            if (
                not parking
                or parking["tags"].get("amenity") != "parking"
                or any(
                    parking["tags"].get(k) in forbidden
                    for k in ["access", "vehicle", "motor_vehicle", "motorcar"]
                )
                or not in_polygon(x, y, parking["geometry"])
            ):
                raise ValueError("coastal arrival is not within permissible mapped visitor parking")
            selected.append(parking)
        if method == "public-paid-parking" and (
            not parking_id
            or parking["tags"].get("access") != "yes"
            or parking["tags"].get("fee") != "yes"
            or parking["tags"].get("opening_hours") != "Mo-Su 06:00-23:00"
            or tags.get("opening_hours") != "Mo-Su 06:00-23:00"
            or "Parking Pay & display parking" not in plain(beach)
        ):
            raise ValueError(
                "coastal customer parking lacks source-bound paid public access/clocks"
            )
    else:
        raise ValueError("unsupported coastal arrival proof")
    return {
        "method": method,
        "road_way_id": road["id"],
        "destination_distance_m": target["distance"],
        "actual_geometry_distance_m": actual,
        "coordinate_replaced": False,
        "parking_availability": "unknown",
        "parking_price": "unknown",
        "operator_facts": proof["operator_facts"],
    }, selected


def prepare(
    path: str | Path,
    manifest: dict[str, Any] | None = None,
    *,
    max_rows: int = MAX_ROWS,
    max_bytes: int = MAX_BYTES,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Replay all pinned source rows against the complete immutable parent offline."""
    if (
        type(max_rows) is not int
        or type(max_bytes) is not int
        or not 0 < max_rows <= MAX_ROWS
        or not 0 < max_bytes <= MAX_BYTES
    ):
        raise ValueError("coastal import ceilings cannot be raised")
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= min(256 * 1024, max_bytes):
        raise ValueError("coastal review missing or exceeds configuration byte ceiling")
    raw = path.read_bytes()
    if not 0 < len(raw) <= 256 * 1024 or digest(raw) != REVIEW_SHA256:
        raise ValueError("coastal review fingerprint differs")
    if manifest is not None and manifest != {
        "schema_version": SCHEMA,
        "sha256": REVIEW_SHA256,
    }:
        raise ValueError("coastal manifest does not bind exact reviewed source admission")
    review = json.loads(raw)
    if review.get("schema_version") != SCHEMA:
        raise ValueError("coastal review schema differs")
    reader = Reader(path.parent, max_bytes)
    reader.paths.add(path.resolve())
    reader.bytes = len(raw)
    baseline_raw = reader.read(review["baseline"], fresh=False, ceiling=8 * 1024 * 1024)
    baseline = json.loads(baseline_raw)
    if (
        not isinstance(baseline, list)
        or len(baseline) != BASELINE_COUNT
        or len({row["source_id"] for row in baseline}) != BASELINE_COUNT
        or canonical_rows_digest(baseline) != BASELINE_ROWS_SHA256
        or review.get("parent_binding")
        != {
            "rows": BASELINE_COUNT,
            "normalized_rows_sha256": BASELINE_ROWS_SHA256,
        }
    ):
        raise ValueError("coastal requires full immutable preserved 576 parent")
    original, other_rows = source_rows(
        reader.read(review["archive"], fresh=False, ceiling=20 * 1024 * 1024)
    )
    if len(original) + len(other_rows) > max_rows:
        raise ValueError("coastal scanned primary archive row ceiling exceeded")
    metadata = json.loads(reader.read(review["metadata"]))
    if (
        metadata.get("ref") != REF
        or metadata.get("currentVersionNumber") != VERSION
        or metadata.get("licenseName") != "CC0: Public Domain"
    ):
        raise ValueError("coastal official Kaggle publisher/version differs")
    for key, identity in [
        ("source_metadata", "y7qa-tvqx"),
        ("canonical_metadata", "eix4-gf83"),
    ]:
        meta = json.loads(reader.read(review[key]))
        if (
            meta.get("id") != identity
            or meta.get("provenance") != "official"
            or meta.get("licenseId") != "PUBLIC_DOMAIN"
            or meta.get("attribution") != "Chicago Park District"
        ):
            raise ValueError("coastal primary factual public-domain rights differ")
    reader.read(review["odbl"], fresh=False)
    canonical = json.loads(reader.read(review["canonical"]))
    global_raw = reader.read(review["global_beaches"])
    profiles = {p["source_key"]: p for p in review["profiles"]}
    if len(profiles) != len(review["profiles"]):
        raise ValueError("duplicate coastal selected native record")
    closed = {h["source_key"]: h for h in review["closure_holds"]}
    for key, hold in closed.items():
        if key in profiles or hold["literal"] not in plain(reader.read(hold["evidence"])):
            raise ValueError("coastal explicit current beach closure cannot be overridden")
    probes = {p["key"]: p for p in review["road_probes"]}
    beaches = {key: row for key, row in original.items() if row["FACILITY NAME"] == "BEACH"}
    if len(beaches) != 27 or set(probes) != set(beaches) or set(profiles) - set(beaches):
        raise ValueError("coastal complete native beach pool/probe ledger differs")
    arrival_holds = {}
    for hold in review.get("arrival_holds", []):
        key = hold["source_key"]
        if key not in beaches or key in profiles or key in arrival_holds:
            raise ValueError("coastal incompatible-road hold identity differs")
        target, _ = driving_destination(
            beaches[key],
            probes[key]["receipt"],
            reader.read(probes[key]["receipt"], ceiling=262144),
        )
        elements = osm_elements(reader.read(hold["map"]))
        road = elements.get(("way", hold["road_way_id"]))
        if (
            not road
            or road["tags"].get("highway")
            not in {"motorway", "motorway_link", "trunk", "trunk_link"}
            or geometry_distance(target["location"][1], target["location"][0], road["geometry"])[0]
            > 3
            or hold["name"] not in plain(reader.read(hold["beach"]))
        ):
            raise ValueError("coastal held route lacks its actual incompatible-road proof")
        arrival_holds[key] = hold
    rows, calendars, ledger, public, aux_counts = [], [], [], {}, {}
    for key, row in original.items():
        if key not in beaches:
            ledger.append(
                {
                    "source_key": key,
                    "status": "hold",
                    "reason": "Native facility type is not BEACH; no unrelated park facility filler.",
                }
            )
            continue
        probe = probes[key]
        if probe["source_row"] != row:
            raise ValueError("coastal raw road probe targets another native source row")
        target, actual = driving_destination(
            row, probe["receipt"], reader.read(probe["receipt"], ceiling=262144)
        )
        if key not in profiles:
            reason = (
                closed[key]["reason"]
                if key in closed
                else "No complete approved public arrival/current component calendar combination in this bounded pilot."
            )
            if target["distance"] > 75 or actual > 75:
                reason = "Actual unchanged native driving destination exceeds 75 m; no coordinate replacement."
            if row["PARK NUMBER"] == "1265" and key != "chi-facility-1676":
                reason = "Earlier alternate Lane feature is absent within 0.2 m from current canonical registry and overlaps selected unchanged GISOBJID 2965; held duplicate, not relocated."
            if row["PARK NUMBER"] == "1248":
                reason = "Hartigan shares nearby shore/campus with selected Doria within 250 m; its actual service-alley arrival also lacks selected documented parking proof."
            if key in arrival_holds:
                reason = "Actual unchanged native route ends on a motorway ramp, not a practical visitor arrival; no coordinate replacement."
            ledger.append(
                {
                    "source_key": key,
                    "status": "hold",
                    "reason": reason,
                    "native_name": row["PARK"],
                    "destination_distance_m": target["distance"],
                    "driving": _receipt(probe["receipt"], extraction="$.waypoints[-1]"),
                }
            )
            continue
        p = profiles[key]
        if p["source_row"] != row or p["driving"] != probe["receipt"]:
            raise ValueError("coastal selected native row/route differs")
        lat, lon = source_point(row)
        matched = [
            c
            for c in canonical
            if c.get("facility_n") == "BEACH"
            and float(c.get("park_no", -1)) == float(row["PARK NUMBER"])
            and distance(
                (lat, lon),
                (c["the_geom"]["coordinates"][1], c["the_geom"]["coordinates"][0]),
            )
            <= 0.2
        ]
        if len(matched) != 1 or float(matched[0]["gisobjid"]) != p["official_gisobjid"]:
            raise ValueError(
                "coastal unchanged native feature has no unique exact canonical GIS identity"
            )
        identity = "chicago-facility:" + str(p["official_gisobjid"])
        if any(
            r["source_id"] == identity
            or distance((lat, lon), (r["latitude"], r["longitude"])) < 250
            for r in [*baseline, *rows]
        ):
            raise ValueError(
                "coastal native destination overlaps preserved or newly selected campus"
            )
        beach, parent = reader.read(p["beach"]), reader.read(p["parent"])
        calendar = calendar_for(p, beach, parent, global_raw)
        map_raw = reader.read(p["map"])
        arrival, elements = arrival_for(
            p, row, beach, reader.read(p["driving"], ceiling=262144), map_raw
        )
        aux_counts[p["map"]["path"]] = dict(
            Counter(
                e.tag
                for e in ElementTree.fromstring(map_raw)
                if e.tag in {"node", "way", "relation"}
            )
        )
        archive_receipt = _receipt(
            review["archive"],
            extraction=f"zip:{MEMBER}#record={key};PARK NUMBER={row['PARK NUMBER']};X={row['X COORDINATE']};Y={row['Y COORDINATE']}",
        )
        current_receipt = _receipt(
            review["canonical"], extraction=f"record[gisobjid={p['official_gisobjid']}]"
        )
        calendar["source_receipts"] = [
            archive_receipt,
            current_receipt,
            *calendar["source_receipts"],
            _receipt(
                review["global_beaches"],
                extraction="2026 swim-season notice and current lakefront trail-maintenance alert",
            ),
        ]
        constraints = [
            {
                **archive_receipt,
                "fields": row,
                "restrictions": [
                    "Native Kaggle beach coordinates retained without replacement; source row has no dedicated unique facility ID."
                ],
            },
            {
                **current_receipt,
                "fields": matched[0],
                "restrictions": [
                    "Canonical GISOBJID is a publisher-native identity join, not a substituted coordinate. Native point agrees within 0.2 m rounding tolerance."
                ],
            },
            {
                **_receipt(
                    p["beach"],
                    extraction="Facility Hours explanatory paragraph, seasonal swim condition, Parking/Directions and Location Notes",
                ),
                "facts": [BEACH_ACCESS, SWIM_SEASON, *p["arrival"]["operator_facts"]],
                "source_component_clocks": {
                    "shore_access": "06:00-23:00",
                    "seasonal_swimming_and_structured_facility_hours": "11:00-19:00",
                },
                "restrictions": [
                    "Selected activity is shore walking/sitting; swimming, surfing, boat launches and indoors are excluded.",
                    "Swim hours do not establish general beach opening hours; the explanatory paragraph independently publishes beach access.",
                    "Parking capacity and prices remain unknown.",
                ],
            },
            {
                **_receipt(
                    p["parent"],
                    extraction="Park Hours seven-day table; separately retain Fieldhouse Hours if present",
                ),
                "facts": [f"{d}: 6:00 am-11:00 pm" for d in WEEKDAYS],
                "restrictions": [
                    "Parent park corroborates shore access; indoor/fieldhouse/program hours do not apply to the selected beach component."
                ],
            },
            {
                **_receipt(
                    review["global_beaches"],
                    extraction="2026 swim-season notice; Lakefront Trail Maintenance Alert; Beach Rules",
                ),
                "facts": [CLOSED_SWIM, TRAIL_ALERT],
                "restrictions": [
                    "No swimming in the current ended 2026 season.",
                    "Avoid active lakefront construction zones; no all-site closure is inferred from a trail-work advisory.",
                    "Swim conditions, flags, weather restrictions, lifeguard instructions and posted rules remain source-dependent; swimming is not an admitted activity.",
                ],
            },
            {
                **_receipt(
                    p["map"],
                    extraction="Original OSM road/park/parking ways listed in public subset",
                ),
                "road_tags": [e["tags"] for e in elements],
                "restrictions": [
                    "Mapped customer parking is accepted only where published pay-and-display and mapped access=yes establish public visitor use.",
                    "No parking lot location, capacity or price is invented.",
                ],
            },
        ]
        rows.append(
            {
                "source_id": identity,
                "name": p["name"],
                "latitude": lat,
                "longitude": lon,
                "region": "IL",
                "categories": ["beach", "daytime"],
                "address": None,
                "url": p["beach"]["url"],
                "source_updated_at": None,
                "provenance": [
                    {
                        "dataset": REF,
                        "source_url": f"https://www.kaggle.com/datasets/{REF}/versions/{VERSION}",
                        "release": str(VERSION),
                        "license": "CC0-1.0",
                        "rights": [
                            "CC0-1.0",
                            "LicenseRef-Chicago-Park-District-Public-Domain",
                            "ODbL-1.0",
                        ],
                        "archive_sha256": ARCHIVE_SHA256,
                        "source_csv_sha256": CSV_SHA256,
                        "record_id": key,
                        "native_record": row,
                        "source_coordinates": [lat, lon],
                        "source_point_replaced": False,
                        "source_id_method": "Current official GISOBJID, uniquely joined to unchanged native Kaggle BEACH row within 0.2 m; no invented native ID",
                        "canonical_record": matched[0],
                    },
                    {
                        "dataset": "Current Chicago Park District beach/park access",
                        "primary_category": "beaches",
                        "component": "Public shore access only; no swimming or indoor/program admission",
                        "source_constraints": constraints,
                        "practical_arrival": arrival,
                        "prices_imported": False,
                        "future_ticket_availability": "unknown",
                        "review_sha256": REVIEW_SHA256,
                    },
                    {
                        "dataset": "OSRM and OpenStreetMap public beach arrival",
                        "license": "ODbL-1.0",
                        "attribution": "OpenStreetMap contributors; OSRM",
                        "route": _receipt(p["driving"], extraction="$.waypoints[-1]"),
                        "map": _receipt(
                            p["map"], extraction="Original OSM public arrival elements"
                        ),
                        "public_elements": [{"type": e["type"], "id": e["id"]} for e in elements],
                    },
                ],
            }
        )
        calendars.append(
            {
                "source_id": identity,
                "source_visit_calendar": calendar,
                "source_constraints": constraints,
                "transformation": {
                    "kind": "explicit-beach-shore-access-with-separate-seasonal-swimming",
                    "source_shore_clock": "06:00-23:00 daily",
                    "source_swimming_clock": "11:00-19:00 only during published beach season with lifeguards",
                    "selected_activity": "shore visit",
                    "swimming_eligible": False,
                    "review_policy_window": None,
                    "native_coordinate_replaced": False,
                    "dwell": "Planner policy of 2 hours; not a source claim of visit duration.",
                },
            }
        )
        for e in elements:
            public[e["type"], e["id"]] = e
        ledger.append(
            {
                "source_key": key,
                "source_id": identity,
                "status": "admit",
                "reason": "Unique unchanged native beach feature, current public shore calendar and documented actual visitor arrival.",
                "arrival": arrival,
            }
        )
    ledger.extend(
        {
            "source_key": f"chi-park-metadata-{i}",
            "status": "hold",
            "reason": "Park/address metadata row is not imported as a second arrival; only explicit BEACH facility coordinates are eligible.",
        }
        for i, _ in enumerate(other_rows)
    )
    if len(rows) != len(profiles):
        raise ValueError("coastal selected profiles do not match admitted native source rows")
    return rows, {
        "schema_version": SCHEMA,
        "scanned": len(original) + len(other_rows),
        "source_row_counts": {
            "native_facilities": len(original),
            "nonimported_native_park_metadata_rows": len(other_rows),
        },
        "beach_pool": len(beaches),
        "accepted": len(rows),
        "held_beaches": len(beaches) - len(rows),
        "held": len(original) + len(other_rows) - len(rows),
        "baseline_rows": len(baseline),
        "baseline_rows_sha256": canonical_rows_digest(baseline),
        "bytes": reader.bytes,
        "new_evidence_bytes": reader.bytes - len(baseline_raw),
        "auxiliary_registry_rows": len(canonical),
        "auxiliary_osm_record_counts": aux_counts,
        "input_files": [
            {
                "path": p.relative_to(reader.root).as_posix(),
                "bytes": p.stat().st_size,
                "sha256": digest(p.read_bytes()),
            }
            for p in sorted(reader.paths)
        ],
        "calendar_entries": calendars,
        "decisions": ledger,
        "public_osm_subset": {
            "license": "ODbL-1.0",
            "attribution": "OpenStreetMap contributors",
            "elements": list(public.values()),
        },
    }
