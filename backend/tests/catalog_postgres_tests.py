"""Opt-in real PostgreSQL tests; only a disposable test database is allowed."""

import os
from pathlib import Path

import psycopg2
import pytest
from psycopg2.extras import Json, execute_values

from app.catalog import ingest, repository
from tests.catalog_ingest_tests import bundle, feature


def test_automatic_calendar_filter_precedes_the_bounded_sql_limit(connection):
    """More than sixty unknown timed records cannot hide usable nearby places."""
    calendar = {
        "schema_version": "roadtrips-source-visit-calendar/1",
        "weekly_windows": [{"weekdays": [5], "opens": "09:00", "closes": "14:00"}],
        "source_receipts": [{"source_url": "https://operator.example/fixture-hours"}],
    }
    rows = [
        (
            "fixture",
            f"usda-market:{index:05d}",
            f"Unknown timed fixture {index}",
            37.8,
            -122.4,
            "CA",
            ["daytime", "food_destination"],
            Json([]),
        )
        for index in range(61)
    ]
    rows.extend(
        [
            (
                "fixture",
                "usda-market:99999-closed",
                "Closed-only fixture",
                37.8,
                -122.4,
                "CA",
                ["daytime", "food_destination"],
                Json(
                    [
                        {
                            "source_visit_calendar": {
                                **calendar,
                                "weekly_windows": [],
                                "date_overrides": [{"date": "2026-10-17", "windows": []}],
                            }
                        }
                    ]
                ),
            ),
            (
                "fixture",
                "usda-market:99999-ready",
                "Verified-calendar fixture",
                37.8,
                -122.4,
                "CA",
                ["daytime", "food_destination"],
                Json([{"source_visit_calendar": calendar}]),
            ),
            (
                "fixture",
                "zz-outdoor",
                "Outdoor fixture",
                37.8,
                -122.4,
                "CA",
                ["daytime", "nature"],
                Json([]),
            ),
        ]
    )
    with connection, connection.cursor() as cur:
        cur.execute(
            "INSERT INTO places_catalog_imports(generation,release,manifest,row_count) VALUES (%s,%s,%s,%s)",
            ("fixture", "fixture", Json({"attribution": "Controlled test records"}), len(rows)),
        )
        execute_values(
            cur,
            "INSERT INTO places_catalog(generation,source_id,name,latitude,longitude,region,categories,provenance) VALUES %s",
            rows,
        )
        cur.execute("INSERT INTO places_catalog_active VALUES(true,'fixture')")
    assert len(repository.nearby([37.8, -122.4], ["daytime"])) == 60
    found = repository.nearby([37.8, -122.4], ["daytime"], require_visit_calendar=True)
    assert [row["provider_id"] for row in found] == [
        "usda-market:99999-ready",
        "overture:zz-outdoor",
    ]


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
            "DROP TABLE IF EXISTS places_catalog_active, places_catalog_calendars, places_catalog, places_catalog_imports CASCADE"
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


def test_mixed_active_generation_returns_child_release_attribution_and_identity(
    connection, tmp_path, monkeypatch
):
    import json

    from tests.boulder_catalog_tests import bundle as boulder_bundle
    from tests.catalog_extraction_tests import load_script

    ov, bo = tmp_path / "ov", tmp_path / "bo"
    ov.mkdir()
    bo.mkdir()
    a, ma = bundle(ov, [feature()])
    ma["schema_version"] = "roadtrips-overture-places-v1"
    a.with_suffix(a.suffix + ".manifest.json").write_text(json.dumps(ma))
    b, mb = boulder_bundle(bo, monkeypatch)
    b.with_suffix(b.suffix + ".manifest.json").write_text(json.dumps(mb))
    output = tmp_path / "mixed.json"
    load_script("catalog_mix").build([a, b], output)
    manifest = json.loads(output.with_suffix(".json.manifest.json").read_text())
    report = ingest.stage(connection, output, manifest)
    ingest.activate(connection, report["generation"])
    ov_result = repository.nearby([37.8, -122.4], ["daytime"])[0]
    bo_result = repository.nearby([39.997223, -105.309001], ["daytime"])[0]
    assert ov_result["provider_id"] == "overture:stable-1"
    assert bo_result["provider_id"] == "boulder:272"
    for result, child in [(ov_result, ma), (bo_result, mb)]:
        assert result["source_release"] == child["release"]
        assert result["source_attribution"] == child["attribution"]
        assert result["source_provenance"][-1] == {
            "dataset": "Roadtrips active catalog",
            "generation": report["generation"],
            "release": manifest["release"],
        }
