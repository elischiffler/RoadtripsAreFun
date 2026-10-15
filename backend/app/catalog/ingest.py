"""Strictly bounded, atomic generation importer. No connection is made for dry runs."""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from psycopg2.extras import Json, execute_values

from app.catalog import boulder, mixed, nps, nps_public, roadside
from app.catalog.normalize import normalize

UPSTREAM_LICENSES = {
    "meta": "CDLA-Permissive-2.0",
    "microsoft": "CDLA-Permissive-2.0",
    "pinmeto": "CDLA-Permissive-2.0",
    "krick": "CDLA-Permissive-2.0",
    "renderseo": "CDLA-Permissive-2.0",
    "dac": "CDLA-Permissive-2.0",
    "brightquery": "CDLA-Permissive-2.0",
    "foursquare": "Apache-2.0",
    "alltheplaces": "CC0-1.0",
}
MAX_ROWS = 50_000
MAX_BYTES = 100 * 1024 * 1024
MAX_CATALOG_BYTES = 256 * 1024 * 1024
MAX_DATABASE_BYTES = 512 * 1024 * 1024


def validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    for field in (
        "release",
        "schema_version",
        "retrieved_at",
        "source_url",
        "sha256",
        "filters",
        "attribution",
        "licenses",
    ):
        if not manifest.get(field):
            raise ValueError(f"manifest missing {field}")
    if len(json.dumps(manifest).encode()) > 32_768:
        raise ValueError("manifest exceeds 32 KiB")
    if manifest["schema_version"] == boulder.SCHEMA:
        if set(manifest["licenses"]) != {"CC0-1.0"}:
            raise ValueError("Boulder requires retained CC0 license evidence")
        validate_license_file(manifest["licenses"]["CC0-1.0"])
        return
    if manifest["schema_version"] == nps.SCHEMA:
        if set(manifest["licenses"]) != {"CC0-1.0", "LicenseRef-US-Government-Work"}:
            raise ValueError("NPS requires archive and government-work rights evidence")
        for evidence in manifest["licenses"].values():
            validate_license_file(evidence)
        return
    if manifest["schema_version"] == mixed.SCHEMA:
        if not isinstance(manifest["licenses"], dict):
            raise ValueError("mixed licenses must map to retained evidence")
        for identifier, evidence in manifest["licenses"].items():
            validate_license_file(evidence)
            if identifier == "Apache-2.0":
                validate_license_file(evidence.get("notice"))
        return
    if manifest["schema_version"] == nps_public.SCHEMA:
        if set(manifest["licenses"]) != {"LicenseRef-US-Government-Work"}:
            raise ValueError("public NPS inputs require retained government-work evidence")
        validate_license_file(manifest["licenses"]["LicenseRef-US-Government-Work"])
        return
    if manifest["schema_version"] == roadside.SCHEMA:
        identifiers = set(manifest["licenses"])
        if not {"CC0-1.0", "LicenseRef-LOC-Margolies-Notice"} <= identifiers or identifiers - {
            "CC0-1.0",
            "LicenseRef-LOC-Margolies-Notice",
            "CDLA-Permissive-2.0",
            "Apache-2.0",
        }:
            raise ValueError("roadside requires reviewed archive and licensed point evidence")
        for identifier, evidence in manifest["licenses"].items():
            validate_license_file(evidence)
            if identifier == "Apache-2.0":
                validate_license_file(evidence.get("notice"))
        return
    release = manifest["release"]
    if not isinstance(release, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}\.\d+", release):
        raise ValueError("invalid pinned release")
    url = urlparse(manifest["source_url"])
    allowed = (url.scheme == "s3" and url.netloc == "overturemaps-us-west-2") or (
        url.scheme == "https"
        and url.netloc
        in (
            "overturemaps-us-west-2.s3.us-west-2.amazonaws.com",
            "overturemaps-us-west-2.s3.amazonaws.com",
        )
    )
    if (
        not allowed
        or not url.path.startswith(f"/release/{release}/theme=places/type=place")
        or url.query
        or url.fragment
    ):
        raise ValueError("source URL must identify the official pinned Places release")
    if not isinstance(manifest["licenses"], dict):
        raise ValueError("licenses must map SPDX identifiers to retained license evidence")
    for identifier, evidence in manifest["licenses"].items():
        validate_license_file(evidence)
        if identifier == "Apache-2.0":
            validate_license_file(evidence.get("notice"))


