"""Exact-row exceptions never turn a historical identity into a global unhold.

All facts are synthetic. Optional PostgreSQL checks perform SELECTs only against
an explicitly selected disposable catalog_test; no source or provider requests.
"""

import copy
import hashlib
import json
import os
from datetime import UTC, datetime

import pytest

from app.catalog import browse_quarantine
from app.catalog import hold_resolution as h
from tests.catalog_admission_tests import marker

SID = sorted(h.ORIGINAL_HELD_IDS)[0]
ALIAS = sorted(h.ORIGINAL_HELD_IDS)[1]


def payload():
    return browse_quarantine.apply(
        {
            "source_id": SID,
            "name": "Synthetic reviewed visitor center",
            "latitude": 37.8,
            "longitude": -122.4,
            "region": "CA",
            "categories": ["culture", "museum"],
            "address": None,
            "url": "https://operator.example/synthetic",
            "source_updated_at": None,
            "provenance": [
                marker(SID),
                {"aliases": [SID, ALIAS], "synthetic_boolean": False},
                {
                    "public_visit_evidence": [
                        {
                            "source_url": "https://operator.example/synthetic",
                            "snapshot_sha256": "1" * 64,
                            "checked_at": "2026-11-02T00:00:00Z",
                        }
                    ]
                },
            ],
        }
    )


def entry(row=None, pg_md5="0" * 32):
    row = payload() if row is None else row
    ids = sorted(h._held_ids(row))
    sha = h.payload_sha256(row)
    return {
        "source_id": row["source_id"],
        "resolved_held_ids": ids,
        "approved_payload": copy.deepcopy(row),
        "payload_sha256": sha,
        "payload_pg_md5": pg_md5,
        "marker": {
            "dataset": h.DATASET,
            "source_hold_resolution": {
                "schema_version": h.MARKER_SCHEMA,
                "source_id": row["source_id"],
                "region": row["region"],
                "payload_sha256": sha,
                "resolved_held_ids": ids,
            },
        },
        "review": {
            "reviewer": "Synthetic test reviewer",
            "reviewed_at": datetime.now(UTC).isoformat(),
            "admission_clock_renewed": False,
            "original_cause_resolution": {
                sid: {
                    "cause": "Synthetic missing policy proof",
                    "resolution": "Synthetic affirmative permitted-source proof, not a real admission",
                }
                for sid in ids
            },
        },
    }


def registry(tmp_path, entries):
    raw = json.dumps(
        {"schema_version": h.SCHEMA, "count": len(entries), "entries": entries}
    ).encode()
    path = tmp_path / "registry.json"
    path.write_bytes(raw)
    return path, hashlib.sha256(raw).hexdigest()


def row_for(item):
    row = copy.deepcopy(item["approved_payload"])
    row["provenance"].append(copy.deepcopy(item["marker"]))
    return row


def test_shipped_registry_matches_pin_and_all_133_bare_identities_stay_held():
    from pathlib import Path

    pinned = h.load_registry(
        Path(h.__file__).with_name("source_hold_resolutions.json"), h.REGISTRY_SHA256
    )
    assert h.RESOLUTIONS == pinned
    assert h.SQL_RESOLVED == h.sql_resolved(pinned)
    assert len(h.ORIGINAL_HELD_IDS) == 133
    assert all(not h.resolved(sid, [sid]) for sid in h.ORIGINAL_HELD_IDS)


def test_explicit_empty_registry_is_fail_closed(tmp_path, monkeypatch):
    path, sha = registry(tmp_path, [])
    empty = h.load_registry(path, sha)
    assert empty == () and h.sql_resolved(empty) == "FALSE"
    monkeypatch.setattr(h, "RESOLUTIONS", empty)
    assert not h.resolved(row_for(entry()), [SID, ALIAS])


def test_pinned_registry_accepts_append_only_versions_but_not_duplicate_version(tmp_path):
    first = entry()
    second_row = payload()
    second_row["name"] += " revised"
    second = entry(second_row)
    path, sha = registry(tmp_path, [first, second])
    assert len(h.load_registry(path, sha)) == 2
    path, sha = registry(tmp_path, [first, first])
    with pytest.raises(RuntimeError, match="duplicate source/payload"):
        h.load_registry(path, sha)


