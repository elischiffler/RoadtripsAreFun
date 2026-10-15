#!/usr/bin/env python3
"""Reproduce incremental catalog proofs in one isolated loopback PostgreSQL 18 DB.

The DSN is read only from CATALOG_PROOF_DATABASE_URL; a private Docker server
interface additionally requires CATALOG_PROOF_CONTAINER_NAME for attestation.
This script changes catalog
generations and the active pointer only in catalog_expansion_validation. It makes
no remote requests, touches no saved-trip tables, and proves source/eligibility
preservation and local SELECT performance, not a jointly feasible itinerary,
opening at an actual arrival time, provider timezone, or production latency.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import math
import os
import socket
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path, PurePosixPath, PureWindowsPath
from zoneinfo import ZoneInfo

import psycopg2
from psycopg2.extras import RealDictCursor

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from app.catalog import calendar_enrichment as enrich
from app.catalog import repository
from app.catalog.identity import identity
from app.routing.trip_calendar import possible_visit
from app.routing.visit_calendar import (
    VisitCalendarConflict,
    calendar_eligible,
    open_intervals,
    solve_visit,
    source_calendar,
)

from scripts.catalog_500_discovery import samples

DATABASE = "catalog_expansion_validation"


def sha256(body):
    return hashlib.sha256(body).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _loopback(host):
    if host == "localhost":
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        return bool(addresses) and all(
            ipaddress.ip_address(row[4][0]).is_loopback for row in addresses
        )
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def server_attestation(options, address, server_port):
    """Distinguish the loopback client endpoint from Docker's server interface."""
    if _loopback(address):
        return "PostgreSQL server itself reports a loopback interface"
    require(
        ipaddress.ip_address(address).is_private,
        "server interface is not local/private",
    )
    container_name = os.environ.get("CATALOG_PROOF_CONTAINER_NAME", "")
    require(
        bool(container_name),
        "CATALOG_PROOF_CONTAINER_NAME is required for Docker attestation",
    )
    # Read only this explicitly authorized disposable container's networking.
    # Capture output privately; never log inspect data, DSN, host or port.
    inspected = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            "{{json .NetworkSettings}}",
            container_name,
        ],
        capture_output=True,
        check=True,
        text=True,
        timeout=5,
    )
    network = json.loads(inspected.stdout)
    bindings = (network.get("Ports") or {}).get(f"{server_port}/tcp", []) or []
    port = str(options.get("port", "5432"))
    selected = [binding for binding in bindings if binding.get("HostPort") == port]
    require(
        bool(selected)
        and all(_loopback(binding.get("HostIp", "")) for binding in selected),
        "disposable container does not publish this port solely through loopback",
    )
    require(
        any(
            address in {item.get("IPAddress"), item.get("GlobalIPv6Address")}
            for item in (network.get("Networks") or {}).values()
        ),
        "PostgreSQL private interface differs from authorized local container",
    )
    return "Authorized disposable Docker container: loopback published port and private PostgreSQL interface match read-only Docker inspection"


def connect():
    value = os.environ.get("CATALOG_PROOF_DATABASE_URL", "")
    require(
        bool(value),
        "CATALOG_PROOF_DATABASE_URL must select the isolated proof database",
    )
    options = psycopg2.extensions.parse_dsn(value)
    require(
        options.get("dbname") == DATABASE
        and _loopback(options.get("host", ""))
        and ("hostaddr" not in options or _loopback(options["hostaddr"]))
        and "service" not in options,
        "refusing a non-loopback or differently named proof database",
    )
    # Explicitly override libpq's ambient PGHOSTADDR with the validated endpoint.
    # The URL's host alone does not constrain that independent environment field.
    client_address = options.get("hostaddr") or (
        "127.0.0.1" if options["host"] == "localhost" else options["host"]
    )
    conn = psycopg2.connect(
        value,
        hostaddr=client_address,
        connect_timeout=5,
        sslmode="disable",
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_database(),current_setting('server_version_num')::int,"
                "host(inet_server_addr()),inet_server_port()"
            )
            name, version, address, server_port = cur.fetchone()
        conn.rollback()
        require(
            name == DATABASE and version // 10000 == 18,
            "connected server differs from guarded local PostgreSQL 18 target",
        )
        attestation = server_attestation(options, address or "", server_port)
        return conn, version, attestation
    except BaseException:
        conn.close()
        raise


