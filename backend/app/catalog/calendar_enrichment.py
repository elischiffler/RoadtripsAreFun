"""Bounded, separately attributed calendars on immutable catalog generations.

Source adapters own factual transformations. This layer verifies their retained
bytes and runtime contracts, preserves every original place field, and stages a
companion generation without changing the active pointer or any saved trip.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from datetime import datetime
from itertools import product
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urlparse

from psycopg2.extras import Json, RealDictCursor, execute_values

from app.catalog import ingest, release_holds
from app.catalog.mixed import distance
from app.routing.visit_calendar import source_calendar

SCHEMA = "roadtrips-catalog-calendar-enrichment/1"
FIELDS = (
    "source_id,name,latitude,longitude,region,categories,address,url,source_updated_at,provenance"
)
EMPTY_SHA256 = hashlib.sha256(b"[]").hexdigest()


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False).encode()
    ).hexdigest()


def rows_digest(rows):
    return hashlib.sha256(
        "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows).encode()
    ).hexdigest()


def _hex(value):
    return isinstance(value, str) and bool(re.fullmatch("[0-9a-f]{64}", value))


def portable_relative(relative):
    """Accept one canonical relative path usable on POSIX and Windows."""
    return (
        isinstance(relative, str)
        and bool(relative)
        and "\\" not in relative
        and not PurePosixPath(relative).is_absolute()
        and not PureWindowsPath(relative).drive
        and not re.search(r'[<>:"|?*\x00-\x1f]', relative)
        and all(
            part not in {".", "..", ""}
            and not part.endswith((".", " "))
            and not re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part, re.I)
            for part in relative.split("/")
        )
    )


class Reader:
    """Read each evidence body once, bounded across the complete new import."""

    def __init__(self, root, max_bytes):
        self.root = Path(root).resolve()
        self.max_bytes = max_bytes
        self.bytes = 0
        self.seen = {}

    def read(self, relative, sha256, *, allow_empty=False):
        if not portable_relative(relative) or not _hex(sha256):
            raise ValueError("evidence requires a portable relative path and SHA-256")
        path = (self.root / relative).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ValueError("evidence is missing or escapes the artifact")
        if path in self.seen:
            body, actual = self.seen[path]
        else:
            size = path.stat().st_size
            if self.bytes + size > self.max_bytes:
                raise ValueError("calendar import evidence exceeds byte ceiling")
            body = path.read_bytes()
            self.bytes += len(body)
            if self.bytes > self.max_bytes:
                raise ValueError("calendar import evidence exceeds byte ceiling")
            actual = hashlib.sha256(body).hexdigest()
            self.seen[path] = body, actual
        if actual != sha256:
            raise ValueError("calendar evidence checksum mismatch")
        if not body and not allow_empty:
            raise ValueError("positive source or rights evidence is empty")
        return body


def _receipt(receipt, reader):
    if not isinstance(receipt, dict):
        raise ValueError("calendar receipt must be an object")
    parsed = urlparse(receipt.get("source_url", ""))
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
        raise ValueError("calendar receipt needs its attributed public source URL")
    try:
        checked = datetime.fromisoformat(receipt["checked_at"].replace("Z", "+00:00"))
        if checked.tzinfo is None:
            raise ValueError("source timestamp has no timezone")
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise ValueError("calendar receipt requires its original aware acquisition time") from exc
    reader.read(receipt.get("evidence_path"), receipt.get("snapshot_sha256"))


def validate_entries(entries, reader):
    if not isinstance(entries, list) or not 1 <= len(entries) <= ingest.MAX_ROWS:
        raise ValueError("calendar entry count exceeds unchanged row ceiling")
    seen = set()
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or set(entry)
            - {
                "source_id",
                "source_visit_calendar",
                "source_constraints",
                "transformation",
                "source_attribution",
                "source_release",
            }
            or not isinstance(entry.get("source_id"), str)
            or not 1 <= len(entry["source_id"]) <= 512
            or entry["source_id"] in seen
            or not isinstance(entry.get("transformation"), dict)
            or not isinstance(entry.get("source_constraints"), list)
            or not entry["source_constraints"]
        ):
            raise ValueError(
                "calendar entries require unique identities and attributed transformation facts"
            )
        seen.add(entry["source_id"])
        if any(
            key in entry and (not isinstance(entry[key], str) or not 1 <= len(entry[key]) <= limit)
            for key, limit in (("source_attribution", 16384), ("source_release", 256))
        ) or ("source_release" in entry and "source_attribution" not in entry):
            raise ValueError("optional source credits/release require bounded nonempty strings")
        calendar = source_calendar({"source_provenance": [entry]})
        if calendar is None or not (
            calendar.weekly_windows
            or any(item.windows for item in calendar.date_overrides)
            or (calendar.date_overrides and calendar.unknown_reasons)
        ):
            raise ValueError("calendar entry has no valid explicit source windows")
        # Holds can remain explicit in a stored calendar; they never pass automatic eligibility.
        for receipt in calendar.source_receipts:
            _receipt(receipt, reader)
        for fact in entry["source_constraints"]:
            if not isinstance(fact, dict) or not fact:
                raise ValueError("source constraints require separately attributed factual objects")
    return entries


def project(provenance, entry):
    """Expose one effective calendar while retaining the superseded source facts."""
    result = copy.deepcopy(provenance)
    if entry is None:
        return result
    for item in result:
        if "source_visit_calendar" in item:
            item["superseded_source_visit_calendar"] = item.pop("source_visit_calendar")
    result.append({"dataset": "Roadtrips attributed calendar enrichment", **copy.deepcopy(entry)})
    return result


def _adapter_entries(value, adapter_root, artifact_root):
    """Rebase adapter evidence paths without changing attributed source facts."""
    if isinstance(value, list):
        return [_adapter_entries(item, adapter_root, artifact_root) for item in value]
    if not isinstance(value, dict):
        return value
    output = {
        key: _adapter_entries(item, adapter_root, artifact_root) for key, item in value.items()
    }
    if "snapshot_sha256" in value:
        keys = [key for key in ("evidence_path", "body_path", "evidence_body_file") if key in value]
        if keys:
            source = (adapter_root / value[keys[0]]).resolve()
            if not source.is_relative_to(artifact_root):
                raise ValueError("adapter calendar evidence escapes the incremental artifact")
            for key in keys:
                output.pop(key)
            output["evidence_path"] = source.relative_to(artifact_root).as_posix()
    return output


def _additions(payload, reader, *, max_rows, baseline=()):
    """Only typed, replayed source adapters can add places to a parent generation."""
    inputs = payload.get("addition_inputs", [])
    if not isinstance(inputs, list) or len(inputs) > 16:
        raise ValueError("incremental additions require a bounded typed source list")
    if not inputs:
        return [], [], [], 0, 0
    from app.catalog import (
        automated_bindings,
        automated_nps,
        cdfw_nature,
        kaggle_ca_markets,
        kaggle_coastal,
        kaggle_cultural,
        kaggle_ny_markets,
        kaggle_ny_markets_more,
        pilot,
        usfs_current,
    )

    adapters = {
        "automated-nps": automated_nps.prepare,
        "cdfw-nature": cdfw_nature.prepare,
        "usfs-current": usfs_current.prepare,
        "kaggle-cultural": kaggle_cultural.prepare,
        "kaggle-ny-markets": kaggle_ny_markets.prepare,
        "kaggle-ca-markets": kaggle_ca_markets.prepare,
        "kaggle-coastal": kaggle_coastal.prepare,
        "kaggle-ny-markets-more": kaggle_ny_markets_more.prepare,
        "reviewed-browse-pilot": pilot.prepare,
    }
    rows, entries, reports, scanned, size = [], [], [], 0, 0
    for item in inputs:
        if not isinstance(item, dict) or item.get("adapter") not in adapters:
            raise ValueError("unreviewed incremental source adapter")
        reader.read(item.get("path"), item.get("sha256"))
        source = reader.root / item["path"]
        added, report = adapters[item["adapter"]](
            source,
            item.get("manifest"),
            max_rows=max_rows - scanned,
            max_bytes=reader.max_bytes - reader.bytes - size,
        )
        if (
            type(report.get("bytes")) is not int
            or type(report.get("scanned")) is not int
            or report["bytes"] <= 0
            or report["scanned"] <= 0
        ):
            raise ValueError("source adapter did not report actual bounded input consumption")
        scanned += report["scanned"]
        size += report["bytes"]
        if scanned > max_rows or reader.bytes + size > reader.max_bytes:
            raise ValueError("incremental source aggregate ceiling exceeded")
        replayed = {row["source_id"]: row for row in added}
        selected = item.get("selected_source_ids")
        if selected is not None:
            if (
                not isinstance(selected, list)
                or any(not isinstance(key, str) for key in selected)
                or len(selected) != len(set(selected))
                or set(selected) - {row["source_id"] for row in added}
            ):
                raise ValueError("selected source identities differ from replayed source additions")
            added = [row for row in added if row["source_id"] in set(selected)]
        rows.extend(added)
        new_entries = _adapter_entries(
            report.get("calendar_entries", []), source.parent, reader.root
        )
        bindings = item.get("calendar_bindings", {})
        if (
            not isinstance(bindings, dict)
            or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in bindings.items()
            )
            or set(bindings) - replayed.keys()
            or len(set(bindings.values())) != len(bindings)
        ):
            raise ValueError("calendar bindings differ from replayed native facilities")
        parent_rows = {row["source_id"]: row for row in baseline}
        if set(bindings.values()) - parent_rows.keys():
            raise ValueError("calendar binding references an unknown parent identity")
        if bindings and (selected is None or set(bindings) & set(selected)):
            raise ValueError("a bound existing facility cannot also be a new addition")
        if bindings and (
            item["adapter"] not in {"automated-nps", "usfs-current"}
            or set(bindings) - {entry["source_id"] for entry in new_entries}
        ):
            raise ValueError("calendar bindings require a replayed automated source calendar")
        filtered = []
        for entry in new_entries:
            sid = entry["source_id"]
            if sid in bindings:
                filtered.append(
                    automated_bindings.bind_calendar(
                        replayed[sid], parent_rows[bindings[sid]], entry
                    )
                )
            elif selected is None or sid in set(selected):
                filtered.append(entry)
        new_entries = filtered
        for entry in new_entries:
            if item.get("manifest", {}).get("attribution"):
                entry["source_attribution"] = item["manifest"]["attribution"]
            if (
                item.get("manifest", {}).get("release")
                and entry["source_id"] not in bindings.values()
            ):
                entry["source_release"] = item["manifest"]["release"]
        entries.extend(new_entries)
        reports.append(
            {
                "adapter": item["adapter"],
                "scanned": report["scanned"],
                "accepted": len(added),
                "bytes": report["bytes"],
            }
        )
    return rows, entries, reports, scanned, size


def _cross_source_arrivals(baseline, additions):
    """A spatial grid holds unresolved new arrivals within 250 m across inputs."""
    if not additions:
        return
    prior = {row["source_id"] for row in baseline}
    buckets, offsets = {}, list(product((-1, 0, 1), repeat=3))
    size = 250 / 6_371_000
    for row in [*baseline, *additions]:
        lat, lon = math.radians(row["latitude"]), math.radians(row["longitude"])
        point = (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))
        cell = tuple(math.floor(value / size) for value in point)
        for offset in offsets:
            for other in buckets.get(tuple(a + b for a, b in zip(cell, offset, strict=True)), []):
                if row["source_id"] in prior and other["source_id"] in prior:
                    continue
                if distance(row, other) < 250:
                    raise ValueError(
                        "incremental sources contain an unresolved shared or nearby arrival"
                    )
        buckets.setdefault(cell, []).append(row)


def prepare(path, *, max_rows=ingest.MAX_ROWS, max_bytes=ingest.MAX_BYTES):
    if not 1 <= max_rows <= ingest.MAX_ROWS or not 1 <= max_bytes <= ingest.MAX_BYTES:
        raise ValueError("calendar import limits exceed unchanged hard ceiling")
    path = Path(path).resolve()
    if not path.is_file() or not 0 < path.stat().st_size <= max_bytes:
        raise ValueError("calendar artifact missing or exceeds byte ceiling")
    raw = path.read_bytes()
    payload = json.loads(raw)
    if payload.get("schema_version") != SCHEMA:
        raise ValueError("unsupported calendar enrichment schema")
    parent = payload.get("parent", {})
    if not all(
        _hex(parent.get(key))
        for key in (
            "generation",
            "manifest_sha256",
            "normalized_rows_sha256",
            "calendar_enrichment_sha256",
        )
    ):
        raise ValueError("calendar import requires its immutable parent fingerprints")
    reader = Reader(path.parent, max_bytes - len(raw))
    baseline = json.loads(reader.read(parent.get("snapshot_path"), parent.get("snapshot_sha256")))
    if (
        not isinstance(baseline, list)
        or not 1 <= len(baseline) <= max_rows
        or parent.get("row_count") != len(baseline)
        or rows_digest(baseline) != parent["normalized_rows_sha256"]
        or len({row["source_id"] for row in baseline}) != len(baseline)
    ):
        raise ValueError("parent catalog snapshot differs from reviewed source rows")
    supplement_scanned = payload.get("source_scanned_rows", 0)
    if type(supplement_scanned) is not int or not 0 <= supplement_scanned <= max_rows - len(
        baseline
    ):
        raise ValueError("supplement source row count exceeds unchanged ceiling")
    for evidence in payload.get("source_inputs", []):
        reader.read(
            evidence.get("evidence_path"), evidence.get("snapshot_sha256"), allow_empty=True
        )
    additions, new_calendars, source_reports, scanned, source_bytes = _additions(
        payload, reader, max_rows=max_rows - len(baseline) - supplement_scanned, baseline=baseline
    )
    rows = [*baseline, *additions]
    if len(rows) > max_rows or len({row["source_id"] for row in rows}) != len(rows):
        raise ValueError(
            "incremental additions duplicate preserved identities or exceed row ceiling"
        )
    _cross_source_arrivals(baseline, additions)
    proposed_entries = [*payload.get("entries", []), *new_calendars]
    if not proposed_entries and additions:
        from app.catalog import admission

        # Browse-only imports deliberately have no invented calendar. This
        # exception is confined to replayed T2 rows in the dedicated adapter;
        # legacy calendar enrichments and routing-ready imports keep their gate.
        browse_only = all(
            item.get("adapter") == "reviewed-browse-pilot"
            for item in payload.get("addition_inputs", [])
        ) and all((admission.admission_details(row) or {}).get("tier") == "T2" for row in additions)
        entries = [] if browse_only else validate_entries(proposed_entries, reader)
    else:
        entries = validate_entries(proposed_entries, reader)
    prior_ids = {row["source_id"] for row in baseline}
    if any(entry.get("source_release") and entry["source_id"] in prior_ids for entry in entries):
        raise ValueError("supplementary calendars cannot replace preserved place source credits")
    if len(entries) > max_rows or set(e["source_id"] for e in entries) - {
        r["source_id"] for r in rows
    }:
        raise ValueError("calendar entries exceed bounds or reference unknown parent identities")
    licenses = payload.get("licenses", [])
    if not isinstance(licenses, list) or not licenses:
        raise ValueError("calendar enrichment requires retained factual reuse evidence")
    for license in licenses:
        reader.read(license.get("evidence_path"), license.get("snapshot_sha256"))
        if not license.get("identifier"):
            raise ValueError("calendar rights evidence requires an identifier")
    if reader.bytes + source_bytes > reader.max_bytes:
        raise ValueError("incremental aggregate evidence exceeds unchanged byte ceiling")
    manifest = {
        "schema_version": SCHEMA,
        "release": payload["release"],
        "attribution": payload["attribution"],
        "parent_generation": parent["generation"],
        "parent_manifest_sha256": parent["manifest_sha256"],
        "parent_normalized_rows_sha256": parent["normalized_rows_sha256"],
        "parent_calendar_enrichment_sha256": parent["calendar_enrichment_sha256"],
        "calendar_artifact_sha256": hashlib.sha256(raw).hexdigest(),
        "calendar_update_sha256": digest(entries),
        "calendar_update_count": len(entries),
        "normalized_rows_sha256": rows_digest(rows),
        "additional_source_catalogs": payload.get("additional_source_catalogs", {}),
        "addition_inputs": payload.get("addition_inputs", []),
        "source_reports": source_reports,
        "licenses": licenses,
    }
    if (
        not isinstance(manifest["release"], str)
        or not manifest["release"]
        or not isinstance(manifest["attribution"], str)
        or not manifest["attribution"]
        or len(json.dumps(manifest).encode()) > 32768
    ):
        raise ValueError("calendar metadata invalid or exceeds unchanged 32 KiB manifest ceiling")
    return {
        "baseline": baseline,
        "rows": rows,
        "additions": additions,
        "entries": entries,
        "parent": parent,
        "manifest": manifest,
        "generation": digest(manifest),
        "report": {
            "rows": len(rows),
            "additions": len(additions),
            "source_scanned_rows": scanned + supplement_scanned + len(baseline),
            "calendar_updates": len(entries),
            "bytes": reader.bytes + source_bytes + len(raw),
            "evidence_files": len(reader.seen),
        },
    }


def _rows(cur, generation):
    cur.execute(
        f'SELECT {FIELDS} FROM places_catalog WHERE generation=%s ORDER BY source_id COLLATE "C"',
        (generation,),
    )
    return [dict(row) for row in cur.fetchall()]


def _entries(cur, generation):
    cur.execute(
        'SELECT entry FROM places_catalog_calendars WHERE generation=%s ORDER BY source_id COLLATE "C"',
        (generation,),
    )
    return [row["entry"] for row in cur.fetchall()]


def _same_rows(left, right):
    return {r["source_id"]: r for r in left} == {r["source_id"]: r for r in right}


def _prepared_guard(prepared):
    parent, metadata = prepared["parent"], prepared["manifest"]
    if (
        digest(metadata) != prepared["generation"]
        or digest(prepared["entries"]) != metadata["calendar_update_sha256"]
        or len(prepared["entries"]) != metadata["calendar_update_count"]
        or rows_digest(prepared["baseline"]) != parent["normalized_rows_sha256"]
        or len(prepared["baseline"]) != parent["row_count"]
        or rows_digest(prepared["rows"]) != metadata["normalized_rows_sha256"]
        or not _same_rows(prepared["rows"], [*prepared["baseline"], *prepared["additions"]])
        or any(
            metadata[manifest_key] != parent[parent_key]
            for manifest_key, parent_key in (
                ("parent_generation", "generation"),
                ("parent_manifest_sha256", "manifest_sha256"),
                ("parent_normalized_rows_sha256", "normalized_rows_sha256"),
                ("parent_calendar_enrichment_sha256", "calendar_enrichment_sha256"),
            )
        )
    ):
        raise ValueError("prepared calendar artifact changed after source verification")


def _expected(cur, prepared):
    """Derive complete expected content from the pinned parent, never stored new metadata."""
    parent = prepared["parent"]
    cur.execute(
        "SELECT release,manifest,row_count FROM places_catalog_imports WHERE generation=%s",
        (parent["generation"],),
    )
    metadata = cur.fetchone()
    if (
        not metadata
        or metadata["row_count"] != len(prepared["baseline"])
        or metadata["release"] != metadata["manifest"].get("release")
        or digest(metadata["manifest"]) != parent["manifest_sha256"]
    ):
        raise ValueError("parent catalog metadata differs from immutable fingerprint")
    inherited = _entries(cur, parent["generation"])
    if digest(inherited) != parent["calendar_enrichment_sha256"]:
        raise ValueError("parent calendar enrichment changed")
    binding_targets = {
        target
        for source in prepared["manifest"]["addition_inputs"]
        for target in source.get("calendar_bindings", {}).values()
    }
    if binding_targets & {entry["source_id"] for entry in inherited}:
        raise ValueError(
            "automated calendar bindings cannot overwrite prior calendar facts or holds"
        )
    entries = {entry["source_id"]: entry for entry in inherited}
    for incoming in prepared["entries"]:
        entry = copy.deepcopy(incoming)
        previous = entries.get(entry["source_id"])
        if previous and previous != incoming:
            if previous.get("source_release") and not entry.get("source_release"):
                entry["source_release"] = previous["source_release"]
            if previous.get("source_attribution"):
                entry["source_attribution"] = " | ".join(
                    dict.fromkeys(
                        credit
                        for credit in (
                            previous["source_attribution"],
                            entry.get("source_attribution"),
                        )
                        if credit
                    )
                )
            entry["source_constraints"].append(
                {
                    "dataset": "Prior immutable calendar enrichment",
                    "generation": parent["generation"],
                    "entry": previous,
                    "scope": "Prior source facts retained separately; current adapter owns explicit source conflict resolution",
                }
            )
        entries[entry["source_id"]] = entry
    entries = [entries[key] for key in sorted(entries)]
    source_catalogs = metadata["manifest"].get("source_catalogs", {})
    if any(
        key in source_catalogs and source_catalogs[key] != value
        for key, value in prepared["manifest"]["additional_source_catalogs"].items()
    ):
        raise ValueError("supplement cannot replace preserved source catalog credits")
    manifest = {
        **prepared["manifest"],
        "calendar_enrichment_sha256": digest(entries),
        "calendar_count": len(entries),
        "source_catalogs": {
            **source_catalogs,
            **prepared["manifest"]["additional_source_catalogs"],
        },
    }
    if len(json.dumps(manifest).encode()) > 32768:
        raise ValueError("calendar metadata exceeds unchanged 32 KiB manifest ceiling")
    return manifest, entries


def _storage(cur):
    cur.execute("SELECT pg_database_size(current_database()) AS bytes")
    database = cur.fetchone()["bytes"]
    cur.execute(
        "SELECT COALESCE(sum(pg_total_relation_size(c.oid)),0) AS bytes FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND c.relname IN ('places_catalog','places_catalog_imports','places_catalog_active','places_catalog_calendars')"
    )
    catalog = int(cur.fetchone()["bytes"])
    if database > ingest.MAX_DATABASE_BYTES or catalog > ingest.MAX_CATALOG_BYTES:
        raise ValueError("calendar import exceeds unchanged storage ceiling")
    return {"database_bytes": database, "catalog_bytes": catalog}


def stage(conn, prepared):
    """Clone a verified baseline and atomically stage an immutable companion."""
    release_holds.reject(prepared["rows"])
    _prepared_guard(prepared)
    parent, generation = prepared["parent"], prepared["generation"]
    with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SET LOCAL statement_timeout='30s'")
        cur.execute("SET LOCAL lock_timeout='5s'")
        cur.execute("SELECT pg_advisory_xact_lock(827461905)")
        cur.execute("SELECT generation FROM places_catalog_active WHERE singleton=true")
        active = cur.fetchone()
        if not active or active["generation"] not in {parent["generation"], generation}:
            raise ValueError("unexpected active calendar parent generation")
        prior = _rows(cur, parent["generation"])
        if not _same_rows(prior, prepared["baseline"]):
            raise ValueError("database parent differs from immutable source snapshot")
        manifest, expected = _expected(cur, prepared)
        cur.execute(
            "SELECT release,manifest,row_count FROM places_catalog_imports WHERE generation=%s",
            (generation,),
        )
        existing = cur.fetchone()
        storage = _storage(cur)
        if existing:
            if (
                existing["manifest"] != manifest
                or existing["release"] != manifest["release"]
                or existing["row_count"] != len(prepared["rows"])
                or not _same_rows(_rows(cur, generation), prepared["rows"])
                or _entries(cur, generation) != expected
            ):
                raise ValueError("immutable calendar generation content differs")
            return {**prepared["report"], **storage, "generation": generation, "existing": True}
        cur.execute(
            "INSERT INTO places_catalog_imports(generation,release,manifest,row_count) VALUES(%s,%s,%s,%s)",
            (generation, manifest["release"], Json(manifest), len(prepared["rows"])),
        )
        cur.execute(
            f"INSERT INTO places_catalog(generation,{FIELDS}) SELECT %s,{FIELDS} FROM places_catalog WHERE generation=%s",
            (generation, parent["generation"]),
        )
        if prepared["additions"]:
            fields = FIELDS.split(",")
            execute_values(
                cur,
                f"INSERT INTO places_catalog(generation,{FIELDS}) VALUES %s",
                [
                    (
                        generation,
                        *(Json(row[key]) if key == "provenance" else row[key] for key in fields),
                    )
                    for row in prepared["additions"]
                ],
                page_size=250,
            )
        execute_values(
            cur,
            "INSERT INTO places_catalog_calendars(generation,source_id,entry) VALUES %s",
            [(generation, e["source_id"], Json(e)) for e in expected],
            page_size=250,
        )
        if (
            not _same_rows(_rows(cur, generation), prepared["rows"])
            or _entries(cur, generation) != expected
        ):
            raise ValueError("calendar staging did not preserve immutable source content")
        return {**prepared["report"], **_storage(cur), "generation": generation, "existing": False}


def activate(conn, prepared, *, rollback=False):
    """Validate both generations and change only the active catalog pointer."""
    release_holds.reject(prepared["baseline"] if rollback else prepared["rows"])
    _prepared_guard(prepared)
    parent, new = prepared["parent"]["generation"], prepared["generation"]
    target = parent if rollback else new
    with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SET LOCAL statement_timeout='5s'")
        cur.execute("SET LOCAL lock_timeout='5s'")
        cur.execute("SELECT pg_advisory_xact_lock(827461905)")
        cur.execute("SELECT generation FROM places_catalog_active WHERE singleton=true FOR UPDATE")
        current = cur.fetchone()
        if not current or current["generation"] not in {parent, new}:
            raise ValueError("unexpected calendar activation transition")
        if not _same_rows(_rows(cur, parent), prepared["baseline"]) or not _same_rows(
            _rows(cur, new), prepared["rows"]
        ):
            raise ValueError("calendar activation changes preserved place rows")
        expected_manifest, expected_entries = _expected(cur, prepared)
        cur.execute(
            "SELECT release,manifest,row_count FROM places_catalog_imports WHERE generation=%s",
            (new,),
        )
        metadata = cur.fetchone()
        if (
            not metadata
            or metadata["row_count"] != len(prepared["rows"])
            or metadata["release"] != expected_manifest["release"]
            or metadata["manifest"] != expected_manifest
            or _entries(cur, new) != expected_entries
        ):
            raise ValueError("calendar generation missing, incomplete or changed")
        _storage(cur)
        cur.execute(
            "UPDATE places_catalog_active SET generation=%s WHERE singleton=true", (target,)
        )
    return {"generation": target, "previous_generation": current["generation"]}


RECOVERY_SCHEMA = "roadtrips-catalog-calendar-recovery/1"


def _snapshot(cur, generation):
    """PostgreSQL-native fingerprints include all immutable rows and companion facts."""
    cur.execute(
        """SELECT generation,row_count,
          md5(jsonb_build_object('manifest',manifest,'release',release,'row_count',row_count)::text) AS metadata_md5,
          (SELECT count(*) FROM places_catalog p WHERE p.generation=i.generation) AS actual_count,
          (SELECT md5(COALESCE(jsonb_agg(to_jsonb(p) ORDER BY p.source_id COLLATE "C"),'[]'::jsonb)::text) FROM places_catalog p WHERE p.generation=i.generation) AS rows_md5,
          (SELECT count(*) FROM places_catalog_calendars c WHERE c.generation=i.generation) AS calendar_count,
          (SELECT md5(COALESCE(jsonb_agg(c.entry ORDER BY c.source_id COLLATE "C"),'[]'::jsonb)::text) FROM places_catalog_calendars c WHERE c.generation=i.generation) AS calendars_md5
        FROM places_catalog_imports i WHERE generation=%s AND release=manifest->>'release'""",
        (generation,),
    )
    row = cur.fetchone()
    if not row or row["actual_count"] != row["row_count"]:
        raise ValueError("recovery generation is incomplete or metadata changed")
    return {key: value for key, value in row.items() if key != "actual_count"}


def validate_recovery_receipt(receipt):
    """Only bounded, independently reviewable fingerprints can authorize recovery."""
    keys = {
        "generation",
        "row_count",
        "metadata_md5",
        "rows_md5",
        "calendar_count",
        "calendars_md5",
    }
    if (
        not isinstance(receipt, dict)
        or set(receipt) != {"schema_version", "parent", "candidate"}
        or receipt["schema_version"] != RECOVERY_SCHEMA
    ):
        raise ValueError("invalid frozen calendar recovery receipt")
    for name in ("parent", "candidate"):
        item = receipt[name]
        if (
            not isinstance(item, dict)
            or set(item) != keys
            or not _hex(item["generation"])
            or type(item["row_count"]) is not int
            or not 0 < item["row_count"] <= ingest.MAX_ROWS
            or type(item["calendar_count"]) is not int
            or not 0 <= item["calendar_count"] <= item["row_count"]
            or any(
                not isinstance(item[key], str) or not re.fullmatch("[0-9a-f]{32}", item[key])
                for key in ("metadata_md5", "rows_md5", "calendars_md5")
            )
        ):
            raise ValueError("invalid bounded recovery generation fingerprint")
    if (
        receipt["parent"]["generation"] == receipt["candidate"]["generation"]
        or receipt["parent"]["row_count"] > receipt["candidate"]["row_count"]
    ):
        raise ValueError("invalid recovery parent relationship")
    return receipt


def recovery_receipt(conn, prepared):
    """Freeze recovery only after current source validation and exact staged-content checks.

    The reviewed receipt later restores the prior pointer without re-admitting any
    data, re-fetching sources, or depending on their admission freshness clock.
    """
    _prepared_guard(prepared)
    parent, candidate = prepared["parent"]["generation"], prepared["generation"]
    with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SET LOCAL statement_timeout='5s'")
        cur.execute("SELECT pg_advisory_xact_lock(827461905)")
        expected_manifest, expected_entries = _expected(cur, prepared)
        cur.execute("SELECT manifest FROM places_catalog_imports WHERE generation=%s", (candidate,))
        metadata = cur.fetchone()
        if (
            not metadata
            or metadata["manifest"] != expected_manifest
            or not _same_rows(_rows(cur, parent), prepared["baseline"])
            or not _same_rows(_rows(cur, candidate), prepared["rows"])
            or _entries(cur, candidate) != expected_entries
        ):
            raise ValueError("cannot freeze changed or incomplete recovery generations")
        receipt = {
            "schema_version": RECOVERY_SCHEMA,
            "parent": _snapshot(cur, parent),
            "candidate": _snapshot(cur, candidate),
        }
    return validate_recovery_receipt(receipt)


def rollback(conn, receipt):
    """Restore the verified prior pointer; source admission clocks cannot block recovery."""
    validate_recovery_receipt(receipt)
    parent, candidate = receipt["parent"]["generation"], receipt["candidate"]["generation"]
    with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SET LOCAL statement_timeout='5s'")
        cur.execute("SET LOCAL lock_timeout='5s'")
        cur.execute("SELECT pg_advisory_xact_lock(827461905)")
        cur.execute("SHOW server_version_num")
        if int(cur.fetchone()["server_version_num"]) // 10000 != 18:
            raise ValueError("PostgreSQL 18 required for frozen recovery fingerprints")
        cur.execute("SELECT generation FROM places_catalog_active WHERE singleton=true FOR UPDATE")
        current = cur.fetchone()
        if not current or current["generation"] not in {parent, candidate}:
            raise ValueError("unexpected calendar recovery transition")
        release_holds.check_generation(cur, parent)
        for name in ("parent", "candidate"):
            if _snapshot(cur, receipt[name]["generation"]) != receipt[name]:
                raise ValueError("recovery generation content changed")
        cur.execute(
            f"SELECT {FIELDS} FROM places_catalog WHERE generation=%s EXCEPT SELECT {FIELDS} FROM places_catalog WHERE generation=%s LIMIT 1",
            (parent, candidate),
        )
        if cur.fetchone():
            raise ValueError("recovery candidate did not preserve all parent source facts")
        cur.execute(
            "UPDATE places_catalog_active SET generation=%s WHERE singleton=true", (parent,)
        )
    return {"generation": parent, "previous_generation": current["generation"]}
