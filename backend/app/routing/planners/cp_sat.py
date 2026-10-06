"""Production attraction selection followed by separate hotel/visit scheduling."""

from __future__ import annotations

import math
from typing import Any

from fastapi import HTTPException

from app.agent.progress import emit, stage
from app.models.routing_models.routing_models import MapBox
from app.routing.base import PlanningError, PlanOptions, PlanResult, RoutePlanner
from app.routing.cp_sat_scheduler import schedule_cp_sat_route
from app.routing.cp_sat_selection import select_attractions
from app.routing.discovery import DiscoveryResult, SelectedAttraction, make_discovery_plan
from app.routing.explanation import record_explanation, record_stage
from app.routing.registry import register_planner
from app.routing.runtime import in_run, joined, threaded
from app.routing.services import RoutingServices
from app.routing.sources.mapbox import UnusableRoadRoute

MapBox_route = MapBox.MapBox_Route


class CPSatPlanner(RoutePlanner):
    name = "cp_sat"

    @in_run
    async def plan(
        self, initial_route: MapBox_route, options: PlanOptions, services: RoutingServices
    ) -> PlanResult:
        """Run discovery, road checks, CP-SAT selection, and daily scheduling.

        Inputs are the baseline route, validated trip options, and provider services.
        Returns scheduled attraction/hotel stops and their hotel quote total.
        The caller recalculates the complete road route and validates final timing.
        """
        if services.cp_sat_hotels is None or services.cp_sat_candidates is None:
            raise PlanningError("CP-SAT verified candidate services are not configured", 503)
        if options.num_stops < 0:
            raise PlanningError("num_stops must be nonnegative", 400)

        discovery_plan = make_discovery_plan(initial_route, options.num_stops)
        query_points = [query.coordinates for query in discovery_plan.queries]
        record_explanation(weights=options.weights or {})
        emit(
            "route.samples",
            queries=len(query_points),
            maximumQueries=discovery_plan.maximum_searches,
            sections=discovery_plan.section_count,
            requestedStops=options.num_stops,
        )
        try:
            with stage("route.gathering"):
                if options.num_stops:
                    discovery = await services.cp_sat_candidates(
                        initial_route, discovery_plan, options.weights or {}
                    )
                else:
                    discovery = DiscoveryResult(
                        [], {"plan": discovery_plan.snapshot(), "stop_reason": "zero_requested"}
                    )
                candidates = discovery.candidates
                record_explanation(discovery=discovery.explanation)
            with stage("route.detours", candidates=len(candidates)):
                candidates = await self._verify_detours(initial_route, candidates, services)
            record_stage(
                "candidates",
                "complete",
                f"Collected {len(candidates)} verified candidates; ratings are AI estimates.",
            )
            with stage("route.solver", candidates=len(candidates)):
                if options.num_stops:
                    selected = await threaded(
                        "solver",
                        self._select,
                        candidates,
                        query_points,
                        options.num_stops,
                        initial_route.duration,
                    )
                else:
                    selected = []
                    record_explanation(
                        candidates=[],
                        query_points=[],
                        solver={
                            "status": "NOT_RUN",
                            "skip_reason": "zero_requested",
                            "objective_direction": "minimize",
                            "requested_stops": 0,
                            "eligible_count": 0,
                            "selected_count": 0,
                            "candidate_count": 0,
                        },
                    )
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
        candidates: list[dict[str, Any]],
        query_points: list[list[float]],
        num_stops: int,
        baseline_seconds: float,
    ) -> list[SelectedAttraction]:
        """Pass road-checked records and trip limits to the CP-SAT selection function."""
        return select_attractions(candidates, query_points, num_stops, baseline_seconds)

    @staticmethod
    async def _verify_detours(route, candidates, services):
        """Measure the extra road driving through each candidate before selection.

        Inputs are the baseline route, candidate records, and the road provider.
        Returns usable candidates with detour seconds and measurement provenance.
        Unusable individual routes are excluded; general provider errors propagate.
        """
        if not candidates:
            return []
        if services.candidate_route is None:
            raise PlanningError("Live candidate road verification is not configured", 503)
        start_lon, start_lat = route.geometry.coordinates[0]
        end_lon, end_lat = route.geometry.coordinates[-1]

        records = [{**candidate, "road_check_status": "pending"} for candidate in candidates]
        record_explanation(road_checks=records)

        async def verify(candidate):
            lat, lon = candidate["coordinates"]
            with stage("attractions.detour", providerId=candidate["provider_id"]):
                try:
                    measured = await services.candidate_route(
                        start_lat, start_lon, end_lat, end_lon, f"{lon},{lat}"
                    )
                except UnusableRoadRoute:
                    return {**candidate, "road_exclusion_reason": "no_road_route"}
            if (
                measured is None
                or len(measured.legs) != 2
                or not math.isfinite(measured.duration)
                or measured.duration < 0
                or any(not math.isfinite(leg.duration) or leg.duration < 0 for leg in measured.legs)
            ):
                return {**candidate, "road_exclusion_reason": "unusable_solo_road_route"}
            extra = measured.duration - route.duration
            # Solo detours estimate selection cost; the full route is validated later.
            return {
                **candidate,
                "detour_seconds": max(0.0, extra),
                "detour_raw_seconds": extra,
                "detour_provenance": {
                    "source": "live_mapbox_origin_via_candidate_to_destination",
                    "solo_duration_seconds": measured.duration,
                    "baseline_seconds": route.duration,
                },
            }

        async def retain(index, candidate):
            result = await verify(candidate)
            records[index] = {
                **result,
                "road_check_status": "excluded"
                if "road_exclusion_reason" in result
                else "verified",
            }
            return records[index]

        records = await joined(
            [retain(index, candidate) for index, candidate in enumerate(candidates)]
        )
        record_explanation(road_checks=records)
        return [item for item in records if "road_exclusion_reason" not in item]


register_planner(CPSatPlanner())
