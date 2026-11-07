"""Read admitted catalog ideas without changing, rating or scheduling a trip."""

import math
from urllib.parse import urlsplit

from pydantic import ValidationError

from app.catalog.place_context import context_for_admitted_place
from app.catalog.repository import nearby as catalog_nearby
from app.models.guided_planning import (
    AlternativePlace,
    RouteAlternativesRequest,
    RouteAlternativesResponse,
)
from app.routing.visit_calendar import calendar_eligible

MAX_ALTERNATIVES = 12
NOTICE = (
    "Nearby ideas are not in your itinerary. Driving detours, visit times, tickets "
    "and current availability have not been checked."
)


def _public_place(record):
    """Allow only the public display contract, retaining dated source credits."""
    provider_id = record.get("provider_id")
    fields = {
        key: record.get(key)
        for key in (
            "source",
            "name",
            "coordinates",
            "address",
            "url",
            "source_attribution",
            "source_release",
            "source_updated_at",
        )
    }
    url = fields.get("url")
    if url and (not isinstance(url, str) or urlsplit(url).scheme not in {"https", "http"}):
        fields["url"] = None
    return AlternativePlace(
        id=provider_id,
        provider_id=provider_id,
        place_context=context_for_admitted_place(record),
        categories=record.get("categories") or [],
        source_provenance=(record.get("source_provenance") or [])[:8],
        **fields,
    )


def browse_alternatives(payload: RouteAlternativesRequest) -> RouteAlternativesResponse:
    """At most 48 bounded catalog reads; no provider calls or persistent writes.

    The existing repository owns active-generation admission, calendar eligibility
    and source holds. A browse result is deliberately not automatic routing input.
    """
    if payload.geometry is not None:
        return _browse_route(payload)
    places = []
    seen = set(payload.exclude_ids)
    for point in dict.fromkeys(payload.points):
        records = catalog_nearby(
            list(point),
            ["daytime"],
            radius_miles=5,
            limit=MAX_ALTERNATIVES,
            require_visit_calendar=True,
        )
        for record in records:
            try:
                if not isinstance(record, dict) or not calendar_eligible(record):
                    continue
                place = _public_place(record)
            except (ValidationError, TypeError, ValueError, AttributeError):
                continue  # An unusable source row must not become a map pin.
            if place.id in seen or any(
                _distance(place.coordinates, stop) < 0.1 for stop in payload.exclude_coordinates
            ):
                continue
            seen.add(place.id)
            places.append(place)
            if len(places) == MAX_ALTERNATIVES:
                return RouteAlternativesResponse(places=places, notice=NOTICE)
    return RouteAlternativesResponse(places=places, notice=NOTICE)


EARTH_MILES = 3958.7613
MAX_SAMPLES = 48


def _distance(a, b):
    """Great-circle miles for latitude/longitude pairs, including the dateline."""
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlat, dlon = lat2 - lat1, math.radians(b[1] - a[1])
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_MILES * math.asin(math.sqrt(min(1, h)))


def _interpolate(a, b, fraction):
    # Spherical interpolation avoids dateline jumps and uneven longitude spacing.
    def vector(point):
        lat, lon = map(math.radians, point)
        return (math.cos(lat) * math.cos(lon), math.cos(lat) * math.sin(lon), math.sin(lat))

    av, bv = vector(a), vector(b)
    angle = _distance(a, b) / EARTH_MILES
    if angle < 1e-10:
        return a
    if abs(math.sin(angle)) < 1e-10:
        raise ValueError("Antipodal route edges are unsupported")
    left, right = math.sin((1 - fraction) * angle), math.sin(fraction * angle)
    x, y, z = [left * x + right * y for x, y in zip(av, bv, strict=True)]
    return (math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x)))


def route_samples(geometry):
    """Sample distance, not vertex indices; sparse/uneven geometry stays balanced."""
    points = [(lat, lon) for lon, lat in geometry]
    lengths = [_distance(a, b) for a, b in zip(points, points[1:], strict=False)]
    total = sum(lengths)
    if total == 0:
        return [(points[0], 0.0)], total
    count = min(MAX_SAMPLES, max(2, math.ceil(total / 5) + 1))
    samples, edge, elapsed = [], 0, 0.0
    for index in range(count):
        target = total * index / (count - 1)
        while edge < len(lengths) - 1 and elapsed + lengths[edge] < target:
            elapsed += lengths[edge]
            edge += 1
        ratio = min(1, max(0, (target - elapsed) / lengths[edge])) if lengths[edge] else 0
        samples.append((_interpolate(points[edge], points[edge + 1], ratio), target / total))
    return samples, total


def _browse_route(payload):
    samples, total = route_samples(payload.geometry)
    seen = set(payload.exclude_ids)
    buckets = [[] for _ in range(min(MAX_ALTERNATIVES, len(samples)))]
    for point, fraction in samples:
        records = catalog_nearby(
            list(point),
            ["daytime"],
            radius_miles=5,
            limit=MAX_ALTERNATIVES,
            require_visit_calendar=True,
        )
        for record in records:
            try:
                if not isinstance(record, dict) or not calendar_eligible(record):
                    continue
                place = _public_place(record)
            except (ValidationError, TypeError, ValueError, AttributeError):
                continue
            if place.id in seen or any(
                _distance(place.coordinates, stop) < 0.1 for stop in payload.exclude_coordinates
            ):
                continue
            offset = _distance(point, place.coordinates)
            if offset > 5:
                continue
            seen.add(place.id)
            # Offset is to a sampled route point, an upper bound on nearest-route
            # distance. It is deliberately never presented as a road detour.
            place.offset_miles = round(offset, 2)
            place.route_fraction = round(fraction, 5)
            section = min(len(buckets) - 1, int(fraction * len(buckets)))
            buckets[section].append(place)
    places = []
    while len(places) < MAX_ALTERNATIVES and any(buckets):
        for bucket in buckets:
            if bucket and len(places) < MAX_ALTERNATIVES:
                places.append(bucket.pop(0))
    spacing = total / (len(samples) - 1) if len(samples) > 1 else 0
    return RouteAlternativesResponse(
        places=places,
        notice=NOTICE,
        coverage={
            "sample_count": len(samples),
            "sample_spacing_miles": round(spacing, 2),
            "radius_miles": 5,
            "route_miles": round(total, 2),
            "continuous": False,
            "note": "Five-mile samples along the full route; gaps and bounded catalog results can omit places.",
            "offset_kind": "straight_line_to_route_sample",
            "road_detours_checked": False,
            "trip_date_availability_checked": False,
        },
    )
