"""Indexed nearby reads and uncapped research snapshots through the existing pool."""

import math
import time
from dataclasses import dataclass

from psycopg2.extras import RealDictCursor

from app.catalog import admission, release_holds
from app.catalog.attribution import combine
from app.catalog.calendar_enrichment import project
from app.catalog.identity import identity
from app.catalog.personas import facts as persona_facts
from app.core.config import settings
from app.crud import chat_crud


def source_attribution(row):
    source = identity(row["source_id"])[1]
    entry = row.get("calendar_enrichment") or {}
    primary_override = entry.get("source_attribution") if entry.get("source_release") else None
    primary = primary_override or (
        (row.get("source_catalogs") or {}).get(source, {}).get("attribution", row["attribution"])
    )
    additional = {
        p["source_attribution"]
        for p in project(row["provenance"], row.get("calendar_enrichment"))
        if isinstance(p.get("source_attribution"), str)
    }
    return combine([primary, *sorted(additional)])


@dataclass(frozen=True)
class CatalogCursor:
    generation: str
    distance: float
    source_id: str
    scanned: int
    total: int


@dataclass(frozen=True)
class CatalogPage:
    records: list[dict]
    next_cursor: CatalogCursor | None


def nearby(
    point,
    categories,
    radius_miles=5,
    limit=60,
    *,
    require_visit_calendar=False,
    browse_mode=False,
    legacy_only=False,
):
    return nearby_page(
        point,
        categories,
        radius_miles,
        limit,
        require_visit_calendar=require_visit_calendar,
        browse_mode=browse_mode,
        legacy_only=legacy_only,
    ).records


def browse_nearby(point, categories=None, radius_miles=5, limit=60):
    """Read explicitly admitted T2/T3 for browsing, never for automatic routing."""
    return nearby(
        point,
        ["catalog_browse"] if categories is None else categories,
        radius_miles,
        limit,
        browse_mode=True,
    )


def current_records(source_ids):
    """Read authoritative facts for one bounded batch from one active generation.

    Saved/client calendars are historical facts, never authority to bypass a
    newer access hold. No place or saved-trip row is modified by this read.
    """
    if (
        not isinstance(source_ids, list)
        or not 1 <= len(source_ids) <= 1000
        or any(not isinstance(sid, str) or not 1 <= len(sid) <= 512 for sid in source_ids)
    ):
        raise ValueError("current catalog identities require a bounded nonempty batch")
    if not (settings.DATABASE_URL or "").strip():
        raise RuntimeError("Places catalog database is not configured")
    conn = chat_crud._get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout='2000ms'")
            cur.execute(
                f"""
                SELECT p.source_id,p.latitude,p.longitude,p.categories,p.provenance,p.generation,p.source_updated_at,
                    e.entry AS calendar_enrichment,i.release,
                    i.manifest->>'attribution' AS attribution,
                    i.manifest->'source_catalogs' AS source_catalogs
                FROM places_catalog p
                JOIN places_catalog_active a ON a.generation=p.generation
                JOIN places_catalog_imports i ON i.generation=p.generation
                LEFT JOIN places_catalog_calendars e
                    ON e.generation=p.generation AND e.source_id=p.source_id
                WHERE p.source_id=ANY(%s::text[]) AND {release_holds.SQL_ALLOWED}
                """,
                (source_ids,),
            )
            rows = cur.fetchall()
        return {
            row["source_id"]: {
                "categories": row["categories"],
                "coordinates": [row["latitude"], row["longitude"]],
                "source_provenance": project(row["provenance"], row["calendar_enrichment"])
                + [
                    {
                        "dataset": "Roadtrips active catalog",
                        "generation": row["generation"],
                        "release": row["release"],
                    }
                ],
                "source_attribution": source_attribution(row),
                "source_updated_at": row["source_updated_at"],
                "source_release": (row["calendar_enrichment"] or {}).get("source_release")
                or (row["source_catalogs"] or {})
                .get(identity(row["source_id"])[1], {})
                .get("release", row["release"]),
            }
            for row in rows
        }
    finally:
        conn.rollback()
        chat_crud._put_conn(conn)


