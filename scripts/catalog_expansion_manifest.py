#!/usr/bin/env python3
"""Rebuild reviewed expansion inputs from retained originals; no network or DB.

This publishes existing nps-heritage-arrivals/1 bundles, never a replacement
active generation. The review ledger and starter identities are public review
facts, not an alternative arbitrary-row import format.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.catalog import mixed, nps_heritage
from app.catalog.ingest import prepare

MAX_BYTES = 20 * 1024 * 1024


def read(path, ceiling=2 * 1024 * 1024):
    path = Path(path)
    if not path.is_file() or not 0 < path.stat().st_size <= ceiling:
        raise ValueError("expansion artifact missing or oversized")
    return json.loads(path.read_bytes())


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relocated(evidence, directory):
    """Preserve original evidence fingerprints when moving an artifact directory."""
    result = dict(evidence)
    original = Path(result["path"])
    # Retained evidence lives in either the artifact root or snapshots/.
    suffix = (
        Path("snapshots") / original.name
        if original.parent.name == "snapshots"
        else Path(original.name)
    )
    result["path"] = str(directory / suffix)
    return result


def build(artifacts, review_path, baseline_path, output):
    artifacts, output = Path(artifacts).resolve(), Path(output).resolve()
    review = read(review_path)
    if review.get("schema_version") != "roadtrips-expansion-review/1":
        raise ValueError("unsupported expansion review")
    if fingerprint(baseline_path) != review.get("baseline_identity_sha256"):
        raise ValueError("starter identity fingerprint differs from reviewed baseline")
    baseline = read(baseline_path)
    if len(baseline) != 82 or len({r["source_id"] for r in baseline}) != 82:
        raise ValueError("expected 82 unique starter identities")
    inventory = relocated(review["inventory"], artifacts)
    driving = relocated(review["driving"], artifacts)
    if inventory["sha256"] != nps_heritage.EXPANSION_INDEX_SHA256:
        raise ValueError("expansion inventory differs from reviewed acquisition")
    if fingerprint(driving["path"]) != driving["sha256"]:
        raise ValueError("driving evidence checksum mismatch")
    known = {r["source_id"]: r for r in baseline}
    pending, all_rows, reports = [], [], []
    batches = review["batches"]
    if not isinstance(batches, list) or not 1 <= len(batches) <= 20:
        raise ValueError("expansion requires 1..20 reviewed batches")
    if len({b["id"] for b in batches}) != len(batches):
        raise ValueError("duplicate expansion batch")
    for batch in batches:
        name = batch["id"]
        if not isinstance(name, str) or not re.fullmatch(
            r"heritage-(?:0[1-9]|1[0-9]|20)", name
        ):
            raise ValueError("unreviewed expansion batch")
        target = output / (name + ".json")
        manifest_path = target.with_suffix(".json.manifest.json")
        rows_path = target.with_suffix(".preview.jsonl")
        if any(p.exists() for p in (target, manifest_path, rows_path)):
            raise ValueError("expansion output already exists")
        inputs, selections, expected = {}, {}, {}
        for record in batch["records"]:
            code = record["unit_code"]
            if code in selections or record["source_id"] in known:
                raise ValueError("duplicate expansion or starter identity")
            inputs[code] = relocated(record["operation_evidence"], artifacts)
            selections[code] = record["selection"]
            expected[record["source_id"]] = record
        if not 1 <= len(selections) <= 25:
            raise ValueError("expansion batch must contain 1..25 reviewed units")
        bundle = {
            "inventory": inventory,
            "inputs": inputs,
            "selections": selections,
            "driving": driving,
        }
        raw = (json.dumps(bundle, indent=2) + "\n").encode()
        rights_path = (
            ROOT / "frontend/public/licenses/LicenseRef-US-Government-Work.txt"
        )
        manifest = {
            "schema_version": nps_heritage.SCHEMA,
            "release": review["source_release"],
            "retrieved_at": review["checked_at"],
            "source_url": nps_heritage.SOURCE_URL,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "filters": {"explicit_visitor_facilities": True, "expansion_batch": name},
            "attribution": nps_heritage.ATTRIBUTION,
            "licenses": {
                "LicenseRef-US-Government-Work": {
                    "path": str(rights_path),
                    "sha256": fingerprint(rights_path),
                }
            },
        }
        # prepare reads the original bundle path; temporary publication is local
        # and removed even on failure, before any final output is published.
        output.mkdir(parents=True, exist_ok=True)
        temporary = output / (name + ".partial")
        temporary_created = False
        try:
            with temporary.open("xb") as stream:
                temporary_created = True
                stream.write(raw)
            rows, report = prepare(
                temporary, manifest, max_rows=500, max_bytes=MAX_BYTES
            )
        finally:
            # An existing partial belongs to its original producer.
            if temporary_created:
                temporary.unlink(missing_ok=True)
        if len(rows) != len(expected) or report["rejects"]:
            raise ValueError("reviewed expansion no longer passes current admission")
        for row in rows:
            record = expected[row["source_id"]]
            for key in (
                "source_id",
                "name",
                "latitude",
                "longitude",
                "region",
                "categories",
            ):
                if row[key] != record[key]:
                    raise ValueError("source facts differ from reviewed expansion")
            for other in known.values():
                if row["source_id"] == other["source_id"] or (
                    row["region"] == other["region"]
                    and mixed.names(row).intersection(mixed.names(other))
                    and mixed.distance(row, other) <= 250
                ):
                    raise ValueError(
                        "unresolved duplicate destination against starter or expansion"
                    )
            known[row["source_id"]] = row
        pending.extend(
            [
                (target, raw),
                (manifest_path, (json.dumps(manifest, indent=2) + "\n").encode()),
                (
                    rows_path,
                    (
                        "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows)
                    ).encode(),
                ),
            ]
        )
        all_rows.extend(rows)
        reports.append({"batch": name, "bundle": str(target), "report": report})
    # Validate every child before publishing any final bundle/manifest pair.
    created = []
    try:
        for path, raw in pending:
            with path.open("xb") as stream:
                created.append(path)
                stream.write(raw)
    except BaseException:
        for path in created:
            path.unlink(missing_ok=True)
        raise
    return {"accepted": len(all_rows), "baseline": len(baseline), "batches": reports}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            build(args.artifacts, args.review, args.baseline, args.output),
            sort_keys=True,
        )
    )
