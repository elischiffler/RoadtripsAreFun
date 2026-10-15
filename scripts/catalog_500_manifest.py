#!/usr/bin/env python3
"""Rebuild the complete 500-place proposal from retained originals; no DB/network.

First replay the portable 214 package and PR44's corrected nature package. Pass
the resulting flat 243 bundle and this task's new-sources directory. All output
is written to a new directory; completion.json is published only after every
source, count and preserved-row comparison passes. Source inputs are read-only.
"""

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))
from app.catalog import expansion_venue_profiles, usfs
from app.catalog.ingest import prepare

from scripts.catalog_combine import combine
from scripts.catalog_mix import build as mix

MAX_BYTES = 64 * 1024 * 1024


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True)
        stream.write("\n")


def rows_sha(rows):
    return hashlib.sha256(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows).encode()
    ).hexdigest()


def build(sources, baseline, output):
    sources, baseline, output = (
        Path(sources).resolve(),
        Path(baseline).resolve(),
        Path(output).resolve(),
    )
    if output.exists():
        raise ValueError("output already exists; use a new work directory")
    baseline_rows, baseline_report = prepare(
        baseline,
        read(baseline.with_suffix(baseline.suffix + ".manifest.json")),
        max_rows=500,
        max_bytes=MAX_BYTES,
    )
    baseline_bundle = read(baseline)
    if (
        len(baseline_rows) != 243
        or baseline_report["duplicates"]
        or len(baseline_bundle["inputs"]) != 16
    ):
        raise ValueError(
            "require the complete, revalidated flat 16-child PR44 baseline"
        )
    expected_prior = [
        json.loads(line)
        for line in (
            ROOT
            / "docs/data/catalog-expansion-500-20261015/reviewed-243.expected.jsonl"
        )
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    if {r["source_id"]: r for r in baseline_rows} != {
        r["source_id"]: r for r in expected_prior
    }:
        raise ValueError(
            "baseline differs from the preserved 243 reviewed rows/provenance"
        )
    original_fs = sources / "usfs-source"
    if sha(original_fs / "source-index.json") != usfs.INDEX_SHA256:
        raise ValueError("USFS source inventory changed")
    output.mkdir(parents=True)
    fs = output / "usfs"
    fs.mkdir()
    for name in ("source-index.json", "driving-index.json"):
        shutil.copyfile(original_fs / name, fs / name)
    for name in ("sources", "driving"):
        shutil.copytree(original_fs / name, fs / name)
    selection = read(
        ROOT / "docs/data/catalog-expansion-500-20261015/usfs-selection.json"
    )
    original_bundle = read(original_fs / "usfs-final.json")
    bundle = {"index": original_bundle["index"], "selection": selection}
    write(fs / "usfs.json", bundle)
    manifest = read(original_fs / "usfs-final.json.manifest.json")
    manifest["sha256"] = sha(fs / "usfs.json")
    write(fs / "usfs.json.manifest.json", manifest)
    fs_rows, fs_report = prepare(
        fs / "usfs.json", manifest, max_rows=500, max_bytes=MAX_BYTES
    )
    if len(fs_rows) != 251:
        raise ValueError("expected exactly 251 reviewed USFS destinations")
    venue_source, venues = sources / "venues-source", output / "venues"
    venues.mkdir()
    source_name = "overture-reviewed-v3.jsonl"
    for name in (source_name, source_name + ".manifest.json", "driving-checks.json"):
        shutil.copyfile(venue_source / name, venues / name)
    review = read(venue_source / "review.json")
    if set(review["entries"]) != set(expansion_venue_profiles.PROFILES):
        raise ValueError("venue selection differs from the six inspected profiles")
    for entry in review["entries"].values():
        for evidence in [
            *entry["pages"].values(),
            entry["driving"],
            entry["raw_driving"],
        ]:
            # Active references change only by relocation; URLs, bytes, hashes
            # and acquisition dates remain exactly those in the original review.
            name = Path(evidence["path"]).name
            destination = venues / name
            if not destination.exists():
                shutil.copyfile(venue_source / name, destination)
            if sha(destination) != evidence["sha256"]:
                raise ValueError("retained venue evidence changed during relocation")
            evidence["path"] = str(destination)
    write(venues / "review-relocated.json", review)
    combine(
        [venues / source_name],
        venues / "venues-six.jsonl",
        selected_ids=set(review["entries"]),
        arrival_review=review,
    )
    inputs = [Path(item["path"]) for item in baseline_bundle["inputs"]]
    complete = output / "reviewed-500.json"
    report = mix(
        inputs + [fs / "usfs.json", venues / "venues-six.jsonl"],
        complete,
        max_rows=500,
        max_bytes=MAX_BYTES,
    )
    rows, _ = prepare(
        complete,
        read(complete.with_suffix(".json.manifest.json")),
        max_rows=500,
        max_bytes=MAX_BYTES,
    )
    indexed = {r["source_id"]: r for r in rows}
    if len(rows) != 500 or len(indexed) != 500 or report["duplicates"]:
        raise ValueError("complete generation must contain exactly 500 distinct rows")
    if any(indexed.get(r["source_id"]) != r for r in baseline_rows):
        raise ValueError("a prior reviewed row/provenance changed")
    expected_path = (
        ROOT / "docs/data/catalog-expansion-500-20261015/reviewed-500.preview.jsonl"
    )
    expected = [
        json.loads(line)
        for line in expected_path.read_text(encoding="utf-8").splitlines()
    ]
    if {r["source_id"]: r for r in rows} != {r["source_id"]: r for r in expected}:
        raise ValueError("re-admitted rows differ from the published 500-place review")
    with (output / "reviewed-500.preview.jsonl").open(
        "x", encoding="utf-8", newline="\n"
    ) as stream:
        stream.write("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    write(output / "source-report.json", report)
    proof = {
        "accepted": 500,
        "duplicates": 0,
        "preserved_rows_and_provenance": 243,
        "new_usfs": len(fs_rows),
        "new_venues": 6,
        "evidence_bytes": report["bytes"],
        "max_rows": 500,
        "max_bytes": MAX_BYTES,
        "normalized_rows_sha256": rows_sha(rows),
        "usfs_source_inventory_sha256": usfs.INDEX_SHA256,
        "usfs_evidence_bytes": fs_report["bytes"],
        "regions": report["regions"],
        "source_counts": report["source_counts"],
        "generation_fingerprint_depends_on_relocated_paths": True,
        "production_activation_performed": False,
    }
    write(output / "completion.json", proof)
    return proof


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", required=True, type=Path)
    parser.add_argument("--baseline-bundle", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.sources, args.baseline_bundle, args.output), indent=2))
