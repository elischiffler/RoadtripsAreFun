"""Pinned payload compatibility through main's actual runtime projections."""

import copy
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest

from app.catalog import admission, release_holds, repository
from app.catalog import hold_resolution as h
from app.catalog.identity import identity
from app.routing.catalog_calendars import refresh_for_timing
from app.routing.sources.persona_candidates import VerifiedPlace
from app.routing.visit_calendar import VisitCalendarConflict, calendar_eligible, solve_visit
from tests.catalog_admission_tests import NOW, POINT, record


def row_for(item):
    row = copy.deepcopy(item["approved_payload"])
    row["provenance"].append(copy.deepcopy(item["marker"]))
    return row


def runtime(row):
    return {
        "provider_id": identity(row["source_id"])[0],
        "source": identity(row["source_id"])[1],
        "name": row["name"],
        "coordinates": [row["latitude"], row["longitude"]],
        "categories": row["categories"],
        "address": row["address"],
        "url": row["url"],
        "source_updated_at": row["source_updated_at"],
        "source_provenance": row["provenance"]
        + [{"dataset": "Roadtrips active catalog", "generation": "a" * 64, "release": "fixture"}],
    }


@pytest.mark.parametrize("index", range(170))
def test_every_approved_version_survives_main_model_without_global_unhold(index):
    assert len(h.RESOLUTIONS) == 170
    item = h.RESOLUTIONS[index]
    row = row_for(item)
    contract = next(f["catalog_admission"] for f in row["provenance"] if "catalog_admission" in f)
    now = contract["reviewed_at_epoch"] + 1
    value = runtime(row)
    projected = VerifiedPlace.model_validate(value).model_dump()
    assert not release_holds.blocked(row)
    assert not release_holds.blocked(projected)
    assert h.resolved(projected, item["resolved_held_ids"])
    assert admission.browse_eligible(projected, now_epoch=now)
    assert admission.routing_eligible(projected, now_epoch=now) == (contract["tier"] == "T3")
    assert all(release_holds.blocked(sid) for sid in item["resolved_held_ids"])
    for key in ("name", "url", "address", "source_updated_at"):
        changed = copy.deepcopy(projected)
        changed[key] = "unreviewed change"
        assert release_holds.blocked(changed)
    changed = copy.deepcopy(projected)
    changed["coordinates"][0] += 0.001
    assert release_holds.blocked(changed)
    changed = copy.deepcopy(projected)
    changed["source_provenance"][0]["unreviewed_fact"] = True
    assert release_holds.blocked(changed)
    assert not admission.routing_eligible(projected, now_epoch=contract["expires_at_epoch"])


def test_all_registry_versions_and_legacy_remain_separate():
    tiers = [
        next(
            f["catalog_admission"]["tier"]
            for f in e["approved_payload"]["provenance"]
            if "catalog_admission" in f
        )
        for e in h.RESOLUTIONS
    ]
    assert tiers.count("T2") == 119 and tiers.count("T3") == 51
    assert admission.routing_eligible({"provider_id": "usfs:legacy", "source_provenance": []})


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["missing", "expired", "unresolved", "changed_arrival"])
async def test_refresh_rejects_stale_positive_admission(failure):
    sid = "catalog-pilot:refresh-fixture"
    stale = record(sid, tier="T3", calendar=True) | {"type": "stop"}
    current = copy.deepcopy(stale)
    if failure == "expired":
        current["source_provenance"][0]["catalog_admission"]["expires_at_epoch"] = NOW - 1
    elif failure == "unresolved":
        held = sorted(release_holds.SOURCE_IDS)[0]
        current["source_provenance"].append({"aliases": [held]})
    elif failure == "changed_arrival":
        current["coordinates"][0] += 0.001
    async_calls = []

    def lookup(ids):
        async_calls.append(ids)
        return {} if failure == "missing" else {sid: current}

    with pytest.raises(VisitCalendarConflict):
        await refresh_for_timing([stale], catalog_lookup=lookup)
    assert async_calls == [[sid]]


@pytest.mark.asyncio
async def test_exact_qualified_current_record_overrides_stale_identity_fields(monkeypatch):
    item = next(
        e
        for e in h.RESOLUTIONS
        if any(
            f.get("catalog_admission", {}).get("tier") == "T3"
            for f in e["approved_payload"]["provenance"]
        )
    )
    row = row_for(item)
    value = runtime(row)
    contract = next(f["catalog_admission"] for f in row["provenance"] if "catalog_admission" in f)
    monkeypatch.setattr(admission.time, "time", lambda: contract["reviewed_at_epoch"] + 1)
    stale = copy.deepcopy(value) | {
        "type": "stop",
        "name": "old name",
        "address": "old address",
        "url": "https://stale.example",
    }
    await refresh_for_timing(
        [stale], catalog_lookup=lambda ids: {row["source_id"]: copy.deepcopy(value)}
    )
    assert (
        stale["name"] == value["name"]
        and stale["address"] == value["address"]
        and stale["url"] == value["url"]
    )
    assert calendar_eligible(stale)