def test_exact_row_and_every_held_alias_required(monkeypatch):
    item = entry()
    monkeypatch.setattr(h, "RESOLUTIONS", (item,))
    row = row_for(item)
    assert h.resolved(row, [SID, ALIAS])
    assert not h.resolved(row, [SID])
    assert not h.resolved(row, [SID, ALIAS, "not-held"])
    assert not h.resolved(row, SID)
    assert not h.resolved(item["approved_payload"], [SID, ALIAS])
    assert not h.resolved(SID, [SID])


@pytest.mark.parametrize(
    "change",
    [
        lambda row: row.update(name="Another site"),
        lambda row: row.update(latitude=38.0),
        lambda row: row.update(region="NV"),
        lambda row: row.update(url="https://other.example"),
        lambda row: row["categories"].append("culture"),
        lambda row: row["provenance"][1].update(synthetic_boolean=0),
        lambda row: row["provenance"][0]["catalog_admission"].update(expires_at_epoch=9999999999),
        lambda row: row["provenance"].append(copy.deepcopy(row["provenance"][-1])),
        lambda row: row["provenance"][-1]["source_hold_resolution"].update(resolved_held_ids=[SID]),
        lambda row: row["provenance"][-2]["source_visit_calendar"].update(weekly_windows=[{}]),
        lambda row: row.update(extra_unreviewed="untrusted"),
        lambda row: row.pop("name"),
        lambda row: row.pop("address"),
    ],
)
def test_payload_marker_or_clock_drift_fails_closed(monkeypatch, change):
    item = entry()
    monkeypatch.setattr(h, "RESOLUTIONS", (item,))
    row = row_for(item)
    change(row)
    assert not h.resolved(row, [SID, ALIAS])


def test_documented_runtime_projection_is_checked_without_restoring_missing_facts(monkeypatch):
    item = entry()
    monkeypatch.setattr(h, "RESOLUTIONS", (item,))
    canonical = row_for(item)
    runtime = {
        key: value
        for key, value in canonical.items()
        if key not in {"source_id", "latitude", "longitude", "region", "provenance"}
    }
    runtime.update(
        provider_id=SID,
        source="catalog-pilot",
        coordinates=[37.8, -122.4],
        source_provenance=canonical["provenance"]
        + [{"dataset": "Roadtrips active catalog", "generation": "a" * 64, "release": "synthetic"}],
    )
    assert h.resolved(runtime, [SID, ALIAS])
    runtime["provider_id"] = "overture:" + SID
    runtime["source"] = "overture"
    assert h.resolved(runtime, [SID, ALIAS])
    runtime["source_provenance"][-1]["unrecognized"] = True
    assert not h.resolved(runtime, [SID, ALIAS])
    runtime["source_provenance"].pop()
    runtime.pop("url")
    assert not h.resolved(runtime, [SID, ALIAS])


@pytest.mark.parametrize(
    "change",
    [
        lambda item: item.update(payload_sha256="f" * 64),
        lambda item: item.update(payload_pg_md5="not-a-hash"),
        lambda item: item.update(resolved_held_ids=[SID]),
        lambda item: item["review"].update(admission_clock_renewed=True),
        lambda item: item["review"].update(reviewed_at="2026-11-02"),
        lambda item: item["review"].update(reviewed_at="2999-01-01T00:00:00Z"),
        lambda item: item["review"].update(reviewer=" "),
        lambda item: item["review"]["original_cause_resolution"].pop(ALIAS),
        lambda item: item["marker"]["source_hold_resolution"].update(region="NV"),
        lambda item: item["approved_payload"]["categories"].append("daytime"),
        lambda item: item["approved_payload"]["provenance"][0]["catalog_admission"].update(
            tier="T3"
        ),
        lambda item: item["approved_payload"].update(latitude=False),
        lambda item: item["approved_payload"]["provenance"][-1]["source_visit_calendar"].update(
            unknown_reasons=[]
        ),
    ],
)
def test_invalid_registry_reviews_and_unsafe_payloads_rejected(tmp_path, change):
    item = entry()
    change(item)
    path, sha = registry(tmp_path, [item])
    with pytest.raises(RuntimeError):
        h.load_registry(path, sha)


