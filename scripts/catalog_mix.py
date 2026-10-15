#!/usr/bin/env python3
"""Build one complete reviewed mixed-source generation, with no database calls.

Every input uses its existing .manifest.json. Child adapters revalidate the
original artifacts/evidence. Optional deduplication JSON contains explicit keep,
merge and evidence_url records; unresolved colocated identities fail closed.
Existing bundle/manifest paths are never overwritten.
"""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.catalog import mixed  # noqa: E402
from app.catalog.ingest import MAX_BYTES, MAX_ROWS, prepare  # noqa: E402


def build(inputs, output, *, deduplications=None, max_rows=500, max_bytes=20 * 1024 * 1024):
    if not 1 <= max_rows <= MAX_ROWS or not 1 <= max_bytes <= MAX_BYTES:
        raise ValueError("mixed limits exceed hard ceilings")
    output = Path(output)
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    if output.exists() or manifest_path.exists():
        raise ValueError("mixed output already exists")
    descriptions = []
    for path in inputs:
        path = Path(path).resolve()
        m = path.with_suffix(path.suffix + ".manifest.json")
        _, sha = mixed.read_json(m)
        descriptions.append({"path": str(path), "manifest": str(m), "manifest_sha256": sha})
    bundle = {"inputs": descriptions, "deduplications": deduplications or []}
    _, sources, licenses, report = mixed.assemble(bundle, max_rows=max_rows, max_bytes=max_bytes)
    raw = (json.dumps(bundle, indent=2) + "\n").encode()
    if len(raw) > 32_768:
        raise ValueError("mixed bundle exceeds 32 KiB")
    manifest = {
        "schema_version": mixed.SCHEMA,
        "release": "pilot-" + datetime.now(UTC).date().isoformat() + ".1",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "source_url": mixed.SOURCE_URL,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "filters": {
            "complete_generation": True,
            "regions": report["regions"],
            "source_counts": report["source_counts"],
        },
        "attribution": "; ".join(s["attribution"] for s in sources.values()),
        "licenses": licenses,
        "source_catalogs": sources,
    }
    encoded = (json.dumps(manifest, indent=2) + "\n").encode()
    if len(encoded) > 32_768:
        raise ValueError("mixed manifest exceeds 32 KiB")
    published = False
    try:
        with output.open("xb") as stream:
            stream.write(raw)
        published = True
        prepare(output, manifest, max_rows=max_rows, max_bytes=max_bytes)
        with manifest_path.open("xb") as stream:
            stream.write(encoded)
    except BaseException:
        if published:
            output.unlink()
        raise
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--deduplications", type=Path)
    parser.add_argument("--max-rows", type=int, default=500)
    parser.add_argument("--max-bytes", type=int, default=20 * 1024 * 1024)
    args = parser.parse_args()
    mappings = []
    if args.deduplications:
        mappings, _ = mixed.read_json(args.deduplications)
    print(
        json.dumps(
            build(
                args.inputs,
                args.output,
                deduplications=mappings,
                max_rows=args.max_rows,
                max_bytes=args.max_bytes,
            ),
            sort_keys=True,
        )
    )
