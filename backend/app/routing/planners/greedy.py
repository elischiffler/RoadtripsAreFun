"""Greedy single-pass planner — the original MyRoadtrip algorithm.

Walks the initial single-leg route once in simulated time, committing to a
locally-best choice at each decision point: end the day at the best in-budget
hotel, or stop for the best-ranked nearby attraction at a segment boundary. It
never backtracks. See docs/algorithm-analysis.md §3 for the full characterization.

The day/hotel scheduling loop now lives in the shared
:func:`app.routing.scheduler.schedule_route`. Greedy is defined by its
*selection* behavior: it discovers attractions on the fly, so it simply hands the
live ``services.find_stop`` to the scheduler as the stop provider. The scheduler
is a verbatim extraction of the former ``_add_stops``, so greedy's output is
unchanged.
"""

from __future__ import annotations

from fastapi import HTTPException

from app.models.routing_models.routing_models import MapBox
from app.routing.base import PlanningError, PlanOptions, PlanResult, RoutePlanner
from app.routing.registry import register_planner
from app.routing.scheduler import schedule_route
from app.routing.services import RoutingServices

MapBox_route = MapBox.MapBox_Route


class GreedyPlanner(RoutePlanner):
    name = "greedy"

    async def plan(
        self,
        initial_route: MapBox_route,
        options: PlanOptions,
        services: RoutingServices,
    ) -> PlanResult:
        try:
            # Greedy's "selection" is on-the-fly: the scheduler asks for an
            # attraction at each segment boundary and greedy answers with the live
            # find_stop lookup at that position.
            stopping_points, total_cost = await schedule_route(
                initial_route,
                options.num_stops,
                date=options.start,
                budget=options.budget,
                daily_start=options.daily_start,
                daily_end=options.daily_end,
                services=services,
                stop_provider=services.find_stop,
            )
        except HTTPException as exception:
            # Preserve the original status code at the neutral boundary.
            raise PlanningError(
                exception.detail if isinstance(exception.detail, str) else str(exception.detail),
                status_code=exception.status_code,
            )
        return PlanResult(stopping_points=stopping_points, total_cost=total_cost)


register_planner(GreedyPlanner())