def validate_license_file(evidence):
    if not isinstance(evidence, dict) or not evidence.get("path") or not evidence.get("sha256"):
        raise ValueError("license/notice requires path and sha256")
    path = Path(evidence["path"])
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[3] / path
    if not path.is_file() or not 1 <= path.stat().st_size <= 1024 * 1024:
        raise ValueError("retained license/notice missing or oversized")
    if hashlib.sha256(path.read_bytes()).hexdigest() != evidence["sha256"]:
        raise ValueError("retained license/notice checksum mismatch")


def provenance_licenses(row):
    """Return required SPDX identifiers, or None for unreviewed upstreams."""
    upstream = {s["dataset"].casefold() for s in row["provenance"]}
    known = upstream & UPSTREAM_LICENSES.keys()
    if not known or upstream - UPSTREAM_LICENSES.keys() - {"overture", "overture-signals"}:
        return None
    signals = [s for s in row["provenance"] if s["dataset"].casefold() == "overture-signals"]
    if any(
        s.get("property") != "/properties/operating_status"
        or s.get("license") != "CDLA-Permissive-2.0"
        for s in signals
    ):
        return None
    return {UPSTREAM_LICENSES[s] for s in known} | ({"CDLA-Permissive-2.0"} if signals else set())


def prepare(path, manifest, *, max_rows=MAX_ROWS, max_bytes=MAX_BYTES):
    validate_manifest(manifest)
    if not 1 <= max_rows <= MAX_ROWS or not 1 <= max_bytes <= MAX_BYTES:
        raise ValueError("import limits exceed hard ceiling")
    if manifest["schema_version"] == boulder.SCHEMA:
        return boulder.prepare(path, manifest, max_rows=max_rows, max_bytes=max_bytes)
    if manifest["schema_version"] == nps.SCHEMA:
        return nps.prepare(path, manifest, max_rows=max_rows, max_bytes=max_bytes)
    if manifest["schema_version"] == mixed.SCHEMA:
        return mixed.prepare(path, manifest, max_rows=max_rows, max_bytes=max_bytes)
    if manifest["schema_version"] == nps_public.SCHEMA:
        return nps_public.prepare(path, manifest, max_rows=max_rows, max_bytes=max_bytes)
    if manifest["schema_version"] == roadside.SCHEMA:
        return roadside.prepare(path, manifest, max_rows=max_rows, max_bytes=max_bytes)
    digest = hashlib.sha256()
    rows = {}
    rejects = Counter()
    scanned = size = 0
    with Path(path).open("rb") as stream:
        while line := stream.readline(min(max_bytes + 1, 1024 * 1024 + 1)):
            size += len(line)
            if size > max_bytes or len(line) > 1024 * 1024:
                raise ValueError("input byte/line ceiling exceeded; pre-extract a bounded file")
            digest.update(line)
            scanned += 1
            if scanned > max_rows:
                raise ValueError("input row ceiling exceeded; pre-extract a bounded file")
            feature = json.loads(line)
            row, reason = normalize(feature)
            if reason:
                rejects[reason] += 1
                continue
            required_licenses = provenance_licenses(row)
            if required_licenses is None:
                rejects["unapproved_provenance"] += 1
                continue
            if required_licenses - manifest["licenses"].keys():
                raise ValueError("manifest lacks upstream license/notice")
            if row["source_id"] in rows:
                if rows[row["source_id"]] != row:
                    raise ValueError("conflicting duplicate source ID")
                rejects["duplicate"] += 1
            rows[row["source_id"]] = row
    if digest.hexdigest() != manifest["sha256"]:
        raise ValueError("input checksum does not match manifest")
    return list(rows.values()), {
        "scanned": scanned,
        "accepted": len(rows),
        "bytes": size,
        "rejects": dict(rejects),
    }


