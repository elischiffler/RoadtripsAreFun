#!/usr/bin/env python3
"""Inspect a bounded LOCAL GeoNames TSV prefix; publish review leads, never import.

Schema: https://download.geonames.org/export/dump/readme.txt
Codes: https://www.geonames.org/export/codes.html
This does not download files, approve rights, verify Kaggle compatibility, turn
source points into arrivals, or connect to any database. No CSV/header guessing.
"""

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.catalog.normalize import US_REGIONS  # noqa: E402

MAX_CANDIDATES = 500
MAX_SCANNED = 10_000
MAX_BYTES = 20 * 1024 * 1024
MAX_LINE_BYTES = 64 * 1024
MAX_SECONDS = 30


def parse_line(raw, regions, feature_codes):
    """Read documented positions, preserving a source point with no access claim."""
    try:
        fields = raw.decode("utf-8").rstrip("\r\n").split("\t")
    except UnicodeDecodeError:
        return None, "encoding"
    if len(fields) != 19:
        return None, "column_count"
    if fields[8] != "US" or fields[10] not in regions:
        return None, "country_region"
    code = f"{fields[6]}.{fields[7]}"
    if code not in feature_codes:
        return None, "feature_code"
    if (
        not re.fullmatch(r"[1-9][0-9]{0,18}", fields[0])
        or not fields[1].strip()
        or len(fields[1]) > 200
        or any(ord(c) < 32 for c in fields[1])
    ):
        return None, "identity"
    try:
        lat, lon = float(fields[4]), float(fields[5])
        if not math.isfinite(lat) or not math.isfinite(lon):
            raise ValueError
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError
    except ValueError:
        return None, "coordinates"
    try:
        modified = date.fromisoformat(fields[18])
        if fields[18] != modified.isoformat() or modified > datetime.now(UTC).date():
            raise ValueError
    except ValueError:
        return None, "modification_date"
    return {
        "review_only": True,
        "import_eligible": False,
        "source_id": "geonames:" + fields[0],
        "native_id": fields[0],
        "name": fields[1].strip(),
        "country": "US",
        "region": fields[10],
        "feature_code": code,
        "source_point": {"latitude": lat, "longitude": lon, "arrival_verified": False},
        "source_modified_on": modified.isoformat(),
        "arrival_point": None,
        "current_operation_evidence": None,
        "rights_review": "unreviewed",
    }, None


