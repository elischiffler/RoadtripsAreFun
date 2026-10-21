"""Durable trait JSON, freshness, validation and failure behavior."""

import os
from contextlib import contextmanager
from pathlib import Path

import psycopg2
import pytest

from app.agent.persona import ATTRIBUTE_KEYS
from app.routing.sources import persona_candidates as source
from app.routing.sources import trait_cache as cache


def place(**change):
    return source.VerifiedPlace(
        provider_id="overture:trait-test", name="Test Park", coordinates=[40, -74], **change
    )


def traits(value):
    return dict.fromkeys(ATTRIBUTE_KEYS, value)


def test_place_key_uses_identity_relevant_facts_and_rating_contract(monkeypatch):
    original = place()
    assert cache.key(original) == cache.key(original.model_copy())
    assert cache.key(original) != cache.key(original.model_copy(update={"provider_id": "other:1"}))
    assert cache.key(original) != cache.key(original.model_copy(update={"coordinates": [41, -74]}))
    assert cache.key(original) != cache.key(place(description="Changed activities"))
    # New opening-hours evidence doesn't change enduring traits or bypass its checks.
    assert cache.key(original) == cache.key(
        original.model_copy(update={"source_release": "new-calendar"})
    )
    monkeypatch.setattr(cache, "VERSION", "attraction-traits-v2")
    new = cache.key(original)
    monkeypatch.setattr(cache, "VERSION", "attraction-traits-v1")
    assert new != cache.key(original)


def test_cache_outage_is_a_miss_and_does_not_lose_fresh_estimates(monkeypatch):
    @contextmanager
    def unavailable():
        raise RuntimeError("fixture database unavailable")
        yield

    monkeypatch.setattr(cache, "transaction", unavailable)
    assert cache.get_many([place()]) == {}
    assert cache.put_many([(place(), traits(0.5))], "fixture") == {}
    with pytest.raises(ValueError):
        cache.put_many([(place(), {"nature": 0.9})], "fixture")


@pytest.fixture
def real_database(monkeypatch):
    url = os.getenv("RESEARCH_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set RESEARCH_TEST_DATABASE_URL to a disposable PostgreSQL database")
    monkeypatch.setattr(cache.settings, "NEON_READ_ONLY", False)
    monkeypatch.setattr(cache.chat_crud, "_get_conn", lambda: psycopg2.connect(url))
    monkeypatch.setattr(cache.chat_crud, "_put_conn", lambda conn: conn.close())
    with psycopg2.connect(url) as conn:
        with conn.cursor() as cur:
            ddl = (
                Path(__file__).resolve().parents[2] / "sql/place_attribute_traits.sql"
            ).read_text()
            cur.execute(ddl)
            cur.execute(ddl)
    from uuid import uuid4

    return place().model_copy(update={"provider_id": f"fixture:{uuid4()}"})


def test_real_database_json_reuse_first_writer_expiry_and_invalid_data(real_database, monkeypatch):
    p = real_database
    assert cache.get_many([p]) == {}
    first = cache.put_many([(p, traits(0.3))], "fixture:first")[p.provider_id]
    assert first["attribute_ratings"] == traits(0.3) and first["rated_at"]
    assert cache.put_many([(p, traits(0.9))], "fixture:second")[p.provider_id] == first
    assert cache.get_many([p.model_copy(update={"description": "Different place facts"})]) == {}
    with cache.transaction() as cur:
        cur.execute(
            "UPDATE place_attribute_traits SET expires_at=now()-interval '1 second' WHERE cache_key=%s",
            (cache.key(p),),
        )
    assert cache.get_many([p]) == {}
    refreshed = cache.put_many([(p, traits(0.9))], "fixture:refresh")[p.provider_id]
    assert (
        refreshed["attribute_ratings"] == traits(0.9) and refreshed["provider"] == "fixture:refresh"
    )
    with cache.transaction() as cur:
        cur.execute(
            "UPDATE place_attribute_traits SET attribute_ratings='{}'::jsonb WHERE cache_key=%s",
            (cache.key(p),),
        )
    assert cache.get_many([p]) == {}
    assert cache.put_many([(p, traits(0.6))], "fixture:repair")[p.provider_id][
        "attribute_ratings"
    ] == traits(0.6)
    monkeypatch.setattr(cache.settings, "NEON_READ_ONLY", True)
    assert cache.put_many([(p, traits(0.7))], "fixture") == {}
