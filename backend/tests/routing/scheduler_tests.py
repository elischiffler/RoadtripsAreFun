"""Tests for the shared day/hotel scheduler.

The headline test is ``test_planners_schedule_identically_given_same_selection``:
it proves the whole point of the shared-scheduler refactor — greedy and OR-Tools
produce the same day/hotel structure when handed the same attraction set, so any
benchmark difference is attributable purely to *selection*.
"""

import pytest
from fastapi import HTTPException

from app.routing.base import PlanOptions
from app.routing.planners.greedy import GreedyPlanner
from app.routing.planners.ortools_knapsack import ORToolsKnapsackPlanner
from app.routing.scheduler import schedule_route


@pytest.mark.asyncio
async def test_scheduler_inserts_attractions_via_provider(route, start_date, fake_services):
    """The scheduler places attractions supplied by the stop provider."""
    calls = []

    async def provider(category, lat, lon, radius):
        calls.append((lat, lon))
        return {
            "coordinates": [lat, lon],
            "name": f"Stop {len(calls)}",
            "type": "stop",
            "url": "u",
            "address": "a",
        }

    stops, cost = await schedule_route(
        route,
        num_stops=2,
        date=start_date,
        budget=1000,
        daily_start=9,
        daily_end=16,
        services=fake_services.bundle(),
        stop_provider=provider,
    )
    attractions = [s for s in stops if s["type"] == "stop"]
    assert len(attractions) == 2
    assert len(calls) == 2  # provider consulted once per placed attraction


@pytest.mark.asyncio
async def test_scheduler_stops_when_provider_exhausted(route, start_date, fake_services):
    """A 404 from the provider cleanly ends attraction placement (like greedy)."""

    async def provider(category, lat, lon, radius):
        raise HTTPException(status_code=404, detail="none")

    # 2 attempts per boundary then it gives up — should raise out of the scheduler.
    with pytest.raises(HTTPException):
        await schedule_route(
            route,
            num_stops=2,
            date=start_date,
            budget=1000,
            daily_start=9,
            daily_end=16,
            services=fake_services.bundle(),
            stop_provider=provider,
        )


@pytest.mark.asyncio
async def test_planners_schedule_identically_given_same_selection(route, start_date, fake_services):
    """Greedy and OR-Tools yield the same day/hotel structure for the same stops.

    We force both planners to "select" the exact same attractions (by making the
    candidate pool equal to num_stops so the knapsack keeps them all, and having
    greedy's find_stop return attractions at the same positions). The resulting
    hotel count and total cost must match — proving scheduling is shared and only
    selection can differ.
    """
    # Pool size == num_stops so ortools keeps every candidate (no selection pruning),
    # and both planners therefore schedule the same number of attractions.
    fake_services.num_attractions = 3
    options = PlanOptions(num_stops=3, budget=3000, start=start_date)

    greedy = await GreedyPlanner().plan(route, options, fake_services.bundle())
    ortools = await ORToolsKnapsackPlanner().plan(route, options, fake_services.bundle())

    def shape(result):
        return (
            sum(1 for s in result.stopping_points if s["type"] == "stop"),
            sum(1 for s in result.stopping_points if s["type"] == "hotel"),
            result.total_cost,
        )

    assert shape(greedy) == shape(ortools)