def relative_file(root, value):
    require(
        isinstance(value, str)
        and bool(value)
        and "\\" not in value
        and not PurePosixPath(value).is_absolute()
        and not PureWindowsPath(value).drive
        and not any(part in {"", ".", ".."} for part in value.split("/")),
        "retained evidence requires a relative portable path",
    )
    path = (root / value).resolve()
    require(
        path.is_relative_to(root) and path.is_file(),
        "retained evidence is missing or escapes its root",
    )
    return path


def routes(index_path, route_root):
    raw = index_path.read_bytes()
    require(0 < len(raw) <= 2 * 1024 * 1024, "retained route index exceeds proof bound")
    index = json.loads(raw)
    receipts = {}
    for receipt in index["receipts"]:
        require(
            receipt["path"] not in receipts, "duplicate retained route receipt path"
        )
        body = relative_file(route_root, receipt["path"]).read_bytes()
        require(
            len(body) == receipt["bytes"] and sha256(body) == receipt["sha256"],
            "retained route/geocode receipt bytes changed",
        )
        receipts[receipt["path"]] = receipt
    loaded, seen = [], set()
    for route in index["routes"]:
        require(route["id"] not in seen, "duplicate corridor ID")
        seen.add(route["id"])
        receipt = receipts[route["response_path"]]
        require(
            receipt["status"] == 200 and receipt["url"].startswith("https://"),
            "route lacks successful original HTTPS acquisition",
        )
        checked = datetime.fromisoformat(receipt["retrieved_at"].replace("Z", "+00:00"))
        require(checked.tzinfo is not None, "route acquisition time must remain aware")
        body = relative_file(route_root, route["response_path"]).read_bytes()
        response = json.loads(body)
        require(
            response.get("code") == "Ok" and bool(response.get("routes")),
            "retained response has no successful driving route",
        )
        geometry = response["routes"][0]["geometry"]
        coordinates = geometry["coordinates"]
        require(
            geometry["type"] == "LineString" and len(coordinates) >= 2,
            "route geometry is not a driving LineString",
        )
        require(
            all(
                len(point) == 2
                and all(type(n) in (int, float) and math.isfinite(n) for n in point)
                and -180 <= point[0] <= 180
                and -90 <= point[1] <= 90
                for point in coordinates
            ),
            "invalid retained driving geometry",
        )
        loaded.append(
            {
                "id": route["id"],
                "role": route.get("role"),
                "samples": samples(coordinates),
                "receipt": receipt,
            }
        )
    require(bool(loaded), "proof needs retained real routes")
    return loaded, {
        "sha256": sha256(raw),
        "bytes": len(raw),
        "attribution": index.get("attribution"),
        "verified_receipts": list(receipts.values()),
    }


