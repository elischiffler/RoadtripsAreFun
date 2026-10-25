"""Rate all geographic matches without AI-based discovery or pool truncation."""

from app.agent.persona import normalize_weights
from app.agent.providers import build_default_chain
from app.routing.corridor import CorridorConfig, RouteCorridor
from app.routing.explanation import record_explanation
from app.routing.runtime import run_resource, threaded
from app.routing.sources import trait_cache
from app.routing.sources.persona_candidates import (
    MAX_PROPOSALS_PER_QUERY,
    ProposedPlace,
    VerifiedPlace,
    _candidate,
    _name_key,
    _propose,
)


def corridor_config(inputs):
    config = inputs["corridor"]
    return CorridorConfig(
        **{key: config[key] for key in ("endpoint_miles", "midpoint_miles", "sigma")}
    )


async def rated_pool(route, inputs, catalog, *, ai=None, cache=trait_cache):
    """Persist missing traits, then score every corridor place for the persona.

    Batch size limits request size only. Missing or unpersisted scores fail the
    capture rather than silently shrinking the solver's candidate universe.
    """
    corridor = RouteCorridor(route, corridor_config(inputs))
    matches = corridor.select(catalog["records"])
    places = [VerifiedPlace.model_validate(row) for row in matches]
    weights = normalize_weights(inputs["persona_weights"])
    cached = await threaded("catalog", cache.get_many, places)
    entries = dict(cached)
    missing = [place for place in places if place.provider_id not in entries]
    diagnostics = {
        "corridor": corridor.config.snapshot(),
        "catalog_generation": catalog["generation"],
        "admitted_catalog_count": len(catalog["records"]),
        "geographic_count": len(matches),
        "geographic_candidates": matches,
        "trait_cache": {"hits": len(cached), "misses": len(missing), "stored": 0},
        "rating_attempts": [],
        "stop_reason": "entire_admitted_catalog_checked",
    }
    record_explanation(discovery=diagnostics)
    if missing:
        ai = ai or run_resource("rating_provider", build_default_chain)
    # Same-name identities cannot share a name-matched provider response.
    groups = []
    for place in missing:
        group = next(
            (
                group
                for group in groups
                if len(group) < MAX_PROPOSALS_PER_QUERY
                and all(_name_key(other.name) != _name_key(place.name) for other in group)
            ),
            None,
        )
        if group is None:
            group = []
            groups.append(group)
        group.append(place)
    for group in groups:
        remaining = list(group)
        for attempt in range(2):
            validation = {}
            proposals = await _propose(
                ai,
                "attractions",
                remaining[0].coordinates,
                len(remaining),
                names=[place.name for place in remaining],
                place_facts=[trait_cache.context(place) for place in remaining],
                diagnostics=validation,
                repair=bool(attempt),
            )
            by_name = {_name_key(proposal.name): proposal for proposal in proposals}
            fresh = [
                (place, by_name[_name_key(place.name)].attribute_ratings.model_dump())
                for place in remaining
                if _name_key(place.name) in by_name
            ]
            provider = validation.get("provider", "unknown")
            if not validation.get("model"):
                raise ValueError("Research ratings require the actual upstream model identity")
            stored = await threaded(
                "catalog", cache.put_many, fresh, f"{provider}/{validation['model']}"
            )
            entries.update(stored)
            diagnostics["trait_cache"]["stored"] += len(stored)
            diagnostics["rating_attempts"].append(
                validation | {"attempt": attempt + 1, "stored": len(stored)}
            )
            remaining = [place for place in remaining if place.provider_id not in entries]
            if not remaining:
                break
        if remaining:
            raise ValueError(
                "Not all corridor places have valid persisted AI traits; capture incomplete"
            )
    candidates = []
    for place, projection in zip(places, matches):
        entry = entries[place.provider_id]
        candidate = _candidate(
            place,
            ProposedPlace(name=place.name, attribute_ratings=entry["attribute_ratings"]),
            weights,
        )
        candidate["provenance"].update(
            ratings_cache="hit" if place.provider_id in cached else "fresh",
            ratings_version=entry.get("rating_version", trait_cache.VERSION),
            ratings_created_at=entry.get("rated_at"),
            ratings_provider=entry.get("provider"),
        )
        candidate.update(
            {
                key: projection[key]
                for key in (
                    "route_progress_seconds",
                    "distance_meters",
                    "segment_index",
                    "route_distance_fraction",
                    "corridor_radius_miles",
                    "inside_corridor",
                )
            }
        )
        candidates.append(candidate)
    return candidates, diagnostics
