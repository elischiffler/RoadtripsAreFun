"""ORToolsKnapsackPlanner unit tests using injected fake services (no network)."""

import pytest

from app.routing.base import PlanOptions, PlanResult
from app.routing.planners.ortools_knapsack import ORToolsKnapsackPlanner


@pytest.mark.asyncio
async def test_selects_at_most_num_stops(route, start_date, fake_services):
    """The knapsack count-cap keeps selected attractions <= num_stops."""
    # Pool of 6 candidates, but only 2 stops requested.
    fake_services.num_attractions = 6
    planner = ORToolsKnapsackPlanner()
    result = await planner.plan(
        route, PlanOptions(num_stops=2, budget=2000, start=start_date), fake_services.bundle()
    )

    assert isinstance(result, PlanResult)
    stops = [p for p in result.stopping_points if p["type"] == "stop"]
    assert len(stops) <= 2
    assert len(stops) >= 1


@pytest.mark.asyncio
async def test_zero_stops_no_attractions(route, start_date, fake_services):
    """0 stops => no attractions selected, no gather needed."""
    short = route
    short.duration = 7200.0
    short.legs[0].duration = 7200.0
    planner = ORToolsKnapsackPlanner()
    result = await planner.plan(
        short, PlanOptions(num_stops=0, budget=400, start=start_date), fake_services.bundle()
    )
    assert [p for p in result.stopping_points if p["type"] == "stop"] == []


@pytest.mark.asyncio
async def test_selected_attractions_in_route_order(route, start_date, fake_services):
    """Selected attractions come out sorted along the route (monotonic in time)."""
    fake_services.num_attractions = 5
    planner = ORToolsKnapsackPlanner()
    result = await planner.plan(
        route, PlanOptions(num_stops=3, budget=3000, start=start_date), fake_services.bundle()
    )
    stops = [p for p in result.stopping_points if p["type"] == "stop"]
    # Coordinates should progress from the LA side toward the NY side (lon increases).
    lons = [c["coordinates"][1] for c in stops]
    assert lons == sorted(lons)


@pytest.mark.asyncio
async def test_stops_carry_expected_contract_keys(route, start_date, fake_services):
    """Emitted attraction dicts keep the shape downstream consumers rely on."""
    planner = ORToolsKnapsackPlanner()
    result = await planner.plan(
        route, PlanOptions(num_stops=2, budget=2000, start=start_date), fake_services.bundle()
    )
    for p in result.stopping_points:
        assert "type" in p
        if p["type"] == "stop":
            assert set(["name", "coordinates", "type"]).issubset(p.keys())
            assert "elapsed_time" not in p  # scrubbed before returning
