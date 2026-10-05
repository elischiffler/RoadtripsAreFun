"""Server-owned preset identities and clearly synthetic, frozen teaching inputs."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.agent.persona import ATTRIBUTE_KEYS, default_weights
from app.models.scheduling_policy import SchedulingPolicy
from app.routing.profiles import crossmatch
from app.routing.sources.persona_candidates import LocationProfile

ENDPOINTS = {
    "sf": {"label": "San Francisco, California, USA", "coordinates": [37.7749, -122.4194]},
    "monterey": {"label": "Monterey, California, USA", "coordinates": [36.6002, -121.8947]},
    "la": {"label": "Los Angeles, California, USA", "coordinates": [34.0522, -118.2437]},
}
PRESETS = {
    "coastal-nature": (
        "Coastal nature",
        "monterey",
        2,
        {"nature": 0.6, "history": 0.3, "food": 0.1},
    ),
    "coastal-culture": (
        "Same corridor, culture",
        "monterey",
        2,
        {"nature": 0.1, "history": 0.7, "food": 0.2},
    ),
    "overnight": ("Overnight road trip", "la", 3, default_weights()),
}
SNAPSHOTS = [
    {
        "id": "teaching-v1",
        "label": "Frozen profile comparison",
        "source": "Synthetic teaching fixture v1; no provider verification or road route",
    },
    {
        "id": "empty-v1",
        "label": "No eligible attractions",
        "source": "Synthetic teaching fixture v1; all ratings below threshold",
    },
]


def preset_catalog():
    tomorrow = (
        (datetime.now(ZoneInfo("America/Los_Angeles")) + timedelta(days=1)).date().isoformat()
    )
    return [
        {
            "id": key,
            "label": label,
            "inputs": {
                "start_id": "sf",
                "destination_id": destination,
                "departure_date": tomorrow,
                "departure_time": "09:00",
                "num_stops": stops,
                "traveler_count": 2,
                "hotel_rooms": [{"adults": 2, "child_ages": []}],
                "budget": 180,
                "car_status": "skipped",
                "car": None,
                "persona_weights": {**dict.fromkeys(ATTRIBUTE_KEYS, 0.0), **weights},
                "scheduling_policy": SchedulingPolicy().model_dump(),
                "evening_interests": [],
            },
        }
        for key, (label, destination, stops, weights) in PRESETS.items()
    ]


def replay_candidates(snapshot_id, weights):
    """Changing a profile changes scores, never the frozen candidate attributes."""
    points = [[37.6, -122.35], [37.3, -122.2], [37.0, -122.0], [36.8, -121.95]]
    records = [
        ("a", "Forest walk (fixture)", 0, (0.9, 0.2, 0.3)),
        ("b", "Historic market (fixture)", 0, (0.2, 0.9, 0.8)),
        ("c", "Scenic museum (fixture)", 1, (0.8, 0.8, 0.4)),
        ("d", "Local gardens (fixture)", 2, (0.7, 0.7, 0.7)),
        ("e", "Low match (fixture)", 3, (0.2, 0.2, 0.2)),
    ]
    candidates = []
    for key, name, slot, (nature, history, food) in records:
        ratings = dict.fromkeys(ATTRIBUTE_KEYS, 0.2)
        if snapshot_id != "empty-v1":
            ratings.update(nature=nature, history=history, food=food)
        profile = LocationProfile(
            provider_id=f"fixture:{key}",
            name=name,
            coordinates=points[slot],
            attribute_ratings=ratings,
            provenance={
                "identity_source": "synthetic fixture; not provider verified",
                "ratings_source": "fixed synthetic teaching values",
                "verified_at": None,
                "snapshot_version": "1",
            },
        )
        candidates.append({**profile.model_dump(), **crossmatch(weights, ratings).model_dump()})
    return candidates, points
