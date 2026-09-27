"""Tests for planner metrics, objective scoring, and the counting services wrapper."""

import pytest

from app.routing.base import PlanOptions, score_trip
from app.routing.planners.greedy import GreedyPlanner
from app.routing.planners.ortools_knapsack import ORToolsKnapsackPlanner
from app.routing.services import CountingServices


def test_score_trip_rewards_value_penalizes_cost_and_detour():
    """Objective score = w_v*value - w_c*cost - w_d*detour_hours."""
    stops = [
        {"type": "stop", "name": "A"},
        {"type": "stop", "name": "B"},
        {"type": "hotel", "name": "H", "price": 100},
    ]
    # 2 attractions, value 1.0 each, 2h detour each; default weights v=100,c=1,d=10.
    score, components = score_trip(stops, total_cost=100.0)
    assert components["total_value"] == 2.0
    assert components["total_detour_hours"] == 4.0
    # 100*2 - 1*100 - 10*4 = 60
    assert score == pytest.approx(60.0)


def test_score_trip_respects_custom_weights():
    stops = [{"type": "stop", "name": "A"}]
    score, _ = score_trip(stops, total_cost=0.0, weights={"value": 1.0, "detour": 0.0})
    assert score == pytest.approx(1.0)  # 1*1 - 1*0 - 0*2


@pytest.mark.asyncio
async def test_run_attaches_metrics(route, start_date, fake_services):
    """run() attaches PlanMetrics with timing, counts, and a score."""
    planner = GreedyPlanner()
    services = CountingServices(fake_services.bundle())
    result = await planner.run(
        route, PlanOptions(num_stops=2, budget=2000, start=start_date), services
    )
    m = result.metrics
    assert m is not None
    assert m.algorithm == "greedy"
    assert m.feasible is True
    assert m.wall_clock_ms >= 0
    assert m.num_attractions == 2
    assert m.api_calls == services.api_calls
    assert m.api_calls > 0  # at least the two attraction lookups


@pytest.mark.asyncio
async def test_counting_services_counts_only_io(route, start_date, fake_services):
    """Only find_stop/find_hotel/gather are counted; pure helpers are not."""
    services = CountingServices(fake_services.bundle())
    # Pure helpers shouldn't move the counter.
    services.find_position([[0, 0], [1, 1]], route.legs[0].steps, 0)
    services.get_price_range(
        remaining_budget=100, duration_left=3600, stops_left=1, daily_drive_time=7
    )
    assert services.api_calls == 0
    # Each I/O method increments the counter exactly once per call.
    await services.find_stop("attractions", 33.0, -117.0, 30)
    assert services.api_calls == 1
    await services.find_hotel(33.0, -117.0, ((0, 200), "0-200"), start_date)
    assert services.api_calls == 2
    await services.gather_candidates(route, 3)
    assert services.api_calls == 3


@pytest.mark.asyncio
async def test_run_marks_infeasible_on_planning_error(route, start_date):
    """A PlanningError is captured as an infeasible result, not raised."""

    class BoomServices:
        api_calls = 3

        async def find_stop(self, *a, **k):
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="nope")

        async def find_hotel(self, *a, **k):
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="nope")

        async def gather_candidates(self, *a, **k):
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="nope")

        def require_gather(self):
            return self.gather_candidates

        def __getattr__(self, name):
            # find_position / get_price_range fall through to a no-op-ish default.
            raise AttributeError(name)

    # Greedy will hit find_stop failures until it raises; run() should capture it.
    from app.routing.geometry import find_position
    from app.routing.pricing import get_price_range

    boom = BoomServices()
    boom.find_position = find_position
    boom.get_price_range = get_price_range

    planner = ORToolsKnapsackPlanner()
    result = await planner.run(route, PlanOptions(num_stops=3, budget=500, start=start_date), boom)
    assert result.metrics is not None
    assert result.metrics.feasible is False
    assert result.metrics.error is not None
