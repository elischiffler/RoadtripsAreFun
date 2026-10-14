"""Opt-in real PostgreSQL tests; only a disposable test database is allowed."""

import os
from pathlib import Path

import psycopg2
import pytest

from app.catalog import ingest, repository
from tests.catalog_ingest_tests import bundle, feature


@pytest.fixture
def connection(monkeypatch):
    dsn = os.environ.get("CATALOG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("CATALOG_TEST_DATABASE_URL must point to isolated PostgreSQL")
    monkeypatch.setattr(repository.settings, "DATABASE_URL", dsn)
    conn = psycopg2.connect(dsn)
    with conn, conn.cursor() as cur:
        cur.execute("SELECT current_database()")
        if cur.fetchone()[0] != "catalog_test":
            pytest.fail("refusing a database not named catalog_test")
        cur.execute(
            "DROP TABLE IF EXISTS places_catalog_active, places_catalog, places_catalog_imports CASCADE"
        )
        cur.execute((Path(__file__).parents[1] / "sql/places_catalog.sql").read_text())
    monkeypatch.setattr(repository.chat_crud, "_get_conn", lambda: conn)
    monkeypatch.setattr(repository.chat_crud, "_put_conn", lambda c: None)
    yield conn
    conn.close()


def test_atomic_stage_activation_closure_refresh_and_rollback(connection, tmp_path):
    path, manifest = bundle(tmp_path, [feature()])
    first = ingest.stage(connection, path, manifest)
    assert first["catalog_bytes"] > 0
    assert repository.nearby([37.8, -122.4], ["daytime"]) == []
    assert ingest.stage(connection, path, manifest)["existing"] is True
    assert ingest.activate(connection, first["generation"])["previous_generation"] is None
    places = repository.nearby([37.8, -122.4], ["daytime"])
    assert places[0]["provider_id"] == "overture:stable-1"
    assert places[0]["source_release"] == manifest["release"]
    assert not repository.nearby([0, 0], ["daytime"])
    assert not repository.nearby([37.8, -122.4], ["food"])
    new = feature(id="stable-2", names={"primary": "New Museum"})
    path, second_manifest = bundle(tmp_path, [feature(operating_status="permanently_closed"), new])
    second_manifest["release"] = "2026-10-01.0"
    second_manifest["source_url"] = second_manifest["source_url"].replace(
        "2026-09-23.1", "2026-10-01.0"
    )
    second = ingest.stage(connection, path, second_manifest)
    assert repository.nearby([37.8, -122.4], ["daytime"])[0]["provider_id"] == "overture:stable-1"
    assert (
        ingest.activate(connection, second["generation"])["previous_generation"]
        == first["generation"]
    )
    assert repository.nearby([37.8, -122.4], ["daytime"])[0]["provider_id"] == "overture:stable-2"
    ingest.activate(connection, first["generation"])
    assert repository.nearby([37.8, -122.4], ["daytime"])[0]["provider_id"] == "overture:stable-1"
    with pytest.raises(ValueError, match="missing"):
        ingest.activate(connection, "missing")


def test_storage_ceiling_rolls_back_generation(connection, tmp_path, monkeypatch):
    path, manifest = bundle(tmp_path, [feature()])
    monkeypatch.setattr(ingest, "MAX_CATALOG_BYTES", 1)
    with pytest.raises(ValueError, match="ceiling"):
        ingest.stage(connection, path, manifest)
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM places_catalog_imports")
        assert cur.fetchone()[0] == 0


def test_exact_distance_and_antimeridian(connection, tmp_path):
    points = []
    for ident, lon, lat in (
        ("near", 179.99, 52),
        ("across", -179.99, 52),
        ("far", -179, 52),
        ("diagonal", 179.89, 52.07),
    ):
        f = feature(id=ident, addresses=[{"country": "US", "region": "AK"}])
        f["geometry"]["coordinates"] = [lon, lat]
        points.append(f)
    path, manifest = bundle(tmp_path, points)
    report = ingest.stage(connection, path, manifest)
    ingest.activate(connection, report["generation"])
    assert [r["provider_id"] for r in repository.nearby([52, 179.99], ["daytime"])] == [
        "overture:near",
        "overture:across",
    ]


def test_post_insert_storage_failure_is_atomic(connection, tmp_path, monkeypatch):
    path, manifest = bundle(tmp_path, [feature()])
    checks = iter([0, ingest.MAX_CATALOG_BYTES + 1])
    monkeypatch.setattr(ingest, "catalog_size", lambda cur: next(checks))
    with pytest.raises(ValueError, match="transaction rolled back"):
        ingest.stage(connection, path, manifest)
    with connection.cursor() as cur:
        cur.execute(
            "SELECT (SELECT count(*) FROM places_catalog_imports), (SELECT count(*) FROM places_catalog)"
        )
        assert cur.fetchone() == (0, 0)
