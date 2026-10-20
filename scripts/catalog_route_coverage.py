#!/usr/bin/env python3
"""Read-only corridor diagnostics for source-backed catalog snapshots.

This compares real retained driving geometry using four-mile vertex samples,
unchanged five-mile radius and sixty-result bounds. Published-clock checks use
explicit source-local dates and an artificial UTC arithmetic zone: they prove
only a complete chosen dwell fits a published clock window, not the candidate's
actual timezone, arrival, driving access, ticket inventory or a feasible trip.
No database, provider or network operation is performed by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from app.catalog.calendar_enrichment import project
from app.catalog.identity import identity
from app.routing.visit_calendar import calendar_eligible, day_intervals, source_calendar

from scripts.catalog_500_discovery import distance
from scripts.catalog_incremental_proof import routes

RADIUS_MILES = 5
RESULT_LIMIT = 60
MAX_BYTES = 64 * 1024 * 1024


def read(path):
    path = Path(path)
    if not 0 < path.stat().st_size <= MAX_BYTES:
        raise ValueError("snapshot must contain 1..64 MiB of JSON")
    value = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in value.splitlines() if line.strip()]
    return json.loads(value)


def candidates(rows, entries):
    if isinstance(entries, list):
        entries = {entry["source_id"]: entry for entry in entries}
    if not isinstance(rows, list) or len(rows) > 50_000:
        raise ValueError("snapshot requires at most 50,000 normalized catalog rows")
    if len({row["source_id"] for row in rows}) != len(rows):
        raise ValueError("snapshot contains duplicate source identities")
    return [
        {
            "provider_id": identity(row["source_id"])[0],
            "source_id": row["source_id"],
            "name": row["name"],
            "categories": row["categories"],
            "coordinates": [row["latitude"], row["longitude"]],
            "source_provenance": project(
                row["provenance"], entries.get(row["source_id"])
            ),
        }
        for row in rows
    ]


def published_clock_fit(record, local_date, dwell_seconds):
    """Necessary source-clock condition; never silently approve missing hours."""
    calendar = source_calendar(record)
    if calendar is None or calendar.unknown_reasons or calendar.fixed_starts:
        # Fixed-start instants need a real candidate timezone to match a local day.
        return False
    return any(
        (closes - opens).total_seconds() >= dwell_seconds
        for opens, closes in day_intervals(calendar, local_date, ZoneInfo("UTC"))
    )


def coverage(records, route_inputs, local_dates, *, dwell_seconds=7200):
    if (
        type(dwell_seconds) is not int
        or not 1 <= dwell_seconds <= 86400
        or not local_dates
        or len(local_dates) > 366
    ):
        raise ValueError(
            "provide bounded source-local dates and a positive dwell up to one day"
        )
    eligible = [
        record
        for record in records
        if "daytime" in record["categories"] and calendar_eligible(record)
    ]
    confirmed = {
        record["source_id"]
        for record in eligible
        if source_calendar(record) is not None
        and not source_calendar(record).unknown_reasons
    }
    clock_fit = {
        local_date.isoformat(): {
            record["source_id"]
            for record in eligible
            if published_clock_fit(record, local_date, dwell_seconds)
        }
        for local_date in local_dates
    }
    output = {}
    for route in route_inputs:
        union, occupied, occupied_verified, capped = set(), 0, 0, 0
        for point in route["samples"]:
            nearby = sorted(
                (
                    (distance(point, record["coordinates"]), record["source_id"])
                    for record in eligible
                ),
                key=lambda item: (item[0], item[1]),
            )
            within = [(miles, sid) for miles, sid in nearby if miles <= RADIUS_MILES]
            capped += len(within) > RESULT_LIMIT
            ids = {sid for _, sid in within[:RESULT_LIMIT]}
            occupied += bool(ids)
            occupied_verified += bool(ids & confirmed)
            union.update(ids)
        output[route["id"]] = {
            "role": route.get("role"),
            "sample_points": len(route["samples"]),
            "samples_with_structural_hits": occupied,
            "samples_with_verified_calendar_hits": occupied_verified,
            "samples_exceeding_sixty_results": capped,
            "structural_hits": len(union),
            "verified_calendar_hits": len(union & confirmed),
            "published_clock_full_dwell_hits_by_local_date": {
                day: len(union & ids) for day, ids in clock_fit.items()
            },
            "source_ids": sorted(union),
            "verified_calendar_source_ids": sorted(union & confirmed),
            "source_route_receipt": route["receipt"],
        }
    return {
        "schema_version": "roadtrips-catalog-route-coverage/1",
        "created_at": datetime.now(UTC).isoformat(),
        "scope": "read_only_snapshot_diagnostic; not an actual-arrival or complete-itinerary proof",
        "query": {
            "categories": ["daytime"],
            "radius_miles": RADIUS_MILES,
            "limit_per_sample": RESULT_LIMIT,
            "geometry_vertex_sampling_miles": 4,
            "calendar_filter": "existing calendar_eligible; outdoor unknown hours remain structural only",
        },
        "clock_check": {
            "dwell_seconds": dwell_seconds,
            "source_local_dates": [day.isoformat() for day in local_dates],
            "arithmetic_zone": "artificial UTC; actual candidate IANA timezone and arrival remain unverified",
            "fixed_start_calendars": "excluded until real candidate timezone is supplied",
            "meaning": "one full chosen dwell fits a published local clock window on this source-local date",
        },
        "catalog": {
            "rows": len(records),
            "structurally_eligible_daytime_rows": len(eligible),
            "verified_calendar_daytime_rows": len(confirmed),
        },
        "corridors": output,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", required=True, type=Path)
    parser.add_argument("--calendars", required=True, type=Path)
    parser.add_argument("--routes-index", required=True, type=Path)
    parser.add_argument("--routes-root", type=Path)
    parser.add_argument("--local-date", required=True, type=date.fromisoformat)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--dwell-minutes", type=int, default=120)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not 1 <= args.days <= 366:
        parser.error("--days must be 1..366")
    route_inputs, verified = routes(
        args.routes_index, (args.routes_root or args.routes_index.parent).resolve()
    )
    output = coverage(
        candidates(read(args.rows), read(args.calendars)),
        route_inputs,
        [args.local_date + timedelta(days=offset) for offset in range(args.days)],
        dwell_seconds=args.dwell_minutes * 60,
    )
    output["retained_route_inputs"] = verified
    output["snapshot_receipts"] = {
        key: {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
        for key, path in {"rows": args.rows, "calendars": args.calendars}.items()
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "catalog": output["catalog"],
                "corridors": {
                    key: {
                        name: value[name]
                        for name in (
                            "structural_hits",
                            "verified_calendar_hits",
                            "published_clock_full_dwell_hits_by_local_date",
                        )
                    }
                    for key, value in output["corridors"].items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
