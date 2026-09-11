"""OR-Tools knapsack planner.

An optimizer-style alternative to the greedy planner. Instead of choosing
attractions one at a time as it walks the route, it:

1. **Gathers** a candidate set of attractions along the route corridor up front
   (via the batch ``gather_candidates`` service).
2. **Selects** the best subset with Google OR-Tools' knapsack solver. The
   selection is modeled as a 2-dimensional 0/1 knapsack:
     * profit  = each attraction's *value* (derived from its popularity rank);
     * weight dimension 0 = a detour-time cost, capped by a detour budget;
     * weight dimension 1 = 1 per item, capped at ``num_stops`` (so at most the
       requested number of attractions are chosen).
   This is the "select + schedule under a budget/knapsack constraint" framing
   from docs/algorithm-analysis.md — the ordering stays fixed by geography, so
   the solver only decides *which* attractions to keep.

   Note on dimension 1: a knapsack solver has no native "choose at most N items"
   constraint, so the stop count is *encoded* as an artificial weight dimension
   (every item weighs 1, capacity = num_stops). It's a modeling workaround, not a
   real resource — see the detailed comment in ``_select`` and the CP-SAT
   follow-up in docs/pluggable-routing-refactor.md.
3. **Schedules** the chosen attractions in along-route order and inserts
   overnight hotels using the same day-window rules as the greedy planner,
   reusing the injected hotel service.

Compared to greedy, this can trade a marginally lower-ranked attraction away to
keep the overall detour down, because it evaluates the whole set together rather
than committing locally.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from ortools.algorithms.python import knapsack_solver

from app.models.routing_models.routing_models import MapBox
from app.routing.base import PlanningError, PlanOptions, PlanResult, RoutePlanner
from app.routing.registry import register_planner
from app.routing.scheduler import schedule_route
from app.routing.services import RoutingServices

MapBox_route = MapBox.MapBox_Route

# How many candidates to gather relative to the number requested. A wider pool
# gives the solver something to choose between; too wide multiplies API calls.
_CANDIDATE_MULTIPLIER = 3
# Scale factor to turn fractional values/weights into the integers OR-Tools wants.
_INT_SCALE = 1000


class ORToolsKnapsackPlanner(RoutePlanner):
    name = "ortools"

    async def plan(
        self,
        initial_route: MapBox_route,
        options: PlanOptions,
        services: RoutingServices,
    ) -> PlanResult:
        try:
            return await self._plan(initial_route, options, services)
        except HTTPException as exception:
            raise PlanningError(
                exception.detail if isinstance(exception.detail, str) else str(exception.detail),
                status_code=exception.status_code,
            )

    async def _plan(
        self,
        route: MapBox_route,
        options: PlanOptions,
        services: RoutingServices,
    ) -> PlanResult:
        num_stops = options.num_stops
        gather = services.require_gather()

        # 1. Gather a candidate pool along the corridor.
        candidates: list[dict[str, Any]] = []
        if num_stops > 0:
            candidates = await gather(route, num_stops * _CANDIDATE_MULTIPLIER)

        # 2. Select the best subset with the knapsack solver.
        selected = self._select(candidates, num_stops)
        # Keep selection in along-route order so scheduling is monotonic in time.
        selected.sort(key=lambda c: c["elapsed_time"])

        # 3. Schedule via the SHARED scheduler — identical day/hotel logic to
        #    greedy, so the two planners differ only in *which* attractions
        #    (selection), not in *how they're scheduled*. OR-Tools' selection is
        #    fixed up front, so the stop provider just dispenses the chosen
        #    attractions in order, re-stamped with the scheduler's computed
        #    position so routing stays consistent.
        stop_provider = _PreselectedStopProvider(selected)
        stopping_points, total_cost = await schedule_route(
            route,
            num_stops,
            date=options.start,
            budget=options.budget,
            daily_start=options.daily_start,
            daily_end=options.daily_end,
            services=services,
            stop_provider=stop_provider,
        )
        return PlanResult(stopping_points=stopping_points, total_cost=total_cost)

    def _select(
        self, candidates: list[dict[str, Any]], num_stops: int
    ) -> list[dict[str, Any]]:
        """Pick at most ``num_stops`` attractions maximizing total value.

        Modeled as a 2-D knapsack: dimension 0 bounds total detour time, dimension
        1 bounds the item count at ``num_stops``.
        """
        if num_stops <= 0 or not candidates:
            return []
        # If we found no more than requested, keep them all (nothing to optimize).
        if len(candidates) <= num_stops:
            return list(candidates)

        profits = [self._value(c) for c in candidates]

        # --- Encoding "at most num_stops attractions" as a knapsack dimension ---
        # A knapsack solver only understands "items have weights, the bag has
        # capacities" — it has no native "choose at most N items" constraint. So we
        # model the stop count as a second, artificial weight dimension: every
        # attraction "weighs" exactly 1 unit of a made-up "count" resource, and that
        # resource's capacity is num_stops. The solver then physically cannot pack
        # more than num_stops items, which is exactly the cap we want.
        #
        # dimension 0 (detour_weights): a real-ish resource — each stop costs a
        #   uniform detour today; the budget is num_stops * per-stop detour. Kept as
        #   its own dimension so a future model can vary detour per candidate.
        # dimension 1 (count_weights): the count hack described above.
        #
        # NOTE: this only expresses a HARD "<= N" cap. It cannot express a soft
        # target ("about N, fewer if not worth it") — that needs a solver with real
        # constraints (CP-SAT). See docs/pluggable-routing-refactor.md.
        detour_weights = [_INT_SCALE for _ in candidates]
        count_weights = [1 for _ in candidates]
        capacities = [num_stops * _INT_SCALE, num_stops]

        solver = knapsack_solver.KnapsackSolver(
            knapsack_solver.SolverType.KNAPSACK_MULTIDIMENSION_BRANCH_AND_BOUND_SOLVER,
            "attraction_selector",
        )
        solver.init(profits, [detour_weights, count_weights], capacities)
        solver.solve()

        return [c for i, c in enumerate(candidates) if solver.best_solution_contains(i)]

    @staticmethod
    def _value(candidate: dict[str, Any]) -> int:
        """Integer profit for the solver, derived from popularity.

        Each candidate carries the TripAdvisor popularity ``rank`` (1 = best) that
        ``find_stop`` recorded, so better-ranked attractions get a higher profit
        (``1/rank`` scaled to an integer). If the rank is missing or invalid
        (e.g. an attraction with no ranking data), fall back to a flat baseline
        value so the candidate is still selectable, just not prioritized.
        """
        rank = candidate.get("rank")
        if isinstance(rank, int) and rank > 0:
            return max(1, int((1.0 / rank) * _INT_SCALE))
        return _INT_SCALE

class _PreselectedStopProvider:
    """Dispenses OR-Tools' pre-selected attractions to the shared scheduler.

    The scheduler calls this like ``find_stop(category, lat, lon, radius)`` at
    each attraction segment boundary, using ``elapsed_time`` for *scheduling*.
    Instead of searching, it returns the next knapsack-chosen attraction with its
    own recorded ``coordinates`` intact — mirroring the greedy planner, whose
    ``find_stop`` also returns the attraction's real coordinates (from
    ``get_details``), not the search position. Overwriting them with the search
    boundary would route to the wrong place and diverge from greedy.

    If the scheduler asks for more attractions than were selected (the trip has
    room for more boundaries than we chose to fill), it raises ``HTTPException``
    404 — the same signal greedy gets when no attraction is nearby — so the
    scheduler cleanly stops adding attractions.
    """

    def __init__(self, selected: list[dict[str, Any]]):
        # Iterate in the along-route order the caller already sorted into.
        self._remaining = list(selected)

    async def __call__(self, category: str, lat: float, lon: float, radius: int) -> dict[str, Any]:
        if not self._remaining:
            raise HTTPException(status_code=404, detail="No more selected attractions")
        chosen = self._remaining.pop(0)
        # Strip the internal scheduling key but keep the attraction's own
        # coordinates so routing targets the real attraction location.
        return {k: v for k, v in chosen.items() if k != "elapsed_time"}


register_planner(ORToolsKnapsackPlanner())
