#!/usr/bin/env python3
"""Bounded cloud expansion: capture public corridors or replay original adapters.

Never connects to the configured database or an AI endpoint. Replay preserves
the source outputs and emits source-ID selectors for the existing incremental
import workflow. A current complete parent snapshot remains required for release.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from app.catalog import calendar_enrichment as enrich
from app.catalog import personas, usfs_current
from app.catalog.automated_bindings import native_key

from scripts.catalog_automated_import import ADAPTERS, select_arrivals
from scripts.catalog_test_routes import SERVER
from scripts.catalog_test_routes import acquire as capture

BASELINE = (
    "docs/data/catalog-expansion-500-20261015/reviewed-500.preview.jsonl",
    "docs/data/catalog-expansion-kaggle-20261015/additions.preview.jsonl",
    "docs/data/catalog-incremental-20261015/additions.preview.json",
    "docs/data/catalog-growth-20261016/additions.preview.json",
)
# Approximate city centers are diagnostic endpoints, never attraction entrances.
# A fixed sixteen-route scope covers multiple low-coverage eastern/southern and
# intermountain regions without an open-ended nationwide crawl.
CORRIDORS = (
    ("boston-burlington", (42.3601, -71.0589), (44.4759, -73.2121)),
    ("portland-me-wilmington", (43.6591, -70.2568), (39.7391, -75.5398)),
    ("asheville-roanoke", (35.5951, -82.5515), (37.2710, -79.9414)),
    ("atlanta-asheville", (33.7490, -84.3880), (35.5951, -82.5515)),
    ("nashville-knoxville", (36.1627, -86.7816), (35.9606, -83.9207)),
    ("little-rock-memphis", (34.7465, -92.2896), (35.1495, -90.0490)),
    ("houston-new-orleans", (29.7604, -95.3698), (29.9511, -90.0715)),
    ("denver-salt-lake", (39.7392, -104.9903), (40.7608, -111.8910)),
    ("phoenix-albuquerque", (33.4484, -112.0740), (35.0844, -106.6504)),
    ("rapid-city-billings", (44.0805, -103.2310), (45.7833, -108.5007)),
    ("minneapolis-duluth", (44.9778, -93.2650), (46.7867, -92.1005)),
    ("reno-lakeview", (39.5296, -119.8138), (42.1888, -120.3458)),
    ("sacramento-eureka", (38.5816, -121.4944), (40.8021, -124.1637)),
    ("medford-bend", (42.3265, -122.8756), (44.0582, -121.3153)),
    ("salt-lake-boise", (40.7608, -111.8910), (43.6150, -116.2023)),
    ("boise-portland", (43.6150, -116.2023), (45.5152, -122.6784)),
)
SCENIC_CORRIDORS = (
    ("bennington-rutland", (42.8781, -73.1968), (43.6106, -72.9726)),
    ("slade-stanton", (37.7995, -83.7066), (37.8456, -83.8583)),
    ("lead-spearfish", (44.3522, -103.7652), (44.4908, -103.8594)),
    ("duluth-grand-marais", (46.7867, -92.1005), (47.7504, -90.3343)),
    ("cody-red-lodge", (44.5263, -109.0565), (45.1858, -109.2468)),
    ("john-day-baker-city", (44.4160, -118.9530), (44.7749, -117.8344)),
    ("missoula-hamilton", (46.8721, -113.9940), (46.2469, -114.1548)),
    ("marienville-warren", (41.4681, -79.1231), (41.8439, -79.1450)),
)


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def baseline():
    rows = []
    for relative in BASELINE:
        path = ROOT / relative
        rows.extend(
            [json.loads(line) for line in path.read_text().splitlines()]
            if path.suffix == ".jsonl"
            else json.loads(path.read_bytes())
        )
    if len(rows) != 603 or len({row["source_id"] for row in rows}) != 603:
        raise ValueError(
            "reviewed repository baseline changed; inspect before expansion"
        )
    evidence = json.loads(
        (ROOT / "docs/evidence/catalog-automated-import-20261019.json").read_bytes()
    )
    known_additions = {item["source_id"] for item in evidence["hosted_read"]["checks"]}
    if len(known_additions) != 5:
        raise ValueError("documented later additions changed; inspect before expansion")
    return rows, known_additions


def specs(scenic=False):
    result = []
    for ident, start, end in SCENIC_CORRIDORS if scenic else CORRIDORS:
        result.append(
            {
                "id": ident,
                "role": "Bounded expansion coverage; approximate city centers, not visitor arrivals",
                "endpoint_coordinates_lat_lon": [list(start), list(end)],
                "url": SERVER
                + "/route/v1/driving/"
                + ";".join(f"{lon},{lat}" for lat, lon in (start, end))
                + "?"
                + urlencode(
                    {
                        "overview": "full",
                        "geometries": "geojson",
                        "steps": "false",
                        "alternatives": "false",
                    }
                ),
            }
        )
    return result


def routes(output, *, scenic=False):
    """Use the cloud's configured HTTPS proxy without ambient .netrc credentials."""
    import requests

    with requests.Session() as session:
        session.trust_env = False
        # Explicit proxy support is required in this cloud environment. No direct
        # fallback, credentials, custom TLS policy or endpoint substitution.
        proxies = requests.utils.get_environ_proxies(SERVER)
        verify = (
            os.environ.get("REQUESTS_CA_BUNDLE")
            or os.environ.get("CURL_CA_BUNDLE")
            or True
        )
        return capture(
            output,
            route_specs=specs(scenic),
            request_get=lambda url, **kw: session.get(
                url, proxies=proxies, verify=verify, **kw
            ),
        )