def nearby_page(
    point,
    categories,
    radius_miles=5,
    limit=60,
    *,
    require_visit_calendar=False,
    cursor=None,
    browse_mode=False,
    legacy_only=False,
):
    """Read routing-safe facts, or explicitly admitted browse records.

    Pages are at most sixty rows, ordered by distance and stable source ID.
    A cursor pins the immutable generation, so activation between pages cannot
    mix source snapshots. The provider rejects trip-infeasible calendars before
    accumulating its sixty usable results; exhausted pages consume no quota.
    """
    if len(point) != 2 or any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in point
    ):
        raise ValueError("point requires finite [latitude, longitude]")
    lat, lon = point
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError("invalid coordinates")
    if (
        not isinstance(radius_miles, (int, float))
        or not math.isfinite(radius_miles)
        or not 0 < radius_miles <= 5
    ):
        raise ValueError("radius must be within five miles")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 60:
        raise ValueError("limit must be 1..60")
    if not isinstance(legacy_only, bool) or (legacy_only and browse_mode):
        raise ValueError("legacy_only requires a boolean and cannot enable browse_mode")
    if not isinstance(browse_mode, bool):
        raise ValueError("browse_mode must be a boolean")
    if not isinstance(require_visit_calendar, bool):
        raise ValueError("require_visit_calendar must be a boolean")
    if cursor is not None and not isinstance(cursor, CatalogCursor):
        raise ValueError("invalid catalog cursor")
    if (
        not categories
        or len(categories) > 4
        or set(categories)
        - (
            {"daytime", "food", "culture", "nightlife", "catalog_browse"}
            if browse_mode
            else {"daytime", "food", "culture", "nightlife"}
        )
    ):
        raise ValueError("invalid catalog categories")
    lat_delta = math.degrees(radius_miles / 3958.7613)
    lon_delta = (
        180
        if abs(lat) + lat_delta >= 90
        else math.degrees(
            math.asin(min(1, math.sin(math.radians(lat_delta)) / math.cos(math.radians(lat))))
        )
    )
    low, high = lon - lon_delta, lon + lon_delta
    if not (settings.DATABASE_URL or "").strip():
        raise RuntimeError("Places catalog database is not configured")
    conn = chat_crud._get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout='2000ms'")
            now_epoch = int(time.time())
            cur.execute(
                f"""
                WITH candidates AS (
                    SELECT p.*, e.entry AS calendar_enrichment,
                    i.release, i.row_count AS generation_row_count,
                    i.manifest->>'attribution' AS attribution,
                    i.manifest->'source_catalogs' AS source_catalogs,
                    2*3958.7613*asin(sqrt(least(1.0,
                      power(sin(radians(latitude-%s)/2),2)
                      +cos(radians(%s))*cos(radians(latitude))
                      *power(sin(radians(longitude-%s)/2),2)))) AS distance
                    FROM places_catalog p
                    JOIN places_catalog_imports i ON i.generation=p.generation
                    LEFT JOIN places_catalog_calendars e
                      ON e.generation=p.generation AND e.source_id=p.source_id
                    CROSS JOIN LATERAL (
                      SELECT CASE WHEN e.entry IS NULL THEN p.provenance
                        ELSE jsonb_build_array(e.entry) END AS calendar_provenance
                    ) facts
                    {admission.SQL_JOINS}
                    WHERE p.generation=COALESCE(%s, (SELECT generation FROM places_catalog_active))
                      AND p.latitude BETWEEN %s AND %s
                      AND ((%s >= -180 AND %s <= 180 AND p.longitude BETWEEN %s AND %s)
                        OR (%s < -180 AND (p.longitude >= %s+360 OR p.longitude <= %s))
                        OR (%s > 180 AND (p.longitude >= %s OR p.longitude <= %s-360)))
                      AND p.categories && %s::text[]
                      AND {admission.sql_predicate(browse_mode=browse_mode)}
                      AND {"NOT admission_review.required" if legacy_only else "true"}
                      AND ((NOT %s AND (NOT admission_review.required OR {"true" if browse_mode else "false"})) OR (
                        (NOT admission_review.required
                          AND NOT p.categories && ARRAY['food','culture','nightlife']::text[]
                          AND split_part(p.source_id, ':', 1) NOT IN ('usda-market','wikidata-park')
                          AND NOT jsonb_path_exists(facts.calendar_provenance, '$[*].source_visit_calendar'))
                        OR (
                          jsonb_array_length(jsonb_path_query_array(facts.calendar_provenance, '$[*].source_visit_calendar'))=1
                          AND jsonb_path_exists(facts.calendar_provenance,
                            '$[*].source_visit_calendar ? (@.schema_version == "roadtrips-source-visit-calendar/1" && (!exists(@.unknown_reasons) || @.unknown_reasons.size() == 0) && @.source_receipts.size() > 0 && (@.weekly_windows.size() > 0 || exists(@.date_overrides[*].windows[*])))')
                        )
                      ))
                ) SELECT * FROM candidates WHERE distance<=%s
                  AND (%s::text IS NULL OR (distance,source_id)>(%s,%s))
                  ORDER BY distance, source_id LIMIT %s
                """,
                (
                    lat,
                    lat,
                    lon,
                    cursor.generation if cursor else None,
                    lat - lat_delta,
                    lat + lat_delta,
                    low,
                    high,
                    low,
                    high,
                    low,
                    low,
                    high,
                    high,
                    low,
                    high,
                    categories,
                    now_epoch,
                    now_epoch,
                    require_visit_calendar,
                    radius_miles,
                    cursor.source_id if cursor else None,
                    cursor.distance if cursor else None,
                    cursor.source_id if cursor else None,
                    limit,
                ),
            )
            rows = cur.fetchall()
        scanned = (cursor.scanned if cursor else 0) + len(rows)
        total = cursor.total if cursor else (rows[0]["generation_row_count"] if rows else 0)
        if scanned > total:
            raise RuntimeError("catalog pagination exceeded its immutable generation")
        next_cursor = (
            CatalogCursor(
                rows[-1]["generation"], rows[-1]["distance"], rows[-1]["source_id"], scanned, total
            )
            if len(rows) == limit and scanned < total
            else None
        )
        records = [
            _record(r, (cursor.scanned if cursor else 0) + rank) for rank, r in enumerate(rows)
        ]
        return CatalogPage(records, next_cursor)
    finally:
        conn.rollback()
        chat_crud._put_conn(conn)


