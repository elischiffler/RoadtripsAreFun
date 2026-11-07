"""Optional reviewed context, attached only after authoritative source admission.

This registry is deliberately separate from pinned source rows, calendars and
persona/rating data. No category templates, model calls or network fallback.
New facts or images require a checked-in primary-source/rights review.
"""

import json
from functools import lru_cache
from pathlib import Path

from app.models.place_context import PlaceContext
from app.routing.visit_calendar import calendar_eligible

REGISTRY_PATH = Path(__file__).with_name("place_context_registry.json")


@lru_cache(maxsize=1)
def _registry():
    data = json.loads(REGISTRY_PATH.read_text())
    if data["schema"] != "roadtrips-reviewed-place-context/1":
        raise ValueError("Unknown place-context registry schema")
    entries = {}
    for entry in data["entries"]:
        identity = entry["identity"]
        key = identity["provider_id"]
        if key in entries:
            raise ValueError("Duplicate reviewed place identity")
        entries[key] = (identity, PlaceContext.model_validate(entry["context"]))
    return entries


def context_for_admitted_place(record):
    """Read display facts for an exact currently admitted source identity.

    Callers must first perform their existing authoritative admission/refresh.
    The extra eligibility check does not replace that boundary. Client-supplied
    place_context, descriptions, URLs and photo metadata are never consulted.
    Name + native ID + source + exact arrival coordinates bind the review; a
    changed identity loses context until reviewed. Publisher URLs may migrate.
    """
    if not isinstance(record, dict) or not calendar_eligible(record):
        return None
    entry = _registry().get(record.get("provider_id"))
    if entry is None:
        return None
    identity, context = entry
    if (
        record.get("source") != identity["source"]
        or record.get("name") != identity["name"]
        or list(record.get("coordinates") or []) != identity["coordinates"]
    ):
        return None
    return context


def route_place_context(stops):
    """A top-level map keeps derived display fields out of exact source rows."""
    result = {}
    for stop in stops or []:
        if stop.get("type") == "stop" and (context := context_for_admitted_place(stop)):
            result[stop["provider_id"]] = context
    return result
