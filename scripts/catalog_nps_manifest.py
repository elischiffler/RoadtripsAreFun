#!/usr/bin/env python3
"""Build a local NPS enrichment manifest from reviewed selections and snapshots.

No downloads or database calls. Selection JSON maps Kaggle park codes to an
actual visitor_center_id and primary_category (national_parks or museums).
Snapshot-index JSON is a list of URL/path/SHA/retrieved_at records. Admission
rechecks the pinned archive, native IDs, official fields and arrival guards.
"""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.catalog import nps  # noqa: E402
from app.catalog.ingest import prepare  # noqa: E402


def build(archive, index, selections, output):
    archive, index, selections, output = map(Path, (archive, index, selections, output))
    if output.exists():
        raise ValueError("output already exists")
    if index.stat().st_size > 128 * 1024 or selections.stat().st_size > 16 * 1024:
        raise ValueError("NPS index/selection ceiling exceeded")
    selected = json.loads(selections.read_text())
    sources = {
        e["code"]: {k: e[k] for k in ("url", "path", "sha256", "retrieved_at")}
        for e in json.loads(index.read_text())
        if e.get("status") == 200 and e["code"] in selected
    }
    licenses = {}
    for identifier in ("CC0-1.0", "LicenseRef-US-Government-Work"):
        p = ROOT / "frontend/public/licenses" / (identifier + ".txt")
        licenses[identifier] = {
            "path": str(p),
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
    manifest = {
        "schema_version": nps.SCHEMA,
        "release": "kaggle-nps-v3+nps-" + datetime.now(UTC).date().isoformat(),
        "retrieved_at": datetime.now(UTC).isoformat(),
        "source_url": nps.SOURCE_URL,
        "sha256": nps.ARCHIVE_SHA256,
        "filters": {
            "country": "US",
            "one_arrival_per_park": True,
            "no_park_centroids": True,
            "species_omitted": True,
            "exclude_active_dated_closures": True,
        },
        "attribution": nps.ATTRIBUTION,
        "licenses": licenses,
        "official_inputs": sources,
        "selections": selected,
    }
    _, report = prepare(archive, manifest, max_rows=500, max_bytes=20 * 1024 * 1024)
    encoded = json.dumps(manifest, indent=2) + "\n"
    if len(encoded.encode()) > 32_768:
        raise ValueError("NPS manifest exceeds 32 KiB")
    with output.open("x") as stream:
        stream.write(encoded)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--snapshot-index", type=Path, required=True)
    parser.add_argument("--selections", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                build(args.archive, args.snapshot_index, args.selections, args.output),
                sort_keys=True,
            )
        )
    except Exception as exc:
        raise SystemExit(f"NPS manifest failed ({type(exc).__name__}); no secrets logged") from None
