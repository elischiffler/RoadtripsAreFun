"""Permanent, persona-independent place ratings; never automatically re-estimated."""

import hashlib
import json
import logging
import os
from contextlib import contextmanager

from psycopg2.extras import Json, RealDictCursor

from app.core.config import settings
from app.crud import chat_crud
from app.routing.profiles import AttributeRatings
from app.routing.sources.trait_rubric import VERSION

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
    # Metadata, model and prompt changes must not replace an existing place's ratings.
    payload = {"identity": "permanent-place-traits-v1", "source_id": place.provider_id}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class TraitStoreError(RuntimeError):
    """Persistence must work before a place can be rated or used."""


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
        source_ids = sorted({place.provider_id for place in places})
        with transaction() as cur:
            cur.execute(
                "SELECT DISTINCT ON (source_id) * FROM place_attribute_traits "
                "WHERE source_id=ANY(%s) ORDER BY source_id,rated_at,cache_key",
                (source_ids,),
            )
            rows = cur.fetchall()
        result = {}
        for row in rows:
            # A corrupt stored rating requires explicit repair, never a fresh AI estimate.
            result[row["source_id"]] = _entry(row)
        return result
    except Exception as exc:
        logger.warning(
            "Place trait read failed (%s); refusing automatic re-rating", type(exc).__name__
        )
        raise TraitStoreError(
            "Stored place ratings unavailable; no ratings were regenerated"
        ) from None


def put_many(entries, provider):
    """Insert only unrated source identities; the first persisted rating wins forever."""
    if not entries:
        return {}
    if settings.NEON_READ_ONLY:
        raise TraitStoreError("Place rating storage is read-only")
    validated = [
        (place, AttributeRatings.model_validate(ratings).model_dump()) for place, ratings in entries
    ]
    try:
        with transaction() as cur:
            for place, ratings in sorted(validated, key=lambda entry: entry[0].provider_id):
                cache_key = key(place)
                # Serialize even the first insert, before a source has a row to lock.
                cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    ("place-traits:" + place.provider_id,),
                )
                cur.execute(
                    "SELECT attribute_ratings FROM place_attribute_traits WHERE source_id=%s "
                    "ORDER BY rated_at,cache_key LIMIT 1 FOR UPDATE",
                    (place.provider_id,),
                )
                previous = cur.fetchone()
                if previous:
                    AttributeRatings.model_validate(previous["attribute_ratings"])
                    continue
                cur.execute(
                    "INSERT INTO place_attribute_traits(cache_key,source_id,rating_version,place_context,"
                    "attribute_ratings,provider,expires_at) VALUES(%s,%s,%s,%s,%s,%s,'infinity') "
                    "ON CONFLICT(cache_key) DO NOTHING",
                    (
                        cache_key,
                        place.provider_id,
                        VERSION,
                        Json(context(place)),
                        Json(ratings),
                        provider,
                    ),
                )
        # Re-read the canonical winner so concurrent trips do not keep different fresh estimates.
        return get_many([place for place, _ in validated])
    except Exception as exc:
        logger.warning(
            "Place trait write failed (%s); refusing unpersisted ratings", type(exc).__name__
        )
        raise TraitStoreError(
            "Place ratings could not be stored; no replacement ratings used"
        ) from None
