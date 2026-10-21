"""Deterministic, explicitly inferred traveler fit on admitted source facts.

This builds the existing LocationProfile contract. No model, geocoder, database
or network is called. Unknown subjective attributes use an uninformative 0.5
prior, not a factual claim or a measured review score.
"""

from app.agent.persona import ATTRIBUTE_KEYS
from app.catalog import pilot_personas
from app.catalog.identity import identity

VERSION = "roadtrips-source-persona/1"
DATASET = "Roadtrips deterministic source persona"
RULES = {
    "trailhead": (
        "Trail gateway",
        ["Check permitted trail activities before using the trailhead"],
        {"nature": 0.9},
    ),
    "picnic_site": (
        "Outdoor picnic stop",
        ["Consider a picnic"],
        {"nature": 0.8, "relaxation": 0.8},
    ),
    "day_use_area": (
        "Outdoor day-use stop",
        ["Explore the designated day-use area"],
        {"nature": 0.8},
    ),
    "viewpoint": (
        "Scenic viewing stop",
        ["Look for published viewing opportunities"],
        {"scenery": 0.9, "nature": 0.8},
    ),
    "interpretive_site": (
        "Interpretive stop",
        ["Explore published interpretation"],
        {"history": 0.8, "culture_arts": 0.7},
    ),
    "wildlife_viewing": (
        "Wildlife viewing stop",
        ["Look for wildlife without expecting sightings"],
        {"nature": 0.9},
    ),
    "swimming_site": (
        "Waterside stop",
        ["Check current water access and safety restrictions"],
        {"nature": 0.8, "beaches_water": 0.8},
    ),
    "historic_site": (
        "Heritage visitor stop",
        ["Explore published historical interpretation"],
        {"history": 0.9, "culture_arts": 0.8},
    ),
    "visitor_center": (
        "Visitor information stop",
        ["Consult visitor information"],
        {"culture_arts": 0.6},
    ),
}


def build(row, calendar_entry, *, release, attribution):
    """Return a typed profile plus evidence/unknowns; inputs must be source-admitted."""
    from app.routing.sources.persona_candidates import LocationProfile

    if calendar_entry["source_id"] != row["source_id"]:
        raise ValueError("persona calendar identity differs")
    if not row.get("provenance") or not any(p.get("snapshot_sha256") for p in row["provenance"]):
        raise ValueError("persona requires traceable original source evidence")
    category = next((key for key in RULES if key in row["categories"]), None)
    if category is None:
        raise ValueError("no reviewed persona rule for source category")
    character, suggestions, supported = RULES[category]
    ratings = dict.fromkeys(ATTRIBUTE_KEYS, 0.5) | supported
    description = (
        f"{row['name']} is a publisher-listed {category.replace('_', ' ')} "
        f"in {row['region']}. Its native visitor-arrival point is retained unchanged."
    )
    profile = LocationProfile(
        provider_id=identity(row["source_id"])[0],
        name=row["name"],
        coordinates=[row["latitude"], row["longitude"]],
        address=row["address"],
        url=row["url"],
        categories=row["categories"],
        description=description,
        # Suggestions remain outside factual activities; a type alone does not
        # establish trails, exhibitions, swimming safety or available programs.
        activities=[],
        source=identity(row["source_id"])[1],
        source_release=release,
        source_attribution=attribution,
        source_updated_at=row["source_updated_at"],
        source_provenance=row["provenance"],
        attribute_ratings=ratings,
        provenance={
            "identity_source": "publisher-native facility and retained arrival evidence",
            "ratings_source": VERSION + ": category-based estimates, not verified facts",
            "description_source": "deterministic name, source category and state facts",
        },
    )
    return {
        "schema_version": VERSION,
        "source_id": row["source_id"],
        "location_profile": profile.model_dump(mode="json"),
        "inferred_traveler_fit": {
            "character": character,
            "suggested_activities": suggestions,
            "interests": list(supported),
            "rule_category": category,
            "estimated_attribute_keys": list(supported),
            "uninformative_prior_keys": [key for key in ATTRIBUTE_KEYS if key not in supported],
            "basis": "Source facility type; recommendations require traveler judgment.",
            "confidence": "limited; deterministic category inference, not visitor research",
        },
        "practical_context": {
            "calendar": calendar_entry["source_visit_calendar"],
            "source_constraints": calendar_entry.get("source_constraints", []),
            "hours_are_current_inventory": False,
            "cost": None,
            "accessibility": None,
            "parking_availability": None,
            "reservation_availability": None,
            "live_operating_status": None,
        },
        "validation_scope": {
            "identity_coordinates_and_arrival": "source-adapter evidence checks passed; not a field survey",
            "traveler_fit": "inferred",
            "future_availability": "unknown outside the bounded source-calendar review",
            "fact_confidence": "source-corroborated; no claim of independent field verification",
            "checked_at": sorted(
                {p["checked_at"] for p in row["provenance"] if p.get("checked_at")}
            ),
        },
    }


def stored(profile):
    """Persist the typed profile's recommendations beside unchanged source facts."""
    place = profile["location_profile"]
    return {
        "dataset": DATASET,
        "schema_version": VERSION,
        "source_id": profile["source_id"],
        "description": place["description"],
        "activities": place["activities"],
        "attribute_ratings": place["attribute_ratings"],
        "inferred_traveler_fit": profile["inferred_traveler_fit"],
        "validation_scope": profile["validation_scope"],
        "method": place["provenance"],
    }


def facts(provenance):
    """Project factual description/activities; recommendations remain labeled."""
    matches = [
        p
        for p in provenance
        if (p.get("dataset"), p.get("schema_version"))
        in {(DATASET, VERSION), (pilot_personas.DATASET, pilot_personas.VERSION)}
    ]
    if len(matches) != 1:
        return {}
    return {key: matches[0][key] for key in ("description", "activities")}
