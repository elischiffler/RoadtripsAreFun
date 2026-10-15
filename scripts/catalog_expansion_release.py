#!/usr/bin/env python3
"""Prepare a complete replacement from the immutable 500 and admitted children.

This does not connect to a database. Existing rows and their provenance must
survive byte-for-byte; source adapters, aggregate ceilings and deduplication
checks remain authoritative. A failed output has no completion marker.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
from app.catalog.ingest import MAX_BYTES, MAX_ROWS, prepare  # noqa: E402

from scripts.catalog_mix import build as mix  # noqa: E402

BASELINE_SHA256 = "804b0854158423d44917e7ed27e2ea9b00ce21ec4048f8520ec7cc158678a896"


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True, allow_nan=False)
        stream.write("\n")


def row_bytes(rows):
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows).encode()


def admitted(path, max_rows, max_bytes):
    return prepare(
        path,
        read(path.with_suffix(path.suffix + ".manifest.json")),
        max_rows=max_rows,
        max_bytes=max_bytes,
    )


def build(baseline, additions, output, *, max_rows, max_bytes):
    if not 500 < max_rows <= MAX_ROWS or not 1 <= max_bytes <= MAX_BYTES:
        raise ValueError("explicit expansion limits must fit unchanged importer ceilings")
    baseline, output = Path(baseline).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError("output already exists; choose a new directory")
    prior, _ = admitted(baseline, 500, max_bytes)
    if len(prior) != 500 or hashlib.sha256(row_bytes(prior)).hexdigest() != BASELINE_SHA256:
        raise ValueError("baseline differs from the immutable reviewed 500")
    recipe = read(baseline)
    if recipe.get("deduplications"):
        raise ValueError("baseline mappings require an explicitly reviewed flattening")
    output.mkdir(parents=True)
    artifact = output / "catalog.json"
    report = mix(
        [*[Path(item["path"]) for item in recipe["inputs"]], *additions],
        artifact,
        max_rows=max_rows,
        max_bytes=max_bytes,
    )
    rows, _ = admitted(artifact, max_rows, max_bytes)
    lookup = {row["source_id"]: row for row in rows}
    if any(lookup.get(row["source_id"]) != row for row in prior):
        raise ValueError("replacement changes or omits a preserved row/provenance")
    if len(rows) <= 500:
        raise ValueError("expansion did not add any unique places")
    with (output / "catalog.preview.jsonl").open("xb") as stream:
        stream.write(row_bytes(rows))
    proof = {
        **report,
        "preserved_rows_and_provenance": 500,
        "additions": len(rows) - 500,
        "normalized_rows_sha256": hashlib.sha256(row_bytes(rows)).hexdigest(),
        "baseline_normalized_rows_sha256": BASELINE_SHA256,
        "max_rows": max_rows,
        "max_bytes": max_bytes,
        "database_or_network_calls": False,
    }
    write(output / "completion.json", proof)
    return proof


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, type=Path)
    parser.add_argument("--additions", required=True, nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-rows", required=True, type=int)
    parser.add_argument("--max-bytes", required=True, type=int)
    arguments = parser.parse_args()
    print(json.dumps(build(**vars(arguments)), indent=2))
