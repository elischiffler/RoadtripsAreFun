"""The dependency bundle injected into every planner.

Planners never import ``requests`` or hit an external API directly — they call
through :class:`RoutingServices`. This keeps each planner focused on *algorithm*
logic (SRP), makes them trivially testable with fakes, and lets the greedy and
optimizer planners share one candidate-sourcing implementation.

Two sourcing styles are exposed because different algorithms need different
access patterns:

* ``find_stop`` / ``find_hotel`` — per-point, on-demand lookups. The greedy
  planner uses these as it walks the route.
* ``gather_candidates`` — a batch corridor gather. The knapsack/optimizer
  planners use this to collect the whole candidate set up front.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models.routing_models.routing_models import MapBox

MapBox_route = MapBox.MapBox_Route
Mapbox_step = MapBox.MapBox_Route.Mapbox_leg.Mapbox_step

# Numeric hotel band + its "min-max" string form, as produced by get_price_range.
PriceRange = tuple[tuple[float, float], str]

# --- Callable signatures for the injected dependencies -----------------------

# find_stop(category, lat, lon, radius) -> attraction dict
FindStop = Callable[[str, float, float, int], Awaitable[dict[str, Any]]]

# find_hotel(lat, lon, price_range, check_in, radius=...) -> hotel dict
FindHotel = Callable[..., Awaitable[dict[str, Any]]]

# find_position(coordinates, steps, elapsed_time) -> [lat, lon]  (pure, no I/O)
FindPosition = Callable[[list[list[float]], list[Mapbox_step], float], list[float]]

# get_price_range(remaining_budget, duration_left, stops_left, daily_drive_time) -> PriceRange
GetPriceRange = Callable[..., PriceRange]

# gather_candidates(route, num_candidates, radius) -> list of attraction dicts
# Used by batch/optimizer planners; collects candidates along the route corridor.
GatherCandidates = Callable[..., Awaitable[list[dict[str, Any]]]]


@dataclass
class RoutingServices:
    """Injected dependencies a planner may use.

    ``gather_candidates`` is optional so a planner that only needs per-point
    sourcing (greedy) can be constructed without it.
    """

    find_stop: FindStop
    find_hotel: FindHotel
    find_position: FindPosition
    get_price_range: GetPriceRange
    gather_candidates: GatherCandidates | None = None

    def require_gather(self) -> GatherCandidates:
        """Return ``gather_candidates`` or fail loudly if a planner needs it."""
        if self.gather_candidates is None:
            raise RuntimeError(
                "This planner requires gather_candidates but the service bundle "
                "was built without it."
            )
        return self.gather_candidates


class CountingServices(RoutingServices):
    """A :class:`RoutingServices` that counts external candidate-sourcing calls.

    Every ``find_stop`` / ``find_hotel`` / ``gather_candidates`` call increments
    ``api_calls``. The pure helpers (``find_position`` / ``get_price_range``) are
    *not* counted — they make no external calls. Used by the benchmark harness
    (via :meth:`RoutePlanner.run`) to report each algorithm's API cost, which is
    the real wall-clock driver. Requires no planner changes: the planner just
    sees a normal ``RoutingServices``.
    """

    def __init__(self, inner: RoutingServices):
        self.api_calls = 0
        self._inner = inner
        super().__init__(
            find_stop=self._wrap(inner.find_stop),
            find_hotel=self._wrap(inner.find_hotel),
            find_position=inner.find_position,  # pure, not counted
            get_price_range=inner.get_price_range,  # pure, not counted
            gather_candidates=(
                self._wrap(inner.gather_candidates) if inner.gather_candidates else None
            ),
        )

    def _wrap(self, fn):
        async def wrapper(*args, **kwargs):
            self.api_calls += 1
            return await fn(*args, **kwargs)

        return wrapper


# Late import to avoid a cycle; re-exported for convenience.
__all__ = ["RoutingServices", "CountingServices", "PriceRange", "datetime"]
