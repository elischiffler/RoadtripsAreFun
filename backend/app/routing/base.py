"""Core interface and data types shared by every route planner.

A *planner* is an algorithm that, given the raw driving route and the user's
inputs, decides which attractions/hotels to insert and how the trip is
scheduled across days. Every planner consumes the same inputs
(:class:`PlanOptions`) and produces the same output (:class:`PlanResult`), so the
endpoint and every downstream consumer (itinerary, DB storage, frontend) stay
identical regardless of which algorithm ran.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.models.routing_models.routing_models import MapBox

if TYPE_CHECKING:  # avoid a runtime import cycle (services imports base)
    from app.routing.services import RoutingServices

# Default objective weights (see docs/algorithm-analysis.md §2). A trip is scored:
#   score = w_v * attraction_value - w_c * hotel_cost - w_d * detour_hours
# These encode a balanced "see things, but don't overspend or over-detour"
# traveler. Override per-run via PlanOptions.weights.
DEFAULT_WEIGHTS: dict[str, float] = {
    "value": 100.0,  # reward per unit of attraction value (per attraction ~= 1.0)
    "cost": 1.0,  # penalty per dollar of hotel spend
    "detour": 10.0,  # penalty per hour of detour time
}

# Each attraction stop costs a fixed ~2h detour today (matches the scheduler).
_DETOUR_HOURS_PER_STOP = 2.0

# A stopping point is an ad-hoc dict — this loose shape is the de-facto contract
# the itinerary endpoint, CRUD storage, and frontend all depend on. Documented
# here so every planner emits the same keys:
#   name(str), type("stop"|"hotel"|"end"|"generic"), coordinates([lat, lon]),
#   duration(float, filled by the router), price(float, hotels), address, url.
StoppingPoint = dict[str, Any]

MapBox_route = MapBox.MapBox_Route


class PlanningError(Exception):
    """Neutral, algorithm-agnostic planning failure.

    Planners raise this (rather than an HTTP-specific error) so the boundary
    between "the algorithm couldn't build a trip" and "how the API reports it"
    stays clean. The router maps this to an :class:`fastapi.HTTPException`.

    ``status_code`` is an optional hint for the router when a specific upstream
    status should be surfaced (e.g. 404 no-hotel vs 502 bad upstream response).
    """

    def __init__(self, detail: str, status_code: int = 500):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass
class PlanOptions:
    """Everything a planner needs about *what* trip to build.

    Kept as a single object so the :meth:`RoutePlanner.plan` signature stays
    stable as future algorithms need more inputs. ``preferences`` and
    ``weights`` are unused by the greedy/knapsack planners today but reserved so
    the preference-aware (AI/hybrid) planners in the analysis doc can slot in
    without a signature change.
    """

    num_stops: int
    budget: float
    start: datetime
    daily_start: int = 9
    daily_end: int = 16
    # Reserved for future preference-aware planners (see docs/algorithm-analysis.md).
    preferences: dict[str, Any] | None = None
    weights: dict[str, float] | None = None


@dataclass
class PlanMetrics:
    """Comparable stats about a single planning run.

    Populated by :meth:`RoutePlanner.run` (not by ``plan`` itself), so the metric
    logic lives in one place and no planner has to compute it. Used by the
    benchmark harness to compare algorithms head-to-head.
    """

    algorithm: str = ""
    feasible: bool = True  # did it produce a valid trip (vs. raise PlanningError)?
    wall_clock_ms: float = 0.0  # planning wall-clock time
    api_calls: int = 0  # external candidate-sourcing calls made
    num_attractions: int = 0
    num_hotels: int = 0
    total_cost: float = 0.0  # summed hotel cost
    total_detour_hours: float = 0.0  # time lost to attraction detours
    total_value: float = 0.0  # summed attraction value (objective reward term)
    objective_score: float = 0.0  # the scalar §2 score (higher is better)
    error: str | None = None  # failure detail when feasible is False

    def as_dict(self) -> dict[str, Any]:
        return {
            "algorithm": self.algorithm,
            "feasible": self.feasible,
            "wall_clock_ms": round(self.wall_clock_ms, 2),
            "api_calls": self.api_calls,
            "num_attractions": self.num_attractions,
            "num_hotels": self.num_hotels,
            "total_cost": round(self.total_cost, 2),
            "total_detour_hours": round(self.total_detour_hours, 2),
            "total_value": round(self.total_value, 3),
            "objective_score": round(self.objective_score, 3),
            "error": self.error,
        }


@dataclass
class PlanResult:
    """Everything the router needs to assemble the final :class:`Route`.

    Mirrors exactly what the original ``_add_stops`` returned (ordered stopping
    points + summed hotel cost), plus optional :class:`PlanMetrics` attached by
    :meth:`RoutePlanner.run` for benchmarking. ``metrics`` is ``None`` on the
    normal request path (via ``plan``), so it never affects the API response.
    """

    stopping_points: list[StoppingPoint] = field(default_factory=list)
    total_cost: float = 0.0
    metrics: PlanMetrics | None = None

    def as_tuple(self) -> tuple[list[StoppingPoint], float]:
        """Backwards-compatible ``(stopping_points, total_cost)`` view."""
        return self.stopping_points, self.total_cost


def _attraction_value(stop: StoppingPoint) -> float:
    """Objective reward for one attraction, from popularity rank (1 = best).

    Falls back to 1.0 when no rank is present (the current sourcing path doesn't
    persist rank onto the stop dict). Kept in one place so both scoring and the
    knapsack's profit can converge on it later.
    """
    rank = stop.get("rank")
    if isinstance(rank, int) and rank > 0:
        return 1.0 / rank
    return 1.0


def score_trip(
    stopping_points: list[StoppingPoint],
    total_cost: float,
    weights: dict[str, float] | None = None,
) -> tuple[float, dict[str, float]]:
    """Compute the scalar objective score for a finished trip (see analysis §2).

    Returns ``(score, components)`` where components holds the raw
    value/cost/detour terms so the benchmark can report them individually.
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    attractions = [s for s in stopping_points if s.get("type") == "stop"]
    total_value = sum(_attraction_value(s) for s in attractions)
    detour_hours = len(attractions) * _DETOUR_HOURS_PER_STOP
    score = w["value"] * total_value - w["cost"] * total_cost - w["detour"] * detour_hours
    return score, {
        "total_value": total_value,
        "total_detour_hours": detour_hours,
    }


