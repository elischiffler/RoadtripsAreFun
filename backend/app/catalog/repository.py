"""Bounded indexed catalog discovery through the application's existing pool."""

import math

from psycopg2.extras import RealDictCursor

from app.catalog.attribution import combine
from app.catalog.calendar_enrichment import project
from app.catalog.identity import identity
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


def nearby(point, categories, radius_miles=5, limit=60, *, require_visit_calendar=False):
    """Read bounded source facts, optionally prefiltering automatic visit candidates.

    Calendar structure/unknown flags are filtered before the SQL result limit so
    unusable timed records cannot consume every slot. Full Python calendar
    validation and chosen-time constraints remain authoritative afterward.
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
    if not isinstance(require_visit_calendar, bool):
        raise ValueError("require_visit_calendar must be a boolean")
    if (
        not categories
        or len(categories) > 4
        or set(categories) - {"daytime", "food", "culture", "nightlife"}
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
            cur.execute(
                """
                WITH candidates AS (
                    SELECT p.*, e.entry AS calendar_enrichment,
                    i.release, i.manifest->>'attribution' AS attribution,
                    i.manifest->'source_catalogs' AS source_catalogs,
                    2*3958.7613*asin(sqrt(least(1.0,
                      power(sin(radians(latitude-%s)/2),2)
                      +cos(radians(%s))*cos(radians(latitude))
                      *power(sin(radians(longitude-%s)/2),2)))) AS distance
                    FROM places_catalog p
                    JOIN places_catalog_active a ON a.generation=p.generation
                    JOIN places_catalog_imports i ON i.generation=p.generation
                    LEFT JOIN places_catalog_calendars e
                      ON e.generation=p.generation AND e.source_id=p.source_id
                    CROSS JOIN LATERAL (
                      SELECT CASE WHEN e.entry IS NULL THEN p.provenance
                        ELSE jsonb_build_array(e.entry) END AS calendar_provenance
                    ) facts
                    WHERE p.latitude BETWEEN %s AND %s
                      AND ((%s >= -180 AND %s <= 180 AND p.longitude BETWEEN %s AND %s)
                        OR (%s < -180 AND (p.longitude >= %s+360 OR p.longitude <= %s))
                        OR (%s > 180 AND (p.longitude >= %s OR p.longitude <= %s-360)))
                      AND p.categories && %s::text[]
                      AND (NOT %s OR (
                        (NOT p.categories && ARRAY['food','culture','nightlife']::text[]
                          AND split_part(p.source_id, ':', 1) NOT IN ('usda-market','wikidata-park')
                          AND NOT jsonb_path_exists(facts.calendar_provenance, '$[*].source_visit_calendar'))
                        OR (
                          jsonb_array_length(jsonb_path_query_array(facts.calendar_provenance, '$[*].source_visit_calendar'))=1
                          AND jsonb_path_exists(facts.calendar_provenance,
                            '$[*].source_visit_calendar ? (@.schema_version == "roadtrips-source-visit-calendar/1" && (!exists(@.unknown_reasons) || @.unknown_reasons.size() == 0) && @.source_receipts.size() > 0 && (@.weekly_windows.size() > 0 || exists(@.date_overrides[*].windows[*])))')
                        )
                      ))
                ) SELECT * FROM candidates WHERE distance<=%s
                  ORDER BY distance, source_id LIMIT %s
                """,
                (
                    lat,
                    lat,
                    lon,
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
                    require_visit_calendar,
                    radius_miles,
                    limit,
                ),
            )
            rows = cur.fetchall()
        return [
            {
                "provider_id": identity(r["source_id"])[0],
                "name": r["name"],
                "coordinates": [r["latitude"], r["longitude"]],
                "address": r["address"],
                "url": r["url"],
                "categories": r["categories"],
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
            for rank, r in enumerate(rows)
        ]
    finally:
        conn.rollback()
        chat_crud._put_conn(conn)
