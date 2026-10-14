#!/usr/bin/env python3
"""Bounded official Overture Places extraction; no database or credential access.

Run with the backend on sys.path (this entrypoint adds it). STAC failures are
fatal: never silently fall back to scanning the global release. Raw Parquet
row-group transfer can exceed emitted JSONL size; both inspected rows and decoded
bytes are capped independently from accepted output. Caps are not a coverage claim.
"""

import argparse
import hashlib
import io
import json
import math
import os
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.catalog.ingest import provenance_licenses  # noqa: E402
from app.catalog.normalize import normalize  # noqa: E402

RELEASE = "2026-09-23.1"
MAX_RECORDS = 50_000
MAX_SCANNED = 200_000
MAX_BYTES = 100 * 1024 * 1024
LICENSES = ROOT / "frontend" / "public" / "licenses"


def parse_bbox(value):
    bounds = tuple(float(x) for x in value.split(","))
    if len(bounds) != 4 or not all(math.isfinite(x) for x in bounds):
        raise argparse.ArgumentTypeError("bbox must contain four finite lon,lat bounds")
    west, south, east, north = bounds
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise argparse.ArgumentTypeError("invalid bbox; split antimeridian regions")
    if (east - west) * (north - south) > 4:
        raise argparse.ArgumentTypeError("pilot bbox must be <=4 square degrees")
    return bounds


