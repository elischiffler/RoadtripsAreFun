"""Permanent trait JSON, first-rating reuse, validation and failure behavior."""

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


def test_place_key_is_stable_across_metadata_and_rating_contract_changes(monkeypatch):
    original = place()
    assert cache.key(original) == cache.key(original.model_copy())
    assert cache.key(original) != cache.key(original.model_copy(update={"provider_id": "other:1"}))
    assert cache.key(original) == cache.key(original.model_copy(update={"coordinates": [41, -74]}))
    assert cache.key(original) == cache.key(place(description="Changed activities"))
    # New opening-hours evidence doesn't change enduring traits or bypass its checks.
    assert cache.key(original) == cache.key(
        original.model_copy(update={"source_release": "new-calendar"})
    )
    monkeypatch.setattr(cache, "VERSION", "attraction-traits-v2")
    new = cache.key(original)
    monkeypatch.setattr(cache, "VERSION", "attraction-traits-v1")
    assert new == cache.key(original)


def test_cache_outage_stops_estimation_and_does_not_accept_unpersisted_ratings(monkeypatch):
    @contextmanager
    def unavailable():
        raise RuntimeError("fixture database unavailable")
        yield

    monkeypatch.setattr(cache, "transaction", unavailable)
    with pytest.raises(cache.TraitStoreError):
        cache.get_many([place()])
    with pytest.raises(cache.TraitStoreError):
        cache.put_many([(place(), traits(0.5))], "fixture")
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


def test_real_database_preserves_first_rating_despite_expiry_metadata_and_prompt_changes(
    real_database, monkeypatch
):
    p = real_database
    assert cache.get_many([p]) == {}
    first = cache.put_many([(p, traits(0.3))], "fixture:first")[p.provider_id]
    assert first["attribute_ratings"] == traits(0.3) and first["rated_at"]
    assert cache.put_many([(p, traits(0.9))], "fixture:second")[p.provider_id] == first
    changed = p.model_copy(update={"description": "Different place facts"})
    assert cache.get_many([changed])[p.provider_id] == first
    # Simulate a legacy context-hashed, expired record. It must still win.
    with cache.transaction() as cur:
        cur.execute(
            "UPDATE place_attribute_traits SET cache_key=%s,expires_at=now()-interval '1 second' WHERE cache_key=%s",
            ("a" * 64, cache.key(p)),
        )
    monkeypatch.setattr(cache, "VERSION", "future-rubric")
    assert cache.get_many([changed])[p.provider_id] == first
    assert cache.put_many([(changed, traits(0.9))], "fixture:refresh")[p.provider_id] == first
    with cache.transaction() as cur:
        cur.execute(
            "SELECT count(*) AS n FROM place_attribute_traits WHERE source_id=%s", (p.provider_id,)
        )
        assert cur.fetchone()["n"] == 1
        cur.execute("DELETE FROM place_attribute_traits WHERE source_id=%s", (p.provider_id,))


def test_real_database_corruption_requires_explicit_repair(real_database, monkeypatch):
    p = real_database
    cache.put_many([(p, traits(0.3))], "fixture:first")
    with cache.transaction() as cur:
        cur.execute(
            "UPDATE place_attribute_traits SET attribute_ratings='{}'::jsonb WHERE cache_key=%s",
            (cache.key(p),),
        )
    with pytest.raises(cache.TraitStoreError):
        cache.get_many([p])
    with pytest.raises(cache.TraitStoreError):
        cache.put_many([(p, traits(0.6))], "fixture:automatic-repair")
    with cache.transaction() as cur:
        cur.execute(
            "SELECT attribute_ratings FROM place_attribute_traits WHERE source_id=%s",
            (p.provider_id,),
        )
        assert cur.fetchone()["attribute_ratings"] == {}
    monkeypatch.setattr(cache.settings, "NEON_READ_ONLY", True)
    with pytest.raises(cache.TraitStoreError):
        cache.put_many([(p, traits(0.7))], "fixture")


def test_real_database_concurrent_first_writers_return_one_permanent_rating(real_database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    barrier = Barrier(2)

    def write(value):
        barrier.wait(timeout=10)
        return cache.put_many([(real_database, traits(value))], f"fixture:{value}")[
            real_database.provider_id
        ]

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(write, [0.2, 0.8]))
    assert first == second
    assert first["attribute_ratings"] in [traits(0.2), traits(0.8)]
    with cache.transaction() as cur:
        cur.execute(
            "SELECT count(*) AS n FROM place_attribute_traits WHERE source_id=%s",
            (real_database.provider_id,),
        )
        assert cur.fetchone()["n"] == 1