def native(row):
    key = native_key(row)
    if key:
        return key
    if row["source_id"].startswith("usfs:"):
        return (
            "usfs-facility",
            row["source_id"].removeprefix("usfs:").removeprefix("facility:"),
        )
    return None


def counts(rows):
    return {
        "places": len(rows),
        "regions": dict(sorted(Counter(row["region"] for row in rows).items())),
        "categories": dict(
            sorted(
                Counter(
                    category for row in rows for category in row["categories"]
                ).items()
            )
        ),
    }


def shortlist(source_dir, output, *, limit=150):
    """Rank already acquired original USFS facts by underrepresented states.

    The older independent public-feed lookup and road check still happen in the
    subsequent acquire. This is a prospect list, never an admission decision.
    """
    if type(limit) is not int or not 1 <= limit <= 250:
        raise ValueError("shortlist limit must be 1..250")
    source_dir, output = Path(source_dir).resolve(), Path(output)
    if output.exists():
        raise ValueError("shortlist output exists")
    from app.catalog import usfs

    acquisition = json.loads((source_dir / "acquisition.json").read_bytes())
    config = json.loads((source_dir / "bundle.json").read_bytes())
    reader = enrich.Reader(source_dir, 100 * 1024 * 1024)
    states = config["states"]
    shapes = usfs.state_shapes(
        json.loads(reader.read(states["path"], states["sha256"]))
    )
    old, known = baseline()
    prior = {native(row) for row in old}
    prior_counts = counts(old)["regions"]
    groups, ledger, scanned, identities = {}, [], 0, set()
    for receipt in acquisition["discovery_receipts"]:
        data = json.loads(reader.read(receipt["path"], receipt["sha256"]))
        for feature in data["features"]:
            scanned += 1
            a = feature["attributes"]
            if scanned > 10_000 or a["site_cn"] in identities:
                raise ValueError("bounded discovery identity/row ceiling violated")
            identities.add(a["site_cn"])
            qualified, reason = usfs_current.qualify(
                a,
                None,
                shapes,
                date.fromisoformat(config["reviewed_on"]),
                primary_publication=True,
            )
            if qualified:
                row, _ = qualified
                if native(row) in prior or row["source_id"] in known:
                    reason = "existing_native_identity"
                else:
                    groups.setdefault(row["region"], []).append(a["site_cn"])
            ledger.append({"site_cn": a["site_cn"], "preliminary_hold": reason})
    for group in groups.values():
        group.sort()
    regions = sorted(groups, key=lambda key: (prior_counts.get(key, 0), key))
    chosen = []
    while len(chosen) < limit:
        batch = [groups[key].pop(0) for key in regions if groups[key]]
        if not batch:
            break
        chosen.extend(batch[: limit - len(chosen)])
    for item in ledger:
        item["selection"] = "prospect" if item["site_cn"] in chosen else "held"
        if not item["preliminary_hold"] and item["site_cn"] not in chosen:
            item["preliminary_hold"] = "bounded_batch_limit"
    result = {
        "status": "prospects_only; independent public lookup and road checks required",
        "site_ids": chosen,
        "scanned": scanned,
        "bytes": reader.bytes,
        "source_directory": str(source_dir),
        "reviewed_on": config["reviewed_on"],
        "ranking": "Round robin by state, starting with lowest repository coverage; stable native-ID order within each state",
        "ledger": ledger,
    }
    write(output, result)
    return {key: value for key, value in result.items() if key != "ledger"}


