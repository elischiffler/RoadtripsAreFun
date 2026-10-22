#!/usr/bin/env python3
"""Replay two-place government geometry research; never grant routing admission."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]


def review(root):
    from app.catalog.usfs import ring_contains

    root = Path(root).resolve()
    receipts = json.loads((root / "receipts.json").read_bytes())
    evidence = {}
    for receipt in receipts:
        if receipt.get("status") != 200 or not receipt.get("path"):
            continue
        path = (root / receipt["path"]).resolve()
        if (
            not path.is_relative_to(root)
            or not 0 < path.stat().st_size <= 2 * 1024 * 1024
        ):
            raise ValueError("geometry evidence path/size differs")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
            raise ValueError("geometry evidence digest differs")
        evidence[receipt["id"]] = (receipt, raw)

    def load(ident, expected):
        receipt, raw = evidence[ident]
        target = urlparse(receipt["url"])
        if target.scheme + "://" + target.netloc + target.path != expected:
            raise ValueError("geometry source is not the reviewed agency layer")
        if parse_qs(target.query).get("outSR") != ["4326"]:
            raise ValueError("geometry must be acquired explicitly in WGS84")
        data = json.loads(raw)
        if data.get("exceededTransferLimit") or data.get("error"):
            raise ValueError("geometry query is incomplete or failed")
        return data["features"]

    roads = load(
        "chapelhill-front-parking-approaches",
        "https://gis-portal.townofchapelhill.org/server/rest/services/OpenData/Streets/FeatureServer/0/query",
    )
    lots = load(
        "unc-parking-near-ncbg",
        "https://gismaps.unc.edu/arcgis/rest/services/UNCOpenData/UNCOpenData/FeatureServer/7/query",
    )
    amc_roads = load(
        "deldot-public-approach-context",
        "https://enterprise.firstmaptest.delaware.gov/arcgis/rest/services/Transportation/DE_Roadways_Main/MapServer/1/query",
    )
    amc_names = {row["attributes"]["STREET_NAME"].upper() for row in amc_roads}
    if "BAYSIDE DRIVE" not in amc_names or "72 - AIR FORCE" not in amc_names:
        raise ValueError(
            "AMC context lacks the reviewed public-road/military-road distinction"
        )
    driveway = next(r for r in roads if r["attributes"]["OBJECTID"] == 8202)
    street = next(r for r in roads if r["attributes"]["OBJECTID"] == 9286)
    lot = next(r for r in lots if r["attributes"]["OBJECTID"] == 3864)
    if (
        driveway["attributes"]["FullName"] != "PARKING LOT"
        or driveway["attributes"]["Cross1"] != "OLD MASON FARM RD"
        or street["attributes"]["FullName"] != "OLD MASON FARM RD"
        or lot["attributes"]["LOT_NAME"] != "BOTANICAL GARDEN"
        or lot["attributes"]["LOT_NUMBER"] != "P256"
    ):
        raise ValueError(
            "geometry entities differ from the reviewed front-lot relationship"
        )
    path = driveway["geometry"]["paths"]
    street_paths = street["geometry"]["paths"]
    if len(path) != 1 or len(street_paths) != 1:
        raise ValueError("driveway/street geometry needs a new multipart review")
    junction = [
        p
        for p in (path[0][0], path[0][-1])
        if p in (street_paths[0][0], street_paths[0][-1])
    ]
    if len(junction) != 1:
        raise ValueError("no unique original shared street/driveway endpoint")
    internal = path[0][-1] if junction[0] == path[0][0] else path[0][0]
    if (
        sum(ring_contains(*internal, ring) for ring in lot["geometry"]["rings"]) % 2
        != 1
    ):
        raise ValueError(
            "driveway does not lead into the named university parking polygon"
        )
    return {
        "schema_version": "roadtrips-arrival-geometry-research/1",
        "scope": "Government geometry corroboration plus separate operator map review; research only",
        "admission_changes": 0,
        "qualified_arrivals": 0,
        "itinerary_ready": 0,
        "ncbg": {
            "source_id": "catalog-pilot:wikidata:Q1099139",
            "status": "source_geometry_candidate_not_admitted",
            "front_driveway_coordinate_lat_lon": list(reversed(junction[0])),
            "inside_parking_junction_lat_lon": list(reversed(internal)),
            "point_role": "Original shared road/driveway endpoint; not centroid or routing snap",
            "method": "Chapel Hill streets8202/9286 share an exact endpoint;8202 leads into UNC parking3864/P256",
            "approach": "Old Mason Farm Road front lot, corroborated by the operator visitor page and2025 map",
            "forbidden_visitor_vehicle_approach": "Laurel Hill Road service/back entrance remains closed",
            "coordinate_encoding": "Agency-transformed EPSG4326; full native returned precision retained",
            "horizontal_accuracy_metres": None,
            "display_precision": "Round to5decimals for display; decimal resolution is not positional accuracy",
            "limits": [
                "Not operator-published latitude/longitude or a surveyed gate",
                "UNC lot observation date and current driveway/gate position unverified",
                "Separate geometry reuse/redistribution rights review remains unresolved",
                "No driving leg, pedestrian connection or full calendar qualification",
            ],
        },
        "amc": {
            "source_id": "catalog-pilot:wikidata:Q21028346",
            "status": "held_public_gate_or_parking_point_unknown",
            "arrival_coordinate_lat_lon": None,
            "approach": "Operator requires its separate Route9/Kitts Hummock Road approach via exit91; no Dover AFB entry",
            "limits": [
                "DelDOT public context contains Bayside Drive and multiple72-AirForce roads",
                "Military road geometry does not identify the public museum gate, parking or fence boundary",
                "No road endpoint or venue pin was promoted to a public arrival",
            ],
        },
        "evidence": receipts,
        "operator_sources": [
            "https://amcmuseum.org/visit/",
            "https://amcmuseum.org/faq/",
            "https://ncbg.unc.edu/visit/visitor-information/",
            "https://ncbg.unc.edu/2025/07/08/storm-recovery-updates/",
            "https://ncbg.unc.edu/wp-content/uploads/sites/963/2025/04/NCBG-Master-Map-2025_web.pdf",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--research-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = review(args.research_dir)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