class RoutePlanner(ABC):
    """Interface every routing algorithm implements.

    Implementations live under ``app/routing/planners/`` and are registered by
    name in ``app/routing/registry.py``.
    """

    #: Stable identifier used for registry lookup and the ``algorithm`` request field.
    name: str = ""

    @abstractmethod
    async def plan(
        self,
        initial_route: MapBox_route,
        options: PlanOptions,
        services: RoutingServices,
    ) -> PlanResult:
        """Produce the scheduled stops for ``initial_route``.

        Args:
            initial_route: The raw single-leg Mapbox route from phase 1.
            options: User inputs (stops, budget, start, day window, preferences).
            services: Injected candidate-sourcing and geometry/pricing helpers.

        Returns:
            A :class:`PlanResult` with the ordered stopping points and total cost.

        Raises:
            PlanningError: When a feasible trip cannot be produced.
        """
        raise NotImplementedError

    async def run(
        self,
        initial_route: MapBox_route,
        options: PlanOptions,
        services: RoutingServices,
    ) -> PlanResult:
        """Run :meth:`plan` and attach :class:`PlanMetrics`.

        This is the benchmark/measurement entry point. The request path calls
        ``plan`` directly (no metrics overhead); the benchmark calls ``run`` so it
        gets timing, API-call counts, and the objective score for free — without
        any per-planner metric code.

        A :class:`PlanningError` is captured as an infeasible result rather than
        propagated, so one failing planner doesn't abort a benchmark sweep.
        """
        start = time.perf_counter()
        metrics = PlanMetrics(algorithm=self.name)
        try:
            result = await self.plan(initial_route, options, services)
        except PlanningError as exc:
            metrics.feasible = False
            metrics.error = exc.detail
            metrics.wall_clock_ms = (time.perf_counter() - start) * 1000
            metrics.api_calls = getattr(services, "api_calls", 0)
            return PlanResult(metrics=metrics)

        metrics.wall_clock_ms = (time.perf_counter() - start) * 1000
        metrics.api_calls = getattr(services, "api_calls", 0)
        stops = result.stopping_points
        metrics.num_attractions = sum(1 for s in stops if s.get("type") == "stop")
        metrics.num_hotels = sum(1 for s in stops if s.get("type") == "hotel")
        metrics.total_cost = result.total_cost
        score, components = score_trip(stops, result.total_cost, options.weights)
        metrics.total_value = components["total_value"]
        metrics.total_detour_hours = components["total_detour_hours"]
        metrics.objective_score = score
        result.metrics = metrics
        return result