def profile_source(source, arrival_review, output):
    """Opt into reviewed personas without changing any original acquisition file."""
    source, output = Path(source).resolve(), Path(output).absolute()
    if output.parent != source.parent or output == source:
        raise ValueError("profiled source must be a new sibling of the original source")
    review_path = output.with_suffix(".arrival-review.json")
    sidecar = Path(str(output) + ".manifest.json")
    if any(
        path.exists() or path.is_symlink() for path in (output, review_path, sidecar)
    ):
        raise ValueError("profiled source output exists")
    body, review_body = source.read_bytes(), Path(arrival_review).read_bytes()
    if len(body) > 128 * 1024 or len(review_body) > 1024 * 1024:
        raise ValueError("profile input exceeds byte ceiling")
    review = json.loads(review_body)
    compact = {key: value for key, value in review.items() if key != "records"}
    compact["source_bundle_sha256"] = review.get("source_bundle_sha256") or review.get(
        "source_bundle", {}
    ).get("sha256")
    compact["full_review_sha256"] = hashlib.sha256(review_body).hexdigest()
    compact["records"] = [
        {key: value for key, value in item.items() if key != "evidence_fields"}
        | {
            "evidence_fields": [
                {
                    key: field[key]
                    for key in (
                        "evidence_path",
                        "snapshot_sha256",
                        "source",
                        "source_record_id",
                        "projected_fields_sha256",
                    )
                    if key in field
                }
                for field in item.get("evidence_fields", [])
            ]
        }
        for item in review.get("records", [])
    ]
    review_body = (json.dumps(compact, sort_keys=True, indent=2) + "\n").encode()
    if len(review_body) > 256 * 1024:
        raise ValueError("compact arrival review exceeds unchanged ceiling")
    manifest = json.loads(Path(str(source) + ".manifest.json").read_bytes())
    if manifest["sha256"] != hashlib.sha256(body).hexdigest():
        raise ValueError("original source fingerprint changed")
    manifest["persona_enrichment"] = personas.VERSION
    manifest["arrival_review"] = {
        "path": review_path.name,
        "sha256": hashlib.sha256(review_body).hexdigest(),
    }
    created = []
    try:
        for path, content in ((review_path, review_body), (output, body)):
            with path.open("xb") as stream:
                stream.write(content)
            created.append(path)
        rows, report = usfs_current.prepare(output, manifest)
        with sidecar.open("x") as stream:
            json.dump(manifest, stream, sort_keys=True, indent=2)
            stream.write("\n")
        created.append(sidecar)
    except Exception:
        for path in reversed(created):
            path.unlink()
        raise
    return {
        "source_path": str(output),
        "accepted": len(rows),
        "rejects": report["rejects"],
        "network_or_database_calls": False,
    }


