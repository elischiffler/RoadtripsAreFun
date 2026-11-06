"""Deterministic traveler-fit recommendations for evidence-reviewed pilot places."""

from app.agent.persona import ATTRIBUTE_KEYS

VERSION = "roadtrips-pilot-persona/1"
DATASET = "Roadtrips reviewed pilot persona"
RULES = {
    "museum": ("Museum visit", {"culture_arts": 0.8}),
    "science_center": ("Science interpretation visit", {"culture_arts": 0.8}),
    "historic_site": ("Public heritage visit", {"history": 0.8}),
    "public_art": ("Public art stop", {"culture_arts": 0.8}),
    "botanical_garden": ("Garden visit", {"nature": 0.8}),
    "zoo": ("Animal interpretation visit", {"nature": 0.8}),
    "observatory": ("Astronomy visit", {"culture_arts": 0.7}),
    "show_cave": ("Cave interpretation visit", {"nature": 0.8}),
    "visitor_center": ("Visitor information stop", {}),
    "wildlife_viewing": ("Wildlife interpretation stop", {"nature": 0.8}),
    "viewpoint": ("Scenic stop", {"scenery": 0.8}),
    "interpretive_site": ("Interpretive visit", {"culture_arts": 0.7}),
    "farmers_market": ("Public market visit", {"food": 0.8}),
    "food_experience": ("Visitor food experience", {"food": 0.8}),
    "industrial_heritage": ("Industrial heritage visit", {"history": 0.8}),
    "roadside_attraction": ("Roadside visitor stop", {"unique_local_experiences": 0.7}),
    "lighthouse": ("Lighthouse visitor stop", {"scenery": 0.8}),
    "heritage_rail": ("Heritage railway visit", {"history": 0.8}),
}


def build(row, category, admission, *, release="catalog-pilot-600-20261021"):
    """Retain unknown practical facts; a category is not an activity inventory."""
    from app.routing.sources.persona_candidates import LocationProfile

    character, estimates = RULES[category]
    ratings = dict.fromkeys(ATTRIBUTE_KEYS, 0.5) | estimates
    description = (
        f"{row['name']} is review-classified as a {category.replace('_', ' ')} in {row['region']}. "
        "Public visitor identity was reviewed against retained operator evidence. "
        "Arrival and visit timing require separate verification."
    )
    profile = LocationProfile(
        provider_id=row["source_id"],
        name=row["name"],
        coordinates=[row["latitude"], row["longitude"]],
        address=row["address"],
        url=row["url"],
        categories=row["categories"],
        activities=[],
        description=description,
        source="catalog-pilot",
        source_release=release,
        source_attribution="See retained field-level source credits; no agency endorsement.",
        source_updated_at=row["source_updated_at"],
        source_provenance=row["provenance"],
        attribute_ratings=ratings,
        provenance={
            "identity_source": "Retained native source fields and operator public-visit review",
            "ratings_source": VERSION + ": category inferences; unknown attributes use 0.5 priors",
        },
    )
    return {
        "dataset": DATASET,
        "schema_version": VERSION,
        "source_id": row["source_id"],
        "description": description,
        "activities": [],
        "attribute_ratings": ratings,
        "inferred_traveler_fit": {
            "character": character,
            "interests": list(estimates),
            "estimated_attribute_keys": list(estimates),
            "uninformative_prior_keys": [key for key in ATTRIBUTE_KEYS if key not in estimates],
            "basis": "Reviewed source category; recommendations are not measured visitor facts.",
            "confidence": "limited category inference",
        },
        "practical_context": {
            "hours": None,
            "cost": None,
            "accessibility": None,
            "amenities": None,
            "parking_capacity": None,
            "reservation_availability": None,
            "live_operating_status": None,
            "arrival_verified": False,
            "source_constraints": row["provenance"][0].get("reviewed_constraints", []),
        },
        "validation_scope": {
            "identity_location": "Source-corroborated physical feature; not a surveyed arrival",
            "public_access": "Dated operator/source claim review; not real-time availability",
            "schema_validation_is_factual_verification": False,
            "reviewed_at_epoch": admission["reviewed_at_epoch"],
            "expires_at_epoch": admission["expires_at_epoch"],
            "live_parent_reconciled": False,
        },
        "location_profile": profile.model_dump(mode="json"),
    }


def stored(profile):
    """Store recommendations once without duplicating the full provider profile."""
    return {key: value for key, value in profile.items() if key != "location_profile"}
