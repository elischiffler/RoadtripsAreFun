"""Kaggle NPS v3 park identities enriched with current official visitor arrivals.

No web/database calls. Only factual fields from retained NPS structured data are
used; images, website prose, contact details and park-center geometry are not
imported as destinations. One selected arrival represents each parent park.
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
from urllib.parse import urlparse

from app.catalog.normalize import US_REGIONS

SCHEMA = "kaggle-nps-arrivals/1"
ARCHIVE_SHA256 = "19537d3229511b8471801b2a0525958b05bcd2231ed033418c63834ef114f8ec"
SOURCE_URL = "https://www.kaggle.com/api/v1/datasets/download/nationalparkservice/park-biodiversity?datasetVersionNumber=3"
ATTRIBUTION = "National Park Service; Kaggle park-biodiversity v3. No claim to original U.S. Government works. No NPS endorsement."
# Their mainland information offices or isolated local roads are not driving
# arrivals to these island/fly-in parks. See official park directions snapshots.
NON_DRIVING_PARKS = {"chis", "drto", "gaar", "glba", "isro", "katm", "kova", "lacl"}
CLOSURE = re.compile(
    r"\b(permanently closed|temporarily closed|closed until further notice|closed indefinitely|closed due to|no access to)\b",
    re.I,
)


def read_snapshot(evidence, code):
    expected = f"https://www.nps.gov/{code}/structured_data_{code}.json"
    if evidence.get("url") != expected:
        raise ValueError("NPS evidence must name the park's published structured-data URL")
    checked = datetime.fromisoformat(evidence.get("retrieved_at", "").replace("Z", "+00:00"))
    if checked.tzinfo is None or not datetime.now(UTC) - timedelta(
        days=30
    ) <= checked <= datetime.now(UTC):
        raise ValueError("NPS evidence must be dated within 30 days")
    path = Path(evidence.get("path", ""))
    if not path.is_file() or not 0 < path.stat().st_size <= 2 * 1024 * 1024:
        raise ValueError("NPS snapshot missing or exceeds 2 MiB")
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != evidence.get("sha256"):
        raise ValueError("NPS snapshot checksum mismatch")
    data = json.loads(content.decode("utf-8-sig"))
    if data.get("siteCode") != code or data.get("physicalAddressCountryCode") != "US":
        raise ValueError("NPS snapshot identity/country mismatch")
    return data, checked.isoformat(), len(content)


def normalize_arrival(park, source, selection, evidence, checked):
    code = park["Park Code"].lower()
    if code in NON_DRIVING_PARKS:
        return None, "park_requires_non_driving_access"
    choices = [
        v
        for v in source.get("visitorCenters", [])
        if v.get("visitorCenterID") == selection.get("visitor_center_id")
    ]
    if len(choices) != 1:
        raise ValueError("selected NPS visitor-center identity is missing or ambiguous")
    vc = choices[0]
    name = vc.get("name", "").strip()
    if (
        not name
        or len(name) > 180
        or not isinstance(vc.get("directions"), str)
        or not vc["directions"].strip()
    ):
        return None, "visitor_arrival_evidence_missing"
    schedules = vc.get("operatingHours", {})
    if not isinstance(schedules, dict):
        return None, "schedule_unknown"
    descriptions = " ".join(
        str(v)
        for v in [
            vc.get("description", ""),
            vc["directions"],
            *[s.get("description", "") + " " + s.get("label", "") for s in schedules.values()],
        ]
    )
    if CLOSURE.search(descriptions):
        return None, "closure_evidence"
    hours = [h for s in schedules.values() for h in s.get("hours", [])]
    if not any(
        h.get("is_closed") == 0 and h.get("time_open") and h.get("time_close") for h in hours
    ):
        return None, "schedule_unknown_or_closed"
    amenities = vc.get("amenities", [])
    directions = vc["directions"].casefold()
    car_access = "Parking - Auto" in amenities or re.search(
        r"\b(parking lot|parking area|park at|park in|drive|driving|highway|interstate|parkway)\b",
        directions,
    )
    if not car_access:
        return None, "car_arrival_unverified"
    address = vc.get("physical_address", {})
    state = address.get("state_code", "").strip()
    if not state and park["State"].strip() in US_REGIONS:
        state = park["State"].strip()
    if state not in US_REGIONS:
        return None, "arrival_state_unresolved"
    try:
        lat, lon = float(vc["location"]["latitude"]), float(vc["location"]["longitude"])
        if (
            not math.isfinite(lat)
            or not math.isfinite(lon)
            or not -90 <= lat <= 90
            or not -180 <= lon <= 180
        ):
            return None, "coordinates"
    except (KeyError, TypeError, ValueError):
        return None, "coordinates"
    url = urlparse(vc.get("siteURL", ""))
    if (
        url.scheme not in {"https", "http"}
        or url.netloc not in {"www.nps.gov", "nps.gov"}
        or url.query
    ):
        # Some official records link a partner bookstore or leave this empty.
        # The retained structured record remains the facility evidence; link
        # the actual official park URL rather than inventing a facility page.
        url = urlparse(source.get("url", ""))
        if (
            url.scheme not in {"https", "http"}
            or url.netloc not in {"www.nps.gov", "nps.gov"}
            or url.query
        ):
            return None, "official_visitor_page_missing"
    category = selection.get("primary_category", "national_parks")
    if category not in {"national_parks", "museums"}:
        raise ValueError("unsupported NPS reporting category")
    if category == "museums" and not (
        re.search(r"\bmuseum\b", name, re.I)
        or re.search(
            r"functions only as a museum|a beautiful museum", vc.get("description", ""), re.I
        )
    ):
        return None, "museum_classification_unverified"
    labels = ["daytime", "national_park", "visitor_center"]
    if category == "museums":
        labels += ["culture", "museum"]
    return {
        "source_id": "nps:" + code,
        "name": (source["name"] + " — " + name)[:300],
        "latitude": lat,
        "longitude": lon,
        "region": state,
        "categories": sorted(labels),
        "address": ", ".join(
            str(address.get(k, "")).strip()
            for k in ("line_1", "line_2", "city", "state_code", "postal_code")
            if str(address.get(k, "")).strip()
        )
        or None,
        "url": url._replace(scheme="https").geturl(),
        "source_updated_at": None,
        "provenance": [
            {
                "dataset": "Kaggle NPS park-biodiversity",
                "record_id": park["Park Code"],
                "release": "3",
                "archive_sha256": ARCHIVE_SHA256,
                "source_url": SOURCE_URL,
                "license": "CC0-1.0",
                "source_point_role": "park reference only; never used as arrival",
            },
            {
                "dataset": "National Park Service structured visitor facility",
                "record_id": str(vc["visitorCenterID"]),
                "park_code": code,
                "source_url": evidence["url"],
                "snapshot_sha256": evidence["sha256"],
                "checked_at": checked,
                "license": "LicenseRef-US-Government-Work",
                "arrival_type": "visitor_center",
                "arrival_state_source": "NPS facility physical address"
                if address.get("state_code")
                else "single-state park inventory",
                "primary_category": category,
                "auto_parking_listed": "Parking - Auto" in amenities,
                "operation_basis": "published visitor facility and nonempty weekly schedule; future access and dated hours unknown",
                "limitations": "Check current NPS road/seasonal closures, reservations, fees and facility hours before travel.",
            },
        ],
    }, None


def prepare(path, manifest, *, max_rows, max_bytes):
    if (
        manifest.get("source_url") != SOURCE_URL
        or manifest.get("sha256") != ARCHIVE_SHA256
        or manifest.get("attribution") != ATTRIBUTION
    ):
        raise ValueError("NPS intake requires the inspected Kaggle v3 source and attribution")
    if not re.fullmatch(r"kaggle-nps-v3\+nps-\d{4}-\d{2}-\d{2}", manifest.get("release", "")):
        raise ValueError("NPS intake requires a dated official enrichment release")
    path = Path(path)
    if (
        path.stat().st_size > max_bytes
        or hashlib.sha256(path.read_bytes()).hexdigest() != ARCHIVE_SHA256
    ):
        raise ValueError("NPS archive checksum/size mismatch")
    evidence, selections = manifest.get("official_inputs"), manifest.get("selections")
    if (
        not isinstance(evidence, dict)
        or not isinstance(selections, dict)
        or not 1 <= len(selections) <= 56
        or set(selections) - set(evidence)
    ):
        raise ValueError("NPS selections require retained official snapshots")
    with zipfile.ZipFile(path) as archive:
        info = archive.getinfo("parks.csv")
        if not 0 < info.file_size <= 128 * 1024:
            raise ValueError("NPS parks member oversized")
        reader = csv.DictReader(io.StringIO(archive.read(info).decode("utf-8-sig")))
        if set(reader.fieldnames or []) != {
            "Park Code",
            "Park Name",
            "State",
            "Acres",
            "Latitude",
            "Longitude",
        }:
            raise ValueError("unexpected NPS Kaggle schema")
        records = list(reader)
    if len(records) > max_rows:
        raise ValueError("NPS row ceiling exceeded")
    rows, used, rejects, regions, categories = [], set(), Counter(), Counter(), Counter()
    evidence_bytes = 0
    for park in records:
        code = park["Park Code"].lower()
        if code not in selections:
            rejects["no_reviewed_arrival_selected"] += 1
            continue
        if code in used:
            raise ValueError("duplicate NPS park identity")
        used.add(code)
        data, checked, size = read_snapshot(evidence[code], code)
        evidence_bytes += size
        if evidence_bytes + path.stat().st_size > max_bytes:
            raise ValueError("NPS aggregate source/evidence byte ceiling exceeded")
        row, reason = normalize_arrival(park, data, selections[code], evidence[code], checked)
        if reason:
            rejects[reason] += 1
            continue
        rows.append(row)
        regions[row["region"]] += 1
        categories[selections[code].get("primary_category", "national_parks")] += 1
    if used != set(selections):
        raise ValueError("unknown NPS park selection")
    return rows, {
        "scanned": len(records),
        "accepted": len(rows),
        "bytes": path.stat().st_size + evidence_bytes,
        "rejects": dict(rejects),
        "regions": dict(regions),
        "primary_categories": dict(categories),
    }
