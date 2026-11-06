"""Synthetic seven-identity regressions; no live NPS or parking assertions."""

import copy
from types import SimpleNamespace

import pytest

from app.catalog import repository
from app.models.itinerary_models import Itinerary_Payload
from app.routers.itinerary_api import build_itinerary
from app.routing.sources.visit_durations import DurationCache, estimate_durations
from app.routing.trip_calendar import TripCalendar
from app.routing.visit_calendar import VisitCalendarConflict, solve_visit
from app.routing.visit_duration import VisitDuration, fallback_duration
from tests.routing.catalog_calendar_refresh_tests import IDS, START, authoritative, payload, record


@pytest.mark.asyncio
@pytest.mark.parametrize("identifier", IDS)
@pytest.mark.parametrize(
    "seconds,source",
    [(900, "ai_estimate"), (21600, "ai_estimate"), (7200, "conservative_fallback")],
)
async def test_all_seven_current_holds_override_variable_and_fallback_saved_dwell(
    monkeypatch, identifier, seconds, source
):
    held = record(identifier)
    monkeypatch.setattr(
        repository, "current_records", lambda ids: {identifier: authoritative(held)}
    )
    stale = payload(record(identifier, held=False), policy=False, provenance=False)
    stale.route.stops[0]["visit_duration"] = (
        fallback_duration("provider_failure").model_dump()
        if source == "conservative_fallback"
        else VisitDuration(seconds=seconds, source="ai_estimate", reason="estimated").model_dump()
    )
    saved = stale.model_dump(mode="json")
    before = copy.deepcopy(saved)
    data = Itinerary_Payload.model_validate(copy.deepcopy(saved))
    with pytest.raises(VisitCalendarConflict, match="current catalog access is unresolved"):
        await build_itinerary(data)
    assert saved == before
    assert data.route.stops[0]["visit_duration"]["seconds"] == seconds


@pytest.mark.asyncio
@pytest.mark.parametrize("identifier", IDS)
async def test_cached_short_estimate_never_bypasses_a_new_hold(identifier):
    import json

    class AI:
        calls = 0

        def complete(self, _messages, _tools):
            self.calls += 1
            return SimpleNamespace(
                content=json.dumps({"estimates": [{"provider_id": identifier, "minutes": 15}]})
            )

    ai, cache = AI(), DurationCache()
    before = record(identifier, held=False)
    first = await estimate_durations([before], {}, ai, cache=cache)
    held = record(identifier)
    second = await estimate_durations([held], {}, ai, cache=cache)
    assert ai.calls == 1 and first[0]["visit_duration"] == second[0]["visit_duration"]
    assert second[0]["visit_duration"]["seconds"] == 900

    async def zone(_point):
        return "America/Phoenix"

    assert not await TripCalendar(START, zone).eligible(second[0])
    with pytest.raises(VisitCalendarConflict):
        solve_visit(second[0], START, START.replace(hour=17))


@pytest.mark.parametrize("identifier", IDS)
@pytest.mark.parametrize("seconds", [900, 7200, 21600])
def test_itinerary_http_hold_failure_preserves_saved_duration_metadata(
    monkeypatch, allow_provider_auth, identifier, seconds
):
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setattr(
        repository, "current_records", lambda ids: {identifier: authoritative(record(identifier))}
    )
    saved = payload(record(identifier, held=False)).model_dump(mode="json")
    saved["route"]["stops"][0]["visit_duration"] = VisitDuration(
        seconds=seconds, source="ai_estimate", reason="estimated"
    ).model_dump()
    before = copy.deepcopy(saved)
    response = TestClient(app).post("/generate-itinerary", json=saved)
    assert response.status_code == 422
    assert "current catalog access is unresolved" in response.json()["detail"]
    assert saved == before
    assert saved["route"]["stops"][0]["visit_duration"]["seconds"] == seconds
