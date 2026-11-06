#!/usr/bin/env python3
"""Separate discovery rights scopes without admitting places or renewing reviews.

Noncommercial, noncommercial/no-derivatives and unclear-rights evidence stays
quarantined. Absence of revenue is not an automatic license eligibility review.
This command has no network, database, model or production write capability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

NC = re.compile(r"CC-BY-NC(?:-SA|-ND)?-(?:1\.0|2\.0|2\.5|3\.0|4\.0)")
PERMISSIVE = {"CC0-1.0", "CC-BY-4.0", "CC-BY-3.0", "CC-BY-2.0"}


def read(path):
    if not path.is_file() or not 0 < path.stat().st_size <= 3 * 1024 * 1024:
        raise ValueError("rights partition input exceeds3MiB ceiling")
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def build(ledger, candidates):
    sources, source_sha = read(ledger)
    prospects, prospects_sha = read(candidates)
    sources = sources["sources"]
    records = prospects["records"]
    if not 1 <= len(sources) <= 20 or not len(records) <= 100:
        raise ValueError("rights research exceeds bounded source/candidate count")
    by_id = {s["source_id"]: s for s in sources}
    if len(by_id) != len(sources) or len({r["candidate_id"] for r in records}) != len(
        records
    ):
        raise ValueError("source or candidate identities are duplicated")
    partitions = {
        "noncommercial_only": [],
        "permissive_discovery": [],
        "unclear_rights": [],
    }
    for candidate in records:
        source = by_id[candidate["source_id"]]
        license_id = source.get("license_identifier", "Unknown")
        partition = (
            "noncommercial_only"
            if isinstance(license_id, str)
            and (
                NC.fullmatch(license_id)
                or source.get("partition") == "noncommercial_only"
                and license_id not in PERMISSIVE
            )
            else "permissive_discovery"
            if license_id in PERMISSIVE
            else "unclear_rights"
        )
        no_derivatives = "-ND" in license_id if isinstance(license_id, str) else None
        partitions[partition].append(
            {
                **candidate,
                "source_id": "catalog-pilot:quarantine:" + candidate["candidate_id"],
                "native_source_id": candidate["source_id"],
                "reuse_partition": partition,
                "future_monetization_excluded": partition != "permissive_discovery",
                "license_identifier": license_id,
                "license_version": source.get("license_version"),
                "license_url": source.get("license_url"),
                "attribution": source.get("attribution"),
                "rights_scope": source.get("rights_scope"),
                "redistribution": source.get("redistribution", "unknown"),
                "adaptation": "Adapted redistribution is not cleared under ND terms; factual extraction needs separate scope review"
                if no_derivatives
                else source.get("adaptation", "unknown"),
                "retention": source.get("retention", "unknown"),
                "access_terms": source.get("access_terms", "unknown"),
                "commercial_definition": source.get("commercial_definition", "unknown"),
                "tier": "T1",
                "review_status": "quarantined",
                "routing_eligible": False,
                "browse_eligible": False,
                "profile": None,
                "precise_question": source.get("precise_question")
                or (
                    "Does this application's actual intended use qualify under the exact noncommercial grant, including redistribution and transformed profiles?"
                    if partition == "noncommercial_only"
                    else "Are exact field rights, public visitor identity/location/access and duplicate checks complete for a typed source adapter?"
                ),
            }
        )
    return {
        "schema_version": "roadtrips-rights-discovery-partitions/1",
        "source_ledger_sha256": source_sha,
        "candidates_sha256": prospects_sha,
        "main_catalog_admissions": 0,
        "itinerary_ready": 0,
        "scope": "Discovery/quarantine only; license labels do not prove rights or noncommercial eligibility",
        "partitions": partitions,
        "counts": {key: len(value) for key, value in partitions.items()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.ledger, args.candidates)
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
        stream.write("\n")


if __name__ == "__main__":
    main()
