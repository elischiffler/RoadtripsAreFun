"""Origin-local departure validation with a fixed clock and no live providers."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.agent import departure
from app.agent.persona import AccountPersona
from app.main import app
from app.models.routing_models.routing_models import Route_Payload
from app.routers import routing_api
from app.routing.base import PlanningError, PlanResult


@pytest.fixture
def boundary(monkeypatch, route):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2035, 6, 1, 16, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(departure, "datetime", Clock)
    route.duration = route.legs[0].duration = 300
    services = SimpleNamespace(timezone_at=AsyncMock(return_value="America/Los_Angeles"))
    planner = SimpleNamespace(plan=AsyncMock(return_value=PlanResult([], 0)))
    monkeypatch.setattr(routing_api, "_build_services", lambda: services)
    monkeypatch.setattr(routing_api, "get_planner", lambda name: planner)
    monkeypatch.setattr(routing_api, "_call_route", AsyncMock(return_value=route))
    monkeypatch.setattr(routing_api, "load_account_persona", lambda user: AccountPersona.default())
    monkeypatch.setattr(
        routing_api, "get_location", lambda **kwargs: SimpleNamespace(address="Fixture")
    )
    monkeypatch.setattr(routing_api, "refresh_for_timing", AsyncMock())
    monkeypatch.setattr(routing_api, "enrich_evenings", AsyncMock())
    monkeypatch.setattr(routing_api, "owner_routing_claims", lambda *args, **kwargs: {})
    return services, planner


def payload(route, start, **kwargs):
    return Route_Payload(
        initial_route=route,
        num_stops=1,
        budget=100,
        start=start,
        traveler_count=1,
        hotel_rooms=[{"adults": 1, "child_ages": []}],
        **kwargs,
    )


@pytest.mark.asyncio
async def test_western_origin_near_now_is_future_and_reaches_planner(boundary, route):
    services, planner = boundary
    # 09:30 PDT is 16:30 UTC, even though its naive clock reads earlier than UTC now.
    result = await routing_api.plan_final_route(
        payload(route, "2035-06-01T09:30:00", start_timezone="Asia/Tokyo"), user_id="fixture"
    )
    options = planner.plan.call_args.args[1]
    assert options.start.isoformat() == "2035-06-01T09:30:00-07:00"
    assert result.departure_time == options.start
    assert result.start_timezone == "America/Los_Angeles"
    assert services.timezone_at.await_args_list[0].args == ([33.72, -117.93],)


@pytest.mark.asyncio
async def test_eastern_origin_near_now_is_past_before_planning(boundary, route):
    services, planner = boundary
    services.timezone_at.return_value = "Asia/Tokyo"
    # 00:30 JST June 2 is 15:30 UTC June 1, already past.
    with pytest.raises(PlanningError, match="upcoming trip start date") as error:
        await routing_api.plan_final_route(payload(route, "2035-06-02T00:30:00"), "fixture")
    assert error.value.status_code == 422
    planner.plan.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("start", ["2035-06-01T18:30:00+02:00", "2035-06-01T16:30:00Z"])
async def test_explicit_offset_preserved_through_planner_and_response(boundary, route, start):
    _, planner = boundary
    request = payload(route, start)
    result = await routing_api.plan_final_route(request, "fixture")
    planned = planner.plan.call_args.args[1].start
    assert planned is request.start
    assert result.departure_time.isoformat() == request.start.isoformat()


@pytest.mark.asyncio
@pytest.mark.parametrize("start", ["2035-06-01T16:00:00Z", "2035-06-01T18:00:00+02:00"])
async def test_explicit_instant_at_now_is_rejected_without_geocoding(boundary, route, start):
    services, planner = boundary
    with pytest.raises(PlanningError, match="upcoming trip start date") as error:
        await routing_api.plan_final_route(payload(route, start), "fixture")
    assert error.value.status_code == 422
    services.timezone_at.assert_not_awaited()
    planner.plan.assert_not_awaited()


@pytest.mark.parametrize("start", ["2036-03-09T02:30:00", "2035-11-04T01:30:00"])
def test_dst_gap_and_fold_are_actionable_http_errors(boundary, route, start, allow_provider_auth):
    _, planner = boundary
    response = TestClient(app).post(
        "/generate-final-route", json=payload(route, start).model_dump(mode="json")
    )
    assert response.status_code == 422, response.text
    assert "ambiguous or does not exist locally" in response.json()["detail"]
    planner.plan.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_dst_fold_offset_is_not_treated_as_ambiguous(boundary, route):
    _, planner = boundary
    result = await routing_api.plan_final_route(
        payload(route, "2035-11-04T01:30:00-08:00"), "fixture"
    )
    assert result.departure_time.isoformat() == "2035-11-04T01:30:00-08:00"
    planner.plan.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("zone", [None, "", "Unknown/Place", "/etc/passwd"])
async def test_unverified_origin_zone_fails_before_planning(boundary, route, zone):
    services, planner = boundary
    services.timezone_at.return_value = zone
    with pytest.raises(PlanningError, match="starting location timezone") as error:
        await routing_api.plan_final_route(payload(route, "2035-06-01T09:30:00"), "fixture")
    assert error.value.status_code == 503
    planner.plan.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_timezone_service_has_explicit_failure(boundary, route):
    services, planner = boundary
    services.timezone_at = None
    with pytest.raises(PlanningError, match="starting location timezone") as error:
        await routing_api.plan_final_route(payload(route, "2035-06-01T09:30:00"), "fixture")
    assert error.value.status_code == 503
    planner.plan.assert_not_awaited()
