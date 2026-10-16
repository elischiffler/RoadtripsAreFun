#!/usr/bin/env python3
"""Rebuild inspected NPS nature source children from retained originals, offline.

Review facts support comparison/deduplication, never arbitrary-row admission.
Every new row comes from the existing public NPS schema's explicit nature profile.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.catalog import mixed, nps_nature, nps_public
from app.catalog.ingest import prepare

FIELDS = ("source_id", "name", "latitude", "longitude", "region", "categories")
MAX_BYTES = 20 * 1024 * 1024


def read(path):
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= 2 * 1024 * 1024:
        raise ValueError("nature review artifact missing or oversized")
    return json.loads(path.read_bytes())


def baseline(directory):
    directory = Path(directory)
    rows = read(directory / "starter-82-identities.json")
    for name in (
        "reviewed-103.preview.jsonl",
        "reviewed-nature-12.preview.jsonl",
        "reviewed-venues-17.preview.jsonl",
    ):
        path = directory / name
        if not 0 < path.stat().st_size <= 2 * 1024 * 1024:
            raise ValueError("baseline review preview oversized")
        rows.extend(json.loads(line) for line in path.read_text().splitlines())
    if len(rows) != 214 or len({r["source_id"] for r in rows}) != 214:
        raise ValueError("expected 214 unique reviewed baseline identities")
    facts = [
        {k: r[k] for k in FIELDS} for r in sorted(rows, key=lambda r: r["source_id"])
    ]
    digest = hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()
    return rows, digest


def build(artifacts, review_path, baseline_directory, output):
    artifacts, output = Path(artifacts).resolve(), Path(output).resolve()
    review = read(review_path)
    if (
        review.get("schema_version") != "roadtrips-nps-nature-review/1"
        or review.get("profile") != nps_nature.PROFILE
    ):
        raise ValueError("unsupported inspected nature review")
    known, baseline_sha = baseline(baseline_directory)
    if review.get("baseline_identity_sha256") != baseline_sha:
        raise ValueError("reviewed 214 baseline facts differ")
    used_ids = {r["source_id"] for r in known}
    used_units = {
        r["source_id"].split(":")[1]
        for r in known
        if r["source_id"].startswith(("nps:", "nps-public:", "nps-heritage:"))
    }
    known_native = {
        str(p["record_id"])
        for r in known
        for p in r.get("provenance", [])
        if p.get("dataset") == "National Park Service structured visitor facility"
    }
    batches = review.get("batches")
    if (
        not isinstance(batches, list)
        or not 1 <= len(batches) <= 20
        or len({b["id"] for b in batches}) != len(batches)
    ):
        raise ValueError("require unique bounded nature batches")
    output.mkdir(parents=True, exist_ok=True)
    pending, reports = [], []
    for batch in batches:
        name = batch["id"]
        if not re.fullmatch(r"nature-(?:0[1-9]|1[0-9]|20)", name):
            raise ValueError("uninspected nature batch name")
        path = output / (name + ".json")
        manifest_path = path.with_suffix(".json.manifest.json")
        preview = path.with_suffix(".preview.jsonl")
        if any(p.exists() for p in (path, manifest_path, preview)):
            raise ValueError("nature output already exists")
        inputs, selections, expected = {}, {}, {}
        for item in batch["records"]:
            code = item["unit_code"]
            if (
                code in used_units
                or code in inputs
                or item["row"]["source_id"] in used_ids
            ):
                raise ValueError("duplicate natural unit or reviewed identity")
            inputs[code] = {
                **item["operation_evidence"],
                "path": str(artifacts / "snapshots" / (code + ".json")),
            }
            selections[code] = {"visitor_center_id": item["visitor_center_id"]}
            expected[item["row"]["source_id"]] = item["row"]
        bundle = {
            "profile": nps_nature.PROFILE,
            "inventory": {
                **review["inventory"],
                "path": str(artifacts / "inventory.json"),
            },
            "inputs": inputs,
            "selections": selections,
            "driving": {
                **review["driving"],
                "path": str(artifacts / "driving-reviewed.json"),
            },
        }
        if "driving_original" in review:
            bundle["driving_original"] = {
                **review["driving_original"],
                "path": str(artifacts / "driving-original.json"),
            }
        raw = (json.dumps(bundle, indent=2) + "\n").encode()
        license_path = (
            ROOT / "frontend/public/licenses/LicenseRef-US-Government-Work.txt"
        )
        manifest = {
            "schema_version": nps_public.SCHEMA,
            "release": review["source_release"],
            "retrieved_at": review["checked_at"],
            "source_url": nps_nature.SOURCE_URL,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "filters": {
                "arrival_profile": nps_nature.PROFILE,
                "explicit_visitor_facilities": True,
                "nature_batch": name,
            },
            "attribution": nps_nature.ATTRIBUTION,
            "licenses": {
                "LicenseRef-US-Government-Work": {
                    "path": str(license_path),
                    "sha256": hashlib.sha256(license_path.read_bytes()).hexdigest(),
                }
            },
        }
        temporary = output / (name + ".partial")
        created = False
        try:
            with temporary.open("xb") as stream:
                created = True
                stream.write(raw)
            rows, report = prepare(
                temporary, manifest, max_rows=500, max_bytes=MAX_BYTES
            )
        finally:
            if created:
                temporary.unlink(missing_ok=True)
        if len(rows) != len(expected) or report["rejects"]:
            raise ValueError("reviewed nature sources no longer pass admission")
        for row in rows:
            if row != expected.get(row["source_id"]):
                raise ValueError(
                    "natural source facts/provenance differ from reviewed row"
                )
            native = next(
                str(p["record_id"])
                for p in row["provenance"]
                if p.get("dataset")
                == "National Park Service structured visitor facility"
            )
            if native in known_native:
                raise ValueError("shared visitor facility requires parent review")
            for other in known:
                if row["source_id"] == other["source_id"] or (
                    row["region"] == other["region"]
                    and mixed.names(row).intersection(mixed.names(other))
                    and mixed.distance(row, other) <= 250
                ):
                    raise ValueError("unresolved colocated destination")
            known.append(row)
            known_native.add(native)
            used_ids.add(row["source_id"])
            used_units.add(row["source_id"].split(":")[1])
        pending.extend(
            [
                (path, raw),
                (manifest_path, (json.dumps(manifest, indent=2) + "\n").encode()),
                (
                    preview,
                    "".join(
                        json.dumps(r, sort_keys=True) + "\n" for r in rows
                    ).encode(),
                ),
            ]
        )
        reports.append({"batch": name, "report": report})
    created_paths = []
    try:
        for path, content in pending:
            with path.open("xb") as stream:
                created_paths.append(path)
                stream.write(content)
    except BaseException:
        for path in created_paths:
            path.unlink(missing_ok=True)
        raise
    return {
        "baseline": 214,
        "accepted": sum(b["report"]["accepted"] for b in reports),
        "batches": reports,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", required=True, type=Path)
    parser.add_argument("--review", required=True, type=Path)
    parser.add_argument("--baseline-directory", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            build(args.artifacts, args.review, args.baseline_directory, args.output),
            sort_keys=True,
        )
    )
