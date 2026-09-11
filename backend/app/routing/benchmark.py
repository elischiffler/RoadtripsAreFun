"""Offline benchmark harness for comparing routing planners.

Runs every registered planner against a fixed set of trip cases using **cached,
deterministic candidate data** (no live API calls, no quota burned), and reports
the comparable :class:`~app.routing.base.PlanMetrics` for each — objective score,
cost, detour, latency, and API-call count.

This is the "offline benchmark with cached candidates" from
docs/algorithm-analysis.md §6: because every planner runs on identical inputs,
any difference in the numbers comes purely from the algorithm.

Usage:
    # From backend/, with the project deps installed:
    python -m app.routing.benchmark            # human-readable table
    python -m app.routing.benchmark --json     # machine-readable JSON

The same runner backs the ``/benchmark`` debug endpoint (see routing_api.py).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.models.routing_models.routing_models import MapBox
from app.routing.base import PlanMetrics, PlanOptions
from app.routing.geometry import find_position
from app.routing.pricing import get_price_range
from app.routing.registry import available_planners, get_planner
from app.routing.services import CountingServices, RoutingServices

MapBox_route = MapBox.MapBox_Route


# ---------------------------------------------------------------------------
# Deterministic offline route + candidate fixtures
# ---------------------------------------------------------------------------


def _build_route(duration_hours: float, start_lonlat, end_lonlat) -> MapBox_route:
    """A synthetic single-leg Mapbox route between two [lon, lat] points."""
    duration = duration_hours * 3600
    distance = duration * 25  # ~25 m/s average; distance isn't scored, so approximate
    mid = [
        (start_lonlat[0] + end_lonlat[0]) / 2,
        (start_lonlat[1] + end_lonlat[1]) / 2,
    ]
    data = {
        "code": "Ok",
        "uuid": "bench",
        "waypoints": [
            {"name": "Start", "location": start_lonlat, "distance": 0},
            {"name": "End", "location": end_lonlat, "distance": 0},
        ],
        "routes": [
            {
                "weight_name": "auto",
                "weight": duration,
                "duration": duration,
                "distance": distance,
                "geometry": {
                    "coordinates": [start_lonlat, mid, end_lonlat],
                    "type": "LineString",
                },
                "legs": [
                    {
                        "weight": duration,
                        "duration": duration,
                        "distance": distance,
                        "summary": "",
                        "steps": [
                            {
                                "distance": distance,
                                "duration": duration,
                                "weight": duration,
                                "mode": "driving",
                                "driving_side": "right",
                                "name": "",
                                "intersections": [],
                                "maneuver": {
                                    "type": "depart",
                                    "instruction": "Drive",
                                    "bearing_after": 90,
                                    "bearing_before": 0,
                                    "location": start_lonlat,
                                },
                                "geometry": {
                                    "coordinates": [start_lonlat, end_lonlat],
                                    "type": "LineString",
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }
    return MapBox.model_validate(data).routes[0]


class CachedServices:
    """Fake candidate sourcing backed by deterministic in-memory data.

    Mimics the real services' behavior (returning attraction/hotel dicts of the
    right shape) but never touches the network, so benchmark runs are repeatable
    and free. ``ranks`` lets a case give candidates differing values so the
    knapsack has something meaningful to optimize.
    """

    def __init__(self, hotel_price: float = 120.0, pool_size: int = 12, ranks=None):
        self.hotel_price = hotel_price
        self.pool_size = pool_size
        # Default: descending quality (rank 1 best). Cycled if shorter than pool.
        self.ranks = ranks or list(range(1, pool_size + 1))

    async def find_stop(self, category, lat, lon, radius):
        # Per-point: return a single attraction at this location (rank unknown here).
        return {
            "coordinates": [float(lat), float(lon)],
            "name": f"Attraction @ {lat:.2f},{lon:.2f}",
            "type": "stop",
            "url": "http://example.com/a",
            "address": "1 Attraction Way",
        }

    async def find_hotel(self, lat, lon, price_range, check_in, radius: int = 30):
        return {
            "coordinates": [float(lat), float(lon)],
            "name": "Cached Hotel",
            "type": "hotel",
            "price": self.hotel_price,
            "address": "1 Hotel Rd",
            "url": "http://example.com/h",
        }

    async def gather_candidates(self, route, num_candidates: int, radius: int = 30):
        n = min(self.pool_size, max(num_candidates, 0))
        duration = route.duration
        out: list[dict[str, Any]] = []
        for i in range(1, n + 1):
            elapsed = duration * i / (n + 1)
            lat, lon = find_position(route.geometry.coordinates, route.legs[0].steps, elapsed)
            out.append(
                {
                    "coordinates": [lat, lon],
                    "name": f"Candidate {i}",
                    "type": "stop",
                    "url": "http://example.com/c",
                    "address": f"{i} Candidate St",
                    "elapsed_time": elapsed,
                    "rank": self.ranks[(i - 1) % len(self.ranks)],
                }
            )
        return out

    def bundle(self) -> RoutingServices:
        return RoutingServices(
            find_stop=self.find_stop,
            find_hotel=self.find_hotel,
            find_position=find_position,
            get_price_range=get_price_range,
            gather_candidates=self.gather_candidates,
        )


@dataclass
class BenchmarkCase:
    """One fixed trip scenario every planner is run against."""

    name: str
    duration_hours: float
    num_stops: int
    budget: float
    hotel_price: float = 120.0
    pool_size: int = 12

    def route(self) -> MapBox_route:
        # LA-ish -> NY-ish corridor; exact coords don't matter for offline scoring.
        return _build_route(self.duration_hours, [-117.93, 33.72], [-74.16, 40.65])

    def services(self) -> CachedServices:
        return CachedServices(hotel_price=self.hotel_price, pool_size=self.pool_size)


# A small, fixed suite. Add cases here to broaden coverage.
DEFAULT_CASES: list[BenchmarkCase] = [
    BenchmarkCase("short_no_stops", duration_hours=2, num_stops=0, budget=400),
    BenchmarkCase("day_trip_2_stops", duration_hours=6, num_stops=2, budget=600),
    BenchmarkCase("cross_country_5_stops", duration_hours=40, num_stops=5, budget=1200),
    BenchmarkCase("tight_budget_4_stops", duration_hours=30, num_stops=4, budget=300),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def run_case(case: BenchmarkCase, algorithms: list[str]) -> list[PlanMetrics]:
    """Run each algorithm against one case; return their metrics."""
    results: list[PlanMetrics] = []
    for name in algorithms:
        planner = get_planner(name)
        # Fresh services + counter per run so api_calls is isolated.
        services = CountingServices(case.services().bundle())
        options = PlanOptions(
            num_stops=case.num_stops, budget=case.budget, start=datetime(2025, 6, 1, 9, 0, 0)
        )
        result = await planner.run(case.route(), options, services)
        metrics = result.metrics or PlanMetrics(algorithm=name, feasible=False)
        results.append(metrics)
    return results


async def run_benchmark(
    cases: list[BenchmarkCase] | None = None, algorithms: list[str] | None = None
) -> dict[str, Any]:
    """Run the full suite and return a structured result payload."""
    cases = cases or DEFAULT_CASES
    algorithms = algorithms or available_planners()
    payload: dict[str, Any] = {"algorithms": algorithms, "cases": []}
    for case in cases:
        metrics = await run_case(case, algorithms)
        payload["cases"].append(
            {
                "case": case.name,
                "num_stops": case.num_stops,
                "budget": case.budget,
                "duration_hours": case.duration_hours,
                "results": [m.as_dict() for m in metrics],
            }
        )
    return payload


# ---------------------------------------------------------------------------
# Pretty-printing
# ---------------------------------------------------------------------------


def format_table(payload: dict[str, Any]) -> str:
    """Render the benchmark payload as a human-readable table."""
    lines: list[str] = []
    headers = ["algorithm", "score", "attractions", "hotels", "cost", "detour_h", "ms", "api"]
    widths = [16, 10, 12, 7, 9, 9, 9, 5]

    def row(cells):
        return "  ".join(str(c).ljust(w) for c, w in zip(cells, widths))

    for case in payload["cases"]:
        lines.append("")
        lines.append(
            f"CASE: {case['case']}  "
            f"(stops={case['num_stops']}, budget=${case['budget']}, "
            f"{case['duration_hours']}h drive)"
        )
        lines.append(row(headers))
        lines.append("-" * (sum(widths) + 2 * len(widths)))
        # Winner (highest score among feasible) marked with a *.
        feasible = [r for r in case["results"] if r["feasible"]]
        best = max((r["objective_score"] for r in feasible), default=None)
        for r in case["results"]:
            mark = " *" if r["feasible"] and r["objective_score"] == best else ""
            score = r["objective_score"] if r["feasible"] else "INFEASIBLE"
            lines.append(
                row(
                    [
                        r["algorithm"] + mark,
                        score,
                        r["num_attractions"],
                        r["num_hotels"],
                        r["total_cost"],
                        r["total_detour_hours"],
                        r["wall_clock_ms"],
                        r["api_calls"],
                    ]
                )
            )
    lines.append("")
    lines.append("(* = best objective score for the case; higher score is better)")
    return "\n".join(lines)


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Compare routing planners offline.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table.")
    parser.add_argument(
        "--algorithms", nargs="*", help="Subset of algorithm names (default: all registered)."
    )
    args = parser.parse_args()

    payload = asyncio.run(run_benchmark(algorithms=args.algorithms))
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(format_table(payload))


if __name__ == "__main__":
    _main()
