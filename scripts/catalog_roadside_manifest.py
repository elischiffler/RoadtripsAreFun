#!/usr/bin/env python3
"""Validate a retained roadside evidence bundle and write its manifest sidecar.

No downloads or database calls. Only explicitly reviewed adapter profiles are
accepted. The bundle contains original CSV, rights, point and current visitor/
parking/driving evidence references, with paths, hashes and acquisition dates.
Existing sidecars are never overwritten.
"""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.catalog import roadside  # noqa: E402
from app.catalog.ingest import prepare  # noqa: E402


def build(bundle, *, max_rows=500, max_bytes=20 * 1024 * 1024):
    bundle = Path(bundle)
    output = bundle.with_suffix(bundle.suffix + ".manifest.json")
    if output.exists():
        raise ValueError("manifest output already exists")
    if not 0 < bundle.stat().st_size <= 32_768:
        raise ValueError("roadside bundle exceeds 32 KiB")
    licenses = {}
    for identifier in ("CC0-1.0", "CDLA-Permissive-2.0", "LicenseRef-LOC-Margolies-Notice"):
        p = ROOT / "frontend/public/licenses" / (identifier + ".txt")
        licenses[identifier] = {
            "path": str(p),
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
    manifest = {
        "schema_version": roadside.SCHEMA,
        "release": "kaggle-loc-v4+review-" + datetime.now(UTC).date().isoformat(),
        "retrieved_at": datetime.now(UTC).isoformat(),
        "source_url": roadside.SOURCE_URL,
        "sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
        "filters": {"country": "US", "explicit_arrival_profiles": True, "no_photographs": True},
        "attribution": roadside.ATTRIBUTION,
        "licenses": licenses,
    }
    _, report = prepare(bundle, manifest, max_rows=max_rows, max_bytes=max_bytes)
    with output.open("x") as stream:
        stream.write(json.dumps(manifest, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(build(args.bundle), sort_keys=True))
    except Exception as exc:
        raise SystemExit(
            f"roadside manifest failed ({type(exc).__name__}); no secrets logged"
        ) from None