def inspect(
    input_path,
    output,
    *,
    regions,
    feature_codes,
    max_candidates=MAX_CANDIDATES,
    max_scanned=MAX_SCANNED,
    max_bytes=MAX_BYTES,
    max_seconds=MAX_SECONDS,
):
    """Stop at hard ceilings and atomically publish a clearly ineligible queue."""
    regions, feature_codes = set(regions), set(feature_codes)
    if not regions or regions - US_REGIONS:
        raise ValueError(
            "select explicit US states/DC; territories and unknown regions are excluded"
        )
    if (
        not feature_codes
        or len(feature_codes) > 30
        or any(not re.fullmatch(r"[AHLPRSTUV]\.[A-Z][A-Z0-9]{0,9}", code) for code in feature_codes)
    ):
        raise ValueError("select 1..30 explicit class.code filters from the source documentation")
    for value, ceiling in (
        (max_candidates, MAX_CANDIDATES),
        (max_scanned, MAX_SCANNED),
        (max_bytes, MAX_BYTES),
        (max_seconds, MAX_SECONDS),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= ceiling:
            raise ValueError("inspection limits must be positive integers within hard ceilings")
    output = Path(output)
    report_path = output.with_suffix(output.suffix + ".review.json")
    if output.exists() or report_path.exists():
        raise ValueError("output already exists; use a new path")
    rows, row_digests = {}, {}
    rejects, region_counts, code_counts = Counter(), Counter(), Counter()
    prefix_digest = hashlib.sha256()
    scanned = scanned_bytes = 0
    started = time.monotonic()
    with os.fdopen(os.open(input_path, os.O_RDONLY | os.O_NONBLOCK), "rb") as stream:
        original = os.fstat(stream.fileno())
        if not stat.S_ISREG(original.st_mode):
            raise ValueError("input must be a local regular uncompressed TSV file")
        while True:
            if scanned_bytes == original.st_size:
                stop_reason = "source_exhausted"
                break
            if len(rows) >= max_candidates:
                stop_reason = "candidate_limit"
                break
            if scanned >= max_scanned:
                stop_reason = "scan_limit"
                break
            if scanned_bytes >= max_bytes:
                stop_reason = "byte_limit"
                break
            if time.monotonic() - started >= max_seconds:
                stop_reason = "time_limit"
                break
            raw = stream.readline(min(MAX_LINE_BYTES + 1, max_bytes - scanned_bytes))
            if not raw:
                raise ValueError("input changed during inspection")
            scanned_bytes += len(raw)
            prefix_digest.update(raw)
            if len(raw) > MAX_LINE_BYTES:
                raise ValueError("source line exceeds 64 KiB")
            if not raw.endswith(b"\n") and scanned_bytes != original.st_size:
                # Never parse a partial row at the byte ceiling.
                stop_reason = "byte_limit"
                break
            scanned += 1
            row, reason = parse_line(raw, regions, feature_codes)
            if reason:
                rejects[reason] += 1
                continue
            ident = row["source_id"]
            row_digest = hashlib.sha256(raw.rstrip(b"\r\n")).hexdigest()
            if ident in rows:
                if row_digests[ident] != row_digest:
                    raise ValueError("conflicting duplicate GeoNames ID; manual review required")
                rejects["duplicate"] += 1
                continue
            rows[ident], row_digests[ident] = row, row_digest
            region_counts[row["region"]] += 1
            code_counts[row["feature_code"]] += 1
        current = os.fstat(stream.fileno())
        if (original.st_size, original.st_mtime_ns, original.st_ctime_ns) != (
            current.st_size,
            current.st_mtime_ns,
            current.st_ctime_ns,
        ):
            raise ValueError("input changed during inspection")
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows.values()).encode()
    report = {
        "review_only": True,
        "import_eligible": False,
        "kaggle_compatibility": "unverified",
        "schema_reference": "https://download.geonames.org/export/dump/readme.txt",
        "feature_codes_reference": "https://www.geonames.org/export/codes.html",
        "inspected_at": datetime.now(UTC).isoformat(),
        "filters": {"country": "US", "regions": sorted(regions), "codes": sorted(feature_codes)},
        "limits": {
            "candidates": max_candidates,
            "scanned_rows": max_scanned,
            "bytes": max_bytes,
            "seconds": max_seconds,
        },
        "scanned_rows": scanned,
        "input_bytes": original.st_size,
        "scanned_bytes": scanned_bytes,
        "scanned_prefix_sha256": prefix_digest.hexdigest(),
        "complete_input_scan": stop_reason == "source_exhausted",
        "stop_reason": stop_reason,
        "review_candidates": len(rows),
        "accepted_for_import": 0,
        "rejects": dict(rejects),
        "regions": dict(region_counts),
        "feature_codes": dict(code_counts),
        "output_sha256": hashlib.sha256(payload).hexdigest(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="geonames-review-", dir=output.parent) as temp:
        data = Path(temp) / "leads.jsonl"
        metadata = Path(temp) / "review.json"
        data.write_bytes(payload)
        metadata.write_text(json.dumps(report, indent=2) + "\n")
        published = False
        try:
            os.link(data, output)
            published = True
            os.link(metadata, report_path)
        except BaseException:
            if published:
                output.unlink()
            raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--region", required=True, action="append", dest="regions")
    parser.add_argument("--feature-code", required=True, action="append", dest="feature_codes")
    parser.add_argument("--max-candidates", type=int, default=MAX_CANDIDATES)
    parser.add_argument("--max-scanned", type=int, default=MAX_SCANNED)
    parser.add_argument("--max-bytes", type=int, default=MAX_BYTES)
    parser.add_argument("--max-seconds", type=int, default=MAX_SECONDS)
    args = parser.parse_args()
    result = inspect(
        args.input,
        args.output,
        **{key: value for key, value in vars(args).items() if key not in {"input", "output"}},
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