def test_current_records_selects_full_payload_and_excludes_holds_before_return(monkeypatch):
    item = h.RESOLUTIONS[-1]
    row = row_for(item)
    row.update(
        generation="a" * 64,
        release="fixture",
        attribution="Fixture",
        source_catalogs={},
        calendar_enrichment=None,
    )
    conn = MagicMock()
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchall.return_value = [row]
    monkeypatch.setattr(repository.settings, "DATABASE_URL", "synthetic-unused")
    monkeypatch.setattr(repository.chat_crud, "_get_conn", lambda: conn)
    monkeypatch.setattr(repository.chat_crud, "_put_conn", lambda _: None)
    current = repository.current_records([row["source_id"]])[row["source_id"]]
    query = cur.execute.call_args_list[1].args[0]
    assert "p.name,p.region,p.address,p.url" in query
    assert release_holds.SQL_ALLOWED in query
    assert current["name"] == row["name"] and current["region"] == row["region"]
    assert not release_holds.blocked(current)
    conn.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_all_blocked_custom_candidates_return_before_ai_and_quotas():
    from app.agent.persona import default_weights
    from tests.routing.persona_candidates_tests import FakePlaces, discover

    class NeverAI:
        def complete(self, *_args, **_kwargs):
            pytest.fail("ineligible records must not reach AI")

    blocked = [record(f"catalog-pilot:blocked-{i}") for i in range(61)]
    result = await discover(
        None, [POINT], default_weights(), places=FakePlaces(attractions=blocked), ai=NeverAI()
    )
    assert result == []


def test_admission_and_holds_reject_before_final_timing():
    start = datetime(2026, 11, 4, 9, tzinfo=ZoneInfo("America/Los_Angeles"))
    for value in (record(), record(sorted(release_holds.SOURCE_IDS)[0], tier="T3", calendar=True)):
        with pytest.raises(VisitCalendarConflict):
            solve_visit(value, start, start + timedelta(hours=8))


@pytest.mark.asyncio
async def test_alias_only_held_legacy_evenings_are_blocked_before_directions():
    from app.routing.catalog_calendars import explicit_calendar_ineligible
    from app.routing.sources import evenings

    value = {
        "provider_id": "manual:unmarked",
        "name": "Legacy held alias",
        "coordinates": POINT,
        "categories": ["culture"],
        "category": "culture",
        "source_provenance": [{"aliases": [sorted(release_holds.SOURCE_IDS)[0]]}],
    }
    assert explicit_calendar_ineligible(value)

    class Provider:
        async def nearby(self, *_args):
            return [value]

        async def travel(self, *_args):
            pytest.fail("held alias must not reach directions")

    hotel = {"type": "hotel", "coordinates": POINT, "evening_suggestions": []}
    start = datetime(2026, 11, 4, 18, tzinfo=ZoneInfo("America/Los_Angeles"))
    await evenings._hotel_suggestions(
        hotel, start, start + timedelta(hours=4), ["culture"], Provider()
    )
    assert hotel["evening_suggestions"] == []


def test_runtime_imports_do_not_load_ingestion_or_qualification_factories():
    root = Path(__file__).resolve().parents[2]
    code = """
import os, runpy, socket, sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path[:0] = [str(root), str(root / 'backend')]
runpy.run_path(str(root / 'scripts/run_offline_tests.py'))['install']()
from app.routing.sources import persona_candidates, evenings
from app.routing import catalog_calendars
for name in ('app.catalog.ingest', 'app.catalog.calendar_enrichment', 'app.catalog.pilot', 'app.catalog.routing_qualification'):
    assert name not in sys.modules, name
assert 'DATABASE_URL' not in os.environ
assert not any(key.startswith('MENTRO_') for key in os.environ)
try:
    socket.getaddrinfo('operator.example', 443)
except OSError as exc:
    assert 'offline tests prohibit external DNS' in str(exc)
else:
    raise AssertionError('offline DNS guard missing')
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(root)], capture_output=True, text=True, timeout=20
    )
    assert result.returncode == 0, result.stderr
