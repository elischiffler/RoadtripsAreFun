"""Name -> planner registry ("plug and play" selection).

Adding a new algorithm is a two-line change: implement a
:class:`~app.routing.base.RoutePlanner` under ``planners/`` and register it here.
The router resolves a planner by name (from the request or the
``ROUTING_ALGORITHM`` env var) via :func:`get_planner`.
"""

from __future__ import annotations

from app.routing.base import PlanningError, RoutePlanner

# Default algorithm when neither the request nor the environment specifies one.
DEFAULT_ALGORITHM = "greedy"

_REGISTRY: dict[str, RoutePlanner] = {}


def register_planner(planner: RoutePlanner) -> None:
    """Register a planner instance under its ``name``."""
    if not planner.name:
        raise ValueError("Planner must define a non-empty 'name'.")
    _REGISTRY[planner.name] = planner


def get_planner(name: str) -> RoutePlanner:
    """Look up a registered planner by name.

    Raises:
        PlanningError: 400 if the name is unknown (surfaced as HTTP 400).
    """
    _ensure_loaded()
    planner = _REGISTRY.get(name)
    if planner is None:
        raise PlanningError(
            f"Unknown routing algorithm '{name}'. Available: {', '.join(available_planners())}",
            status_code=400,
        )
    return planner


def available_planners() -> list[str]:
    """Sorted list of registered algorithm names."""
    _ensure_loaded()
    return sorted(_REGISTRY)


def _ensure_loaded() -> None:
    """Import planner modules on first use so they self-register.

    Done lazily to avoid import cycles (planners import base/services, which the
    router also imports) and to keep OR-Tools import cost off the hot path until
    a planner is actually requested.
    """
    if _REGISTRY:
        return
    # Importing each module triggers its register_planner(...) call.
    from app.routing.planners import (
        greedy,  # noqa: F401
        ortools_knapsack,  # noqa: F401
    )
