"""Cross-layer CP-SAT identity, persona, and final-route checks with fakes."""

from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.agent.agent import run_turn
from app.agent.persona import AccountPersona
from app.agent.schemas import AgentChatRequest
from app.agent.tool_dispatcher import AppToolDispatcher
from app.agent.tools import ToolCall, ToolContext
from app.agent.trip_profile import TripProfile
from app.main import app
from app.models.routing_models.routing_models import Route_Payload
from app.routers import routing_api
from app.routing import registry
from app.routing.base import PlanningError, PlanResult
from app.routing.occupancy import HotelRoom
from app.routing.selection import OWNER_EMAIL
from tests.agent.conftest import FakeMemory, FakeProvider
from tests.conftest import CLIENT


@pytest.fixture
def alternate_planners(monkeypatch, route):
    """Test-only planners make unauthorized selection observable without providers."""
    registry.available_planners()
    seen = []
    route.duration = route.legs[0].duration = 3600

    class Planner:
        def __init__(self, name):
            self.name = name

        async def plan(self, initial, options, services):
            seen.append(self.name)
            return PlanResult(stopping_points=[], total_cost=0)

    monkeypatch.setitem(registry._REGISTRY, "cp_sat", Planner("cp_sat"))
    monkeypatch.setitem(registry._REGISTRY, "test_alternate", Planner("test_alternate"))
    monkeypatch.setenv("ROUTING_ALGORITHM", "test_alternate")
    monkeypatch.setattr(routing_api, "load_account_persona", lambda user: AccountPersona.default())
    monkeypatch.setattr(
        routing_api,
        "get_location",
        lambda **kwargs: SimpleNamespace(
            address="fixture", raw={"annotations": {"timezone": {"name": "America/Los_Angeles"}}}
        ),
    )

    async def final_route(*args):
        return route

    monkeypatch.setattr(routing_api, "_call_route", final_route)
    return seen


@pytest.mark.parametrize("owner", [False, True])
@pytest.mark.parametrize("requested", [None, "test_alternate", "unknown"])
def test_http_selection_enforced(signed_token, route, alternate_planners, owner, requested):
    headers = {"Authorization": f"Bearer {signed_token()}"}
    if owner:
        headers["X-Cognito-Id-Token"] = signed_token(
            token_use="id", aud=CLIENT, email=OWNER_EMAIL, email_verified=True
        )
    payload = Route_Payload(
        initial_route=route,
        num_stops=0,
        budget=100,
        start=datetime(2035, 6, 1, 9),
        algorithm=requested,
        traveler_count=2,
        hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
    )
    response = TestClient(app).post(
        "/generate-final-route", json=payload.model_dump(mode="json"), headers=headers
    )
    if owner and requested == "unknown":
        assert response.status_code == 400
        assert alternate_planners == []
    else:
        assert response.status_code == 200, response.text
        assert alternate_planners == [requested if owner and requested else "cp_sat"]