def code_receipts():
    paths = {Path(__file__).resolve(), ROOT / "scripts/catalog_500_discovery.py"}
    paths.update((ROOT / "backend/app/catalog").glob("*.py"))
    for module in list(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if filename:
            path = Path(filename).resolve()
            if path.is_relative_to(ROOT) and path.suffix == ".py" and path.is_file():
                paths.add(path)
    return {
        path.relative_to(ROOT).as_posix(): {
            "sha256": sha256(path.read_bytes()),
            "bytes": path.stat().st_size,
        }
        for path in sorted(paths)
    }


def active(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT generation FROM places_catalog_active WHERE singleton=true")
        value = cur.fetchone()
    conn.rollback()
    require(value is not None, "proof database has no active generation")
    return value[0]


def snapshot(conn, generation):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        rows = enrich._rows(cur, generation)
        entries = enrich._entries(cur, generation)
        cur.execute(
            "SELECT manifest,release,row_count FROM places_catalog_imports WHERE generation=%s",
            (generation,),
        )
        metadata = dict(cur.fetchone())
    conn.rollback()
    return rows, {entry["source_id"]: entry for entry in entries}, metadata


def candidate(row, entries):
    return {
        "provider_id": identity(row["source_id"])[0],
        "categories": row["categories"],
        "source_provenance": enrich.project(
            row["provenance"], entries.get(row["source_id"])
        ),
    }


def quantiles(values):
    return (
        {
            "query_count": len(values),
            "p50_ms": statistics.median(values),
            "p95_ms": sorted(values)[int((len(values) - 1) * 0.95)],
            "max_ms": max(values),
        }
        if values
        else {"query_count": 0}
    )


def counts(rows, entries):
    return {
        "rows": len(rows),
        "categories": dict(
            sorted(
                Counter(
                    category for row in rows for category in row["categories"]
                ).items()
            )
        ),
        "regions": dict(sorted(Counter(row["region"] for row in rows).items())),
        "automatic_eligible_rows": sum(
            calendar_eligible(candidate(row, entries)) for row in rows
        ),
        "companion_rows": sum(row["source_id"] in entries for row in rows),
    }


def discover(conn, generation, route_inputs):
    rows, entries, metadata = snapshot(conn, generation)
    expected = {identity(row["source_id"])[0]: row for row in rows}
    positives, corridor_times, native_times, corridors = {}, [], [], {}

    def match(found):
        require(
            calendar_eligible(found), "automatic SELECT returned a source-calendar hold"
        )
        row = expected[found["provider_id"]]
        projected = enrich.project(row["provenance"], entries.get(row["source_id"]))
        projected.append(
            {
                "dataset": "Roadtrips active catalog",
                "generation": generation,
                "release": metadata["release"],
            }
        )
        require(
            found["source_provenance"] == projected,
            "application SELECT changed full source facts or effective receipts",
        )
        require(
            found["coordinates"] == [row["latitude"], row["longitude"]]
            and all(
                found[key] == row[key]
                for key in ("name", "address", "url", "categories", "source_updated_at")
            ),
            "application SELECT changed native place fields",
        )
        actual_calendar = source_calendar(found)
        expected_calendar = source_calendar({"source_provenance": projected})
        receipts = actual_calendar.source_receipts if actual_calendar else []
        require(
            receipts
            == (expected_calendar.source_receipts if expected_calendar else []),
            "full effective source receipt list differs",
        )
        positives[found["provider_id"]] = {
            "source_id": row["source_id"],
            "name": row["name"],
            "coordinates": found["coordinates"],
            "categories": row["categories"],
            "source_release": found["source_release"],
            "source_attribution": found["source_attribution"],
            "full_source_provenance_sha256": enrich.digest(projected),
            "full_calendar_source_receipts": receipts,
            "full_place_fields_and_receipts_match": True,
        }

    def lookup(point, categories, timings):
        started = time.perf_counter()
        found = repository.nearby(point, categories, require_visit_calendar=True)
        timings.append((time.perf_counter() - started) * 1000)
        for record in found:
            match(record)
        return found

    eligible = [row for row in rows if calendar_eligible(candidate(row, entries))]
    for row in eligible:
        categories = [
            category
            for category in ("daytime", "food", "culture", "nightlife")
            if category in row["categories"]
        ]
        require(
            bool(categories),
            "eligible source row has no application discovery category",
        )
        found = lookup([row["latitude"], row["longitude"]], categories, native_times)
        require(
            identity(row["source_id"])[0]
            in {record["provider_id"] for record in found},
            "eligible source row missing from actual native-point discovery",
        )
    for route in route_inputs:
        ids, occupied = set(), 0
        for point in route["samples"]:
            found = lookup(point, ["daytime"], corridor_times)
            occupied += bool(found)
            ids.update(record["provider_id"] for record in found)
        corridors[route["id"]] = {
            "role": route["role"],
            "sample_points": len(route["samples"]),
            "samples_with_hits": occupied,
            "eligible_count": len(ids),
            "eligible_ids": sorted(ids),
            "source_route_receipt": route["receipt"],
        }
    return {
        "counts": counts(rows, entries),
        "native_point_SELECT_timings": quantiles(native_times),
        "corridor_SELECT_timings": quantiles(corridor_times),
        "all_eligible_native_point_probes_passed": True,
        "positive_source_matches": positives,
        "corridors": corridors,
    }


def storage(conn, parent, generation):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT count(*) AS row_count,COALESCE(sum(pg_column_size(p)),0)::bigint AS whole_generation_row_bytes FROM places_catalog p WHERE generation=%s",
            (generation,),
        )
        whole = dict(cur.fetchone())
        cur.execute(
            "SELECT count(*) AS new_row_count,COALESCE(sum(pg_column_size(p)),0)::bigint AS genuinely_new_row_bytes FROM places_catalog p WHERE generation=%s AND NOT EXISTS(SELECT 1 FROM places_catalog old WHERE old.generation=%s AND old.source_id=p.source_id)",
            (generation, parent),
        )
        new = dict(cur.fetchone())
        cur.execute(
            "SELECT count(*) AS companion_row_count,COALESCE(sum(pg_column_size(c)),0)::bigint AS companion_generation_row_bytes,COALESCE(sum(octet_length(entry::text)),0)::bigint AS companion_generation_json_text_bytes FROM places_catalog_calendars c WHERE generation=%s",
            (generation,),
        )
        companion = dict(cur.fetchone())
        cur.execute(
            "SELECT pg_database_size(current_database()) AS database_bytes,pg_table_size('places_catalog') AS catalog_table_bytes,pg_indexes_size('places_catalog') AS catalog_index_bytes,pg_table_size('places_catalog_calendars') AS companion_table_bytes,pg_indexes_size('places_catalog_calendars') AS companion_index_bytes,pg_total_relation_size('places_catalog_calendars') AS companion_total_bytes"
        )
        physical = dict(cur.fetchone())
        guards = enrich._storage(cur)
    conn.rollback()
    return {
        **whole,
        **new,
        **companion,
        **physical,
        **guards,
        "measurement": "pg_column_size sums are measured composite datum bytes; physical table/index totals include all retained generations and TOAST, not a per-generation physical allocation estimate.",
    }


def temporal_contract(rows, entries):
    """Bulk-test actual stored serialization in a declared artificial test zone."""
    zone = ZoneInfo("UTC")
    start, end = date(2026, 10, 15), date(2026, 11, 13)
    totals = Counter()
    records, failures = [], []

    def reject(record, earliest, cutoff, kind):
        totals[kind] += 1
        try:
            solve_visit(record, earliest, cutoff, dwell=7200)
        except VisitCalendarConflict:
            return
        failures.append(
            {
                "provider_id": record["provider_id"],
                "control": kind,
                "earliest": earliest.isoformat(),
                "cutoff": cutoff.isoformat(),
            }
        )

    by_id = {row["source_id"]: row for row in rows}
    for source_id in sorted(entries):
        record = candidate(by_id[source_id], entries)
        calendar = source_calendar(record)
        detail = {
            "source_id": source_id,
            "source_calendar_sha256": enrich.digest(
                entries[source_id]["source_visit_calendar"]
            ),
        }
        if calendar is None or calendar.unknown_reasons:
            detail.update(
                status="held_unknown_or_invalid",
                unknown_reasons=calendar.unknown_reasons
                if calendar
                else ["Calendar did not validate"],
            )
            require(
                not calendar_eligible(record),
                "unknown calendar passed automatic eligibility",
            )
            totals["held_unknown_records"] += 1
            records.append(detail)
            continue
        positive, short = 0, 0
        day = start
        while day <= end:
            earliest = datetime.combine(day, datetime.min.time(), zone)
            cutoff = earliest + timedelta(days=1) - timedelta(microseconds=1)
            intervals = open_intervals(calendar, earliest, cutoff, zone)
            # Prior overnight sessions are tested on their actual starting day.
            for opens, closes in intervals:
                if opens.date() != day:
                    continue
                totals["source_window_occurrences"] += 1
                if (closes - opens).total_seconds() < 7200:
                    short += 1
                    reject(record, opens, closes, "short_window_rejections")
                    continue
                positive += 1
                latest = closes - timedelta(seconds=7200)
                for arrival in (opens, latest):
                    totals["full_7200_second_acceptance_checks"] += 1
                    try:
                        actual, proof = solve_visit(record, arrival, closes, dwell=7200)
                        if (
                            actual != arrival
                            or proof["dwell_seconds"] != 7200
                            or datetime.fromisoformat(proof["visit_end"]) > closes
                        ):
                            failures.append(
                                {
                                    "source_id": source_id,
                                    "control": "full_dwell_serialization",
                                    "arrival": arrival.isoformat(),
                                }
                            )
                    except VisitCalendarConflict:
                        failures.append(
                            {
                                "source_id": source_id,
                                "control": "positive_window_withheld",
                                "arrival": arrival.isoformat(),
                            }
                        )
                reject(
                    record,
                    latest + timedelta(minutes=1),
                    closes,
                    "latest_start_plus_one_minute_rejections",
                )
            overlaps = any(
                max(opens, earliest) < min(closes, cutoff)
                for opens, closes in intervals
            )
            if not overlaps:
                explicit = day.strftime("%m-%d") in calendar.annual_closures or any(
                    value.date == day and not value.windows
                    for value in calendar.date_overrides
                )
                reject(
                    record,
                    earliest,
                    cutoff,
                    "explicit_closed_date_rejections"
                    if explicit
                    else "no_published_window_date_rejections",
                )
            day += timedelta(days=1)
        detail.update(
            status="has_full_dwell_test_windows"
            if positive
            else "held_no_supported_7200_second_occurrence_in_test_scope",
            full_dwell_occurrences=positive,
            short_occurrences=short,
        )
        totals[
            "records_with_full_dwell_occurrences"
            if positive
            else "held_short_or_out_of_scope_records"
        ] += 1
        records.append(detail)
    return {
        "test_zone": "UTC",
        "zone_role": "Artificial clock-arithmetic test zone only; not a venue timezone or actual arrival-time claim. Source/local-zone DST tests remain separate.",
        "date_scope": {"start": start.isoformat(), "end": end.isoformat()},
        "dwell_seconds": 7200,
        "counts": dict(totals),
        "failures": failures,
        "records": records,
    }


def run(args):
    require(
        not args.output.exists(),
        "proof output already exists; choose a new immutable filename",
    )
    artifact = args.artifact.resolve()
    route_inputs, route_receipts = routes(
        args.routes.resolve(), args.route_root.resolve()
    )
    prepared = enrich.prepare(artifact)
    code = code_receipts()
    conn, version, attestation = connect()
    parent, generation = prepared["parent"]["generation"], prepared["generation"]
    old_pool = repository.chat_crud._get_conn, repository.chat_crud._put_conn
    old_url = repository.settings.DATABASE_URL
    try:
        before = active(conn)
        require(
            before in {parent, generation},
            "proof database has an unrelated active generation",
        )
        if before == generation:
            enrich.rollback(conn, enrich.recovery_receipt(conn, prepared))
        require(
            active(conn) == parent, "cannot select verified local parent before staging"
        )
        started = time.perf_counter()
        staged = enrich.stage(conn, prepared)
        stage_seconds = time.perf_counter() - started
        require(
            active(conn) == parent and enrich.stage(conn, prepared)["existing"],
            "staging changed pointer or failed idempotence",
        )
        prior_rows, prior_entries, _ = snapshot(conn, parent)
        actual_rows, actual_entries, _ = snapshot(conn, generation)
        require(
            enrich._same_rows(prior_rows, prepared["baseline"])
            and enrich._same_rows(actual_rows, prepared["rows"]),
            "actual PostgreSQL source rows differ from source-validated artifact",
        )
        for source_id, previous in prior_entries.items():
            current = actual_entries[source_id]
            require(
                current == previous
                or any(
                    fact.get("entry") == previous and fact.get("generation") == parent
                    for fact in current["source_constraints"]
                ),
                "prior companion facts were not retained",
            )
        frozen = enrich.recovery_receipt(conn, prepared)
        require(
            active(conn) == parent, "freezing a recovery receipt changed the pointer"
        )
        require(
            enrich.activate(conn, prepared)["generation"] == generation
            and enrich.activate(conn, prepared)["generation"] == generation,
            "activation failed idempotence",
        )
        measured_storage = storage(conn, parent, generation)
        require(
            measured_storage["new_row_count"] == len(prepared["additions"]),
            "new-row footprint count differs from actual admitted additions",
        )
        temporal = temporal_contract(actual_rows, actual_entries)
        require(
            not temporal["failures"],
            "stored calendar serialization failed temporal controls",
        )
        expired = next(row for row in actual_rows if "Weaverville" in row["name"])
        record = candidate(expired, actual_entries)
        native_hash = enrich.digest(record)
        zone = ZoneInfo("America/Los_Angeles")
        trip_checks = {
            day: possible_visit(
                record, datetime.fromisoformat(day).replace(hour=9, tzinfo=zone), zone
            )
            for day in ("2026-10-14", "2026-10-21", "2030-07-17")
        }
        require(
            trip_checks
            == {"2026-10-14": True, "2026-10-21": False, "2030-07-17": False},
            "expired source season escaped the trip gate",
        )
        require(
            enrich.digest(record) == native_hash, "trip filtering mutated source facts"
        )
        repository.settings.DATABASE_URL = "isolated-loopback-proof-only"
        repository.chat_crud._get_conn = lambda: conn
        repository.chat_crud._put_conn = lambda _connection: None
        require(
            enrich.rollback(conn, frozen)["generation"] == parent
            and enrich.rollback(conn, frozen)["generation"] == parent,
            "frozen rollback failed idempotence",
        )
        discovery = {"parent": discover(conn, parent, route_inputs)}
        enrich.activate(conn, prepared)
        discovery["candidate"] = discover(conn, generation, route_inputs)
        require(active(conn) == generation, "local candidate was not restored")
        current_code = code_receipts()
        require(
            all(current_code.get(path) == receipt for path, receipt in code.items()),
            "executable source changed during the proof",
        )
        require(
            sha256(artifact.read_bytes())
            == prepared["manifest"]["calendar_artifact_sha256"],
            "source artifact changed during the proof",
        )
        proof = {
            "schema_version": "roadtrips-local-incremental-proof/1",
            "checked_at": datetime.now(UTC).isoformat(),
            "database": DATABASE,
            "server_version_num": version,
            "loopback_client_endpoint_verified": True,
            "server_location_attestation": attestation,
            "production_calls_or_changes": False,
            "saved_trip_tables_accessed": False,
            "artifact_sha256": sha256(artifact.read_bytes()),
            "code_file_sha256s": current_code,
            "retained_routes": route_receipts,
            "parent_generation": parent,
            "generation": generation,
            "initial_generation": before,
            "final_generation": generation,
            "all_parent_raw_rows_and_provenance_preserved": True,
            "inherited_companion_count": len(prior_entries),
            "inherited_companion_facts_preserved": True,
            "stage_idempotent_and_keeps_parent_pointer": True,
            "activation_idempotent": True,
            "frozen_receipt_rollback_twice_and_candidate_restore": True,
            "frozen_recovery_receipt": frozen,
            "stage_seconds": stage_seconds,
            "stage_result": staged,
            "storage": measured_storage,
            "import": prepared["report"],
            "counts": counts(actual_rows, actual_entries),
            "new_rows_counts": counts(prepared["additions"], actual_entries),
            "temporal_contract": temporal,
            "requested_trip_calendar": {
                "provider_id": record["provider_id"],
                "source_record_sha256": native_hash,
                "source_facts_unchanged": True,
                "results": trip_checks,
                "zone_role": "Explicit regression control for this California source; not a live provider-zone verification",
                "sixty_one_expired_before_two_usable_real_sql_regression": "backend/tests/catalog_postgres_tests.py::test_expired_calendars_do_not_consume_paginated_usable_slots",
            },
            "discovery": discovery,
            "measurement_scope": "Actual application repository SELECTs include local transport and deserialization; complete returned provenance and calendar receipts match source-validated stored facts. Structural eligibility is not opening at an actual arrival time, a provider timezone, a joint itinerary, or Neon/production performance.",
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(
                json.dumps(proof, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
            )
        return {
            "report": str(args.output),
            "sha256": sha256(args.output.read_bytes()),
            "rows": len(actual_rows),
            "new_rows": len(prepared["additions"]),
            "candidate_restored": True,
        }
    finally:
        repository.chat_crud._get_conn, repository.chat_crud._put_conn = old_pool
        repository.settings.DATABASE_URL = old_url
        conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--routes", required=True, type=Path)
    parser.add_argument("--route-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    print(json.dumps(run(parser.parse_args()), indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 -- never print raw DSN/connection errors
        raise SystemExit(
            f"Local catalog proof failed ({type(exc).__name__}); no connection details logged"
        ) from None
