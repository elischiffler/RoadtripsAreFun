#!/usr/bin/env python3
"""Profile the measured CSV schemas in five bounded LOCAL Kaggle archives.

This performs no downloads, licensing approval or database access. It reads only
the named CSV member, never photos/species/GIS, and emits aggregate review data.
Coordinates are source points, not verified driving arrivals. No source listed
here becomes importable except through its separate reviewed catalog adapter.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import zipfile
from collections import Counter
from pathlib import Path

MAX_BYTES = 20 * 1024 * 1024
MAX_ROWS = 50_000
SOURCES = {
    "boulder-v1": (
        "paultimothymooney/trailstrailheadsandrockformationsinboulder",
        1,
        "OSMP_Trailheads.csv",
        "OSMPTrailheadsOSMPACCESSID",
        "Y",
        "X",
        "OSMPTrailheadsOSMPACCESSTYPE",
    ),
    "coasters-v2": (
        "robikscube/rollercoaster-database",
        2,
        "coaster_db.csv",
        "coaster_name",
        "latitude",
        "longitude",
        "Status",
    ),
    "museums-v1": (
        "imls/museum-directory",
        1,
        "museums.csv",
        "Museum ID",
        "Latitude",
        "Longitude",
        "Museum Type",
    ),
    "parks-v3": (
        "nationalparkservice/park-biodiversity",
        3,
        "parks.csv",
        "Park Code",
        "Latitude",
        "Longitude",
        "State",
    ),
    "roadside-v4": (
        "headsortails/us-roadside-attractions-photographs",
        4,
        "us_roadside_attractions.csv",
        "index",
        None,
        None,
        "year",
    ),
}


def profile(path, source):
    slug, version, member, identity, lat, lon, group = SOURCES[source]
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError("archive missing or exceeds 20 MiB")
    raw = path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        matches = [m for m in archive.infolist() if m.filename == member]
        if len(matches) != 1 or not 0 < matches[0].file_size <= MAX_BYTES:
            raise ValueError("CSV member missing, duplicated or exceeds 20 MiB")
        content = archive.read(matches[0])
    csv.field_size_limit(64 * 1024)
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    fields = reader.fieldnames or []
    required = {x for x in (identity, lat, lon, group) if x}
    if not required <= set(fields) or len(fields) != len(set(fields)):
        raise ValueError("unexpected CSV schema")
    seen, groups = set(), Counter()
    count = duplicates = valid = missing_identity = malformed = 0
    physical = administrative_only = 0
    for row in reader:
        count += 1
        if count > MAX_ROWS:
            raise ValueError("CSV exceeds 50,000-row profile ceiling")
        if None in row or any(v is None for v in row.values()):
            malformed += 1
            continue
        key = row[identity].strip()
        missing_identity += not bool(key)
        duplicates += key in seen
        seen.add(key)
        groups[row[group].strip() or "unknown"] += 1
        if lat and lon:
            try:
                a, b = float(row[lat]), float(row[lon])
                valid += (
                    math.isfinite(a) and math.isfinite(b) and -90 <= a <= 90 and -180 <= b <= 180
                )
            except ValueError:
                pass
        if source == "museums-v1":
            physical += bool(row["Street Address (Physical Location)"].strip())
            administrative_only += not row["Street Address (Physical Location)"].strip() and bool(
                row["Street Address (Administrative Location)"].strip()
            )
    return {
        "review_only": True,
        "accepted_for_import": 0,
        "kaggle_slug": slug,
        "version": version,
        "source_url": f"https://www.kaggle.com/datasets/{slug}/versions/{version}",
        "archive_bytes": len(raw),
        "archive_sha256": hashlib.sha256(raw).hexdigest(),
        "member": member,
        "member_bytes": len(content),
        "member_sha256": hashlib.sha256(content).hexdigest(),
        "columns": fields,
        "rows": count,
        "duplicate_keys": duplicates,
        "missing_identity": missing_identity,
        "malformed_rows": malformed,
        "finite_wgs84_source_points": valid if lat else None,
        "source_points_are_verified_arrivals": False,
        "group_field": group,
        "groups": dict(sorted(groups.items())),
        **(
            {
                "physical_street_addresses": physical,
                "administrative_only_street_addresses": administrative_only,
            }
            if source == "museums-v1"
            else {}
        ),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--source", choices=sorted(SOURCES), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    result = profile(args.input, args.source)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "kaggle_slug",
                    "version",
                    "rows",
                    "finite_wgs84_source_points",
                    "accepted_for_import",
                )
            }
        )
    )
