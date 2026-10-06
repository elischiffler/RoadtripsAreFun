"""Typed budgets and deterministic section-balanced discovery contracts."""

import math
from dataclasses import asdict, dataclass, field
from typing import Any, NamedTuple

from app.routing.geometry import RouteMeasure


@dataclass(frozen=True)
class SearchQuery:
    id: str
    section_id: int
    progress_seconds: float
    coordinates: list[float]


@dataclass
class DiscoveryPlan:
    requested_stops: int
    baseline_seconds: float
    section_count: int
    candidate_cap: int
    initial_searches: int
    maximum_searches: int
    rating_cap: int
    raw_pool_cap: int
    queries: list[SearchQuery] = field(default_factory=list)

    def section(self, seconds):
        return (
            min(self.section_count - 1, int(seconds * self.section_count / self.baseline_seconds))
            if self.baseline_seconds
            else 0
        )

    def snapshot(self):
        return asdict(self)


@dataclass
class DiscoveryResult:
    candidates: list[dict[str, Any]]
    explanation: dict[str, Any]


class SelectedAttraction(NamedTuple):
    route_progress_seconds: float
    candidate: dict[str, Any]


def make_discovery_plan(route, requested_stops):
    """Budget discovery and distribute searches across equal driving-time sections."""
    driving_hours = route.duration / 3600
    section_count = min(12, max(1, math.ceil(driving_hours / 2)))
    candidate_cap = min(60, max(18, 6 * requested_stops + 2 * section_count))
    initial_searches = (
        min(36, max(2 * section_count, 3 * requested_stops, math.ceil(driving_hours)))
        if requested_stops
        else 0
    )
    maximum_searches = (
        min(60, max(initial_searches + section_count, math.ceil(route.distance / 1609.344 / 10)))
        if requested_stops
        else 0
    )
    plan = DiscoveryPlan(
        requested_stops=requested_stops,
        baseline_seconds=route.duration,
        section_count=section_count,
        candidate_cap=candidate_cap,
        initial_searches=initial_searches,
        maximum_searches=maximum_searches,
        rating_cap=2 * candidate_cap,
        raw_pool_cap=3 * candidate_cap,
    )
    measure = RouteMeasure(route)
    searches_per_section = [
        initial_searches // section_count + int(i < initial_searches % section_count)
        for i in range(section_count)
    ]
    # Round-robin order gives every section a search before returning to earlier sections.
    for offset in range(max(searches_per_section, default=0)):
        for section, count in enumerate(searches_per_section):
            if offset < count:
                seconds = route.duration * (section + (offset + 1) / (count + 1)) / section_count
                plan.queries.append(
                    SearchQuery(
                        id=f"s{section}-q{offset}",
                        section_id=section,
                        progress_seconds=seconds,
                        coordinates=measure.position(seconds),
                    )
                )
    return plan


def balanced_pool(records, capacity, sections, rank):
    """Section quotas followed by redistribution of every unused quota."""
    buckets = [
        sorted((item for item in records if item["section_id"] == i), key=rank)
        for i in range(sections)
    ]
    result = []
    while len(result) < capacity and any(buckets):
        for bucket in buckets:
            if bucket and len(result) < capacity:
                result.append(bucket.pop(0))
    return result


def category_order(records):
    """Variety uses only supplied categories; missing categories remain missing."""
    buckets = {}
    for item in sorted(
        records, key=lambda item: (item["provider_rank"], item["place"].provider_id)
    ):
        category = item["place"].categories[0] if item["place"].categories else None
        buckets.setdefault(category, []).append(item)
    output = []
    while any(buckets.values()):
        for category in sorted(buckets, key=lambda key: (key is None, str(key))):
            if buckets[category]:
                output.append(buckets[category].pop(0))
    return output
