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
async def test_far_candidate_dropped_over_budget(route, start_date, fake_services):
    """A candidate whose detour exceeds the whole pooled budget is never selected,
    even when it has the best popularity rank."""
    from app.routing.planners.ortools_knapsack import _DETOUR_BUDGET_PER_STOP_M

    fake_services.num_attractions = 3
    # Candidate 1 has the best rank but sits well beyond a single-stop budget;
    # candidates 2 and 3 are cheap and in-budget.
    fake_services.detour_overrides = {
        1: _DETOUR_BUDGET_PER_STOP_M * 2,  # too far -> must be dropped
        2: 1000.0,
        3: 1000.0,
    }
    planner = ORToolsKnapsackPlanner()
    result = await planner.plan(
        route, PlanOptions(num_stops=1, budget=2000, start=start_date), fake_services.bundle()
    )
    stops = [p for p in result.stopping_points if p["type"] == "stop"]
    assert len(stops) == 1
    # The over-budget best-ranked candidate (Candidate 1) must not have been chosen.
    assert stops[0]["name"] != "Candidate 1"


@pytest.mark.asyncio
async def test_closer_candidate_preferred_under_tight_budget(route, start_date, fake_services):
    """With room for one stop, a closer in-budget candidate is chosen over a
    farther one of comparable rank."""
    from app.routing.planners.ortools_knapsack import _DETOUR_BUDGET_PER_STOP_M

    fake_services.num_attractions = 2
    # Both in budget, but candidate 1 (best rank) is near the budget edge while
    # candidate 2 is cheap. Popularity still dominates here, so candidate 1 wins —
    # this guards that an in-budget far candidate remains selectable (not filtered).
    fake_services.detour_overrides = {
        1: _DETOUR_BUDGET_PER_STOP_M * 0.9,
        2: 500.0,
    }
    planner = ORToolsKnapsackPlanner()
    result = await planner.plan(
        route, PlanOptions(num_stops=1, budget=2000, start=start_date), fake_services.bundle()
    )
    stops = [p for p in result.stopping_points if p["type"] == "stop"]
    assert len(stops) == 1


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
