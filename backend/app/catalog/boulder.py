"""Reviewed Kaggle Boulder v1 intake, using retained current operator evidence.

Only the inspected archive/member is supported. This is not a generic Kaggle
license grant. No network or database calls occur here. Arrival coordinates are
read from the city's own directions link, not geocoded or invented.
"""

import csv
import hashlib
import io
import math
import re
import zipfile
from collections import Counter
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

SCHEMA = "kaggle-boulder-trailheads/1"
RELEASE = "kaggle-boulder-v1"
SOURCE_URL = "https://www.kaggle.com/api/v1/datasets/download/paultimothymooney/trailstrailheadsandrockformationsinboulder?datasetVersionNumber=1"
ARCHIVE_SHA256 = "5dfb978b50c8d238eda2362dcd99b1a1b2328bbe2fc8827803fdc99bb48ff5c4"
MEMBER = "OSMP_Trailheads.csv"
PREFIX = "OSMPTrailheadsOSMP"
FIELDS = {"X", "Y", *(PREFIX + s for s in ("ACCESSID", "THNAME", "ACCESSTYPE", "ADDRESS"))}
ATTRIBUTION = "City of Boulder Open Space and Mountain Parks (CC0 1.0); Kaggle mirror by paultimothymooney. No City endorsement."


class OperatorPage(HTMLParser):
    """Read only the structured trailhead name/status, parking and directions."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.name = []
        self.status = []
        self.parking = []
        self.directions = []
        self.heading = []
        self.in_name = self.in_heading = self.in_parking = False
        self.status_depth = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h1":
            self.in_name = True
        if tag in {"h2", "h3", "h4"}:
            self.in_heading = True
            self.in_parking = False
            self.heading = []
        if tag == "div":
            if "field--name-field-open-status" in attrs.get("class", "").split():
                self.status_depth = 1
            elif self.status_depth:
                self.status_depth += 1
        if tag == "a":
            href = attrs.get("href", "")
            if re.fullmatch(r"https?://www\.google\.com/maps/place/-?\d+\.\d+,-?\d+\.\d+", href):
                self.directions.append(href)

    def handle_endtag(self, tag):
        if tag == "h1":
            self.in_name = False
        if tag in {"h2", "h3", "h4"}:
            self.in_heading = False
            self.in_parking = " ".join(self.heading).strip() == "Parking"
        if tag == "div" and self.status_depth:
            self.status_depth -= 1

    def handle_data(self, value):
        value = value.strip()
        if not value:
            return
        if self.in_name:
            self.name.append(value)
        if self.status_depth:
            self.status.append(value)
        if self.in_heading:
            self.heading.append(value)
        elif self.in_parking:
            self.parking.append(value)


def retained_file(evidence, ceiling=128 * 1024):
    if not isinstance(evidence, dict):
        raise ValueError("retained evidence must be an object")
    path = Path(evidence.get("path", ""))
    if not path.is_file() or not 0 < path.stat().st_size <= ceiling:
        raise ValueError("retained evidence missing or oversized")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != evidence.get("sha256"):
        raise ValueError("retained evidence checksum mismatch")
    return content


def arrival(record, evidence):
    url = urlparse(evidence.get("url", ""))
    if (
        url.scheme != "https"
        or url.netloc != "bouldercolorado.gov"
        or not re.fullmatch(r"/trailhead/[a-z0-9-]+", url.path)
        or url.query
        or url.fragment
    ):
        raise ValueError("current evidence must be an official trailhead page")
    checked = datetime.fromisoformat(evidence.get("retrieved_at", "").replace("Z", "+00:00"))
    now = datetime.now(UTC)
    if checked.tzinfo is None or not now - timedelta(days=30) <= checked <= now:
        raise ValueError("operator evidence must be dated within the last 30 days")
    page = OperatorPage()
    page.feed(retained_file(evidence).decode("utf-8"))
    if " ".join(page.name).casefold() != record[PREFIX + "THNAME"].strip().casefold():
        raise ValueError("operator page does not identify this trailhead")
    if " ".join(page.status) != "Status Open":
        return None, "operator_not_open"
    parking = " ".join(page.parking).casefold()
    if (
        not parking
        or "no parking" in parking
        or not any(s in parking for s in ("parking lot", "parking spaces", "small lot"))
    ):
        return None, "parking_unverified"
    if len(set(page.directions)) != 1:
        return None, "arrival_unverified"
    lat, lon = map(float, page.directions[0].rsplit("/", 1)[1].split(","))
    # Boulder-only geographic guard; source X/Y are WGS84 lon/lat. The embedded
    # OSMPTrailheadsOSMPY field duplicates longitude in v1 and must never be used.
    source_lon, source_lat = float(record["X"]), float(record["Y"])
    if not all(math.isfinite(v) for v in (lat, lon, source_lat, source_lon)) or not (
        39.8 <= lat <= 40.2 and -105.7 <= lon <= -105.0
    ):
        return None, "coordinates"
    if max(abs(lat - source_lat), abs(lon - source_lon)) > 0.002:
        return None, "arrival_changed_review_required"
    return (lat, lon, checked.isoformat()), None


def prepare(path, manifest, *, max_rows, max_bytes):
    """Normalize authentic rows only after independently dated arrival review."""
    if (
        manifest.get("release") != RELEASE
        or manifest.get("source_url") != SOURCE_URL
        or manifest.get("sha256") != ARCHIVE_SHA256
    ):
        raise ValueError("Boulder intake requires the inspected pinned Kaggle v1 archive")
    if manifest.get("attribution") != ATTRIBUTION or set(manifest.get("licenses", {})) != {
        "CC0-1.0"
    }:
        raise ValueError("Boulder intake requires its reviewed CC0 attribution")
    path = Path(path)
    if (
        path.stat().st_size > max_bytes
        or hashlib.sha256(path.read_bytes()).hexdigest() != ARCHIVE_SHA256
    ):
        raise ValueError("Boulder archive size/checksum mismatch")
    evidence = manifest.get("operator_evidence")
    if not isinstance(evidence, dict) or not 1 <= len(evidence) <= 36:
        raise ValueError("supply at most 36 independently reviewed trailhead pages")
    rows, rejects, seen, used = [], Counter(), set(), set()
    with zipfile.ZipFile(path) as archive:
        entries = [m for m in archive.infolist() if m.filename == MEMBER]
        if len(entries) != 1 or not 0 < entries[0].file_size < 128 * 1024:
            raise ValueError("unexpected Boulder trailhead CSV member")
        reader = csv.DictReader(io.StringIO(archive.read(entries[0]).decode("utf-8-sig")))
        if not FIELDS <= set(reader.fieldnames or []):
            raise ValueError("unexpected Boulder CSV columns")
        scanned = 0
        for record in reader:
            scanned += 1
            if scanned > max_rows:
                raise ValueError("input row ceiling exceeded")
            native = record[PREFIX + "ACCESSID"]
            if not re.fullmatch(r"[0-9]{1,5}[a-z]?", native) or native in seen:
                raise ValueError("invalid or duplicate Boulder native ID")
            seen.add(native)
            if native not in evidence:
                rejects["operator_evidence_missing"] += 1
                continue
            used.add(native)
            if record[PREFIX + "ACCESSTYPE"] != "TH":
                rejects["not_trailhead"] += 1
                continue
            # Two arrivals at the same summit must not inflate destination counts.
            if native == "279":
                rejects["same_flagstaff_summit_destination"] += 1
                continue
            point, reason = arrival(record, evidence[native])
            if reason:
                rejects[reason] += 1
                continue
            lat, lon, checked = point
            e = evidence[native]
            rows.append(
                {
                    "source_id": "boulder:" + native,
                    "name": record[PREFIX + "THNAME"].strip(),
                    "latitude": lat,
                    "longitude": lon,
                    "region": "CO",
                    "categories": ["daytime", "nature", "trailhead"],
                    "address": record[PREFIX + "ADDRESS"].strip() or None,
                    "url": e["url"],
                    "source_updated_at": None,
                    "provenance": [
                        {
                            "dataset": "City of Boulder OSMP via Kaggle",
                            "record_id": native,
                            "release": RELEASE,
                            "archive_sha256": ARCHIVE_SHA256,
                            "source_url": SOURCE_URL,
                            "license": "CC0-1.0",
                            "source_point": {
                                "latitude": float(record["Y"]),
                                "longitude": float(record["X"]),
                            },
                            "source_metadata_date": "2019-04-17",
                        },
                        {
                            "dataset": "City of Boulder current trailhead",
                            "url": e["url"],
                            "sha256": e["sha256"],
                            "checked_at": checked,
                            "status_at_check": "Open",
                            "arrival_type": "trailhead_parking",
                            "latitude": lat,
                            "longitude": lon,
                            "limitations": "Access, parking and fees may change; check operator closures before travel. Opening hours remain unknown to the scheduler.",
                        },
                    ],
                }
            )
    if set(evidence) - used:
        raise ValueError("operator evidence contains unknown native IDs")
    return rows, {
        "scanned": scanned,
        "accepted": len(rows),
        "bytes": path.stat().st_size,
        "rejects": dict(rejects),
        "regions": {"CO": len(rows)},
        "primary_categories": {"nature": len(rows)},
    }
