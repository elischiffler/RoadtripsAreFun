#!/usr/bin/env python3
"""Merge bounded review updates into a NEW pilot artifact, without network/DB.

Native source facts and rights bindings are immutable. Only the prepared bounded
queue may receive operator-review updates. Arrival/calendar research is separate
and never promotes a place merely because a review was attempted.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from scripts.catalog_pilot import rebase, replay, write

REVIEW_FIELDS = {
    "review",
    "operator_url",
    "access_proofs",
    "operator_identity_location_proofs",
    "hold_reason",
    "constraints",
    "source_constraints",
    "public_access_status",
    "public_access_mode",
}
MAX_BYTES = 64 * 1024 * 1024


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def merge(base, updates, queue, output):
    base, output = Path(base).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("choose a new immutable follow-up directory")
    manifest = json.loads((base / "reviewed.manifest.json").read_bytes())
    if digest(base / "reviewed.json") != manifest["sha256"]:
        raise ValueError("frozen pilot manifest differs")
    payload = json.loads((base / "reviewed.json").read_bytes())
    records = {r["pilot_id"]: r for r in payload["records"]}
    queue_doc = json.loads(Path(queue).read_bytes())
    queue_ids = queue_doc["unreviewed_operator_review"]
    if (
        not isinstance(queue_ids, list)
        or not 1 <= len(queue_ids) <= 100
        or any(
            not isinstance(x, str) or not x.startswith(("culture:wd:", "diversity:wd:"))
            for x in queue_ids
        )
        or len(set(queue_ids)) != len(queue_ids)
        or not set(queue_ids) <= set(records)
    ):
        raise ValueError(
            "expected a unique prepared operator queue of at most100 records"
        )
    allowed = set(queue_ids)
    pinned_native = queue_doc.get("frozen_native_sha256", {})
    if pinned_native and set(pinned_native) != allowed:
        raise ValueError("every queued native snapshot must be explicitly pinned")
    files, total, identities = {}, 0, set()

    def retain(root, receipt):
        nonlocal total
        original = (root / receipt["path"]).resolve()
        if not original.is_relative_to(root) or not original.is_file():
            raise ValueError("evidence escapes its owned directory")
        size = original.stat().st_size
        if not 0 < size <= 2 * 1024 * 1024 or digest(original) != receipt["sha256"]:
            raise ValueError("evidence is oversized, empty or changed")
        relative = "evidence/" + receipt["sha256"] + ".bin"
        if relative not in files:
            total += size
            if total > MAX_BYTES:
                raise ValueError("follow-up exceeds unchanged pilot source budget")
            files[relative] = original
        return {**receipt, "path": relative}

    payload["evidence"] = [retain(base, r) for r in payload["evidence"]]
    frozen = {r["id"]: (r, files[r["path"]].read_bytes()) for r in payload["evidence"]}
    old_ids = {r["id"] for r in payload["evidence"]}
    for number, path in enumerate(updates):
        path = Path(path).resolve()
        if not path.is_file() or path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("review update exceeds4MiB ceiling")
        value = json.loads(path.read_bytes())
        mapping = {ident: ident for ident in old_ids}
        additional_evidence = {}
        for receipt in value["evidence"]:
            ident = receipt["id"]
            if ident in mapping or ident in old_ids or receipt.get("status") != 200:
                raise ValueError("new review evidence identity collides or failed")
            mapping[ident] = f"followup-{digest(path)[:12]}-{number}:{ident}"
            payload["evidence"].append(
                retain(path.parent, receipt) | {"id": mapping[ident]}
            )
            additional_evidence[ident] = (
                receipt,
                (path.parent / receipt["path"]).read_bytes(),
            )
        for update in value["records"]:
            ident = update["pilot_id"]
            if ident not in allowed or ident in identities:
                raise ValueError("review update is outsidequeue or repeated")
            identities.add(ident)
            previous = records[ident]
            if "bindings" in previous:
                if {k: v for k, v in previous.items() if k not in REVIEW_FIELDS} != {
                    k: v for k, v in update.items() if k not in REVIEW_FIELDS
                }:
                    raise ValueError("review update changed frozen native facts/rights")
            else:
                # The first pilot intentionally retained minimal T1 queue rows.
                # Reconstruct their bindings only from immutable original source
                # evidence, tied to the exact queued entity, never operator HTML.
                if any(
                    previous.get(k) != update.get(k) for k in ("pilot_id", "cohort")
                ):
                    raise ValueError("review update changed queue identity/cohort")
            if "bindings" in update or update.get("review", {}).get("decision") == "T2":
                from app.catalog import pilot

                anchor = pilot._same_native_entity(update["bindings"], "wikidata")
                evidence = frozen | additional_evidence
                if (
                    update.get("source_family") != "wikidata"
                    or anchor[0] not in evidence
                ):
                    raise ValueError(
                        "new native binding lacks frozen discovery evidence"
                    )
                native_sha = evidence[anchor[0]][0]["sha256"]
                if (anchor[0] not in frozen and not pinned_native) or (
                    pinned_native and native_sha != pinned_native[ident]
                ):
                    raise ValueError(
                        "native source snapshot differs from its queued hash"
                    )
                native = pilot._value(
                    update["bindings"]["native_id"], evidence, family="wikidata"
                )
                if ident.rsplit(":", 1)[-1] != native:
                    raise ValueError(
                        "new binding does not identify the queued Wikidata entity"
                    )
            if update.get("review", {}).get("decision") not in {None, "T1", "T2"}:
                raise ValueError(
                    "operator-only review cannot grant itinerary readiness"
                )
            records[ident] = rebase(copy.deepcopy(update), mapping)
    for key in ("states", "local_baseline"):
        receipt = payload[key]
        original = (base / receipt["path"]).resolve()
        if not original.is_relative_to(base) or digest(original) != receipt["sha256"]:
            raise ValueError("baseline/state evidence changed")
        relative = "states.json" if key == "states" else "local-baseline.json"
        files[relative] = original
        total += original.stat().st_size
        payload[key] = {**receipt, "path": relative}
    payload["records"] = [records[r["pilot_id"]] for r in payload["records"]]
    body = (
        json.dumps(payload, sort_keys=True, indent=2, allow_nan=False).encode() + b"\n"
    )
    if len(body) > 8 * 1024 * 1024 or total + len(body) > MAX_BYTES:
        raise ValueError("follow-up exceeds unchanged pilot source budget")
    if shutil.disk_usage(output.parent).free < 3 * MAX_BYTES:
        raise ValueError("insufficient disk for immutable follow-up")
    output.mkdir(mode=0o700)
    (output / "evidence").mkdir()
    for relative, original in files.items():
        shutil.copyfile(original, output / relative)
    (output / "reviewed.json").write_bytes(body)
    write(
        output / "reviewed.manifest.json",
        manifest
        | {
            "sha256": hashlib.sha256(body).hexdigest(),
            "release": queue_doc.get("release", "catalog-pilot-followup-20261021"),
        },
    )
    result = replay(
        output / "reviewed.json", output / "reviewed.manifest.json", output / "replay"
    )
    write(
        output / "merge-receipt.json",
        {
            "base_sha256": manifest["sha256"],
            "reviewed_queue_count": len(identities),
            "reviewed_ids": sorted(identities),
            "native_facts_preserved": True,
            "external_calls": 0,
            "production_writes": False,
        },
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--update", type=Path, action="append", required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(merge(args.base, args.update, args.queue, args.output), indent=2))


if __name__ == "__main__":
    main()
