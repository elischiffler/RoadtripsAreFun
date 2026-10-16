#!/usr/bin/env python3
"""Rebuild the immutable reviewed Kaggle parks child; no network or database."""

import argparse
import hashlib
import importlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
kaggle_parks = importlib.import_module("app.catalog.kaggle_parks")


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(sources, output):
    sources, output = Path(sources).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("park output directory already exists")
    review = json.loads((sources / "review.json").read_bytes())
    acquired = min(
        page["retrieved_at"] for profile in review["records"] for page in profile["pages"]
    )
    bundle = {
        key: {
            "path": str(sources / name),
            "sha256": fingerprint(sources / name),
            "retrieved_at": acquired,
        }
        for key, name in (
            ("archive", "archive.zip"),
            ("metadata", "source-metadata.json"),
            ("review", "review.json"),
        )
    }
    # The retained original acquisition timestamp is supplied by the source index,
    # never replaced with rebuild time or claimed as publisher modification time.
    acquisition = json.loads((sources / "acquisition.json").read_bytes())
    for key in ("archive", "metadata"):
        bundle[key]["retrieved_at"] = acquisition[key]["retrieved_at"]
    bundle["review"]["retrieved_at"] = review["reviewed_at"]
    raw = (json.dumps(bundle, indent=2) + "\n").encode()
    licenses = {}
    for identifier in ("CC-BY-4.0", "CC0-1.0", "ODbL-1.0"):
        path = ROOT / "frontend/public/licenses" / (identifier + ".txt")
        licenses[identifier] = {"path": str(path), "sha256": fingerprint(path)}
    manifest = {
        "schema_version": kaggle_parks.SCHEMA,
        "release": "kaggle-rideinpark-v1+review-" + review["reviewed_at"][:10],
        "retrieved_at": datetime.now(UTC).isoformat(),
        "source_url": kaggle_parks.SOURCE_URL,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "filters": {
            "country": "US",
            "explicit_independent_visitor_review": True,
            "native_coordinates_unchanged": True,
            "practical_public_arrival_required": True,
        },
        "attribution": kaggle_parks.ATTRIBUTION,
        "licenses": licenses,
    }
    output.mkdir(parents=True)
    target = output / "reviewed-parks.json"
    target.write_bytes(raw)
    rows, report = kaggle_parks.prepare(
        target, manifest, max_rows=50_000, max_bytes=100 * 1024 * 1024
    )
    target.with_suffix(".json.manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (output / "reviewed-parks.preview.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
    (output / "report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    selected = {}
    destinations = []
    originals = {
        key: json.loads((sources / receipt["path"]).read_bytes())
        for key, receipt in review["arrival_evidence"].items()
    }
    for row in rows:
        proof = row["provenance"][4]
        destinations.append({"source_id": row["source_id"], "elements": proof["elements"]})
        for element in proof["elements"]:
            identity = (element["type"], element["id"])
            if identity not in selected:
                selected[identity] = next(
                    original
                    for original in originals[element["source_snapshot"]]["elements"]
                    if (original["type"], original["id"]) == identity
                )
    allowed_tags = {
        "highway",
        "service",
        "access",
        "motor_vehicle",
        "motorcar",
        "vehicle",
        "layer",
        "name",
        "amenity",
        "building",
        "entrance",
    }
    public_elements = [
        {
            **{
                key: value
                for key, value in element.items()
                if key in {"type", "id", "geometry", "lat", "lon"}
            },
            "tags": {
                key: value for key, value in element.get("tags", {}).items() if key in allowed_tags
            },
        }
        for element in selected.values()
    ]
    (output / "public-arrival-osm.json").write_text(
        json.dumps(
            {
                "schema_version": "roadtrips-selected-osm-arrivals/1",
                "license": "ODbL-1.0",
                "license_url": "https://opendatacommons.org/licenses/odbl/1-0/",
                "attribution": "OpenStreetMap contributors",
                "review_sha256": kaggle_parks.REVIEW_SHA256,
                "changes": "Selected practical-arrival facts and routing/access/name tags only; native OSM identities, selected tag values and geometry unchanged. Contact details, unrelated tags, operator HTML and images excluded.",
                "source_snapshots": rows[0]["provenance"][4]["source_snapshots"],
                "destinations": destinations,
                "elements": public_elements,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (output / "completion.json").write_text(
        json.dumps(
            {
                "accepted": len(rows),
                "bundle_sha256": manifest["sha256"],
                "review_sha256": kaggle_parks.REVIEW_SHA256,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return {
        "accepted": len(rows),
        "bytes": report["bytes"],
        "primary_categories": report["primary_categories"],
        "regions": report["regions"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.sources, arguments.output), sort_keys=True))