def _record(r, rank):
    """Project stored source facts without changing admission or identities."""
    return {
        "provider_id": identity(r["source_id"])[0],
        "name": r["name"],
        "coordinates": [r["latitude"], r["longitude"]],
        "address": r["address"],
        "url": r["url"],
        "categories": r["categories"],
        **persona_facts(r["provenance"]),
        "provider_rank": rank,
        "source": identity(r["source_id"])[1],
        "source_release": (r.get("calendar_enrichment") or {}).get("source_release")
        or (r.get("source_catalogs") or {})
        .get(identity(r["source_id"])[1], {})
        .get("release", r["release"]),
        "source_attribution": source_attribution(r),
        "source_updated_at": r["source_updated_at"],
        "source_provenance": project(r["provenance"], r.get("calendar_enrichment"))
        + (
            [
                {
                    "dataset": "Roadtrips active catalog",
                    "generation": r["generation"],
                    "release": r["release"],
                }
            ]
            if r.get("generation")
            else []
        ),
    }


def routing_snapshot():
    """Read every admitted daytime place from one immutable active generation.

    This is an uncapped research read. Geographic selection happens against the
    continuous route, rather than LIMITed nearby searches. Acquisition holds and
    T3 admission still apply; date/calendar feasibility is a separate assessment.
    """
    if not (settings.DATABASE_URL or "").strip():
        raise RuntimeError("Places catalog database is not configured")
    conn = chat_crud._get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            cur.execute("SET LOCAL statement_timeout='10000ms'")
            cur.execute("SELECT generation FROM places_catalog_active")
            active = cur.fetchone()
            if active is None:
                raise RuntimeError("No active places catalog")
            generation = active["generation"]
            now_epoch = int(time.time())
            cur.execute(
                f"""
                SELECT p.*, e.entry AS calendar_enrichment, i.release,
                    i.manifest->>'attribution' AS attribution,
                    i.manifest->'source_catalogs' AS source_catalogs
                FROM places_catalog p
                JOIN places_catalog_imports i ON i.generation=p.generation
                LEFT JOIN places_catalog_calendars e
                    ON e.generation=p.generation AND e.source_id=p.source_id
                {admission.SQL_JOINS}
                WHERE p.generation=%s AND p.categories && ARRAY['daytime']::text[]
                    AND {admission.sql_predicate()}
                ORDER BY p.source_id
                """,
                (generation, now_epoch, now_epoch),
            )
            rows = cur.fetchall()
        return {
            "generation": generation,
            "records": [_record(row, i) for i, row in enumerate(rows)],
        }
    finally:
        conn.rollback()
        chat_crud._put_conn(conn)
