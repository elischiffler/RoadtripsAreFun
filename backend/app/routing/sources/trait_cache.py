"""Reusable estimated attraction traits; never caches a traveler's utility score."""

import hashlib
import json
import logging
import os
from contextlib import contextmanager

from psycopg2.extras import Json, RealDictCursor

from app.core.config import settings
from app.crud import chat_crud
from app.routing.profiles import AttributeRatings

VERSION = "attraction-traits-v1"
logger = logging.getLogger(__name__)


def enabled():
    return os.getenv("PLACE_TRAITS_CACHE_ENABLED", "false").lower() == "true"


def context(place):
    """Only place facts that affect traits; exclude persona, trip and opening calendars."""
    return place.model_dump(
        include={
            "provider_id",
            "name",
            "coordinates",
            "address",
            "categories",
            "activities",
            "description",
        }
    )


def key(place):
    # Gateway deployment identity is hashed, never persisted as a credential-bearing URL.
    payload = {"version": VERSION, "place": context(place), "gateway": settings.MENTRO_GATEWAY_URL}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()


@contextmanager
def transaction():
    conn = chat_crud._get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SET LOCAL statement_timeout = 2000")
            cur.execute("SET LOCAL lock_timeout = 1000")
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        chat_crud._put_conn(conn)


def _entry(row):
    return {
        "attribute_ratings": AttributeRatings.model_validate(row["attribute_ratings"]).model_dump(),
        "rated_at": row["rated_at"].isoformat(),
        "provider": row["provider"],
        "rating_version": row["rating_version"],
    }


def get_many(places):
    if not places:
        return {}
    try:
        by_key = {key(place): place.provider_id for place in places}
        with transaction() as cur:
            cur.execute(
                "SELECT * FROM place_attribute_traits WHERE cache_key=ANY(%s) AND expires_at>now()",
                (list(by_key),),
            )
            rows = cur.fetchall()
        result = {}
        for row in rows:
            try:
                result[by_key[row["cache_key"]]] = _entry(row)
            except ValueError:
                continue  # Invalid/incomplete stored JSON is a miss, never a fabricated score.
        return result
    except Exception as exc:
        logger.warning(
            "Place trait cache read failed (%s); using fresh ratings", type(exc).__name__
        )
        return {}


def put_many(entries, provider):
    """Validate all 14 traits; first unexpired writer wins concurrent requests."""
    if not entries or settings.NEON_READ_ONLY:
        return {}
    validated = [
        (place, AttributeRatings.model_validate(ratings).model_dump()) for place, ratings in entries
    ]
    try:
        with transaction() as cur:
            for place, ratings in sorted(validated, key=lambda entry: key(entry[0])):
                cache_key = key(place)
                cur.execute(
                    "SELECT attribute_ratings FROM place_attribute_traits WHERE cache_key=%s FOR UPDATE",
                    (cache_key,),
                )
                previous = cur.fetchone()
                invalid = False
                if previous:
                    try:
                        AttributeRatings.model_validate(previous["attribute_ratings"])
                    except ValueError:
                        invalid = True
                cur.execute(
                    "INSERT INTO place_attribute_traits(cache_key,source_id,rating_version,place_context,"
                    "attribute_ratings,provider) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(cache_key) "
                    "DO UPDATE SET attribute_ratings=EXCLUDED.attribute_ratings,provider=EXCLUDED.provider,"
                    "rated_at=now(),expires_at=now()+interval '90 days' "
                    "WHERE place_attribute_traits.expires_at<=now() OR %s",
                    (
                        cache_key,
                        place.provider_id,
                        VERSION,
                        Json(context(place)),
                        Json(ratings),
                        provider,
                        invalid,
                    ),
                )
        # Re-read the canonical winner so concurrent trips do not keep different fresh estimates.
        return get_many([place for place, _ in validated])
    except Exception as exc:
        logger.warning(
            "Place trait cache write failed (%s); retaining fresh ratings", type(exc).__name__
        )
        return {}
