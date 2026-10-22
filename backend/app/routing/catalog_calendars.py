"""Refresh active catalog facts before reusing serialized trip calendars."""

from collections.abc import Callable

from app.catalog import admission, repository
from app.catalog.identity import PREFIXES, catalog_source_id
from app.routing.base import PlanningError
from app.routing.runtime import threaded
from app.routing.visit_calendar import VisitCalendarConflict, calendar_eligible

CatalogLookup = Callable[[list[str]], dict[str, dict]]


def _explicit_calendar(record):
    provenance = record.get("source_provenance", [])
    if not isinstance(provenance, list):
        return True
    return any(isinstance(fact, dict) and "source_visit_calendar" in fact for fact in provenance)


def explicit_calendar_ineligible(record):
    return not isinstance(record.get("source_provenance", []), list) or (
        (admission.requires_admission(record) or _explicit_calendar(record))
        and not calendar_eligible(record)
    )


async def refresh_for_timing(stops, *, catalog_lookup: CatalogLookup | None = None):
    """Refresh one batch and enforce holds using the caller's authoritative facts.

    Live callers use the active catalog. Offline reconstruction supplies a
    validated frozen-fixture lookup through trusted Python code, never HTTP input.
    Missing identities, changed arrivals and held calendars fail identically.
    """
    sources = {source for _, source in PREFIXES} | {"overture"}
    for stop in stops:
        if stop.get("type") == "hotel" and "evening_suggestions" in stop:
            suggestions = stop["evening_suggestions"]
            stop["evening_suggestions"] = (
                [record for record in suggestions if isinstance(record, dict)]
                if isinstance(suggestions, list)
                else []
            )

    def marked(record):
        return (
            admission.requires_admission(record)
            or record.get("source") in sources
            or str(record.get("provider_id", "")).startswith(
                ("overture:", *(prefix for prefix, _ in PREFIXES))
            )
            or any(
                isinstance(fact, dict)
                and fact.get("dataset")
                in {"Roadtrips active catalog", "Roadtrips attributed calendar enrichment"}
                for fact in (
                    record.get("source_provenance", [])
                    if isinstance(record.get("source_provenance", []), list)
                    else []
                )
            )
        )

    main = [
        stop
        for stop in stops
        if stop.get("type") == "stop" or marked(stop) or _explicit_calendar(stop)
    ]
    optional = [
        suggestion
        for stop in stops
        if stop.get("type") == "hotel"
        for suggestion in stop.get("evening_suggestions", [])
    ]
    for record in main:
        if marked(record) and catalog_source_id(record.get("provider_id")) is None:
            raise PlanningError("Catalog visit identity is missing; replan this trip", 422)
    discarded = {
        id(record)
        for record in optional
        if marked(record) and catalog_source_id(record.get("provider_id")) is None
    }
    records = main + [record for record in optional if id(record) not in discarded]
    identifiers = list(
        dict.fromkeys(
            sid for record in records if (sid := catalog_source_id(record.get("provider_id")))
        )
    )
    current = {}
    if identifiers:
        try:
            current = await threaded(
                "catalog",
                repository.current_records if catalog_lookup is None else catalog_lookup,
                identifiers,
            )
        except Exception:
            if any(catalog_source_id(record.get("provider_id")) for record in main):
                raise PlanningError(
                    "Current place access could not be verified; retry this itinerary", 503
                ) from None
            # Optional-only lookup failures remove suggestions without failing
            # an otherwise valid route. Never fall back to stale source facts.
    for record in records:
        sid = catalog_source_id(record.get("provider_id"))
        if sid is not None and sid in current:
            facts = current[sid]
            if record.get("coordinates") != facts["coordinates"]:
                if any(record is suggestion for suggestion in optional):
                    discarded.add(id(record))
                    continue
                raise VisitCalendarConflict(
                    record["provider_id"], "catalog arrival coordinates changed; replan this trip"
                )
            record.update(facts)
    for record in main:
        sid = catalog_source_id(record.get("provider_id"))
        if explicit_calendar_ineligible(record) or (
            sid is not None and (sid not in current or not calendar_eligible(record))
        ):
            raise VisitCalendarConflict(
                record.get("provider_id", "unknown"),
                "current catalog access is unresolved; replan this trip",
            )
        if (sid is not None or _explicit_calendar(record)) and record.get("type") != "stop":
            raise VisitCalendarConflict(
                record.get("provider_id", "unknown"),
                "catalog visits require an attraction stop; replan this trip",
            )
    for stop in stops:
        if stop.get("type") == "hotel" and "evening_suggestions" in stop:
            stop["evening_suggestions"] = [
                suggestion
                for suggestion in stop["evening_suggestions"]
                if id(suggestion) not in discarded
                and not admission.requires_admission(suggestion)
                and not explicit_calendar_ineligible(suggestion)
                and (
                    (sid := catalog_source_id(suggestion.get("provider_id"))) is None
                    or sid in current
                )
            ]