def test_corruption_duplicate_keys_and_sql_identifiers_fail_closed(tmp_path):
    path, sha = registry(tmp_path, [])
    with pytest.raises(RuntimeError, match="byte pin"):
        h.load_registry(path, "f" * 64)
    raw = b'{"schema_version":"x","schema_version":"y","count":0,"entries":[]}'
    path.write_bytes(raw)
    with pytest.raises(RuntimeError, match="duplicate JSON"):
        h.load_registry(path, hashlib.sha256(raw).hexdigest())
    assert h.sql_resolved(()) == "FALSE"
    with pytest.raises(ValueError, match="literal identifier"):
        h.payload_sql("p; DROP TABLE x")


def test_postgres_signature_parity_and_companion_override_exclusion(monkeypatch):
    dsn = os.environ.get("CATALOG_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("explicit disposable PostgreSQL unavailable")
    import psycopg2
    from psycopg2.extras import Json

    conn = psycopg2.connect(dsn)
    conn.set_session(readonly=True)
    try:
        with conn, conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            assert cur.fetchone()[0] == "catalog_test"
            item = entry()
            row = row_for(item)
            row["generation"] = "d" * 64
            cur.execute(
                "SELECT md5(("
                + h.payload_sql()
                + ")::text) FROM jsonb_populate_record(NULL::public.places_catalog,%s) p",
                (Json(row),),
            )
            item["payload_pg_md5"] = cur.fetchone()[0]
            monkeypatch.setattr(h, "RESOLUTIONS", (item,))
            expression = h.sql_resolved((item,))

            def sql_accepts(value):
                cur.execute(
                    "SELECT "
                    + expression
                    + " FROM jsonb_populate_record(NULL::public.places_catalog,%s) p",
                    (Json(value),),
                )
                return cur.fetchone()[0]

            assert sql_accepts(row) and h.resolved(row, [SID, ALIAS])
            for index, change in enumerate(
                (
                    lambda value: value["provenance"][1].update(synthetic_boolean=0),
                    lambda value: value.update(name="Changed"),
                    lambda value: value["categories"].append("culture"),
                    lambda value: value["provenance"].append(
                        copy.deepcopy(value["provenance"][-1])
                    ),
                    lambda value: value["provenance"][-2]["source_visit_calendar"].update(
                        weekly_windows=[{}]
                    ),
                )
            ):
                drift = copy.deepcopy(row)
                change(drift)
                assert not sql_accepts(drift) and not h.resolved(drift, [SID, ALIAS]), index
            # Point the synthetic identity at an existing calendar key without
            # reading its body. Hash a separately approved payload for this
            # negative control; no test creates or changes any database record.
            cur.execute("SELECT generation,source_id FROM public.places_catalog_calendars LIMIT 1")
            companion = cur.fetchone()
            if companion:
                alternative_payload = payload()
                alternative_payload["source_id"] = companion[1]
                alternative_payload["provenance"][0]["catalog_admission"]["source_id"] = companion[
                    1
                ]
                alt = entry(alternative_payload)
                override = row_for(alt)
                override["generation"] = companion[0]
                cur.execute(
                    "SELECT md5(("
                    + h.payload_sql()
                    + ")::text) FROM jsonb_populate_record(NULL::public.places_catalog,%s) p",
                    (Json(override),),
                )
                alt["payload_pg_md5"] = cur.fetchone()[0]
                full = h.sql_resolved((alt,))
                no_companion_check = full.replace(
                    "AND NOT EXISTS (SELECT 1 FROM public.places_catalog_calendars calendar\n             WHERE calendar.generation=p.generation AND calendar.source_id=p.source_id)",
                    "",
                )
                assert no_companion_check != full
                for expression, expected in ((no_companion_check, True), (full, False)):
                    cur.execute(
                        "SELECT "
                        + expression
                        + " FROM jsonb_populate_record(NULL::public.places_catalog,%s) p",
                        (Json(override),),
                    )
                    assert cur.fetchone()[0] is expected
    finally:
        conn.close()


def _trait_annotation(*, state="fresh", stored=False):
    return {
        "identity_source": "catalog-pilot",
        "ratings_source": "AI estimates; source records supply identity, not live verification",
        "verified_at": None,
        "ratings_cache": state,
        "ratings_version": "attraction-traits-v1",
        "ratings_created_at": "2026-11-04T12:00:00+00:00" if stored else None,
        "ratings_provider": "offline-fixture" if stored else None,
    }


def _annotated_runtime(item):
    canonical = row_for(item)
    value = {
        key: copy.deepcopy(content)
        for key, content in canonical.items()
        if key not in {"source_id", "latitude", "longitude", "region", "provenance"}
    }
    value.update(
        provider_id=item["source_id"],
        source="catalog-pilot",
        coordinates=[canonical["latitude"], canonical["longitude"]],
        source_provenance=canonical["provenance"],
        provenance=_trait_annotation(),
    )
    return value


@pytest.mark.parametrize(
    "index",
    [
        index
        for index, item in enumerate(h.RESOLUTIONS)
        if any(
            fact.get("catalog_admission", {}).get("tier") == "T3"
            for fact in item["approved_payload"]["provenance"]
        )
    ],
)
def test_qualified_exact_rows_survive_real_candidates_with_trait_annotations(index):
    from app.agent.persona import default_weights
    from app.routing.sources.persona_candidates import ProposedPlace, VerifiedPlace, _candidate
    from tests.catalog_routing_hold_resolution_tests import runtime

    item = h.RESOLUTIONS[index]
    place = VerifiedPlace.model_validate(runtime(row_for(item)))
    proposal = ProposedPlace(
        name=place.name, attribute_ratings=dict.fromkeys(default_weights(), 0.5)
    )
    candidate = _candidate(place, proposal, default_weights())
    original_facts = copy.deepcopy(candidate["source_provenance"])
    for annotation in (
        _trait_annotation(),
        _trait_annotation(state="fresh", stored=True),
        _trait_annotation(state="hit", stored=True),
    ):
        candidate["provenance"].update(annotation)
        assert h.resolved(candidate, item["resolved_held_ids"])
        assert candidate["source_provenance"] == original_facts


@pytest.mark.parametrize(
    "mutation",
    [
        lambda annotation: annotation.update(unreviewed_override=True),
        lambda annotation: annotation.pop("ratings_provider"),
        lambda annotation: annotation.update(ratings_cache="unreviewed"),
        lambda annotation: annotation.update(ratings_cache=True),
        lambda annotation: annotation.update(ratings_version="attraction-traits-v999"),
        lambda annotation: annotation.update(ratings_version={}),
        lambda annotation: annotation.update(ratings_created_at=True),
        lambda annotation: annotation.update(ratings_created_at="not-a-timestamp"),
        lambda annotation: annotation.update(ratings_created_at="2026-11-04T12:00:00"),
        lambda annotation: annotation.update(ratings_provider={}),
        lambda annotation: annotation.update(ratings_provider=""),
        lambda annotation: annotation.update(ratings_provider=" " * 3),
        lambda annotation: annotation.update(ratings_provider="x" * 257),
        lambda annotation: annotation.update(ratings_created_at=None),
        lambda annotation: annotation.update(ratings_provider=None),
        lambda annotation: annotation.update(verified_at={}),
    ],
)
def test_malformed_or_partial_trait_annotations_do_not_resolve_holds(monkeypatch, mutation):
    item = entry()
    monkeypatch.setattr(h, "RESOLUTIONS", (item,))
    value = _annotated_runtime(item)
    value["provenance"] = _trait_annotation(state="hit", stored=True)
    assert h.resolved(value, item["resolved_held_ids"])
    mutation(value["provenance"])
    assert not h.resolved(value, item["resolved_held_ids"])


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value.update(name="Changed source identity"),
        lambda value: value.update(url="https://changed.example"),
        lambda value: value["coordinates"].__setitem__(0, 0.5),
        lambda value: value["source_provenance"][0]["catalog_admission"].update(
            expires_at_epoch=9999999999
        ),
        lambda value: value["source_provenance"][1].update(synthetic_boolean=0),
        lambda value: value["provenance"].update(source_provenance=[]),
        lambda value: value.update(ratings_cache="hit"),
    ],
)
def test_valid_trait_annotations_cannot_hide_changed_or_missing_source_facts(monkeypatch, mutation):
    item = entry()
    monkeypatch.setattr(h, "RESOLUTIONS", (item,))
    value = _annotated_runtime(item)
    assert h.resolved(value, item["resolved_held_ids"])
    mutation(value)
    assert not h.resolved(value, item["resolved_held_ids"])


def test_uncached_trait_annotations_require_a_complete_fresh_group(monkeypatch):
    item = entry()
    monkeypatch.setattr(h, "RESOLUTIONS", (item,))
    value = _annotated_runtime(item)
    assert h.resolved(value, item["resolved_held_ids"])
    value["provenance"]["ratings_cache"] = "hit"
    assert not h.resolved(value, item["resolved_held_ids"])