@pytest.mark.asyncio
@pytest.mark.parametrize("owner", [False, True])
@pytest.mark.parametrize("remote", [False, True])
@pytest.mark.parametrize("source", ["tool", "context", "default"])
async def test_tool_and_remote_selection(
    monkeypatch, route, alternate_planners, owner, remote, source
):
    from app.agent import routing_remote

    monkeypatch.setattr(
        routing_remote.settings, "ROUTING_REMOTE_URL", "https://fixture" if remote else None
    )
    memory = FakeMemory()
    memory.save_trip_profile(
        "user",
        "chat",
        TripProfile(
            car_status="skipped", traveler_count=2, hotel_rooms=[HotelRoom(adults=2, child_ages=[])]
        ).to_json(),
    )
    ctx = ToolContext(
        user_id="user",
        chat_id="chat",
        memory=memory,
        auth_token="access",
        identity_token="identity" if owner else None,
        can_select_algorithm=owner,
        algorithm="test_alternate" if source == "context" else None,
    )
    arguments = {
        "route_handle": ctx.artifacts.put("initial_route", route),
        "traveler_count": 2,
        "hotel_rooms": [{"adults": 2, "child_ages": []}],
        "num_stops": 0,
        "budget": 100,
        "start": "2035-06-01T09:00:00",
    }
    if source == "tool":
        arguments["algorithm"] = "test_alternate"

    async def remote_plan(payload, token, *, identity_token=None):
        assert token == "access"
        assert identity_token == ("identity" if owner else None)
        # The wire payload must already be forced to CP-SAT for non-owners.
        assert payload.algorithm == (
            "test_alternate" if owner and source != "default" else "cp_sat"
        )
        return await routing_api.plan_final_route(payload, "user", can_select_algorithm=owner)

    monkeypatch.setattr(routing_remote, "plan_final_route_remote", remote_plan)
    result = await AppToolDispatcher().dispatch(
        ToolCall(name="generate_final_route", arguments=arguments), ctx
    )
    assert result.ok, result.error
    assert alternate_planners == ["test_alternate" if owner and source != "default" else "cp_sat"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatch", [False, True])
async def test_agent_context_eligibility_from_verified_identity(signed_token, mismatch):
    contexts = []

    class Tools:
        def specs(self):
            return []

        async def dispatch(self, call, ctx):
            contexts.append(ctx)
            assert ctx.can_select_algorithm is not mismatch
            assert ctx.user_id == "cognito-user-123"
            from app.agent.tools import ToolResult

            return ToolResult(name=call.name, ok=True, result={})

    await run_turn(
        AgentChatRequest(partitionKey=signed_token(), chatId="chat", message="hello"),
        FakeProvider(extraction_responses=['{"details":{"budget":100}}']),
        FakeMemory(),
        Tools(),
        identity_token=signed_token(
            token_use="id",
            aud=CLIENT,
            email=OWNER_EMAIL,
            email_verified=True,
            sub="other" if mismatch else "cognito-user-123",
        ),
    )
    assert contexts
    assert all(ctx.can_select_algorithm is not mismatch for ctx in contexts)


@pytest.mark.asyncio
async def test_cp_sat_uses_verified_identity_and_trip_override(monkeypatch, route):
    route.duration = 3600
    route.legs[0].duration = 3600
    seen = {}

    def persona(user_id):
        seen["user_id"] = user_id
        return AccountPersona.default()

    class Planner:
        async def plan(self, initial, options, services):
            seen["weights"] = options.weights
            seen["services"] = services
            return PlanResult(stopping_points=[], total_cost=0)

    async def final_route(*args):
        return route

    monkeypatch.setattr(routing_api, "load_account_persona", persona)
    monkeypatch.setattr(routing_api, "get_planner", lambda name: Planner())
    monkeypatch.setattr(routing_api, "_call_route", final_route)
    monkeypatch.setattr(
        routing_api,
        "get_location",
        lambda **kwargs: SimpleNamespace(
            address="fixture", raw={"annotations": {"timezone": {"name": "America/Los_Angeles"}}}
        ),
    )
    payload = Route_Payload(
        initial_route=route,
        num_stops=0,
        budget=100,
        start=datetime(2035, 6, 1, 9),
        algorithm="cp_sat",
        persona_weights={"nature": 2},
        traveler_count=2,
        hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
    )
    result = await routing_api.plan_final_route(payload, user_id="verified-user")
    assert result.warnings is None
    assert seen["user_id"] == "verified-user"
    assert seen["weights"]["nature"] > seen["weights"]["food"]
    assert sum(seen["weights"].values()) == pytest.approx(1)
    assert seen["services"].cp_sat_candidates is routing_api.attraction_candidates
    assert seen["services"].cp_sat_hotels is routing_api.hotel_candidates


@pytest.mark.asyncio
async def test_cp_sat_requires_identity_before_persona_lookup(route):
    payload = Route_Payload(
        initial_route=route,
        num_stops=0,
        budget=100,
        algorithm="cp_sat",
        traveler_count=2,
        hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
    )
    with pytest.raises(PlanningError, match="Authenticated identity"):
        await routing_api.plan_final_route(payload)


@pytest.mark.asyncio
async def test_cp_sat_requires_upcoming_date(route):
    payload = Route_Payload(
        initial_route=route,
        num_stops=0,
        budget=100,
        algorithm="cp_sat",
        traveler_count=2,
        hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
    )
    with pytest.raises(PlanningError, match="upcoming trip start date"):
        await routing_api.plan_final_route(payload, user_id="u")


@pytest.mark.asyncio
async def test_final_mapbox_leg_shape_rejected(monkeypatch, route):
    class Planner:
        async def plan(self, initial, options, services):
            return PlanResult(
                stopping_points=[{"name": "A", "type": "stop", "coordinates": [35, -100]}],
                total_cost=0,
            )

    monkeypatch.setattr(
        routing_api, "load_account_persona", lambda user_id: AccountPersona.default()
    )
    monkeypatch.setattr(routing_api, "get_planner", lambda name: Planner())

    async def incomplete(*args):
        return route  # one leg for a route with one selected waypoint

    monkeypatch.setattr(routing_api, "_call_route", incomplete)
    payload = Route_Payload(
        initial_route=route,
        num_stops=1,
        budget=100,
        start=datetime(2035, 6, 1, 9),
        algorithm="cp_sat",
        traveler_count=2,
        hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
    )
    with pytest.raises(PlanningError, match="incomplete final route"):
        await routing_api.plan_final_route(payload, user_id="u")
