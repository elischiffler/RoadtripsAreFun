"""Run the actual discovery, planner, scheduler, timing and itinerary with frozen providers."""

import copy
import json
from datetime import datetime
from types import SimpleNamespace

from geopy.distance import geodesic

from app.catalog import admission
from app.catalog.identity import catalog_source_id
from app.models.itinerary_models import Itinerary_Payload
from app.models.routing_models.routing_models import Route
from app.routers.itinerary_api import build_itinerary
from app.routing.base import PlanningError, PlanOptions
from app.routing.cp_sat_selection import select_attractions
from app.routing.evaluation.fixtures import EvidenceError, Fixture, route_key, validate_route
from app.routing.evaluation.methods import comparator
from app.routing.explanation import record_stage
from app.routing.geometry import find_position
from app.routing.planners.cp_sat import CPSatPlanner
from app.routing.pricing import get_price_range
from app.routing.profiles import crossmatch
from app.routing.run_metrics import fingerprint
from app.routing.services import RoutingServices
from app.routing.sources.mapbox import require_route_capacity
from app.routing.sources.persona_candidates import (
    CalendarFilteredPlaces,
    LivePlaceProvider,
    attraction_candidates,
)
from app.routing.sources.visit_durations import duration_context, duration_context_hash
from app.routing.travel_timing import apply_timing
from app.routing.visit_calendar import VisitCalendarConflict, calendar_eligible
from app.routing.visit_duration import MIN_VISIT_SECONDS, fallback_duration


