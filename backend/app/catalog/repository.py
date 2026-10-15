"""Bounded indexed catalog discovery through the application's existing pool."""

import math

from psycopg2.extras import RealDictCursor

from app.catalog.attribution import combine
from app.catalog.identity import identity
from app.core.config import settings
from app.crud import chat_crud


def source_attribution(row):
    source = identity(row["source_id"])[1]
    primary = (
        (row.get("source_catalogs") or {}).get(source, {}).get("attribution", row["attribution"])
    )
    additional = {
        p["source_attribution"]
        for p in row["provenance"]
        if isinstance(p.get("source_attribution"), str)
    }
    return combine([primary, *sorted(additional)])


def nearby(point, categories, radius_miles=5, limit=60):
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
                    SELECT p.*, i.release, i.manifest->>'attribution' AS attribution,
                    i.manifest->'source_catalogs' AS source_catalogs,
                    2*3958.7613*asin(sqrt(least(1.0,
                      power(sin(radians(latitude-%s)/2),2)
                      +cos(radians(%s))*cos(radians(latitude))
                      *power(sin(radians(longitude-%s)/2),2)))) AS distance
                    FROM places_catalog p
                    JOIN places_catalog_active a ON a.generation=p.generation
                    JOIN places_catalog_imports i ON i.generation=p.generation
                    WHERE p.latitude BETWEEN %s AND %s
                      AND ((%s >= -180 AND %s <= 180 AND p.longitude BETWEEN %s AND %s)
                        OR (%s < -180 AND (p.longitude >= %s+360 OR p.longitude <= %s))
                        OR (%s > 180 AND (p.longitude >= %s OR p.longitude <= %s-360)))
                      AND p.categories && %s::text[]
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
                "source_release": (r.get("source_catalogs") or {})
                .get(identity(r["source_id"])[1], {})
                .get("release", r["release"]),
                "source_attribution": source_attribution(r),
                "source_updated_at": r["source_updated_at"],
                "source_provenance": r["provenance"]
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
