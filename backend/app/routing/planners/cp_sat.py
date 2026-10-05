"""Production attraction selection followed by separate hotel/visit scheduling."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from ortools.sat.python import cp_model  # noqa: F401 - existing injected solver tests

from app.agent.progress import emit, stage
from app.models.routing_models.routing_models import MapBox
from app.routing.base import PlanningError, PlanOptions, PlanResult, RoutePlanner
from app.routing.cp_sat_scheduler import schedule_cp_sat_route
from app.routing.cp_sat_selection import query_count, select_attractions
from app.routing.explanation import record_explanation, record_stage
from app.routing.registry import register_planner
from app.routing.services import RoutingServices

MapBox_route = MapBox.MapBox_Route


class CPSatPlanner(RoutePlanner):
    name = "cp_sat"

    async def plan(
        self, initial_route: MapBox_route, options: PlanOptions, services: RoutingServices
    ) -> PlanResult:
        if services.cp_sat_hotels is None or services.cp_sat_candidates is None:
            raise PlanningError("CP-SAT verified candidate services are not configured", 503)
        if options.num_stops < 0:
            raise PlanningError("num_stops must be nonnegative", 400)

        count = query_count(options.num_stops)
        record_explanation(weights=options.weights or {})
        points = (
            [
                services.find_position(
                    initial_route.geometry.coordinates,
                    initial_route.legs[0].steps,
                    initial_route.duration * j / (count + 1),
                )
                for j in range(1, count + 1)
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
            record_stage(
                "candidates",
                "complete",
                f"Collected {len(candidates)} verified candidates; ratings are AI estimates.",
            )
            with stage("route.solver", candidates=len(candidates)):
                selected = self._select(candidates, points, options.num_stops)
            record_stage(
                "selection",
                "complete",
                f"Selected {len(selected)} attractions; see actual solver status.",
            )
            emit("route.selected", selected=len(selected))
            with stage("route.schedule"):
                stops, cost = await schedule_cp_sat_route(
                    initial_route, selected, options, services
                )
            record_stage(
                "scheduling",
                "complete",
                f"Separate scheduler produced {len(stops)} attraction/hotel stops; final road timing still needs verification.",
            )
        except HTTPException as exc:
            raise PlanningError(str(exc.detail), exc.status_code) from exc
        return PlanResult(stopping_points=stops, total_cost=cost)

    @staticmethod
    def _select(
        candidates: list[dict[str, Any]], query_points: list[list[float]], num_stops: int
    ) -> list[tuple[int, dict[str, Any]]]:
        return select_attractions(candidates, query_points, num_stops)


register_planner(CPSatPlanner())
