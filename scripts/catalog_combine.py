#!/usr/bin/env python3
"""Combine regional extracts into ONE complete replacement catalog generation.

Activation replaces the entire active generation: include every region to retain
in this command. Importing/activating successive regional files does NOT append
coverage. This command does not read the active database, infer retained regions,
or claim complete geographic coverage. Review the combined manifest before stage
and activation. Output JSONL and its .manifest.json never overwrite existing files;
the manifest is published last and is the completion marker.
"""

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.catalog.ingest import (  # noqa: E402 — standalone repository script
    MAX_BYTES,
    MAX_ROWS,
    prepare,
    validate_manifest,
)
from app.catalog.normalize import normalize  # noqa: E402

MAX_INPUTS = 100


def combine(
    inputs,
    output,
    *,
    max_rows=MAX_ROWS,
    max_bytes=MAX_BYTES,
    selected_ids=None,
    arrival_review=None,
):
    """Validate bounded immutable snapshots, deduplicate, then publish a new pair."""
    inputs = list(inputs)
    if not 1 <= len(inputs) <= MAX_INPUTS:
        raise ValueError("require 1..100 regional inputs")
    if not 1 <= max_rows <= MAX_ROWS or not 1 <= max_bytes <= MAX_BYTES:
        raise ValueError("combined limits exceed hard ceilings")
    if selected_ids is not None and (
        not isinstance(selected_ids, set)
        or not 1 <= len(selected_ids) <= max_rows
        or any(not isinstance(v, str) or not v for v in selected_ids)
    ):
        raise ValueError("explicit selection must be a bounded set of source IDs")
    output = Path(output)
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    if output.exists() or manifest_path.exists():
        raise ValueError("output already exists; use a new path")
    output.parent.mkdir(parents=True, exist_ok=True)
    rows, evidence, licenses = {}, [], {}
    attributions, sources = set(), set()
    regions, categories = Counter(), Counter()
    release = schema = None
    total_input_bytes = output_bytes = duplicates = 0
    digest = hashlib.sha256()
    with tempfile.TemporaryDirectory(prefix="catalog-combine-", dir=output.parent) as temp:
        temp = Path(temp)
        combined = temp / "combined.jsonl"
        with combined.open("xb") as destination:
            for index, input_path in enumerate(inputs):
                input_path = Path(input_path)
                source_manifest = input_path.with_suffix(input_path.suffix + ".manifest.json")
                with source_manifest.open("rb") as stream:
                    manifest_bytes = stream.read(32_769)
                if len(manifest_bytes) > 32_768:
                    raise ValueError("input manifest exceeds 32 KiB")
                manifest = json.loads(manifest_bytes)
                validate_manifest(manifest)
                if "arrival_review" in manifest and arrival_review is None:
                    raise ValueError("reviewed input requires an explicit complete arrival review")
                if manifest["schema_version"] in {
                    "kaggle-boulder-trailheads/1",
                    "kaggle-nps-arrivals/1",
                    "nps-public-arrivals/1",
                    "kaggle-loc-roadside-arrivals/1",
                    "roadtrips-mixed-catalog/1",
                }:
                    raise ValueError(
                        "regional combiner supports Overture only; Kaggle requires a reviewed cross-source generation"
                    )
                if release is None:
                    release, schema = manifest["release"], manifest["schema_version"]
                if (release, schema) != (
                    manifest["release"],
                    manifest["schema_version"],
                ):
                    raise ValueError("inputs must have identical pinned release and schema")
                with input_path.open("rb") as stream:
                    raw = stream.read(max_bytes - total_input_bytes + 1)
                total_input_bytes += len(raw)
                if total_input_bytes > max_bytes:
                    raise ValueError("aggregate input byte ceiling exceeded")
                snapshot = temp / f"input-{index}.jsonl"
                snapshot.write_bytes(raw)
                validated, report = prepare(snapshot, manifest)
                if not validated or set(report["rejects"]) - {"duplicate"}:
                    raise ValueError("regional input contains empty or rejected records")
                for spdx, license_evidence in manifest["licenses"].items():
                    if spdx in licenses and licenses[spdx] != license_evidence:
                        # Distinct local paths are fine only when both license and notice match.
                        previous = licenses[spdx]
                        if previous["sha256"] != license_evidence["sha256"] or previous.get(
                            "notice", {}
                        ).get("sha256") != license_evidence.get("notice", {}).get("sha256"):
                            raise ValueError("conflicting license evidence")
                    else:
                        licenses[spdx] = license_evidence
                attributions.add(manifest["attribution"])
                sources.add(manifest["source_url"])
                evidence.append(
                    {
                        "artifact": input_path.name,
                        "sha256": manifest["sha256"],
                        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                        "filters": manifest["filters"],
                        "source_url": manifest["source_url"],
                        "attribution": manifest["attribution"],
                        "retrieved_at": manifest["retrieved_at"],
                        # The retained original manifest contains the full STAC
                        # asset receipts. Repeating them for every region can
                        # exceed the hard 32 KiB manifest ceiling. Pin that
                        # complete evidence instead of truncating or dropping it.
                        "manifest_artifact": source_manifest.name,
                        "extraction_sha256": hashlib.sha256(
                            json.dumps(manifest.get("extraction"), sort_keys=True).encode()
                        ).hexdigest(),
                    }
                )
                for line in raw.splitlines():
                    feature = json.loads(line)
                    row, rejection = normalize(feature)
                    if rejection:
                        raise ValueError("validated input changed unexpectedly")
                    ident = row["source_id"]
                    if selected_ids is not None and ident not in selected_ids:
                        continue
                    if ident in rows:
                        if rows[ident] != row:
                            raise ValueError("conflicting duplicate source ID across regions")
                        duplicates += 1
                        continue
                    if len(rows) >= max_rows:
                        raise ValueError("combined unique row ceiling exceeded")
                    encoded = (
                        json.dumps(feature, ensure_ascii=False, separators=(",", ":")) + "\n"
                    ).encode()
                    output_bytes += len(encoded)
                    if output_bytes > max_bytes:
                        raise ValueError("combined output byte ceiling exceeded")
                    destination.write(encoded)
                    digest.update(encoded)
                    rows[ident] = row
                    regions[row["region"]] += 1
                    categories.update(row["categories"])
                snapshot.unlink()
        if selected_ids is not None and set(rows) != selected_ids:
            raise ValueError("selection includes source IDs absent from reviewed inputs")
        manifest = {
            "release": release,
            "schema_version": schema,
            "retrieved_at": datetime.now(UTC).isoformat(),
            "source_url": f"s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/",
            "sha256": digest.hexdigest(),
            "filters": {
                "generation_semantics": "complete replacement; only the supplied regional inputs are retained",
                "regional_input_count": len(evidence),
                "selected_id_count": len(selected_ids) if selected_ids is not None else None,
                "selected_ids_sha256": hashlib.sha256(
                    json.dumps(sorted(selected_ids)).encode()
                ).hexdigest()
                if selected_ids is not None
                else None,
            },
            "attribution": "; ".join(sorted(attributions)),
            "licenses": licenses,
            "inputs": evidence,
            "source_urls": sorted(sources),
            "combination": {
                "inputs": len(inputs),
                "accepted": len(rows),
                "duplicates": duplicates,
                "input_bytes": total_input_bytes,
                "output_bytes": output_bytes,
                "regions": dict(regions),
                "categories": dict(categories),
            },
        }
        if arrival_review is not None:
            manifest["arrival_review"] = arrival_review
        # Revalidate exact output, including licensing, checksum, row and byte ceilings.
        prepare(combined, manifest, max_rows=max_rows, max_bytes=max_bytes)
        manifest_temp = temp / "manifest.json"
        serialized_manifest = json.dumps(manifest, indent=2) + "\n"
        if len(serialized_manifest.encode()) > 32_768:
            raise ValueError("combined manifest exceeds 32 KiB; reduce metadata/input count")
        manifest_temp.write_text(serialized_manifest)
        published = False
        try:
            os.link(combined, output)
            published = True
            os.link(manifest_temp, manifest_path)
        except BaseException:
            if published:
                output.unlink()
            raise
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="all regional JSONL files to retain")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-rows", type=int, default=MAX_ROWS)
    parser.add_argument("--max-bytes", type=int, default=MAX_BYTES)
    parser.add_argument(
        "--selected-ids",
        type=Path,
        help="explicit bounded JSON list of native Overture IDs",
    )
    parser.add_argument(
        "--arrival-review", type=Path, help="retained explicit publisher-arrival review JSON"
    )
    args = parser.parse_args()
    selected = None
    review = None
    if args.arrival_review:
        with args.arrival_review.open("rb") as stream:
            raw = stream.read(32_769)
        if len(raw) > 32_768:
            parser.error("arrival review exceeds 32 KiB")
        review = json.loads(raw)
    if args.selected_ids:
        with args.selected_ids.open("rb") as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            parser.error("selection exceeds 1 MiB")
        values = json.loads(raw)
        if (
            not isinstance(values, list)
            or any(not isinstance(v, str) for v in values)
            or len(set(values)) != len(values)
        ):
            parser.error("selection must be a unique list of IDs")
        selected = set(values)
    result = combine(
        args.inputs,
        args.output,
        max_rows=args.max_rows,
        max_bytes=args.max_bytes,
        selected_ids=selected,
        arrival_review=review,
    )
    print(json.dumps(result["combination"], sort_keys=True))


if __name__ == "__main__":
    main()
