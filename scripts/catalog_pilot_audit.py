#!/usr/bin/env python3
"""Export factual pilot audit artifacts; original operator bodies stay private.

This command is offline. It neither refreshes evidence nor grants new approvals.
The source directory must be an immutable catalog_pilot.py assembled output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def export(source, proof, output):
    if output.exists():
        raise ValueError("choose a new immutable audit directory")
    reviewed = read(source / "reviewed.json")
    additions = read(source / "replay/additions.preview.json")
    report = read(source / "replay/report.json")
    baseline = read(source / "local-baseline.json")
    decisions = read(source / "replay/decisions.json")
    proof_report = read(proof / "proof.json")
    recovery = read(proof / "recovery-receipt.json")
    manifest_sha = hashlib.sha256((source / "reviewed.json").read_bytes()).hexdigest()
    additions_sha = hashlib.sha256(
        "".join(
            json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in additions
        ).encode()
    ).hexdigest()
    proved_rows = read(proof / "portable-import/catalog.preview.json")
    proved_rows_sha = hashlib.sha256(
        "".join(
            json.dumps(row, sort_keys=True, allow_nan=False) + "\n"
            for row in proved_rows
        ).encode()
    ).hexdigest()
    proof_sha = proof_report.get("source_manifest_sha256")
    if proof_sha is None:
        # Original129-place proof predates explicit source fingerprints. Its
        # retained typed build config still pins the exact reviewed payload.
        config = read(proof / "config.json")
        inputs = config.get("addition_inputs", [])
        if len(inputs) != 1 or inputs[0].get("adapter") != "reviewed-browse-pilot":
            raise ValueError("legacy proof lacks its exact typed source configuration")
        proof_sha = inputs[0]["manifest"]["sha256"]
    if (
        proof_sha != manifest_sha
        or read(source / "reviewed.manifest.json")["sha256"] != manifest_sha
        or report["normalized_rows_sha256"] != additions_sha
        or proof_report.get("source_additions_sha256", additions_sha) != additions_sha
        or proof_report["source_admitted_browse"] != len(additions)
        or proof_report["actual_repository_queries"] != len(additions)
        or proof_report["assembled"]["additions"] != len(additions)
        or proof_report["generation"] != recovery["candidate"]["generation"]
        or recovery["candidate"]["row_count"] != len(additions) + 1
        or proved_rows_sha != proof_report["assembled"]["normalized_rows_sha256"]
        or proved_rows[1:] != additions
        or len(proved_rows) != len(additions) + 1
    ):
        raise ValueError("database proof does not match this source/additions artifact")
    if (
        len(decisions) != 600
        or not 1 <= len(additions) <= 600
        or len(additions) != report["accepted"]
        or len(baseline) != 696
    ):
        raise ValueError("unexpected frozen pilot counts; review before exporting")
    receipts = []
    for receipt in reviewed["evidence"]:
        path = (source / receipt["path"]).resolve()
        if not path.is_relative_to(source.resolve()):
            raise ValueError("evidence path escapes source")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != receipt["sha256"]:
            raise ValueError("evidence digest mismatch")
        receipts.append({**receipt, "bytes": len(raw)})
    output.mkdir(parents=True)
    for name in (
        "additions.preview.json",
        "personas.json",
        "decisions.json",
        "report.json",
    ):
        write(output / name, read(source / "replay" / name))
    write(output / "receipts.json", receipts)
    write(output / "local-proof.json", proof_report)
    write(output / "recovery-receipt.json", recovery)

    def coverage(rows):
        return {
            "records": len(rows),
            "states": dict(sorted(Counter(r["region"] for r in rows).items())),
            "categories": dict(
                sorted(Counter(c for r in rows for c in r["categories"]).items())
            ),
        }

    write(
        output / "coverage.json",
        {
            "scope": "Local diagnostic comparison; no live database reconciliation",
            "before": coverage(baseline),
            "after": coverage(baseline + additions),
            "additions": coverage(additions),
            "live_net_new": None,
        },
    )
    records = {r["pilot_id"]: r for r in reviewed["records"]}
    write(
        output / "next-batches.json",
        {
            "scope": "Work queues only; no automatic promotion or fresh acquisition",
            "arrival_calendar_review": [r["source_id"] for r in additions[:20]],
            "unreviewed_operator_review": [
                d["pilot_id"]
                for d in decisions
                if d["tier"] == "T1" and "unreviewed_current_operator" in d["reason"]
            ][:50],
            "native_contract_review": [
                d
                for d in decisions
                if d["reason"]
                in {
                    "native name does not use the reviewed source field",
                    "FWS original agency ownership/public-use fields are unresolved",
                }
            ],
            "held_counts_by_cohort": dict(
                Counter(
                    records[d["pilot_id"]].get("cohort", "unspecified")
                    for d in decisions
                    if d["tier"] == "T1"
                )
            ),
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--proof", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    export(args.source, args.proof, args.output)


if __name__ == "__main__":
    main()
