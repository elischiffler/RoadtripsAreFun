"""Offline admission of pinned LA/NYS cultural facts and source calendars.

This pilot intentionally accepts only explicitly supported visitor components.
Its review is data, not permission to invent coordinates, hours, entry or parking.
Source rows remain unchanged; a calendar is emitted separately for the root's
generation-bound overlay. No network or database operation occurs here.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import math
import re
import zipfile
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree

from lxml import html

from app.catalog.kaggle_parks import geometry_distance
from app.routing.visit_calendar import Calendar

SCHEMA = "roadtrips-kaggle-cultural-admission/1"
CALENDAR_SCHEMA = "roadtrips-source-visit-calendar/1"
MAX_ROWS = 50_000
MAX_BYTES = 100 * 1024 * 1024
BASELINE_COUNT = 557
BASELINE_ROWS_SHA256 = "f09f0a85a5dbf0cf586c637ffeb99b1472a2098e75127fdc8ee7fb1b4ccf0ce2"
REVIEW_SHA256 = "a2e57653cf2f101f7e48b8e85b3c5f0cee7176ea9ac7d0ea6c851a6258545fb0"
SOURCES = {
    "la": {
        "ref": "cityofLA/la-cultural-centers-theatres-sites-galleries",
        "version": 25,
        "archive_sha256": "a96469b64c7bdbb3b0050a56949376fbaee182d31fcf68d2ca895094bedb6f51",
        "csv": "cultural-centers-theaters-historic-sites-and-galleries-location-and-contact-information.csv",
        "csv_sha256": "faabfe9edc7a3d4feb7ba4e0ae9dc5467e3f46c8111582add1138eb22224179a",
        "count": 30,
        "name": "CENTER NAME",
        "columns": [
            "CENTER NAME",
            "COUNCIL DISTRICT",
            "PHONE",
            "EMAIL",
            "WEBSITE",
            "HOURS",
            "PARKING",
            "ART CLASSES",
            "DESCRIPTION",
            "ADDRESS",
            "Neighborhood Councils (Certified)",
            "Council Districts",
            "LA Specific Plans",
            "Precinct Boundaries",
            "Census Tracts",
            "Zip Codes",
        ],
        "upstream_id": "vdjf-if28",
        "region": "CA",
        "rights": {"CC0-1.0", "ODbL-1.0"},
    },
    "ny": {
        "ref": "new-york-state/nys-state-historic-sites",
        "version": 9,
        "archive_sha256": "45053965f919f7341687afcc730de6945d888fc2f142efcbfd697b8dc9f29687",
        "csv": "state-historic-sites.csv",
        "csv_sha256": "139b36148be92a3aee59502f3b73a11d5e9b50a7333655910e0a9dc58a218a64",
        "count": 41,
        "name": "Name",
        "columns": [
            "Name",
            "Category",
            "Region",
            "County",
            "Facility URL",
            "Longitude",
            "Latitude",
            "Location",
            "NYS Municipal Boundaries",
            "New York Zip Codes",
            "Counties",
        ],
        "upstream_id": "m384-u5q6",
        "region": "NY",
        "rights": {"CC0-1.0", "LicenseRef-Open-NY-Factual-Data", "ODbL-1.0"},
    },
}


def now():
    return datetime.now(UTC)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical_rows_digest(rows):
    return digest("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode())


def plain(raw):
    doc = html.fromstring(raw)
    for element in doc.xpath("//script|//style|//noscript"):
        element.drop_tree()
    return " ".join(" ".join(doc.itertext()).split())


class Reader:
    def __init__(self, root, ceiling):
        self.root, self.ceiling = Path(root).resolve(), ceiling
        self.paths, self.bytes = set(), 0

    def read(self, evidence, *, fresh=True, ceiling=2 * 1024 * 1024):
        value = evidence.get("path", "")
        relative = Path(value)
        if (
            not value
            or relative.is_absolute()
            or ".." in relative.parts
            or "\\" in value
            or any(char in value for char in '<>:"|?*')
            or any(ord(char) < 32 for char in value)
            or any(
                part.endswith((".", " "))
                or part.split(".")[0].upper()
                in {
                    "CON",
                    "PRN",
                    "AUX",
                    "NUL",
                    *(f"COM{n}" for n in range(1, 10)),
                    *(f"LPT{n}" for n in range(1, 10)),
                }
                for part in relative.parts
            )
        ):
            raise ValueError("cultural evidence requires a portable relative body path")
        path = (self.root / relative).resolve()
        if (
            self.root not in path.parents
            or not path.is_file()
            or not 0 < path.stat().st_size <= ceiling
        ):
            raise ValueError("cultural retained evidence missing, escaped or oversized")
        raw = path.read_bytes()
        if digest(raw) != evidence.get("sha256"):
            raise ValueError("cultural retained evidence checksum differs")
        if fresh:
            checked = datetime.fromisoformat(
                evidence.get("retrieved_at", "").replace("Z", "+00:00")
            )
            if checked.utcoffset() is None or not now() - timedelta(days=30) <= checked <= now():
                raise ValueError(
                    "cultural evidence needs an aware genuine acquisition within 30 days"
                )
            url = urlsplit(evidence.get("url", ""))
            if url.scheme != "https" or not url.netloc:
                raise ValueError("cultural evidence requires a retained HTTPS source URL")
        if path not in self.paths:
            self.paths.add(path)
            self.bytes += len(raw)
            if self.bytes > self.ceiling:
                raise ValueError("cultural aggregate input byte ceiling exceeded")
        return raw


def _archive(raw, spec):
    if digest(raw) != spec["archive_sha256"]:
        raise ValueError("unreviewed cultural Kaggle archive or version")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        members = z.infolist()
        names = [m.filename for m in members]
        if (
            len(set(names)) != len(names)
            or spec["csv"] not in names
            or any(m.flag_bits & 1 or m.file_size > 20 * 1024 * 1024 for m in members)
            or sum(m.file_size for m in members) > 20 * 1024 * 1024
            or any(Path(name).is_absolute() or ".." in Path(name).parts for name in names)
        ):
            raise ValueError("unexpected cultural archive inventory or decoded byte ceiling")
        csv_raw = z.read(spec["csv"])
    if digest(csv_raw) != spec["csv_sha256"]:
        raise ValueError("cultural source CSV differs from pinned release")
    reader = csv.DictReader(io.StringIO(csv_raw.decode("utf-8-sig")))
    if reader.fieldnames != spec["columns"]:
        raise ValueError("cultural source schema differs")
    rows = {}
    for count, row in enumerate(reader, 1):
        name = row[spec["name"]]
        if count > spec["count"] or not name or name in rows:
            raise ValueError("cultural source row ceiling or natural identity differs")
        rows[name] = row
    if len(rows) != spec["count"]:
        raise ValueError("cultural pinned source row count differs")
    return rows


def source_id(dataset, row):
    """A native URL identity for NY; explicit natural-key derivation for LA."""
    if dataset == "ny":
        value = ast.literal_eval(row["Facility URL"]).get("url", "")
        match = re.fullmatch(r"https://parks\.ny\.gov/historic-sites/(\d+)/details\.aspx", value)
        if not match:
            raise ValueError("NYS historic source lacks its native facility URL identity")
        return "nys-historic:" + match[1]
    # The native LA file has no row-ID column. Never label this derived key a
    # publisher-supplied ID, and retain the exact native natural key in provenance.
    return "la-cultural:" + digest(row["CENTER NAME"].encode())[:20]


def source_point(dataset, row):
    if dataset == "ny":
        values = row["Latitude"], row["Longitude"]
    else:
        point = ast.literal_eval(row["ADDRESS"])
        values = point["latitude"], point["longitude"]
    lat, lon = map(float, values)
    if (
        not math.isfinite(lat)
        or not math.isfinite(lon)
        or not -90 <= lat <= 90
        or not -180 <= lon <= 180
    ):
        raise ValueError("cultural native coordinate is invalid")
    return lat, lon


def distance(a, b):
    lat, lon, other_lat, other_lon = map(math.radians, (*a, *b))
    return 12_742_017.6 * math.asin(
        min(
            1,
            math.sqrt(
                math.sin((other_lat - lat) / 2) ** 2
                + math.cos(lat) * math.cos(other_lat) * math.sin((other_lon - lon) / 2) ** 2
            ),
        )
    )


def _registry(dataset, rows, current):
    name_key = "name" if dataset == "ny" else "center_name"
    by_name = {}
    for record in current:
        name = record.get(name_key)
        if name in by_name:
            raise ValueError("cultural canonical registry has ambiguous identity")
        by_name[name] = record
    for name, row in rows.items():
        match = by_name.get(name, {})
        actual = (
            (match.get("y"), match.get("x"))
            if dataset == "ny"
            else (
                match.get("address", {}).get("latitude"),
                match.get("address", {}).get("longitude"),
            )
        )
        if None in actual or tuple(map(float, actual)) != source_point(dataset, row):
            raise ValueError(
                "cultural unchanged native identity/coordinates lack official corroboration"
            )
        if dataset == "la" and match.get("hours", "") != row["HOURS"]:
            raise ValueError("cultural canonical clock conflict needs another intersection review")
        if dataset == "la" and match.get("parking", "") != row["PARKING"]:
            raise ValueError("cultural canonical parking conflict needs another access review")
        if dataset == "ny" and (match.get("facility_url") or {}) != (
            ast.literal_eval(row["Facility URL"]) if row["Facility URL"] else {}
        ):
            raise ValueError("cultural canonical native facility URL identity differs")
    return by_name


def _receipt(evidence, *, extraction):
    return {
        "source_url": evidence["url"],
        "snapshot_sha256": evidence["sha256"],
        "checked_at": evidence["retrieved_at"],
        "evidence_path": evidence["path"],
        "extraction_pointer": extraction,
    }


def _hours(raw):
    doc = html.fromstring(raw)
    nodes = doc.xpath("//h3[normalize-space(.)='Hours']/parent::*")
    if len(nodes) != 1:
        raise ValueError("cultural current operator has no unique visitor hours field")
    return " ".join(" ".join(nodes[0].itertext()).split())


def calendar_for(profile, original, pages):
    """Only explicit, component-bound transformations in this reviewed pilot."""
    kind = profile["calendar_kind"]
    receipts = [_receipt(e, extraction=e["extraction_pointer"]) for e, _ in pages]
    result = {
        "schema_version": CALENDAR_SCHEMA,
        "weekly_windows": [],
        "seasons": [],
        "date_overrides": [],
        "annual_closures": [],
        "fixed_starts": [],
        "source_receipts": receipts,
        "unknown_reasons": [],
    }
    if kind == "watts-campus-galleries":
        if original["HOURS"] != "Wednesday- Saturday, 10:00AM - 4:00PM; Sunday, 12:00PM - 4:00PM":
            raise ValueError("native Watts visitor clocks differ from reviewed source")
        if _hours(pages[0][1]) != (
            "Hours Galleries: Wednesday to Saturday from 10:00 a.m. to 4:00 p.m. "
            "Watts Towers Guided Tours: Thursday to Saturday from 11:00 a.m. to 3:00 p.m."
        ):
            raise ValueError("Watts gallery/tour components or clocks differ")
        body = plain(pages[0][1])
        if "Beginning July 8, 2026" not in body or "has reopened to the public" not in body:
            raise ValueError("Watts lacks explicit current reopening evidence")
        # Sunday is in the old feed only. The supported intersection is Wed-Sat.
        result["weekly_windows"] = [
            {"weekdays": [2, 3, 4, 5], "opens": "10:00", "closes": "16:00", "end_day_offset": 0}
        ]
        # The source explicitly describes a temporary June closure and July 8
        # reopening. Retain its dated negative restriction, including the gap.
        day = date(2026, 6, 1)
        while day < date(2026, 7, 8):
            result["date_overrides"].append({"date": day.isoformat(), "windows": []})
            day += timedelta(days=1)
    elif kind == "philipse-affirmative-halloween-visit":
        if original["Name"] != "Philipse Manor Hall" or len(pages) != 3:
            raise ValueError("Philipse visitor/calendar identity differs")
        official, visit, event = (plain(raw) for _, raw in pages)
        required = [
            (official, "Wednesday – 10 am to 5 pm"),
            (official, "The site may be closed for holidays"),
            (visit, "Philipse Manor Hall State Historic Site is self-guided"),
            (visit, "Wednesday: 10 am-5 pm"),
            (visit, "Saturday: 10 am-5 pm"),
            (event, "Saturday, October 31, 2026"),
            (event, "12:00 PM - 4:00 PM"),
        ]
        if any(literal not in body for body, literal in required):
            raise ValueError("Philipse lacks complete source-bound self-guided/date clocks")
        # Unknown holiday closures are not converted into assumed-open weeks.
        # This affirmative operator event supports only the stated date/window;
        # no opening on other days, no movie-specific fixed start is inferred.
        result["date_overrides"] = [
            {
                "date": "2026-10-31",
                "windows": [{"opens": "12:00", "closes": "16:00", "end_day_offset": 0}],
            }
        ]
        result["seasons"] = [{"kind": "dated", "start": "2026-10-31", "end": "2026-10-31"}]
    else:
        raise ValueError("unsupported cultural visitor calendar; no guessed hours")
    Calendar.model_validate(result)
    return result


def osm_elements(raw):
    doc = ElementTree.fromstring(raw)
    if doc.tag != "osm":
        raise ValueError("cultural arrival snapshot is not original OSM map XML")
    nodes = {e.attrib["id"]: e for e in doc.findall("node")}
    result = {}
    for element in [*doc.findall("node"), *doc.findall("way")]:
        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in element.findall("tag")}
        record = {"type": element.tag, "id": int(element.attrib["id"]), "tags": tags}
        if element.tag == "node":
            record.update(lat=float(element.attrib["lat"]), lon=float(element.attrib["lon"]))
        else:
            record["geometry"] = [
                {
                    "lat": float(nodes[n.attrib["ref"]].attrib["lat"]),
                    "lon": float(nodes[n.attrib["ref"]].attrib["lon"]),
                }
                for n in element.findall("nd")
            ]
        result[element.tag, record["id"]] = record
    return result


def driving_destination(dataset, original, evidence, raw):
    lat, lon = source_point(dataset, original)
    route_url = urlsplit(evidence["url"])
    if (
        route_url.scheme != "https"
        or route_url.netloc != "router.project-osrm.org"
        or route_url.path != f"/route/v1/driving/{lon + 0.002},{lat + 0.002};{lon},{lat}"
        or route_url.query != "overview=false&steps=false"
    ):
        raise ValueError("cultural route must target the exact unchanged native point")
    route = json.loads(raw)
    waypoints = route.get("waypoints", [])
    if route.get("code") != "Ok" or len(waypoints) != 2 or not route.get("routes"):
        raise ValueError("cultural actual driving destination failed")
    target = waypoints[-1]
    snap = target.get("location")
    metres = target.get("distance")
    if (
        type(metres) not in {int, float}
        or not math.isfinite(metres)
        or metres < 0
        or not isinstance(snap, list)
        or len(snap) != 2
        or any(type(v) not in {int, float} or not math.isfinite(v) for v in snap)
        or not -180 <= snap[0] <= 180
        or not -90 <= snap[1] <= 90
    ):
        raise ValueError("cultural native destination has malformed driving snap")
    # Verify both the provider's reported error and the actual returned point.
    # A changed or inconsistent receipt cannot evade the arrival bound.
    if abs(distance((lat, lon), (snap[1], snap[0])) - metres) > 2:
        raise ValueError("cultural driving snap distance disagrees with its native point")
    return target


def arrival_for(profile, original, pages, route_raw, osm_raw):
    lat, lon = source_point(profile["dataset"], original)
    target = driving_destination(profile["dataset"], original, profile["driving"], route_raw)
    snap, metres = target["location"], target["distance"]
    if metres > 75 or distance((lat, lon), (snap[1], snap[0])) > 75:
        raise ValueError("cultural native destination exceeds 75 metres")
    elements = osm_elements(osm_raw)
    road = elements.get(("way", profile["arrival"]["road_way_id"]))
    if not road:
        raise ValueError("cultural actual arrival road is not in original map evidence")
    tags = road["tags"]
    forbidden = {"private", "no", "delivery", "agricultural", "forestry"}
    if (
        tags.get("highway")
        not in {"residential", "unclassified", "tertiary", "secondary", "primary", "service"}
        or any(tags.get(k) in forbidden for k in ["access", "vehicle", "motor_vehicle", "motorcar"])
        or float(tags.get("layer", "0")) < 0
    ):
        raise ValueError("cultural road is not documented public visitor vehicle access")
    if (
        geometry_distance(snap[1], snap[0], road["geometry"])[0] > 3
        or geometry_distance(lat, lon, road["geometry"])[0] > 75
    ):
        raise ValueError("cultural map road does not bind the actual snapped destination")
    proof = profile["arrival"]
    page_text = [plain(raw) for _, raw in pages]
    if not proof.get("operator_parking_facts") or any(
        not any(literal in body for body in page_text)
        for literal in proof["operator_parking_facts"]
    ):
        raise ValueError("cultural visitor arrival lacks literal operator parking/directions")
    method = proof["method"]
    if method == "operator-street-frontage":
        if (
            tags.get("highway") == "service"
            or not tags.get("name")
            or tags["name"] != target.get("name")
        ):
            raise ValueError("cultural street frontage cannot use an unnamed/internal road")
    elif method == "operator-entry-frontage":
        markers = []
        for _, raw in pages:
            for href in html.fromstring(raw).xpath("//a/@href"):
                url = urlsplit(href)
                if url.netloc == "www.google.com" and url.path == "/maps":
                    point = parse_qs(url.query).get("q", [""])[0]
                    if re.fullmatch(r"-?[0-9.]+,-?[0-9.]+", point):
                        markers.append(tuple(map(float, point.split(","))))
        if not any(distance((lat, lon), marker) <= 75 for marker in markers):
            raise ValueError("cultural operator main entry differs from native visitor point")
    else:
        raise ValueError("unsupported cultural public arrival method")
    return {
        "method": method,
        "road_way_id": road["id"],
        "snap_distance_m": metres,
        "road_name": target.get("name"),
        "coordinate_replaced": False,
        "parking_availability": "unknown",
        "operator_parking_facts": proof["operator_parking_facts"],
    }, road


def replay(review_path, *, max_rows=MAX_ROWS, max_bytes=MAX_BYTES):
    """Return admitted rows, separate calendars, full held ledger and ODbL subset."""
    if not 0 < max_rows <= MAX_ROWS or not 0 < max_bytes <= MAX_BYTES:
        raise ValueError("cultural import ceilings cannot be raised")
    review_path = Path(review_path)
    raw = review_path.read_bytes()
    if not 0 < len(raw) <= 256 * 1024 or digest(raw) != REVIEW_SHA256:
        raise ValueError("cultural pinned admission review fingerprint differs")
    review = json.loads(raw)
    if review.get("schema_version") != SCHEMA:
        raise ValueError("unsupported cultural review schema")
    reader = Reader(review_path.parent, max_bytes)
    reader.paths.add(review_path.resolve())
    reader.bytes = len(raw)
    baseline_raw = reader.read(review["baseline"], fresh=False, ceiling=8 * 1024 * 1024)
    baseline = [json.loads(line) for line in baseline_raw.decode().splitlines() if line]
    if len(baseline) != BASELINE_COUNT or canonical_rows_digest(baseline) != BASELINE_ROWS_SHA256:
        raise ValueError("cultural dedup requires the exact full preserved baseline")
    by_source, registries = {}, {}
    scanned = 0
    for dataset, evidence in review["sources"].items():
        spec = SOURCES[dataset]
        archive = reader.read(evidence["archive"], fresh=False, ceiling=20 * 1024 * 1024)
        rows = _archive(archive, spec)
        scanned += len(rows)
        if scanned > max_rows:
            raise ValueError("cultural aggregate primary source row ceiling exceeded")
        metadata = json.loads(reader.read(evidence["metadata"]))
        registry_meta = json.loads(reader.read(evidence["registry_metadata"]))
        current = json.loads(reader.read(evidence["registry"]))
        if (
            metadata.get("ref") != spec["ref"]
            or metadata.get("currentVersionNumber") != spec["version"]
            or metadata.get("licenseName") != "CC0: Public Domain"
            or registry_meta.get("id") != spec["upstream_id"]
            or registry_meta.get("provenance") != "official"
        ):
            raise ValueError("cultural publisher/version/upstream rights identity differs")
        if set(evidence["rights"]) != spec["rights"]:
            raise ValueError("cultural exact upstream rights evidence missing")
        for right, receipt in evidence["rights"].items():
            rights_raw = reader.read(receipt, fresh=False)
            if not rights_raw:
                raise ValueError("empty cultural license evidence")
            if (
                right == "CC0-1.0"
                and dataset == "la"
                and registry_meta.get("licenseId") != "CC0_10"
            ):
                raise ValueError("LA upstream no longer affirms CC0 factual data")
        by_source[dataset] = rows
        registries[dataset] = _registry(dataset, rows, current)
    dispositions = review["dispositions"]
    expected = {(dataset, name) for dataset, rows in by_source.items() for name in rows}
    if (
        len(dispositions) != scanned
        or {(d["dataset"], d["name"]) for d in dispositions} != expected
    ):
        raise ValueError("cultural ledger must cover every source row exactly once")
    rows, calendars, decisions, public_roads, osm_record_counts = [], [], [], {}, {}
    profile_by_key = {(p["dataset"], p["name"]): p for p in review["admissions"]}
    if len(profile_by_key) != len(review["admissions"]):
        raise ValueError("duplicate cultural admission identity")
    for disposition in dispositions:
        key = disposition["dataset"], disposition["name"]
        profile = profile_by_key.get(key)
        if disposition["status"] != "admit":
            if disposition["status"] != "hold" or profile or not disposition.get("reason"):
                raise ValueError("cultural held row cannot have an admission or missing reason")
            for evidence in disposition.get("evidence", []):
                body = reader.read(evidence)
                if any(
                    literal not in plain(body) for literal in evidence.get("required_facts", [])
                ):
                    raise ValueError("cultural held disposition differs from retained facts")
            if "driving_evidence" in disposition:
                evidence = disposition["driving_evidence"]
                target = driving_destination(
                    key[0],
                    by_source[key[0]][key[1]],
                    evidence,
                    reader.read(evidence, ceiling=262_144),
                )
                if target["distance"] <= 75:
                    raise ValueError("cultural held over-distance proof is not over 75 metres")
            decisions.append(disposition)
            continue
        if not profile:
            raise ValueError("cultural selected source row lacks reviewed evidence")
        original = by_source[key[0]][key[1]]
        if original != profile["source_row"]:
            raise ValueError("cultural native source facts differ from reviewed row")
        identity = source_id(key[0], original)
        lat, lon = source_point(key[0], original)
        for other in [*baseline, *rows]:
            if (
                identity == other["source_id"]
                or distance((lat, lon), (other["latitude"], other["longitude"])) < 250
            ):
                raise ValueError(
                    "cultural source overlaps preserved catalog or another campus arrival"
                )
        pages, constraints = [], []
        for evidence in profile["pages"]:
            body = reader.read(evidence)
            text = plain(body)
            if not evidence.get("required_facts") or any(
                fact not in text for fact in evidence["required_facts"]
            ):
                raise ValueError("cultural source identity, visitor fact or restriction absent")
            pages.append((evidence, body))
            constraints.append(
                {
                    **_receipt(evidence, extraction=evidence["extraction_pointer"]),
                    "facts": evidence["required_facts"],
                    "restrictions": evidence["restrictions"],
                }
            )
        if (
            profile["public_url"] not in {e["url"] for e, _ in pages}
            or not profile.get("address_parts")
            or any(
                not any(part in plain(body) for _, body in pages)
                for part in profile["address_parts"]
            )
        ):
            raise ValueError("cultural public URL/address is not bound to operator evidence")
        calendar = calendar_for(profile, original, pages)
        if calendar["unknown_reasons"]:
            raise ValueError("cultural automatic admission cannot use unknown calendars")
        route_raw = reader.read(profile["driving"], ceiling=262_144)
        osm_raw = reader.read(profile["osm"])
        osm_record_counts[profile["osm"]["path"]] = dict(
            Counter(
                element.tag
                for element in ElementTree.fromstring(osm_raw)
                if element.tag in {"node", "way", "relation"}
            )
        )
        arrival, road = arrival_for(profile, original, pages, route_raw, osm_raw)
        source = review["sources"][key[0]]
        spec = SOURCES[key[0]]
        url = f"https://www.kaggle.com/datasets/{spec['ref']}/versions/{spec['version']}"
        native_receipt = _receipt(
            source["archive"], extraction=f"zip:{spec['csv']}#record={original[spec['name']]}"
        )
        registry_receipt = _receipt(
            source["registry"],
            extraction=f"record[{'name' if key[0] == 'ny' else 'center_name'!r}={original[spec['name']]!r}]",
        )
        calendar["source_receipts"] = [
            native_receipt,
            registry_receipt,
            *calendar["source_receipts"],
        ]
        native_facts = {
            key: original[key] for key in ("HOURS", "PARKING", "Facility URL") if key in original
        }
        constraints = [
            {
                **native_receipt,
                "fields": native_facts,
                "restrictions": ["Native source values retained; absence of a field is unknown."],
            },
            {
                **registry_receipt,
                "fields": native_facts,
                "restrictions": [
                    "Current official registry reconciled; its old clocks do not override a narrower current operator schedule."
                ],
            },
            *constraints,
        ]
        provenance = [
            {
                "dataset": spec["ref"],
                "source_url": url,
                "release": str(spec["version"]),
                "license": "CC0-1.0",
                "archive_sha256": spec["archive_sha256"],
                "source_csv_sha256": spec["csv_sha256"],
                "record_id": original[spec["name"]],
                "source_id_method": "native facility URL"
                if key[0] == "ny"
                else "SHA256 of exact native CENTER NAME; source has no ID column",
                "source_coordinates": [lat, lon],
                "source_point_replaced": False,
                "native_record": {
                    k: original[k]
                    for k in (
                        ["Name", "Facility URL", "Latitude", "Longitude"]
                        if key[0] == "ny"
                        else ["CENTER NAME", "ADDRESS", "HOURS", "PARKING"]
                    )
                },
                "rights": source["rights"],
                "changes": "Visitor-component and source-calendar intersection; no coordinate changes or invented hours/prices.",
            },
            {
                "dataset": "Current cultural visitor component and public arrival",
                "primary_category": "museums",
                "component": profile["component"],
                "source_constraints": constraints,
                "practical_arrival": arrival,
                "future_ticket_availability": "unknown",
                "prices_imported": False,
                "source_visit_calendar_emitted_separately": True,
                "review_sha256": REVIEW_SHA256,
            },
            {
                "dataset": "OSRM actual driving destination and OpenStreetMap public arrival",
                "license": "ODbL-1.0",
                "attribution": "OpenStreetMap contributors; OSRM",
                "route": _receipt(profile["driving"], extraction="$.waypoints[-1]"),
                "map": _receipt(profile["osm"], extraction=f"/osm/way[@id='{road['id']}']"),
                "public_elements": [{"type": "way", "id": road["id"]}],
            },
        ]
        rows.append(
            {
                "source_id": identity,
                "name": original[spec["name"]],
                "latitude": lat,
                "longitude": lon,
                "region": spec["region"],
                "categories": ["culture", "daytime", "history_museum", "museum"]
                if key[0] == "ny"
                else ["art_gallery", "culture", "daytime", "museum"],
                "address": profile["address"],
                "url": profile["public_url"],
                "source_updated_at": None,
                "provenance": provenance,
            }
        )
        calendars.append(
            {
                "source_id": identity,
                "source_visit_calendar": calendar,
                "source_constraints": constraints,
                "transformation": {
                    "kind": profile["calendar_kind"],
                    "native_coordinate_replaced": False,
                    "ticket_inventory": "unknown",
                    "dwell": "Planner policy of 2 hours; not a source claim of visit duration.",
                    "notes": profile["transformation"],
                },
            }
        )
        public_roads[road["id"]] = {
            **road,
            "tags": {
                k: v
                for k, v in road["tags"].items()
                if k
                in {
                    "highway",
                    "name",
                    "access",
                    "vehicle",
                    "motor_vehicle",
                    "motorcar",
                    "service",
                    "oneway",
                    "layer",
                    "surface",
                }
            },
        }
        decisions.append({**disposition, "source_id": identity, "arrival": arrival})
    if set(profile_by_key) != {
        (d["dataset"], d["name"]) for d in dispositions if d["status"] == "admit"
    }:
        raise ValueError("cultural admissions do not exactly match full source ledger")
    return (
        rows,
        calendars,
        {
            "schema_version": SCHEMA,
            "scanned": scanned,
            "accepted": len(rows),
            "held": scanned - len(rows),
            "bytes": reader.bytes,
            "new_evidence_bytes": reader.bytes - len(baseline_raw),
            "baseline_rows": len(baseline),
            "baseline_rows_sha256": canonical_rows_digest(baseline),
            "source_row_counts": {dataset: len(values) for dataset, values in by_source.items()},
            "auxiliary_registry_rows": {
                dataset: len(values) for dataset, values in registries.items()
            },
            "auxiliary_osm_record_counts": osm_record_counts,
            "regions": dict(Counter(row["region"] for row in rows)),
            "input_files": [
                {
                    "path": path.relative_to(reader.root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": digest(path.read_bytes()),
                }
                for path in sorted(reader.paths)
            ],
            "decisions": decisions,
        },
        {
            "license": "ODbL-1.0",
            "attribution": "OpenStreetMap contributors",
            "elements": list(public_roads.values()),
        },
    )


def prepare(path, manifest=None, *, max_rows=MAX_ROWS, max_bytes=MAX_BYTES):
    """Companion-import adapter contract; calendars remain separate from rows."""
    if manifest is not None and (
        manifest.get("schema_version") != SCHEMA or manifest.get("sha256") != REVIEW_SHA256
    ):
        raise ValueError("cultural companion manifest does not identify the pinned review")
    rows, calendars, report, osm_subset = replay(path, max_rows=max_rows, max_bytes=max_bytes)
    return rows, {**report, "calendar_entries": calendars, "public_osm_subset": osm_subset}
