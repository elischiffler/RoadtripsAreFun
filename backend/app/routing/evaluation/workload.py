"""Optimistic workload screening, never a global infeasibility proof."""

from datetime import UTC, timedelta
from zoneinfo import ZoneInfo


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
    visits = scenario.inputs.num_stops * 7200
    driving = fixture.baseline.duration
    return {
        "assessment": "screening_estimate",
        "proof_of_infeasibility": False,
        "direct_driving_seconds": driving,
        "requested_visit_seconds": visits,
        "optimistic_active_window_seconds": available,
        "utc_windows": windows,
        "workload_exceeds_screening_windows": driving + visits > available,
        "reason": "Direct provider duration is an estimate, not a certified minimum; actual scheduling and final roads decide observed outcomes.",
    }
