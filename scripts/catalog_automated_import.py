#!/usr/bin/env python3
"""Acquire, replay and assemble verified attraction imports; never activate implicitly.

The snapshot subcommand reads only public catalog facts from the configured DB.
Build is offline and emits the existing incremental import/recovery contract.
Explicit stage/activate/rollback operations remain in catalog_incremental_import.py.
"""

from __future__ import annotations

import argparse
import importlib
import json
import math
import re
import sys
from collections import Counter
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from app.catalog import calendar_enrichment as enrich
from app.catalog.automated_bindings import bind_calendar, native_key
from app.catalog.mixed import distance

ADAPTERS = {
    "automated-nps": "app.catalog.automated_nps",
    "usfs-current": "app.catalog.usfs_current",
}
SOURCE_KEYS = {
    "automated-nps": "nps-public",
    "usfs-current": "usfs",
}


class NoUsableChanges(ValueError):
    """A valid acquisition adds neither a new arrival nor a missing calendar."""


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def load(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("missing or oversized artifact")
    return json.loads(path.read_bytes())


def snapshot(conn, output):
    """Pin a consistent parent using a read-only transaction; no user tables."""
    from psycopg2.extras import RealDictCursor

    output = Path(output)
    if output.exists():
        raise ValueError("snapshot output already exists")
    conn.rollback()
    conn.set_session(readonly=True, isolation_level="REPEATABLE READ")
    with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SET LOCAL statement_timeout='5000ms'")
        cur.execute(
            "SELECT a.generation,i.release,i.manifest,i.row_count "
            "FROM places_catalog_active a JOIN places_catalog_imports i USING(generation)"
        )
        metadata = cur.fetchall()
        if len(metadata) != 1 or not 1 <= metadata[0]["row_count"] <= 50_000:
            raise ValueError("active catalog absent or exceeds bounded snapshot")
        metadata = dict(metadata[0])
        rows = enrich._rows(cur, metadata["generation"])
        entries = enrich._entries(cur, metadata["generation"])
        if len(rows) != metadata["row_count"]:
            raise ValueError("active catalog row count differs")
    serialized = json.dumps([metadata, rows, entries], allow_nan=False).encode()
    if len(serialized) > 100 * 1024 * 1024:
        raise ValueError("parent snapshot exceeds byte ceiling")
    output.mkdir(parents=True, mode=0o700)
    write(output / "rows.json", rows)
    write(output / "manifest.json", metadata["manifest"])
    write(output / "calendars.json", entries)
    report = {
        "generation": metadata["generation"],
        "release": metadata["release"],
        "row_count": len(rows),
        "calendar_count": len(entries),
        "manifest_sha256": enrich.digest(metadata["manifest"]),
        "normalized_rows_sha256": enrich.rows_digest(rows),
        "calendar_enrichment_sha256": enrich.digest(entries),
        "checked_at": datetime.now(UTC).isoformat(),
        "database_write": False,
        "scope": "catalog-only read; not production schema or local-gate evidence",
    }
    write(output / "snapshot.json", report)
    return report


def select_arrivals(baseline, sources):
    """Deterministic identity/name and 250m arrival collision holds, never coordinate edits."""
    buckets, names, ids = {}, {}, set()
    scale = 250 / 6_371_000
    offsets = tuple(product((-1, 0, 1), repeat=3))

    def cell(row):
        lat, lon = map(math.radians, (row["latitude"], row["longitude"]))
        return tuple(
            math.floor(value / scale)
            for value in (
                math.cos(lat) * math.cos(lon),
                math.cos(lat) * math.sin(lon),
                math.sin(lat),
            )
        )

    def name(row):
        return row["region"], re.sub(r"[^a-z0-9]", "", row["name"].casefold())

    def insert(row):
        ids.add(row["source_id"])
        names.setdefault(name(row), row["source_id"])
        buckets.setdefault(cell(row), []).append(row)

    for row in baseline:
        insert(row)
    selected, decisions = {}, []
    for adapter, rows in sources:
        selected[adapter] = []
        for row in sorted(rows, key=lambda item: item["source_id"]):
            reason, collision = None, None
            if row["source_id"] in ids:
                reason, collision = "existing_identity", row["source_id"]
            elif name(row) in names:
                reason, collision = "same_name_and_region", names[name(row)]
            else:
                key = cell(row)
                for delta in offsets:
                    nearby = tuple(key[i] + delta[i] for i in range(3))
                    for old in buckets.get(nearby, []):
                        if distance(row, old) < 250:
                            reason, collision = (
                                "unresolved_arrival_within_250m",
                                old["source_id"],
                            )
                            break
                    if reason:
                        break
            decisions.append(
                {
                    "adapter": adapter,
                    "source_id": row["source_id"],
                    "decision": "held" if reason else "selected",
                    "reason": reason,
                    "conflicting_source_id": collision,
                }
            )
            if not reason:
                selected[adapter].append(row["source_id"])
                insert(row)
    return selected, decisions


def bundle(parent_dir, sources, output, *, routes_index=None):
    """Replay typed adapters before selecting additions and building a portable artifact."""
    from scripts.catalog_incremental_bundle import build

    parent_dir, output = Path(parent_dir).resolve(), Path(output).resolve()
    parent = load(parent_dir / "snapshot.json")
    baseline = load(parent_dir / "rows.json")
    prior_calendars = load(parent_dir / "calendars.json")
    if enrich.rows_digest(baseline) != parent["normalized_rows_sha256"]:
        raise ValueError("parent rows differ from pinned snapshot")
    if enrich.digest(prior_calendars) != parent["calendar_enrichment_sha256"]:
        raise ValueError("parent calendars differ from pinned snapshot")
    candidates, prepared_sources, licenses, source_entries = [], [], [], {}
    parent_manifest = load(parent_dir / "manifest.json")
    if (
        enrich.digest(parent_manifest) != parent["manifest_sha256"]
        or len(baseline) != parent["row_count"]
        or parent_manifest.get("release") != parent["release"]
    ):
        raise ValueError("parent metadata differs from pinned snapshot")
    additional_catalogs = {}
    seen = set()
    for adapter, source in sources:
        if adapter not in ADAPTERS or adapter in seen:
            raise ValueError("unknown or repeated source adapter")
        seen.add(adapter)
        source = Path(source).resolve()
        manifest = load(Path(str(source) + ".manifest.json"))
        module = importlib.import_module(ADAPTERS[adapter])
        rows, report = module.prepare(
            source, manifest, max_rows=50_000, max_bytes=100 * 1024 * 1024
        )
        candidates.append((adapter, rows))
        source_entries[adapter] = {
            entry["source_id"]: entry for entry in report["calendar_entries"]
        }
        key = SOURCE_KEYS[adapter]
        if key not in parent_manifest.get("source_catalogs", {}):
            additional_catalogs[key] = {
                field: manifest[field]
                for field in ("release", "attribution", "source_url")
            }
        # Every file in a dedicated acquisition bundle is retained, bounded and portable.
        files = []
        total = 0
        for path in sorted(source.parent.rglob("*")):
            if path.is_file():
                relative = path.relative_to(source.parent).as_posix()
                if path.is_symlink() or not enrich.portable_relative(relative):
                    raise ValueError("acquisition contains an unsafe evidence path")
                total += path.stat().st_size
                if total > 100 * 1024 * 1024 or len(files) >= 50_000:
                    raise ValueError("acquisition exceeds retained evidence ceiling")
                files.append(relative)
        prepared_sources.append(
            {
                "adapter": adapter,
                "path": str(source),
                "manifest": manifest,
                "files": files,
            }
        )
        for identifier, receipt in manifest["licenses"].items():
            path = Path(receipt["path"])
            if not path.is_absolute():
                path = source.parent / path
            licenses.append(
                {
                    "identifier": identifier,
                    "path": str(path),
                    "sha256": receipt["sha256"],
                    "source_url": receipt.get("url")
                    or receipt.get("source_url")
                    or manifest["source_url"],
                }
            )
    selected, decisions = select_arrivals(baseline, candidates)
    route_files = []
    if routes_index is not None:
        from scripts.catalog_500_discovery import distance as miles
        from scripts.catalog_incremental_proof import routes

        routes_index = Path(routes_index).resolve()
        route_inputs, _ = routes(routes_index, routes_index.parent)
        samples = [point for route in route_inputs for point in route["samples"]]
        in_scope = {
            row["source_id"]
            for _, rows in candidates
            for row in rows
            if any(
                miles(point, [row["latitude"], row["longitude"]]) <= 5
                for point in samples
            )
        }
        for adapter in selected:
            selected[adapter] = [sid for sid in selected[adapter] if sid in in_scope]
        for decision in decisions:
            if (
                decision["decision"] == "selected"
                and decision["source_id"] not in in_scope
            ):
                decision.update(
                    decision="held", reason="outside_test_route_five_mile_samples"
                )
        route_files.append({"path": str(routes_index)})
        route_files.extend(
            {"path": str(routes_index.parent / item["response_path"])}
            for item in load(routes_index)["routes"]
        )
    prior_ids = {entry["source_id"] for entry in prior_calendars}
    native_parents = {}
    for row in baseline:
        if (key := native_key(row)) is not None:
            native_parents.setdefault(key, []).append(row)
    bindings = {}
    for adapter, rows in candidates:
        bindings[adapter] = {}
        for row in rows:
            parents = native_parents.get(native_key(row), [])
            if len(parents) != 1 or parents[0]["source_id"] in prior_ids:
                continue
            try:
                bind_calendar(
                    row, parents[0], source_entries[adapter][row["source_id"]]
                )
            except (ValueError, KeyError):
                continue
            bindings[adapter][row["source_id"]] = parents[0]["source_id"]
            if row["source_id"] in selected[adapter]:
                selected[adapter].remove(row["source_id"])
            for decision in decisions:
                if (
                    decision["adapter"] == adapter
                    and decision["source_id"] == row["source_id"]
                ):
                    decision.update(
                        decision="calendar_update",
                        reason="identical_native_facility_and_arrival",
                        conflicting_source_id=parents[0]["source_id"],
                    )
    for source in prepared_sources:
        source["selected_source_ids"] = selected[source["adapter"]]
        source["calendar_bindings"] = bindings[source["adapter"]]
    if not any(selected.values()) and not any(bindings.values()):
        raise NoUsableChanges(
            "no new verified arrivals or missing calendars remain after source review"
        )
    config = {
        "baseline_rows": str(parent_dir / "rows.json"),
        "baseline_manifest": str(parent_dir / "manifest.json"),
        "parent_generation": parent["generation"],
        "baseline_normalized_rows_sha256": parent["normalized_rows_sha256"],
        "parent_calendar_enrichment_sha256": parent["calendar_enrichment_sha256"],
        "calendar_inputs": [],
        "source_files": route_files,
        "source_scanned_rows": 0,
        "licenses": licenses,
        "addition_inputs": prepared_sources,
        "additional_source_catalogs": additional_catalogs,
        "release": "automated-verified-arrivals-"
        + datetime.now(UTC).strftime("%Y-%m-%d"),
        "attribution": "Attributed official visitor hours and arrivals; original parent credits retained.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    config_path = output.parent / (output.name + ".build-config.json")
    if config_path.exists():
        raise ValueError("build config already exists")
    write(config_path, config)
    report = build(config_path, output)
    write(output / "arrival-decisions.json", decisions)
    report["arrival_decisions"] = dict(Counter(item["decision"] for item in decisions))
    write(output / "completion.json", report)
    return report


def acquire_source(
    name,
    output,
    parent,
    routes_index,
    *,
    codes=None,
    parking_publication_urls=(),
    nps_arrival_page_urls=(),
):
    module = importlib.import_module(ADAPTERS[name])
    if name == "automated-nps":
        if parking_publication_urls:
            raise ValueError("parking publications apply only to USFS acquisition")
        return module.acquire(
            output, codes=codes, arrival_page_urls=nps_arrival_page_urls
        )
    if nps_arrival_page_urls:
        raise ValueError("NPS arrival pages apply only to NPS acquisition")
    if parent is None or routes_index is None:
        raise ValueError(
            "USFS acquisition requires parent snapshot and retained routes"
        )
    return module.acquire(
        output,
        parent_rows=Path(parent) / "rows.json",
        routes_index=routes_index,
        route_root=Path(routes_index).parent,
        parking_publication_urls=parking_publication_urls,
    )


def configured_snapshot(output):
    import psycopg2
    from app.core.config import settings

    conn = psycopg2.connect(
        settings.DATABASE_URL, sslmode=settings.DATABASE_SSLMODE, connect_timeout=5
    )
    try:
        return snapshot(conn, output)
    finally:
        conn.close()


def acquire_routes(output):
    from scripts.catalog_test_routes import acquire

    return acquire(output)


def refresh(
    output,
    routes_index,
    sources,
    *,
    parking_publication_urls=(),
    nps_arrival_page_urls=(),
):
    """One bounded acquisition/replay command; never stages or activates a database."""
    output = Path(output).resolve()
    if (
        output.exists()
        or not sources
        or len(sources) != len(set(sources))
        or set(sources) - ADAPTERS.keys()
        or (parking_publication_urls and "usfs-current" not in sources)
        or (nps_arrival_page_urls and "automated-nps" not in sources)
    ):
        raise ValueError(
            "refresh requires a new output and distinct reviewed source adapters"
        )
    output.mkdir(parents=True, mode=0o700)
    if routes_index is None:
        routes_index = acquire_routes(output / "routes")
    parent = output / "parent"
    configured_snapshot(parent)
    acquired = []
    acquisition_summaries = []
    for name in sources:
        report = acquire_source(
            name,
            output / name,
            parent,
            routes_index,
            parking_publication_urls=parking_publication_urls
            if name == "usfs-current"
            else (),
            nps_arrival_page_urls=nps_arrival_page_urls
            if name == "automated-nps"
            else (),
        )
        acquired.append((name, report["source_path"]))
        acquisition_summaries.append(
            {
                "adapter": name,
                **{
                    key: report[key]
                    for key in (
                        "acquired_units",
                        "failed_units",
                        "prequalified_facilities",
                        "discovered_facilities",
                        "selected_facilities",
                        "parent_refresh_candidates",
                        "driving_receipts",
                        "acquired_bytes",
                        "accepted",
                        "calendar_entries",
                    )
                    if key in report
                },
            }
        )
    try:
        report = bundle(parent, acquired, output / "import", routes_index=routes_index)
        result = {
            "status": "prepared",
            **report,
            "artifact": str(output / "import/catalog.enrichment.json"),
        }
    except NoUsableChanges:
        result = {
            "status": "no_change",
            "reason": "No new verified arrivals or missing calendars passed source and identity checks.",
        }
    result["database_write"] = False
    result["acquisitions"] = acquisition_summaries
    result["partial_source_acquisition"] = any(
        item.get("failed_units", 0) > 0 for item in acquisition_summaries
    )
    result["network_or_database_calls"] = True
    result["operations"] = [
        "read_only_catalog_snapshot",
        "official_source_acquisition",
        "offline_replay_and_assembly",
    ]
    write(output / "refresh.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser(
        "snapshot", help="read configured catalog; no database writes"
    )
    export.add_argument("--output", type=Path, required=True)
    route_capture = sub.add_parser(
        "routes", help="capture fixed current Studio route receipts"
    )
    route_capture.add_argument("--output", type=Path, required=True)
    assemble = sub.add_parser(
        "build", help="offline source replay, collision holds and bundle"
    )
    assemble.add_argument("--parent", type=Path, required=True)
    assemble.add_argument(
        "--source",
        action="append",
        nargs=2,
        metavar=("ADAPTER", "BUNDLE"),
        required=True,
    )
    assemble.add_argument("--output", type=Path, required=True)
    assemble.add_argument(
        "--routes-index",
        type=Path,
        help="limit new additions to retained test-route five-mile samples",
    )
    acquire = sub.add_parser(
        "acquire", help="fetch bounded official source evidence; no database writes"
    )
    acquire.add_argument("--source", choices=sorted(ADAPTERS), required=True)
    acquire.add_argument("--output", type=Path, required=True)
    acquire.add_argument(
        "--codes", nargs="+", help="NPS unit codes; omit for published inventory"
    )
    acquire.add_argument(
        "--parent",
        type=Path,
        help="parent snapshot directory for existing facility refreshes",
    )
    acquire.add_argument(
        "--routes-index", type=Path, help="retained routes for new facility selection"
    )
    acquire.add_argument(
        "--parking-publication-url",
        action="append",
        default=[],
        help="reviewed official USFS parking publication URL; repeat for multiple publications",
    )
    acquire.add_argument(
        "--nps-arrival-page-url",
        action="append",
        default=[],
        help="official NPS arrival page linked by native facility/unit facts; repeat for multiple pages",
    )
    run = sub.add_parser(
        "refresh",
        help="read parent, acquire and prepare an import without database writes",
    )
    run.add_argument("--output", type=Path, required=True)
    run.add_argument(
        "--routes-index", type=Path, help="omit to capture fresh fixed test routes"
    )
    run.add_argument(
        "--sources", nargs="+", choices=sorted(ADAPTERS), default=sorted(ADAPTERS)
    )
    run.add_argument(
        "--parking-publication-url",
        action="append",
        default=[],
        help="reviewed official USFS parking publication URL; repeat for multiple publications",
    )
    run.add_argument(
        "--nps-arrival-page-url",
        action="append",
        default=[],
        help="official NPS arrival page linked by native facility/unit facts; repeat for multiple pages",
    )
    args = parser.parse_args()
    if args.command == "snapshot":
        result = configured_snapshot(args.output)
    elif args.command == "routes":
        result = {
            "routes_index": str(acquire_routes(args.output)),
            "database_write": False,
        }
    elif args.command == "refresh":
        result = refresh(
            args.output,
            args.routes_index,
            args.sources,
            parking_publication_urls=args.parking_publication_url,
            nps_arrival_page_urls=args.nps_arrival_page_url,
        )
    elif args.command == "build":
        result = bundle(
            args.parent, args.source, args.output, routes_index=args.routes_index
        )
    else:
        result = acquire_source(
            args.source,
            args.output,
            args.parent,
            args.routes_index,
            codes=args.codes,
            parking_publication_urls=args.parking_publication_url,
            nps_arrival_page_urls=args.nps_arrival_page_url,
        )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 -- DB errors may contain credentials
        raise SystemExit(
            f"Automated import failed ({type(exc).__name__}); no credentials logged"
        ) from None
