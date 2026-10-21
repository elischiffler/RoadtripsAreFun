#!/usr/bin/env python3
"""Assemble/replay a source-reviewed 600-prospect pilot without database or AI.

Inputs remain private local evidence. Source-specific acquisition modules are
separate; assemble copies only selected evidence, bounds total bytes, and pins
the reproducible 603+93 local comparison. It does not claim live net additions.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]


def write(path, value):
    Path(path).write_text(
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    )


def rebase(value, mapping):
    if isinstance(value, list):
        return [rebase(item, mapping) for item in value]
    if isinstance(value, dict):
        return {
            key: mapping[item] if key == "evidence_id" else rebase(item, mapping)
            for key, item in value.items()
        }
    return value


def assemble(inputs, states, output):
    from app.catalog import pilot

    from scripts.catalog_expansion_campaign import baseline

    output = Path(output).absolute()
    if output.exists():
        raise ValueError("choose a new immutable pilot output directory")
    staged, records, seen_ids, evidence, total = {}, [], set(), [], 0
    # Inspect all selected evidence before creating/copying a large output.
    for group_number, source in enumerate(inputs):
        source = Path(source).resolve()
        if not source.is_file() or not 0 < source.stat().st_size <= 8 * 1024 * 1024:
            raise ValueError("pilot group input exceeds8MiB ceiling")
        payload = json.loads(source.read_bytes())
        mapping = {}
        for receipt in payload["evidence"]:
            ident = f"group-{group_number}:{receipt['id']}"
            if receipt["id"] in mapping:
                raise ValueError("duplicate input receipt identity")
            mapping[receipt["id"]] = ident
            original = (source.parent / receipt["path"]).resolve()
            if not original.is_relative_to(source.parent) or not original.is_file():
                raise ValueError("source evidence escapes its owned input directory")
            size = original.stat().st_size
            if size > 2 * 1024 * 1024:
                raise ValueError("single source response exceeds pilot2MiB ceiling")
            raw = original.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            if digest != receipt["sha256"]:
                raise ValueError("source evidence changed since acquisition")
            relative = f"evidence/{digest}.bin"
            if relative not in staged:
                total += len(raw)
                if total > pilot.MAX_BYTES:
                    raise ValueError("aggregate pilot source evidence exceeds64MiB")
                staged[relative] = original
            evidence.append({**receipt, "id": ident, "path": relative})

        for record in payload["records"]:
            if record["pilot_id"] in seen_ids:
                raise ValueError("same prospect included in more than one pilot cohort")
            seen_ids.add(record["pilot_id"])
            records.append(rebase(copy.deepcopy(record), mapping))
    if len(records) != 600:
        raise ValueError(
            "pilot assembly requires exactly600 reviewed-or-held prospects"
        )
    old, known = baseline()
    prior = json.loads(
        (
            ROOT / "docs/data/catalog-expansion-20261021/additions.preview.json"
        ).read_bytes()
    )
    if len(prior) != 93:
        raise ValueError("prior93-source-admitted baseline changed")
    old.extend(prior)
    state_path = Path(states).resolve()
    if (
        not state_path.is_file()
        or not 0 < state_path.stat().st_size <= 32 * 1024 * 1024
    ):
        raise ValueError("Census response exceeds bounded source ceiling")
    state_body = state_path.read_bytes()
    baseline_body = (
        json.dumps(old, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()
    review_estimate = len(json.dumps(records, allow_nan=False).encode()) + len(
        json.dumps(evidence, allow_nan=False).encode()
    )
    retained = total + len(state_body) + len(baseline_body) + review_estimate
    if retained > pilot.MAX_BYTES:
        raise ValueError(
            "aggregate pilot evidence, Census, baseline and review exceed64MiB"
        )
    free_root = output.parent
    while not free_root.exists():
        free_root = free_root.parent
    if shutil.disk_usage(free_root).free < retained * 2 + 100 * 1024 * 1024:
        raise ValueError("insufficient free disk for bounded pilot and replay")
    output.mkdir(mode=0o700, parents=True)
    (output / "evidence").mkdir()
    for relative, original in staged.items():
        shutil.copyfile(original, output / relative)
    shutil.copyfile(state_path, output / "states.json")
    write(output / "local-baseline.json", old)
    payload = {
        "records": records,
        "evidence": evidence,
        "states": {
            "path": "states.json",
            "sha256": hashlib.sha256(state_body).hexdigest(),
        },
        "local_baseline": {
            "path": "local-baseline.json",
            "sha256": hashlib.sha256(
                (output / "local-baseline.json").read_bytes()
            ).hexdigest(),
        },
        "documented_later_exclusion_ids": sorted(known),
        "live_parent_reconciled": False,
        "review_scope": "Codex-assisted primary-source review and deterministic replay; no independent human or field verification.",
    }
    write(output / "reviewed.json", payload)
    manifest = {
        "schema_version": pilot.SCHEMA,
        "sha256": hashlib.sha256((output / "reviewed.json").read_bytes()).hexdigest(),
        "release": "catalog-pilot-600-20261021",
        "attribution": "Original source facts separately credited in place provenance; Codex-assisted review, no agency endorsement. No photos or operator descriptions redistributed.",
    }
    write(output / "reviewed.manifest.json", manifest)
    return replay(
        output / "reviewed.json", output / "reviewed.manifest.json", output / "replay"
    )


def replay(source, manifest, output):
    from app.catalog import calendar_enrichment as enrich
    from app.catalog import pilot

    output = Path(output).absolute()
    if output.exists():
        raise ValueError("choose a new immutable replay directory")
    rows, report = pilot.prepare(source, json.loads(Path(manifest).read_bytes()))
    output.mkdir(mode=0o700, parents=True)
    write(output / "additions.preview.json", rows)
    write(output / "personas.json", report.pop("profiles"))
    decisions = report.pop("decisions")
    write(output / "decisions.json", decisions)
    report.update(
        normalized_rows_sha256=enrich.rows_digest(rows),
        states=dict(sorted(Counter(row["region"] for row in rows).items())),
        categories=dict(
            sorted(Counter(c for row in rows for c in row["categories"]).items())
        ),
        source_families=dict(
            sorted(
                Counter(row["provenance"][0]["source_family"] for row in rows).items()
            )
        ),
        discovery_or_held=sum(item["tier"] == "T1" for item in decisions),
        source_reviewed_browse=len(rows),
        review_method="Codex-assisted source review; deterministic byte/field replay; no independent human approval",
        external_writes=False,
        external_ai_requests=0,
        live_parent_reconciled=False,
    )
    write(output / "report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    build = sub.add_parser("assemble")
    build.add_argument("--input", action="append", required=True, type=Path)
    build.add_argument("--states", required=True, type=Path)
    build.add_argument("--output", required=True, type=Path)
    run = sub.add_parser("replay")
    run.add_argument("--source", required=True, type=Path)
    run.add_argument("--manifest", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = (
        assemble(args.input, args.states, args.output)
        if args.action == "assemble"
        else replay(args.source, args.manifest, args.output)
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