def retained_license(spdx):
    path = LICENSES / f"{spdx}.txt"
    record = {
        "path": str(path.relative_to(ROOT)),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    if spdx == "Apache-2.0":
        notice = LICENSES / "Foursquare-NOTICE.txt"
        record["notice"] = {
            "path": str(notice.relative_to(ROOT)),
            "sha256": hashlib.sha256(notice.read_bytes()).hexdigest(),
        }
    return record


def source_features(bbox, release):
    """Yield small batches from STAC-selected official S3 objects only."""
    import pyarrow.compute as pc
    import pyarrow.dataset as ds
    import pyarrow.fs as fs
    import pyarrow.parquet as pq
    from shapely import from_wkb
    from shapely.geometry import mapping

    with urlopen(
        f"https://stac.overturemaps.org/{release}/collections.parquet", timeout=15
    ) as response:
        data = response.read(16 * 1024 * 1024 + 1)
    if len(data) > 16 * 1024 * 1024:
        raise ValueError("STAC index exceeds 16 MiB")
    index = pq.read_table(io.BytesIO(data))
    west, south, east, north = bbox
    matches = index.filter(
        (pc.field("collection") == "place")
        & (pc.field("type") == "Feature")
        & (pc.field("bbox", "xmin") < east)
        & (pc.field("bbox", "xmax") > west)
        & (pc.field("bbox", "ymin") < north)
        & (pc.field("bbox", "ymax") > south)
    )
    paths = [
        asset["aws-s3"]["href"].removeprefix("s3://") for asset in matches["assets"].to_pylist()
    ]
    if not paths:
        return
    if len(paths) > 100:
        raise ValueError("bbox selects too many Parquet objects; reduce pilot area")
    prefix = f"overturemaps-us-west-2/release/{release}/theme=places/type=place/"
    if any(not path.startswith(prefix) or ".." in path for path in paths):
        raise ValueError("STAC returned a path outside the pinned official places release")
    dataset = ds.dataset(
        paths,
        filesystem=fs.S3FileSystem(
            anonymous=True, region="us-west-2", connect_timeout=10, request_timeout=20
        ),
        format="parquet",
    )
    needed = {
        "id",
        "geometry",
        "names",
        "addresses",
        "sources",
        "basic_category",
        "taxonomy",
        "operating_status",
        "websites",
    }
    if not {"id", "geometry", "names", "addresses", "sources", "taxonomy"} <= set(
        dataset.schema.names
    ):
        raise ValueError("unexpected Places schema; inspect the pinned release")
    condition = (
        (pc.field("bbox", "xmin") >= west)
        & (pc.field("bbox", "xmax") <= east)
        & (pc.field("bbox", "ymin") >= south)
        & (pc.field("bbox", "ymax") <= north)
    )
    scanner = dataset.scanner(
        columns=sorted(needed & set(dataset.schema.names)),
        filter=condition,
        batch_size=128,
        batch_readahead=1,
        fragment_readahead=1,
        use_threads=False,
    )
    for batch in scanner.to_batches():
        if batch.nbytes > 8 * 1024 * 1024:
            raise ValueError("decoded Arrow batch exceeds 8 MiB")
        for row in batch.to_pylist():
            geometry = mapping(from_wkb(row.pop("geometry")))
            yield {"type": "Feature", "geometry": geometry, "properties": row}


def extract(
    features,
    output,
    *,
    bbox,
    region,
    release=RELEASE,
    max_records=500,
    max_scanned=10_000,
    max_bytes=20 * 1024 * 1024,
    max_seconds=120,
):
    """Filter before writing; always publish manifest with the exact truncation cause."""
    if not 1 <= max_records <= MAX_RECORDS or not 1 <= max_scanned <= MAX_SCANNED:
        raise ValueError("row limits exceed hard ceilings")
    if not 1 <= max_bytes <= MAX_BYTES or not 1 <= max_seconds <= 600:
        raise ValueError("byte/time limits exceed hard ceilings")
    output = Path(output)
    manifest_path = output.with_suffix(output.suffix + ".manifest.json")
    if output.exists() or manifest_path.exists():
        raise ValueError("output already exists; use a new path")
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_path = tempfile.mkstemp(
        prefix="catalog-extract-", suffix=".partial", dir=output.parent
    )
    os.close(descriptor)
    partial = Path(temporary_path)
    seen = set()
    rejects, regions, categories, upstreams = Counter(), Counter(), Counter(), Counter()
    inspected = decoded_bytes = emitted_bytes = 0
    licenses = set()
    reason = "source_exhausted"
    started = time.monotonic()
    digest = hashlib.sha256()
    try:
        with partial.open("wb") as stream:
            iterator = iter(features)
            while True:
                if time.monotonic() - started >= max_seconds:
                    reason = "time_limit"
                    break
                if inspected >= max_scanned:
                    reason = "scan_row_limit"
                    break
                if len(seen) >= max_records:
                    reason = "accepted_row_limit"
                    break
                try:
                    feature = next(iterator)
                except StopIteration:
                    break
                encoded = (
                    json.dumps(feature, ensure_ascii=False, separators=(",", ":")) + "\n"
                ).encode()
                inspected += 1
                decoded_bytes += len(encoded)
                if decoded_bytes > max_bytes:
                    reason = "decoded_byte_limit"
                    break
                row, rejection = normalize(feature)
                if rejection:
                    rejects[rejection] += 1
                    continue
                source_licenses = provenance_licenses(row)
                if not source_licenses:
                    rejects["unapproved_provenance"] += 1
                    continue
                if row["source_id"] in seen:
                    rejects["duplicate"] += 1
                    continue
                if emitted_bytes + len(encoded) > max_bytes:
                    reason = "output_byte_limit"
                    break
                stream.write(encoded)
                digest.update(encoded)
                emitted_bytes += len(encoded)
                seen.add(row["source_id"])
                regions[row["region"]] += 1
                categories.update(row["categories"])
                upstreams.update({s["dataset"] for s in row["provenance"]})
                licenses.update(source_licenses)
        manifest = {
            "release": release,
            "schema_version": "roadtrips-overture-places-v1",
            "retrieved_at": datetime.now(UTC).isoformat(),
            "source_url": f"s3://overturemaps-us-west-2/release/{release}/theme=places/type=place/",
            "sha256": digest.hexdigest(),
            "filters": {
                "bbox": bbox,
                "region_label": region,
                "country": "US",
                "states": "50 states and DC; territory/missing-region records excluded",
                "categories": "conservative daytime/food/culture/nightlife mapping v1",
                "max_records": max_records,
                "max_scanned": max_scanned,
                "max_decoded_bytes": max_bytes,
                "max_seconds": max_seconds,
            },
            "attribution": "Overture Maps Foundation; " + "; ".join(sorted(upstreams)),
            "licenses": {license: retained_license(license) for license in sorted(licenses)},
            "extraction": {
                "inspected": inspected,
                "accepted": len(seen),
                "output_bytes": emitted_bytes,
                "decoded_bytes": decoded_bytes,
                "stop_reason": reason,
                "complete_bbox_scan": reason == "source_exhausted",
                "rejects": dict(rejects),
                "regions": dict(regions),
                "categories": dict(categories),
                "upstream_counts": dict(upstreams),
                "network_bytes": "not measured; Parquet range transfer includes overhead",
            },
        }
        if not seen:
            raise ValueError("no eligible records; do not stage an empty catalog")
        # Link publication refuses concurrent destinations instead of overwriting.
        manifest_partial = partial.with_suffix(".manifest.partial")
        published = False
        manifest_created = False
        try:
            with manifest_partial.open("x") as handle:
                manifest_created = True
                handle.write(json.dumps(manifest, indent=2) + "\n")
            os.link(partial, output)
            published = True
            os.link(manifest_partial, manifest_path)
        except BaseException:
            if published:
                output.unlink()
            raise
        finally:
            if manifest_created:
                manifest_partial.unlink(missing_ok=True)
        partial.unlink()
        return manifest
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", type=parse_bbox, required=True)
    parser.add_argument("--region-label", required=True)
    parser.add_argument("--release", choices=[RELEASE], default=RELEASE)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-records", type=int, default=500)
    parser.add_argument("--max-scanned", type=int, default=10_000)
    parser.add_argument("--max-bytes", type=int, default=20 * 1024 * 1024)
    parser.add_argument("--max-seconds", type=int, default=120)
    args = parser.parse_args()
    try:
        manifest = extract(
            source_features(args.bbox, args.release),
            args.output,
            bbox=args.bbox,
            region=args.region_label,
            release=args.release,
            max_records=args.max_records,
            max_scanned=args.max_scanned,
            max_bytes=args.max_bytes,
            max_seconds=args.max_seconds,
        )
    except Exception as exc:
        print(
            f"Extraction failed ({type(exc).__name__}); no database was contacted",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(manifest["extraction"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
