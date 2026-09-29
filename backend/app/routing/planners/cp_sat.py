"""Opt-in selection of verified attractions with CP-SAT."""

from __future__ import annotations

import math
from typing import Any

from fastapi import HTTPException
from geopy.distance import geodesic
from ortools.sat.python import cp_model

from app.models.routing_models.routing_models import MapBox
from app.routing.base import PlanningError, PlanOptions, PlanResult, RoutePlanner
from app.routing.cp_sat_scheduler import schedule_cp_sat_route
from app.routing.registry import register_planner
from app.routing.services import RoutingServices

MapBox_route = MapBox.MapBox_Route
_MIN_UTILITY = 0.60
_MAX_CANDIDATES = 30
_UTILITY_SCALE = 1_000_000


def _valid_coordinates(value: Any) -> bool:
    return (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(c, (float, int)) and math.isfinite(c) for c in value)
        and -90 <= value[0] <= 90
        and -180 <= value[1] <= 180
    )


class CPSatPlanner(RoutePlanner):
    name = "cp_sat"

    async def plan(
        self, initial_route: MapBox_route, options: PlanOptions, services: RoutingServices
    ) -> PlanResult:
        if services.cp_sat_hotels is None or services.cp_sat_candidates is None:
            raise PlanningError("CP-SAT verified candidate services are not configured", 503)
        if options.num_stops < 0:
            raise PlanningError("num_stops must be nonnegative", 400)

        query_count = min(30, max(6, 3 * options.num_stops)) if options.num_stops else 0
        points = (
            [
                services.find_position(
                    initial_route.geometry.coordinates,
                    initial_route.legs[0].steps,
                    initial_route.duration * j / (query_count + 1),
                )
                for j in range(1, query_count + 1)
            ]
            if initial_route.duration > 0
            else []
        )
        try:
            candidates = (
                await services.cp_sat_candidates(initial_route, points, options.weights or {})
                if points
                else []
            )
            selected = self._select(candidates, points, options.num_stops)
            stops, cost = await schedule_cp_sat_route(initial_route, selected, options, services)
        except HTTPException as exc:
            raise PlanningError(str(exc.detail), exc.status_code) from exc
        return PlanResult(stopping_points=stops, total_cost=cost)

    @staticmethod
    def _select(
        candidates: list[dict[str, Any]], query_points: list[list[float]], num_stops: int
    ) -> list[tuple[int, dict[str, Any]]]:
        if not isinstance(candidates, list) or len(candidates) > _MAX_CANDIDATES:
            raise PlanningError("Verified attraction candidate limit exceeded", 502)
        if not query_points or num_stops <= 0:
            return []

        eligible: list[tuple[int, dict[str, Any]]] = []
        seen: set[str] = set()
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            provider_id = candidate.get("provider_id")
            utility = candidate.get("utility")
            coords = candidate.get("coordinates")
            if (
                not isinstance(provider_id, str)
                or not provider_id
                or provider_id in seen
                or not isinstance(candidate.get("name"), str)
                or not candidate["name"]
                or not _valid_coordinates(coords)
                or not isinstance(utility, (float, int))
                or not math.isfinite(utility)
                or not _MIN_UTILITY <= utility <= 1
            ):
                continue
            seen.add(provider_id)
            query_index = min(
                range(len(query_points)),
                key=lambda i: (geodesic(coords, query_points[i]).meters, i),
            )
            eligible.append((query_index, candidate))

        eligible.sort(key=lambda item: (item[0], item[1]["provider_id"]))
        if not eligible:
            return []

        model = cp_model.CpModel()
        variables = [model.NewBoolVar(f"candidate_{i}") for i in range(len(eligible))]
        model.Add(sum(variables) <= num_stops)
        for query_index in {item[0] for item in eligible}:
            model.Add(
                sum(variables[i] for i, item in enumerate(eligible) if item[0] == query_index) <= 1
            )

        # A one-unit utility gain dominates every possible tie term. Stable
        # ordering and a single search worker make equal-score runs repeatable.
        tie_bound = len(eligible) * (len(eligible) + 1)
        model.Maximize(
            sum(
                (
                    round((item[1]["utility"] - _MIN_UTILITY) * _UTILITY_SCALE) * (tie_bound + 1)
                    + len(eligible)
                    - i
                )
                * variables[i]
                for i, item in enumerate(eligible)
            )
        )
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 5.0
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 0
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            detail = (
                "CP-SAT found no feasible selection"
                if status == cp_model.INFEASIBLE
                else "CP-SAT selection timed out"
            )
            raise PlanningError(detail, 503)
        return [item for i, item in enumerate(eligible) if solver.Value(variables[i])]


register_planner(CPSatPlanner())
