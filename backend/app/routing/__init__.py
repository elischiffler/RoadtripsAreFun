"""Pluggable route-planning algorithm layer.

This package holds the swappable "planner" algorithms (greedy, OR-Tools knapsack,
...) behind a single :class:`~app.routing.base.RoutePlanner` interface, plus the
shared infrastructure they depend on (candidate sourcing, geometry, pricing).

The router (`app.routers.routing_api`) selects a planner by name via
:func:`~app.routing.registry.get_planner`, builds a
:class:`~app.routing.services.RoutingServices` bundle of injected dependencies,
and calls ``planner.plan(...)``. Adding a new algorithm means dropping a module
under ``planners/`` and registering it in ``registry.py`` — no endpoint changes.
"""

from app.routing.base import (
    DEFAULT_WEIGHTS,
    PlanMetrics,
    PlanningError,
    PlanOptions,
    PlanResult,
    RoutePlanner,
    score_trip,
)
from app.routing.registry import available_planners, get_planner, register_planner
from app.routing.services import CountingServices, RoutingServices

__all__ = [
    "DEFAULT_WEIGHTS",
    "PlanMetrics",
    "PlanOptions",
    "PlanResult",
    "PlanningError",
    "RoutePlanner",
    "RoutingServices",
    "CountingServices",
    "score_trip",
    "get_planner",
    "register_planner",
    "available_planners",
]