def catalog_size(cur):
    cur.execute(
        "SELECT COALESCE(sum(pg_total_relation_size(c.oid)),0) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND c.relname IN ('places_catalog','places_catalog_imports','places_catalog_active')"
    )
    return int(cur.fetchone()[0])


def stage(conn, path, manifest, *, max_rows=MAX_ROWS, max_bytes=MAX_BYTES, batch_size=250):
    """Validate everything before writing; stage one immutable generation atomically."""
    if not 1 <= batch_size <= 500:
        raise ValueError("batch size must be 1..500")
    rows, report = prepare(path, manifest, max_rows=max_rows, max_bytes=max_bytes)
    if not rows:
        raise ValueError("empty catalog cannot be staged")
    generation = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    with conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='30s'")
            cur.execute("SELECT pg_advisory_xact_lock(827461905)")
            cur.execute(
                "SELECT row_count FROM places_catalog_imports WHERE generation=%s", (generation,)
            )
            existing = cur.fetchone()
            if existing:
                return {**report, "generation": generation, "existing": True}
            cur.execute("SELECT pg_database_size(current_database())")
            if cur.fetchone()[0] >= MAX_DATABASE_BYTES or catalog_size(cur) >= MAX_CATALOG_BYTES:
                raise ValueError("storage ceiling reached before import")
            cur.execute(
                "INSERT INTO places_catalog_imports(generation,release,manifest,row_count) VALUES (%s,%s,%s,%s)",
                (generation, manifest["release"], Json(manifest), len(rows)),
            )
            fields = (
                "source_id",
                "name",
                "latitude",
                "longitude",
                "region",
                "categories",
                "address",
                "url",
                "source_updated_at",
            )
            for offset in range(0, len(rows), batch_size):
                values = [
                    (generation, *(row[k] for k in fields), Json(row["provenance"]))
                    for row in rows[offset : offset + batch_size]
                ]
                execute_values(
                    cur,
                    "INSERT INTO places_catalog(generation,source_id,name,latitude,longitude,region,categories,address,url,source_updated_at,provenance) VALUES %s",
                    values,
                    page_size=batch_size,
                )
            cur.execute("SELECT pg_database_size(current_database())")
            db_bytes = cur.fetchone()[0]
            stored_bytes = catalog_size(cur)
            if db_bytes > MAX_DATABASE_BYTES or stored_bytes > MAX_CATALOG_BYTES:
                raise ValueError("import exceeds storage ceiling; transaction rolled back")
    return {
        **report,
        "generation": generation,
        "catalog_bytes": stored_bytes,
        "database_bytes": db_bytes,
        "existing": False,
    }


def activate(conn, generation):
    """Explicit atomic cutover or rollback to an already validated generation."""
    with conn:
        with conn.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout='5s'")
            cur.execute("SELECT pg_advisory_xact_lock(827461905)")
            cur.execute(
                "SELECT i.row_count, count(p.source_id) FROM places_catalog_imports i LEFT JOIN places_catalog p USING(generation) WHERE i.generation=%s GROUP BY i.row_count",
                (generation,),
            )
            counts = cur.fetchone()
            if not counts or counts[0] == 0 or counts[0] != counts[1]:
                raise ValueError("generation missing, incomplete or empty")
            cur.execute("SELECT generation FROM places_catalog_active WHERE singleton=true")
            previous = cur.fetchone()
            cur.execute(
                "INSERT INTO places_catalog_active(singleton,generation) VALUES(true,%s) ON CONFLICT(singleton) DO UPDATE SET generation=excluded.generation",
                (generation,),
            )
    return {"generation": generation, "previous_generation": previous[0] if previous else None}