def replay(sources, routes_index, output):
    """Revalidate original evidence, then publish all outputs in one rename."""
    output = Path(output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("output already exists; choose a new immutable output")
    old, known = baseline()
    old_native = {key for row in old if (key := native(row)) is not None}
    candidates, reports, entries, metadata, preheld = [], {}, {}, {}, []
    source_units = source_bytes = retained_bytes = retained_files = 0
    selectors = []
    adapters = set()
    for adapter, source in sources:
        if adapter not in ADAPTERS or adapter in adapters:
            raise ValueError("unknown or repeated source adapter")
        adapters.add(adapter)
        path = Path(source).resolve()
        # Charge unused discovery inputs as well as consumed source evidence.
        for item in path.parent.rglob("*"):
            if item.is_symlink():
                raise ValueError("source evidence cannot contain symlinks")
            if item.is_file():
                retained_files += 1
                retained_bytes += item.stat().st_size
                if retained_files > 50_000 or retained_bytes > 100 * 1024 * 1024:
                    raise ValueError("retained source byte ceiling exceeded")
        manifest = json.loads(Path(str(path) + ".manifest.json").read_bytes())
        module = importlib.import_module(ADAPTERS[adapter])
        rows, report = module.prepare(path, manifest)
        source_units += report["scanned"]
        source_bytes += report["bytes"]
        if source_units > 50_000 or source_bytes > 100 * 1024 * 1024:
            raise ValueError("aggregate source ceiling exceeded")
        reports[adapter] = {k: v for k, v in report.items() if k != "calendar_entries"}
        for entry in report["calendar_entries"]:
            entries[entry["source_id"]] = entry
        metadata[adapter] = manifest
        retained = []
        for row in rows:
            if row["source_id"] in known or native(row) in old_native:
                preheld.append(
                    {
                        "source_id": row["source_id"],
                        "decision": "held",
                        "reason": "existing_publisher_native_identity",
                    }
                )
            else:
                retained.append(row)
        candidates.append((adapter, retained))
        selectors.append({"adapter": adapter, "path": str(path), "manifest": manifest})
    selected, decisions = select_arrivals(old, candidates)
    chosen = {sid for ids in selected.values() for sid in ids}
    accepted = [
        (adapter, row)
        for adapter, rows in candidates
        for row in rows
        if row["source_id"] in chosen
    ]
    if not accepted:
        raise ValueError("no admitted additions; evidence remains available for review")
    rows = [row for _, row in accepted]
    if len(rows) > 500:
        raise ValueError("expansion is bounded to 500 additions")
    route_root = Path(routes_index).resolve().parent
    road_routes = usfs_current._load_routes(Path(routes_index), route_root)
    grid = usfs_current.corridor_grid(road_routes)
    corridor_counts = lambda records: (
        dict.fromkeys((ident for ident, _ in road_routes), 0)
        | dict(
            Counter(
                ident
                for row in records
                for ident in usfs_current.nearby_corridors(
                    row["latitude"], row["longitude"], grid
                )
            )
        )
    )
    profiles = [
        personas.build(
            row,
            entries[row["source_id"]],
            release=metadata[adapter]["release"],
            attribution=metadata[adapter]["attribution"],
        )
        for adapter, row in accepted
    ]
    for selector in selectors:
        selector["selected_source_ids"] = selected[selector["adapter"]]
        selector["files"] = sorted(
            p.relative_to(Path(selector["path"]).parent).as_posix()
            for p in Path(selector["path"]).parent.rglob("*")
            if p.is_file()
        )
    completion = {
        "baseline_scope": "603 checked-in full rows; five later documented identities excluded. Hosted 608-row snapshot unreachable; no current-hosted coverage claim.",
        "baseline_normalized_rows_sha256": enrich.rows_digest(old),
        "before": counts(old),
        "after": counts(old + rows),
        "new_places": len(rows),
        "new_personas": len(profiles),
        "selected_candidates_held": len(preheld)
        + sum(d["decision"] == "held" for d in decisions),
        "source_units": source_units,
        "source_unit_scope": "Consumed adapter units only; full discovery prospect counts are reported separately.",
        "consumed_source_bytes": source_bytes,
        "retained_source_bytes": retained_bytes,
        "corridor_definition": "Continuous five-mile buffer of genuine OSRM roads; diagnostic, not sampled runtime queries or itinerary feasibility. Approximate city endpoints.",
        "corridors_before": corridor_counts(old),
        "corridors_after": corridor_counts(old + rows),
        "external_writes": False,
        "ai_requests": 0,
        "release_blockers": [
            "Current complete 608-place parent snapshot and companions required before building a release; configured DB network unreachable."
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="." + output.name + "-", dir=output.parent))
    try:
        write(staging / "additions.preview.json", rows)
        write(staging / "personas.json", profiles)
        write(staging / "calendars.json", [entries[row["source_id"]] for row in rows])
        write(staging / "source-reports.json", reports)
        write(staging / "selection-decisions.json", preheld + decisions)
        write(staging / "addition-inputs.json", selectors)
        write(staging / "completion.json", completion)
        staging.rename(output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return completion


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    route = commands.add_parser("routes")
    route.add_argument("--output", type=Path, required=True)
    route.add_argument("--scenic", action="store_true")
    short = commands.add_parser("shortlist")
    short.add_argument("--source-dir", type=Path, required=True)
    short.add_argument("--output", type=Path, required=True)
    short.add_argument("--limit", type=int, default=150)
    profile = commands.add_parser("profile-source")
    profile.add_argument("--source", type=Path, required=True)
    profile.add_argument("--arrival-review", type=Path, required=True)
    profile.add_argument("--output", type=Path, required=True)
    review = commands.add_parser("replay")
    review.add_argument(
        "--source", nargs=2, action="append", required=True, metavar=("ADAPTER", "PATH")
    )
    review.add_argument("--routes-index", type=Path, required=True)
    review.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "routes":
        print(routes(args.output, scenic=args.scenic))
    elif args.command == "shortlist":
        print(
            json.dumps(
                shortlist(args.source_dir, args.output, limit=args.limit), indent=2
            )
        )
    elif args.command == "profile-source":
        print(
            json.dumps(
                profile_source(args.source, args.arrival_review, args.output), indent=2
            )
        )
    else:
        print(json.dumps(replay(args.source, args.routes_index, args.output), indent=2))


if __name__ == "__main__":
    main()
