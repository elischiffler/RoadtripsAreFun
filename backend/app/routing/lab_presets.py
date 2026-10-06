"""Server-owned live trip presets and isolated solver verification fixtures."""

from copy import deepcopy
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

ENDPOINTS.update(
    {
        "san-diego": {"label": "San Diego, California, USA", "timezone": "America/Los_Angeles"},
        "boise": {"label": "Boise, Idaho, USA", "timezone": "America/Boise"},
        "chicago": {"label": "Chicago, Illinois, USA", "timezone": "America/Chicago"},
        "ely": {"label": "Ely, Nevada, USA", "timezone": "America/Los_Angeles"},
        "reno": {"label": "Reno, Nevada, USA", "timezone": "America/Los_Angeles"},
    }
)

# Driving times and hotel counts are experiment targets, not promised outcomes.

BENCHMARKS = {
    "short-day": (
        "Short single-day",
        "la",
        "san-diego",
        2,
        180,
        "Target: 3–4 hours driving, two stops, no overnight.",
    ),
    "medium-two-day": (
        "Medium two-day",
        "sf",
        "boise",
        4,
        180,
        "Target: 12–14 hours driving and one overnight.",
    ),
    "long-multi-day": (
        "Long multi-day",
        "sf",
        "chicago",
        8,
        180,
        "Target: 30+ hours driving, eight stops, several hotels.",
    ),
    "dense-corridor": (
        "Dense corridor",
        "sf",
        "la",
        4,
        180,
        "Urban California corridor; inspect the observed candidate pool.",
    ),
    "sparse-corridor": (
        "Sparse corridor",
        "ely",
        "reno",
        3,
        180,
        "Remote Nevada corridor; inspect candidate and hotel availability.",
    ),
    "tight-budget": (
        "Tight hotel budget",
        "sf",
        "boise",
        4,
        60,
        "Medium trip with a $60 nightly room target; this is not a hard total budget.",
    ),
}

# Complete form variations share the benchmark routes, not candidate/provider data.
BENCHMARK_PROFILES = {
    "short-day": {
        "departure_time": "08:00",
        "traveler_count": 1,
        "hotel_rooms": [{"adults": 1, "child_ages": []}],
        "car_status": "provided",
        "car": {"year": 2022, "make": "Honda", "model": "Civic"},
        "persona_weights": {"beaches_water": 0.4, "food": 0.35, "relaxation": 0.25},
        "scheduling_policy": {"latest_destination_arrival": "19:00"},
        "evening_interests": [],
    },
    "medium-two-day": {
        "departure_time": "07:00",
        "traveler_count": 4,
        "hotel_rooms": [{"adults": 2, "child_ages": [7, 12]}],
        "car_status": "provided",
        "car": {"year": 2023, "make": "Toyota", "model": "RAV4"},
        "persona_weights": {"family_friendliness": 0.4, "nature": 0.35, "scenery": 0.25},
        "scheduling_policy": {
            "preferred_hotel_arrival": "17:00",
            "latest_hotel_arrival": "19:00",
            "morning_restart": "07:30",
            "latest_destination_arrival": "19:00",
        },
        "evening_interests": ["food"],
    },
    "long-multi-day": {
        "departure_time": "06:30",
        "traveler_count": 4,
        "hotel_rooms": [{"adults": 2, "child_ages": []}, {"adults": 2, "child_ages": []}],
        "car_status": "provided",
        "car": {"year": 2021, "make": "Subaru", "model": "Outback"},
        "persona_weights": {"scenery": 0.35, "history": 0.25, "adventure": 0.25, "food": 0.15},
        "scheduling_policy": {"morning_restart": "07:30", "latest_destination_arrival": "21:00"},
        "evening_interests": ["food", "culture"],
    },
    "dense-corridor": {
        "departure_time": "09:30",
        "traveler_count": 2,
        "hotel_rooms": [{"adults": 2, "child_ages": []}],
        "car_status": "skipped",
        "car": None,
        "persona_weights": {"culture_arts": 0.4, "food": 0.3, "nightlife": 0.2, "shopping": 0.1},
        "scheduling_policy": {
            "late_driving": True,
            "late_cutoff": "23:00",
            "morning_restart": "09:30",
        },
        "evening_interests": ["food", "culture", "nightlife"],
    },
    "sparse-corridor": {
        "departure_time": "07:30",
        "traveler_count": 2,
        "hotel_rooms": [{"adults": 2, "child_ages": []}],
        "car_status": "provided",
        "car": {"year": 2020, "make": "Toyota", "model": "4Runner"},
        "persona_weights": {"nature": 0.4, "hiking_outdoors": 0.3, "crowd_avoidance": 0.3},
        "scheduling_policy": {
            "preferred_hotel_arrival": "17:30",
            "latest_hotel_arrival": "19:30",
            "morning_restart": "07:00",
        },
        "evening_interests": [],
    },
    "tight-budget": {
        "departure_time": "08:30",
        "traveler_count": 3,
        "hotel_rooms": [{"adults": 3, "child_ages": []}],
        "car_status": "skipped",
        "car": None,
        "persona_weights": {"unique_local_experiences": 0.4, "nature": 0.35, "food": 0.25},
        "scheduling_policy": {
            "preferred_hotel_arrival": "18:30",
            "latest_hotel_arrival": "20:30",
            "morning_restart": "08:30",
        },
        "evening_interests": ["food"],
    },
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
    presets = [
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
    for key, (label, start, destination, stops, budget, description) in BENCHMARKS.items():
        inputs = {
            **deepcopy(presets[0]["inputs"]),
            "start_id": start,
            "destination_id": destination,
            "num_stops": stops,
            "budget": budget,
            "persona_weights": dict(presets[0]["inputs"]["persona_weights"]),
        }
        profile = deepcopy(BENCHMARK_PROFILES[key])
        inputs.update(profile)
        inputs["persona_weights"] = {
            **dict.fromkeys(ATTRIBUTE_KEYS, 0.0),
            **profile["persona_weights"],
        }
        inputs["scheduling_policy"] = SchedulingPolicy(**profile["scheduling_policy"]).model_dump()
        presets.append({"id": key, "label": label, "description": description, "inputs": inputs})
    return presets


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
        candidates.append(
            {
                **profile.model_dump(),
                **crossmatch(weights, ratings).model_dump(),
                "route_progress_seconds": (slot + 1) * 600,
                "detour_seconds": 0,
                "section_id": slot,
            }
        )
    return candidates, points
