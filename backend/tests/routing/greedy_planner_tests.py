"""GreedyPlanner unit tests using injected fake services (no network)."""

import pytest

from app.routing.base import PlanOptions, PlanResult
from app.routing.planners.greedy import GreedyPlanner


@pytest.mark.asyncio
async def test_zero_stops_short_trip_makes_no_lookups(route, start_date, fake_services):
    """0 stops on a short trip inserts nothing and calls no sourcing services."""
    short = route
    short.duration = 7200.0  # 2h — under the 4h hotel-search cutoff
    short.legs[0].duration = 7200.0

    planner = GreedyPlanner()
    result = await planner.plan(
        short, PlanOptions(num_stops=0, budget=400, start=start_date), fake_services.bundle()
    )

    assert isinstance(result, PlanResult)
    assert result.stopping_points == []
    assert result.total_cost == 0
    assert fake_services.find_stop_calls == 0
    assert fake_services.find_hotel_calls == 0


@pytest.mark.asyncio
async def test_inserts_requested_attractions(route, start_date, fake_services):
    """With stops requested, greedy inserts attraction stops of type 'stop'."""
    planner = GreedyPlanner()
    result = await planner.plan(
        route, PlanOptions(num_stops=2, budget=1000, start=start_date), fake_services.bundle()
    )

    stops = [p for p in result.stopping_points if p["type"] == "stop"]
    assert len(stops) == 2
    for s in stops:
        assert "coordinates" in s and len(s["coordinates"]) == 2
        assert "name" in s


@pytest.mark.asyncio
async def test_long_trip_inserts_hotels_and_sums_cost(route, start_date, fake_services):
    """A multi-day trip inserts hotels and totals their price into cost."""
    planner = GreedyPlanner()
    result = await planner.plan(
        route, PlanOptions(num_stops=2, budget=2000, start=start_date), fake_services.bundle()
    )

    hotels = [p for p in result.stopping_points if p["type"] == "hotel"]
    assert len(hotels) >= 1
    expected = sum(h["price"] for h in hotels)
    assert result.total_cost == expected
