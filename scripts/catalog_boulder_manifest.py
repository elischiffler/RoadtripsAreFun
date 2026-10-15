#!/usr/bin/env python3
"""Prepare a Boulder v1 manifest from LOCAL archive and retained operator pages.

No downloads or database calls. The page index is a JSON list of objects with
name, url, path, sha256, retrieved_at and status (HTTP). Supply pages obtained
from the city, not hand-authored open/access assertions. The importer parses
their structured status, identity, parking description and directions point.
Output refuses existing files and is not activation permission.
"""

import argparse
import csv
import hashlib
import io
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.catalog import boulder  # noqa: E402
from app.catalog.ingest import prepare  # noqa: E402


def build(archive, index, output, retrieved_at):
    archive, index, output = Path(archive), Path(index), Path(output)
    retrieved = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    if retrieved.tzinfo is None or retrieved > datetime.now(UTC):
        raise ValueError("provide the actual dated archive retrieval time")
    if output.exists():
        raise ValueError("output already exists")
    if not archive.is_file() or archive.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("archive exceeds 20 MiB")
    if hashlib.sha256(archive.read_bytes()).hexdigest() != boulder.ARCHIVE_SHA256:
        raise ValueError("archive differs from inspected Kaggle v1")
    if not index.is_file() or index.stat().st_size > 64 * 1024:
        raise ValueError("page index missing or oversized")
    pages = json.loads(index.read_text())
    if not isinstance(pages, list) or len(pages) > 80:
        raise ValueError("page index requires at most 80 objects")
    by_name = {}
    for page in pages:
        if page.get("status") != 200:
            continue
        name = page["name"].strip().casefold()
        if name in by_name:
            raise ValueError("ambiguous duplicate operator page name")
        by_name[name] = page
    with zipfile.ZipFile(archive) as z:
        if z.getinfo(boulder.MEMBER).file_size > 128 * 1024:
            raise ValueError("CSV member oversized")
        rows = csv.DictReader(io.StringIO(z.read(boulder.MEMBER).decode("utf-8-sig")))
        evidence = {}
        for row in rows:
            name = row[boulder.PREFIX + "THNAME"].strip().casefold()
            if name in by_name:
                evidence[row[boulder.PREFIX + "ACCESSID"]] = {
                    k: by_name[name][k] for k in ("url", "path", "sha256", "retrieved_at")
                }
    license_path = ROOT / "frontend/public/licenses/CC0-1.0.txt"
    manifest = {
        "release": boulder.RELEASE,
        "schema_version": boulder.SCHEMA,
        "retrieved_at": retrieved.isoformat(),
        "source_url": boulder.SOURCE_URL,
        "sha256": boulder.ARCHIVE_SHA256,
        "filters": {
            "country": "US",
            "region": "CO",
            "member": boulder.MEMBER,
            "require_current_operator_page": True,
        },
        "attribution": boulder.ATTRIBUTION,
        "licenses": {
            "CC0-1.0": {
                "path": str(license_path),
                "sha256": hashlib.sha256(license_path.read_bytes()).hexdigest(),
            }
        },
        "operator_evidence": evidence,
    }
    _, report = prepare(archive, manifest, max_rows=500, max_bytes=20 * 1024 * 1024)
    # The existing importer enforces its 32 KiB serialized manifest ceiling.
    encoded = json.dumps(manifest, indent=2) + "\n"
    if len(encoded.encode()) > 32_768:
        raise ValueError("manifest exceeds 32 KiB")
    with output.open("x") as stream:
        stream.write(encoded)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--page-index", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--retrieved-at",
        required=True,
        help="actual archive acquisition timestamp, including UTC offset",
    )
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                build(args.archive, args.page_index, args.output, args.retrieved_at), sort_keys=True
            )
        )
    except Exception as exc:
        raise SystemExit(
            f"Boulder manifest failed ({type(exc).__name__}); no secrets logged"
        ) from None
