"""Real SQL admission/limit parity on disposable synthetic catalog records."""

import asyncio
import copy

import pytest
from psycopg2.extras import Json, execute_values

from app.catalog import admission, ingest, release_holds, repository
from app.routing.sources.persona_candidates import LivePlaceProvider
from tests.catalog_admission_tests import NOW, POINT, record
from tests.catalog_postgres_tests import connection as connection


def _insert(connection, records):
    rows = [
        (
            "admission-fixture",
            item["provider_id"],
            item["name"],
            *item["coordinates"],
            "CA",
            item["categories"],
            Json(item.get("source_provenance", [])),
        )
        for item in records
    ]
    with connection, connection.cursor() as cur:
        cur.execute(
            "INSERT INTO places_catalog_imports(generation,release,manifest,row_count) VALUES (%s,%s,%s,%s)",
            (
                "admission-fixture",
                "synthetic-admission-controls",
                Json({"attribution": "Synthetic records, not source-verified attractions"}),
                len(rows),
            ),
        )
        execute_values(
            cur,
            "INSERT INTO places_catalog(generation,source_id,name,latitude,longitude,region,categories,provenance) VALUES %s",
            rows,
        )
        cur.execute("INSERT INTO places_catalog_active VALUES(true,'admission-fixture')")


def test_browse_only_and_bad_timestamps_cannot_consume_routing_sql_slots(connection):
    blocked = [record(f"catalog-pilot:{index:04d}") for index in range(61)]
    for item in blocked:
        # Deliberately incorrect route category is a negative control: even if
        # present, T2 cannot leak or crowd out a usable T3 behind the SQL LIMIT.
        item["categories"].append("catalog_browse")
    invalid = []
    for index, value in enumerate(["not-an-epoch", 10**100, {}, [], True, -1, 1.5]):
        item = record(f"catalog-pilot:bad-{index}", tier="T3", calendar=True)
        item["source_provenance"][0]["catalog_admission"]["expires_at_epoch"] = value
        invalid.append(item)
    for name, value in [("future", NOW + 3600), ("expired", NOW - 3600)]:
        item = record(f"catalog-pilot:bad-{name}", tier="T3", calendar=True)
        contract = item["source_provenance"][0]["catalog_admission"]
        if name == "future":
            contract["reviewed_at_epoch"] = value
            contract["expires_at_epoch"] = value + 3600
        else:
            contract["expires_at_epoch"] = value
        invalid.append(item)
    invalid.extend(
        [
            {**record("catalog-pilot:missing"), "source_provenance": []},
            record("catalog-pilot:missing-calendar", tier="T3"),
        ]
    )
    ready = record("catalog-pilot:zz-ready", tier="T3", calendar=True)
    ready["categories"].append("catalog_browse")
    legacy = {
        **record("usfs:legacy"),
        "source": "usfs",
        "source_provenance": [],
    }
    _insert(connection, [*blocked, *invalid, ready, legacy])
    assert repository.nearby(POINT, ["daytime"], limit=1)[0]["provider_id"] == ready["provider_id"]
    found = repository.nearby(POINT, ["daytime"])
    assert [item["provider_id"] for item in found] == [ready["provider_id"], "usfs:legacy"]
    assert [
        item["provider_id"] for item in repository.nearby(POINT, ["daytime"], legacy_only=True)
    ] == ["usfs:legacy"]
    assert [
        item.provider_id for item in asyncio.run(LivePlaceProvider().attractions_near(POINT))
    ] == [ready["provider_id"], "usfs:legacy"]
    browse = repository.browse_nearby(POINT)
    assert len(browse) == 60
    assert all(admission.browse_eligible(item) for item in browse)
    assert all(item["provider_id"].startswith("catalog-pilot:") for item in browse)
    assert not any(item["provider_id"].startswith("catalog-pilot:bad-") for item in browse)
    with pytest.raises(ValueError, match="categories"):
        repository.nearby(POINT, ["catalog_browse"])
    with pytest.raises(ValueError, match="legacy_only"):
        repository.nearby(POINT, ["daytime"], browse_mode=True, legacy_only=True)


@pytest.mark.parametrize(
    "mutation", ["duplicate", "source", "gates", "unsupported", "missing", "unknown-key"]
)
def test_malformed_admission_is_filtered_by_sql_not_after_limit(connection, mutation):
    bad = record("catalog-pilot:a-bad", tier="T3", calendar=True)
    contract = bad["source_provenance"][0]["catalog_admission"]
    if mutation == "duplicate":
        bad["source_provenance"].append(copy.deepcopy(bad["source_provenance"][0]))
    elif mutation == "source":
        contract["source_id"] = "catalog-pilot:different"
    elif mutation == "gates":
        contract["gates"]["rights"] = "true"
    elif mutation == "unsupported":
        contract["schema_version"] = "unreviewed/999"
    elif mutation == "missing":
        bad["source_provenance"][0] = {"dataset": admission.DATASET}
    else:
        contract["unreviewed_override"] = True
    ready = record("catalog-pilot:z-ready", tier="T3", calendar=True)
    _insert(connection, [bad, ready])
    assert not admission.routing_eligible(bad)
    assert [item["provider_id"] for item in repository.nearby(POINT, ["daytime"], limit=1)] == [
        ready["provider_id"]
    ]
    assert [
        item["provider_id"] for item in repository.browse_nearby(POINT, ["daytime"], limit=1)
    ] == [ready["provider_id"]]


def test_unknown_hours_browse_has_no_daytime_or_automatic_route_exposure(connection):
    candidate = record()
    candidate["categories"] = ["catalog_browse", "nature"]
    _insert(connection, [candidate])
    assert repository.nearby(POINT, ["daytime"]) == []
    assert repository.browse_nearby(POINT)[0]["provider_id"] == candidate["provider_id"]
    current = repository.current_records([candidate["provider_id"]])[candidate["provider_id"]]
    assert not admission.routing_eligible({"provider_id": candidate["provider_id"], **current})
    assert current["source_provenance"][0] == candidate["source_provenance"][0]


def test_all_audited_holds_are_excluded_before_sql_limits_and_activation(connection):
    blocked = [record(sid, tier="T3", calendar=True) for sid in sorted(release_holds.SOURCE_IDS)]
    ready = record("catalog-pilot:zz-ready", tier="T3", calendar=True)
    alias = record("catalog-pilot:aa-held-alias", tier="T3", calendar=True)
    alias["source_provenance"].append({"aliases": [None, {}, sorted(release_holds.SOURCE_IDS)[0]]})
    blocked.append(alias)
    for item in [*blocked, ready]:
        item["categories"].append("catalog_browse")
    _insert(connection, [*blocked, ready])
    for lookup in [repository.nearby, repository.browse_nearby]:
        assert [r["provider_id"] for r in lookup(POINT, ["daytime"], limit=1)] == [
            ready["provider_id"]
        ]
    found = repository.current_records(
        [*sorted(release_holds.SOURCE_IDS), alias["provider_id"], ready["provider_id"]]
    )
    assert list(found) == [ready["provider_id"]]
    with pytest.raises(ValueError, match="release hold"):
        ingest.activate(connection, "admission-fixture")
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM places_catalog WHERE generation='admission-fixture'")
        assert cur.fetchone()[0] == 135  # Historical facts stay intact for review/deduplication.
        cur.execute("SELECT generation FROM places_catalog_active")
        assert cur.fetchone()[0] == "admission-fixture"
