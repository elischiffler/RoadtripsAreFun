"""Real SQL admission/limit parity on disposable synthetic catalog records."""

import asyncio
import copy

import pytest
from psycopg2.extras import Json, execute_values

from app.catalog import admission, release_holds, repository
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


def test_unknown_hours_has_no_daytime_or_automatic_route_exposure(connection):
    candidate = record()
    candidate["categories"] = ["catalog_browse", "nature"]
    _insert(connection, [candidate])
    assert repository.nearby(POINT, ["daytime"]) == []
    current = repository.current_records([candidate["provider_id"]])[candidate["provider_id"]]
    assert not admission.routing_eligible({"provider_id": candidate["provider_id"], **current})
    assert current["source_provenance"][0] == candidate["source_provenance"][0]


def test_all_audited_holds_are_excluded_before_sql_limits_and_refresh(connection):
    blocked = [record(sid, tier="T3", calendar=True) for sid in sorted(release_holds.SOURCE_IDS)]
    ready = record("catalog-pilot:zz-ready", tier="T3", calendar=True)
    alias = record("catalog-pilot:aa-held-alias", tier="T3", calendar=True)
    alias["source_provenance"].append({"aliases": [None, {}, sorted(release_holds.SOURCE_IDS)[0]]})
    blocked.append(alias)
    for item in [*blocked, ready]:
        item["categories"].append("catalog_browse")
    _insert(connection, [*blocked, ready])
    assert [r["provider_id"] for r in repository.nearby(POINT, ["daytime"], limit=1)] == [
        ready["provider_id"]
    ]
    found = repository.current_records(
        [*sorted(release_holds.SOURCE_IDS), alias["provider_id"], ready["provider_id"]]
    )
    assert list(found) == [ready["provider_id"]]
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM places_catalog WHERE generation='admission-fixture'")
        assert cur.fetchone()[0] == 135  # Historical facts stay intact for review/deduplication.
        cur.execute("SELECT generation FROM places_catalog_active")
        assert cur.fetchone()[0] == "admission-fixture"


def test_all_170_registry_versions_match_independent_postgres_hash_and_admission(connection):
    from app.catalog import hold_resolution as h
    from tests.catalog_routing_hold_resolution_tests import row_for

    rows = [dict(row_for(item), generation="a" * 64) for item in h.RESOLUTIONS]
    with connection.cursor() as cur:
        cur.execute(
            "SELECT p.source_id, md5(("
            + h.payload_sql()
            + ")::text), "
            + release_holds.SQL_ALLOWED
            + ", "
            + admission.sql_predicate()
            + " FROM jsonb_populate_recordset(NULL::public.places_catalog,%s) p "
            + admission.SQL_JOINS,
            (NOW, NOW, Json(rows)),
        )
        result = cur.fetchall()
        assert len(result) == len(rows) == 170
        for item, row, (sid, pg_md5, allowed, routes) in zip(
            h.RESOLUTIONS, rows, result, strict=True
        ):
            assert sid == item["source_id"]
            assert pg_md5 == item["payload_pg_md5"]
            assert allowed and not release_holds.blocked(row)
            assert routes == admission.routing_eligible(row, now_epoch=NOW)


def test_tampered_exact_payloads_fail_sql_and_python_without_global_unhold(connection):
    from app.catalog import hold_resolution as h
    from tests.catalog_routing_hold_resolution_tests import row_for

    rows = []
    for item in h.RESOLUTIONS:
        value = dict(row_for(item), generation="a" * 64)
        value["name"] += " unreviewed change"
        rows.append(value)
    with connection.cursor() as cur:
        cur.execute(
            "SELECT "
            + release_holds.SQL_ALLOWED
            + " FROM jsonb_populate_recordset(NULL::public.places_catalog,%s) p",
            (Json(rows),),
        )
        assert all(allowed is False for (allowed,) in cur.fetchall())
    assert all(release_holds.blocked(row) for row in rows)


def test_current_exact_routing_record_keeps_admission_and_full_identity(connection, monkeypatch):
    from app.catalog import hold_resolution as h
    from app.routing.catalog_calendars import refresh_for_timing
    from app.routing.visit_calendar import calendar_eligible
    from tests.catalog_routing_hold_resolution_tests import row_for

    item = next(
        e
        for e in h.RESOLUTIONS
        if any(
            f.get("catalog_admission", {}).get("tier") == "T3"
            for f in e["approved_payload"]["provenance"]
        )
    )
    row = row_for(item)
    contract = next(f["catalog_admission"] for f in row["provenance"] if "catalog_admission" in f)
    monkeypatch.setattr(admission.time, "time", lambda: contract["reviewed_at_epoch"] + 1)
    with connection, connection.cursor() as cur:
        cur.execute(
            "INSERT INTO places_catalog_imports(generation,release,manifest,row_count) VALUES (%s,%s,%s,1)",
            ("a" * 64, "synthetic-review-projection", Json({"attribution": "Fixture only"})),
        )
        cur.execute(
            "INSERT INTO places_catalog SELECT * FROM jsonb_populate_record(NULL::public.places_catalog,%s)",
            (Json(dict(row, generation="a" * 64)),),
        )
        cur.execute("INSERT INTO places_catalog_active VALUES(true,%s)", ("a" * 64,))
    fresh = repository.current_records([row["source_id"]])[row["source_id"]]
    assert fresh["name"] == row["name"] and fresh["region"] == row["region"]
    assert not release_holds.blocked(fresh) and calendar_eligible(fresh)
    stale = dict(
        fresh,
        name="Old serialized name",
        address="Old address",
        url="https://stale.example",
        type="stop",
    )
    asyncio.run(refresh_for_timing([stale]))
    assert stale["name"] == row["name"] and stale["address"] == row["address"]
    assert calendar_eligible(stale)
    # A companion must never override the exact source calendar pinned in the exception.
    companion = {
        "source_id": row["source_id"],
        "source_visit_calendar": {"schema_version": "roadtrips-source-visit-calendar/1"},
    }
    with connection, connection.cursor() as cur:
        cur.execute(
            "INSERT INTO places_catalog_calendars VALUES(%s,%s,%s)",
            ("a" * 64, row["source_id"], Json(companion)),
        )
    assert repository.current_records([row["source_id"]]) == {}
