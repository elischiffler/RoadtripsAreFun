"""Read admitted catalog ideas without changing, rating or scheduling a trip."""

from urllib.parse import urlsplit

from pydantic import ValidationError

from app.catalog.repository import nearby as catalog_nearby
from app.models.guided_planning import (
    AlternativePlace,
    RouteAlternativesRequest,
    RouteAlternativesResponse,
)

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
        categories=record.get("categories") or [],
        source_provenance=(record.get("source_provenance") or [])[:8],
        **fields,
    )


def browse_alternatives(payload: RouteAlternativesRequest) -> RouteAlternativesResponse:
    """At most eight bounded catalog reads; no provider calls or persistent writes.

    The existing repository owns active-generation admission, calendar eligibility
    and source holds. A browse result is deliberately not automatic routing input.
    """
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
                place = _public_place(record)
            except (ValidationError, TypeError, ValueError, AttributeError):
                continue  # An unusable source row must not become a map pin.
            if place.id in seen:
                continue
            seen.add(place.id)
            places.append(place)
            if len(places) == MAX_ALTERNATIVES:
                return RouteAlternativesResponse(places=places, notice=NOTICE)
    return RouteAlternativesResponse(places=places, notice=NOTICE)
