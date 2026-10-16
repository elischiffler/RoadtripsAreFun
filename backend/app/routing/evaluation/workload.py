"""Optimistic workload screening, never a global infeasibility proof."""

from datetime import UTC, timedelta
from zoneinfo import ZoneInfo

from app.routing.visit_duration import LEGACY_VISIT_SECONDS, MAX_VISIT_SECONDS, MIN_VISIT_SECONDS


def screen_workload(fixture, scenario):
    policy = scenario.inputs.scheduling_policy
    zones = {node["timezone"] for node in fixture.data["nodes"]}
    start = scenario.departure().astimezone(UTC)
    local_day = scenario.departure().date()
    windows = []
    for index in range(scenario.target_days):
        day = local_day + timedelta(days=index)
        # Give the screening estimate the most generous window across all
        # captured corridor zones; it cannot stand in for actual scheduling.
        begin = (
            start
            if index == 0
            else min(
                policy.at(day, policy.morning_restart, ZoneInfo(zone)).astimezone(UTC)
                for zone in zones
            )
        )
        end = max(
            policy.deadline(
                day, ZoneInfo(zone), final=index == scenario.target_days - 1
            ).astimezone(UTC)
            for zone in zones
        )
        windows.append(
            {
                "start_utc": begin.isoformat(),
                "end_utc": end.isoformat(),
                "active_seconds": max(0, (end - begin).total_seconds()),
            }
        )
    available = sum(window["active_seconds"] for window in windows)
    minimum_visits = scenario.inputs.num_stops * MIN_VISIT_SECONDS
    maximum_visits = scenario.inputs.num_stops * MAX_VISIT_SECONDS
    driving = fixture.baseline.duration
    return {
        "assessment": "screening_estimate",
        "proof_of_infeasibility": False,
        "direct_driving_seconds": driving,
        "requested_visit_seconds": None,
        "minimum_requested_visit_seconds": minimum_visits,
        "maximum_requested_visit_seconds": maximum_visits,
        "legacy_policy_visit_seconds": scenario.inputs.num_stops * LEGACY_VISIT_SECONDS,
        "visit_duration_basis": "bounded_estimates_not_yet_selected",
        "optimistic_active_window_seconds": available,
        "utc_windows": windows,
        "workload_exceeds_screening_windows": driving + minimum_visits > available,
        "reason": "Direct provider duration is an estimate, not a certified minimum; actual scheduling and final roads decide observed outcomes.",
    }
