"""Offline release controls combining admission gates and variable visit estimates."""

import copy
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.agent.persona import default_weights
from app.catalog import admission, hold_resolution, release_holds
from app.routing.catalog_calendars import refresh_for_timing
from app.routing.discovery import DiscoveryPlan, SearchQuery
from app.routing.sources import persona_candidates as source
from app.routing.sources import trait_cache
from app.routing.visit_calendar import VisitCalendarConflict, solve_visit
from app.routing.visit_duration import VisitDuration
from tests.catalog_admission_tests import POINT, record
from tests.catalog_routing_hold_resolution_tests import row_for, runtime
from tests.routing.conftest import build_route


@pytest.mark.asyncio
@pytest.mark.parametrize("blocked_kind", ["browse_only", "held_alias"])
async def test_preestimate_gate_rejects_ineligible_sources_before_calendar_ai_or_duration(
    blocked_kind,
):
    value = record(tier="T2", calendar=True)
    if blocked_kind == "held_alias":
        value = {
            "provider_id": "manual:unmarked-held-alias",
            "name": "Synthetic held alias",
            "coordinates": POINT.copy(),
            "categories": ["daytime", "nature"],
            "source_provenance": [{"aliases": [sorted(release_holds.SOURCE_IDS)[0]]}],
        }
    assert not admission.routing_eligible(value)

    class Places:
        async def attractions_near(self, _point):
            return [copy.deepcopy(value)]

    class NeverAI:
        def complete(self, *_args):
            pytest.fail("An ineligible source reached ratings")

    class NeverCalendar:
        departure = datetime(2030, 7, 1, 9, tzinfo=ZoneInfo("America/Los_Angeles"))

        def snapshot(self):
            return {"fixture": "admission-before-calendar"}

        async def eligible(self, *_args, **_kwargs):
            pytest.fail("An ineligible source reached the minimum-dwell calendar check")

    async def never_duration(*_args):
        pytest.fail("An ineligible source reached duration estimates")

    route = build_route(3600)
    lat, lon = POINT
    route.geometry.coordinates = [[lon, lat], [lon + 0.05, lat]]
    route.legs[0].steps[0].geometry.coordinates = route.geometry.coordinates
    plan = DiscoveryPlan(1, 3600, 1, 18, 1, 1, 36, 54, [SearchQuery("gate", 0, 0, POINT)])
    plan.trip_calendar = NeverCalendar()
    result = await source.attraction_candidates(
        route,
        plan,
        default_weights(),
        places=Places(),
        ai=NeverAI(),
        duration_estimator=never_duration,
    )
    assert result.candidates == []


@pytest.mark.asyncio
@pytest.mark.parametrize("seconds", [900, 3600])
async def test_exact_exception_keeps_variable_dwell_after_annotations_and_authoritative_refresh(
    monkeypatch, seconds
):
    entry = next(
        item
        for item in hold_resolution.RESOLUTIONS
        if any(
            fact.get("catalog_admission", {}).get("tier") == "T3"
            for fact in item["approved_payload"]["provenance"]
        )
    )
    row = row_for(entry)
    value = runtime(row)
    contract = next(
        fact["catalog_admission"] for fact in row["provenance"] if "catalog_admission" in fact
    )
    qualification = next(
        fact
        for fact in row["provenance"]
        if fact.get("dataset") == "Roadtrips routing qualification"
    )
    monkeypatch.setattr(admission.time, "time", lambda: contract["reviewed_at_epoch"] + 1)
    candidate = source._candidate(
        source.VerifiedPlace.model_validate(value),
        source.ProposedPlace(
            name=value["name"], attribute_ratings=dict.fromkeys(default_weights(), 0.8)
        ),
        default_weights(),
    )
    candidate["provenance"].update(
        ratings_cache="fresh",
        ratings_version=trait_cache.VERSION,
        ratings_created_at=None,
        ratings_provider=None,
    )
    candidate.update(
        type="stop",
        visit_duration=VisitDuration(
            seconds=seconds, source="ai_estimate", reason="estimated"
        ).model_dump(),
    )
    untouched_source = copy.deepcopy(value)
    await refresh_for_timing(
        [candidate], catalog_lookup=lambda _ids: {row["source_id"]: copy.deepcopy(value)}
    )
    assert hold_resolution.resolved(candidate, entry["resolved_held_ids"])
    assert all(release_holds.blocked(identifier) for identifier in entry["resolved_held_ids"])
    assert candidate["visit_duration"]["seconds"] == seconds
    zone = ZoneInfo(qualification["timezone"])
    earliest = datetime(2026, 11, 4, 9, tzinfo=zone)
    start, availability = solve_visit(candidate, earliest, earliest + timedelta(hours=12))
    assert availability["dwell_seconds"] == seconds
    assert availability["dwell_source"] == "ai_estimate"
    assert datetime.fromisoformat(availability["visit_end"]) - start == timedelta(seconds=seconds)
    assert value == untouched_source

    tampered = copy.deepcopy(value)
    tampered["url"] = "https://unreviewed.example/changed-source"
    with pytest.raises(VisitCalendarConflict):
        await refresh_for_timing(
            [candidate], catalog_lookup=lambda _ids: {row["source_id"]: tampered}
        )