class FrozenProviders(LivePlaceProvider):
    def __init__(self, fixture):
        self.fixture = fixture
        self.data = fixture.data
        self.calls = {}
        self.by_id = {item["provider_id"]: item for item in self.data["attractions"]}
        self.aliases = {
            f"__capture_id__{fingerprint(key)}": item for key, item in self.by_id.items()
        }

    def count(self, name):
        self.calls[name] = self.calls.get(name, 0) + 1

    def catalog_records(self, source_ids):
        """Project source facts from the validated capture, never the active DB."""
        if not isinstance(self.fixture, Fixture):
            raise EvidenceError("frozen itinerary facts require a validated fixture")
        self.count("captured_catalog_fact_reads")
        return {
            sid: {
                "coordinates": copy.deepcopy(item["coordinates"]),
                "categories": copy.deepcopy(item.get("categories", [])),
                "source_provenance": copy.deepcopy(item.get("source_provenance", [])),
                "source_attribution": item.get("source_attribution"),
                "source_updated_at": item.get("source_updated_at"),
                "source_release": item.get("source_release"),
            }
            for item in self.data["attractions"]
            if (sid := catalog_source_id(item["provider_id"])) in source_ids
        }

    async def attractions_near(self, point, *, require_visit_calendar=False, trip_calendar=None):
        self.count("captured_catalog_queries")
        # Filter the complete immutable subset before the same five-mile/60 quota.
        # Otherwise closed venues could consume the slots of usable destinations.
        output, tight, excluded = [], [], []
        for item in sorted(
            self.data["attractions"],
            key=lambda item: (item.get("provider_rank", 0), item["provider_id"]),
        ):
            if geodesic(point, item["coordinates"]).miles > 5:
                continue
            usable = (
                admission.routing_eligible(item)
                and (not admission.requires_admission(item) or calendar_eligible(item))
                and (
                    await trip_calendar.eligible(item, dwell=MIN_VISIT_SECONDS)
                    if trip_calendar is not None
                    else not require_visit_calendar or calendar_eligible(item)
                )
            )
            if not usable:
                excluded.append(item["provider_id"])
                continue
            aliased = {
                **copy.deepcopy(item),
                "name": f"__capture_id__{fingerprint(item['provider_id'])}",
            }
            if trip_calendar is None or await trip_calendar.eligible(item):
                output.append(aliased)
            elif len(tight) < 60:
                tight.append(aliased)
            if len(output) == 60:
                break
        return CalendarFilteredPlaces((output + tight)[:60], excluded)

    def complete(self, messages, tools):
        self.count("captured_rating_reads")
        marker = " Rate only these source-record names, preserving each exactly: "
        prompt = messages[-1].content
        if marker not in prompt:
            raise EvidenceError("offline ratings require exact captured source names")
        names = json.loads(prompt.split(marker, 1)[1])
        by_name = self.aliases
        if any(name not in by_name for name in names):
            raise EvidenceError("captured rating miss")
        return SimpleNamespace(
            content=json.dumps(
                {
                    "candidates": [
                        {"name": name, "attribute_ratings": by_name[name]["attribute_ratings"]}
                        for name in names
                    ]
                }
            )
        )

    async def candidates(self, route, plan, weights):
        result = await attraction_candidates(
            route, plan, weights, ai=self, places=self, duration_estimator=self.durations
        )
        for item in result.explanation.get("rated_candidates", []):
            original = self.by_id[item["provider_id"]]
            item["name"] = original["name"]
            for key in ("source_generation", "rating_capture_id", "evidence_references"):
                if key in original:
                    item[key] = original[key]
        for item in result.candidates:
            original = self.by_id[item["provider_id"]]
            item["name"] = original["name"]
            for key in ("source_generation", "rating_capture_id", "evidence_references"):
                if key in original:
                    item[key] = original[key]
        return result

    async def durations(self, candidates, weights, _ai):
        """Read only context-matched captures; no fresh AI call or process cache.

        The fixture loader validates bounds and real capture provenance. Missing
        captures use the same conservative fallback and remain visibly labeled.
        Original names are restored solely for the canonical context signature.
        """
        captures = getattr(self.fixture, "duration_estimates", {})
        result = []
        for candidate in candidates:
            original = self.by_id[candidate["provider_id"]]
            context = duration_context({**candidate, "name": original["name"]}, weights)
            key = (candidate["provider_id"], duration_context_hash(context))
            estimate = captures.get(key)
            self.count("captured_duration_reads" if estimate else "duration_fallbacks")
            result.append(
                {
                    **candidate,
                    "visit_duration": copy.deepcopy(estimate)
                    if estimate
                    else fallback_duration("missing_estimate").model_dump(),
                }
            )
        return result

    async def hotels(self, position, check_in, price_range, weights, rooms):
        self.count("captured_hotel_queries")
        allocation = [room.model_dump() for room in rooms]
        return [
            {**copy.deepcopy(item), **crossmatch(weights, item["attribute_ratings"]).model_dump()}
            for item in self.data.get("hotel_offers", [])
            if item["check_in_date"] == check_in.isoformat()
            and item["hotel_rooms"] == allocation
            and geodesic(position, item["coordinates"]).miles <= 30
        ][:30]

    async def timezone(self, position):
        self.count("captured_timezone_reads")
        for lookup in [*self.data["nodes"], *self.data.get("timezone_lookups", [])]:
            if lookup["coordinates"] == position:
                return lookup["timezone"]
        if self.fixture.manifest.evidence_type == "synthetic_unit_only" and self.data.get(
            "synthetic_single_timezone"
        ):
            return self.data["synthetic_single_timezone"]
        raise EvidenceError("captured timezone lookup missing; no inferred or live fallback")

    async def road(self, start_lat, start_lon, end_lat, end_lon, waypoints=None):
        points = [[start_lat, start_lon]]
        for pair in (waypoints or "").split(";"):
            if pair:
                lon, lat = map(float, pair.split(","))
                points.append([lat, lon])
        points.append([end_lat, end_lon])
        require_route_capacity(len(points))
        self.count("captured_route_reads")
        record = self.data.get("routes", {}).get(route_key(points))
        if record is None:
            raise EvidenceError(
                "captured exact route request missing; matrix sums are not reroutes"
            )
        return validate_route(copy.deepcopy(record["response"]), points)

    async def denied(self, *args, **kwargs):
        raise EvidenceError("uncaptured provider capability requested")

    def services(self):
        return RoutingServices(
            find_stop=self.denied,
            find_hotel=self.denied,
            find_position=find_position,
            get_price_range=get_price_range,
            cp_sat_candidates=self.candidates,
            cp_sat_hotels=self.hotels,
            candidate_route=self.road,
            timezone_at=self.timezone,
        )


