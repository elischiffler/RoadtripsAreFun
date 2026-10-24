"""Collect real selection inputs without scheduling or planning a complete trip."""

from datetime import datetime
from time import perf_counter

from app.agent.persona import normalize_weights
from app.agent.provider_diagnostics import collecting_attempts, diagnostic, retry_async
from app.agent.trip_dates import resolve_departure
from app.research.evidence import without_costs
from app.routers.algorithm_lab import resolve_endpoint
from app.routers.routing_api import _build_services
from app.routing.discovery import make_discovery_plan
from app.routing.explanation import capture_explanation, record_explanation
from app.routing.planners.cp_sat import CPSatPlanner
from app.routing.run_metrics import measuring
from app.routing.runtime import in_run, joined
from app.routing.sources.mapbox import call_route
from app.routing.trip_calendar import TripCalendar


@in_run
async def collect_inputs(case):
    """Reuse production discovery/calendar/road checks, stopping before selection."""
    inputs = case["inputs"]
    started = perf_counter()
    envelope = {"input_snapshot": inputs, "error": None}
    with (
        capture_explanation() as explanation,
        collecting_attempts() as attempts,
        measuring() as telemetry,
    ):
        try:
            start, destination = await joined(
                [
                    retry_async(lambda: resolve_endpoint(inputs["start_id"])),
                    retry_async(lambda: resolve_endpoint(inputs["destination_id"])),
                ]
            )
            departure = resolve_departure(
                f"{inputs['departure_date']}T{inputs['departure_time']}", start["timezone"]
            )
            initial = await call_route(*start["coordinates"], *destination["coordinates"])
            envelope.update(
                endpoints={"start": start, "destination": destination},
                direct_route=initial.model_dump(mode="json"),
            )
            weights = normalize_weights(inputs["persona_weights"])
            services = _build_services()
            plan = make_discovery_plan(initial, inputs["num_stops"])
            plan.trip_calendar = TripCalendar(
                datetime.fromisoformat(departure), services.timezone_at
            )
            discovery = await services.cp_sat_candidates(initial, plan, weights)
            candidates = [
                item for item in discovery.candidates if await plan.trip_calendar.eligible(item)
            ]
            record_explanation(weights=weights, discovery=discovery.explanation)
            candidates = await CPSatPlanner._verify_detours(initial, candidates, services)
            record_explanation(
                candidates=candidates,
                baseline_seconds=initial.duration,
                query_points=[query.coordinates for query in plan.queries],
            )
        except Exception as exc:
            envelope["error"] = {
                "code": "capture_failed",
                "message": "Real candidate collection failed; inspect provider diagnostics.",
                **diagnostic(exc),
            }
        envelope.update(
            explanation=explanation,
            attempts=attempts,
            provider_measurements={key: value for key, value in telemetry.items() if key != "lock"},
            runtime_seconds=perf_counter() - started,
        )
    return without_costs(envelope)