class EvaluationPlanner(CPSatPlanner):
    def __init__(self, config, method):
        self.config = config
        self.method = method

    def _select(self, candidates, query_points, num_stops, baseline_seconds):
        if self.method != "cp_sat":
            return comparator(
                self.method, candidates, query_points, num_stops, baseline_seconds, self.config
            )
        return select_attractions(
            candidates, query_points, num_stops, baseline_seconds, config=self.config
        )

    @staticmethod
    async def _verify_detours(route, candidates, services):
        checked = await CPSatPlanner._verify_detours(route, candidates, services)
        for item in checked:
            item["detour_provenance"]["source"] = (
                "captured_exact_origin_via_candidate_to_destination"
            )
        return checked


async def pipeline(fixture, scenario, config, method, envelope, progress):
    if fixture.manifest.coverage != "recorded_pipeline":
        raise EvidenceError("recorded full-pipeline road/hotel/timezone evidence required")
    provider = FrozenProviders(fixture)
    envelope["offline_provider_reads"] = provider.calls
    inputs = scenario.inputs
    services = provider.services()
    options = PlanOptions(
        num_stops=inputs.num_stops,
        budget=inputs.budget,
        start=scenario.departure(),
        weights=inputs.persona_weights,
        scheduling_policy=inputs.scheduling_policy,
        traveler_count=inputs.traveler_count,
        hotel_rooms=inputs.hotel_rooms,
    )
    origin = fixture.nodes[fixture.data["origin_id"]]
    end = fixture.nodes[fixture.data["destination_id"]]
    # Match production's bounded reselection after actual road timing conflicts.
    for _ in range(61):
        try:
            progress("discovery_selection_scheduling")
            result = await EvaluationPlanner(config, method).plan(
                fixture.baseline, options, services
            )
            stops = result.stopping_points
            progress("final_reroute")
            points = [stop["coordinates"] for stop in stops]
            final = await provider.road(
                *origin["coordinates"],
                *end["coordinates"],
                ";".join(f"{lon},{lat}" for lat, lon in points),
            )
            for stop, leg in zip(stops, final.legs):
                stop.update(duration=leg.duration, distance=leg.distance)
            stops.append(
                {
                    "type": "end",
                    "name": "Arrive at your destination",
                    "coordinates": end["coordinates"],
                    "duration": final.legs[-1].duration,
                    "distance": final.legs[-1].distance,
                }
            )
            for stop in stops:
                stop["timezone"] = await provider.timezone(stop["coordinates"])
            route = Route(
                coordinates=[origin["coordinates"], *points, end["coordinates"]],
                distance=final.distance,
                duration=final.duration,
                steps=[],
                stops=stops,
                geometry=final.geometry,
                cost=result.total_cost,
                scheduling_policy=options.scheduling_policy,
                start_timezone=origin["timezone"],
                departure_time=options.start,
                traveler_count=inputs.traveler_count,
                hotel_rooms=inputs.hotel_rooms,
                warnings=[stop["warning"] for stop in stops if stop.get("warning")] or None,
            )
            progress("final_timing")
            try:
                apply_timing(
                    route.stops, options.start, options.scheduling_policy, origin["timezone"]
                )
            finally:
                envelope["route"] = route.model_dump(mode="json")
            break
        except VisitCalendarConflict as exc:
            if exc.provider_id in options.excluded_provider_ids:
                raise
            options.excluded_provider_ids |= {exc.provider_id}
            record_stage("availability", "excluded_after_actual_road_route", exc.detail)
    else:
        raise PlanningError("Source-calendar reselection limit exceeded", 422)
    if fixture.reviews:
        for stop in route.stops:
            if stop["type"] == "stop":
                review = fixture.reviews[stop["provider_id"]]
                if review.valid_through < datetime.fromisoformat(stop["arrival_time"]).date():
                    raise EvidenceError("access review expires before observed attraction arrival")
    progress("itinerary")
    itinerary = await build_itinerary(
        Itinerary_Payload(route=route, start_time=options.start),
        catalog_lookup=provider.catalog_records,
    )
    envelope["itinerary"] = [day.model_dump(mode="json") for day in itinerary]
    progress("hotel_quote_validation")
    if any(
        not hotel.get("room_offers") or len(hotel["room_offers"]) != len(inputs.hotel_rooms)
        for hotel in stops
        if hotel["type"] == "hotel"
    ):
        raise PlanningError("Incomplete captured room-night quotes", 422)
    return provider.calls
