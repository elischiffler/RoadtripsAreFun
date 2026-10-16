"""Controlled 5 × 3 × 2 scenario matrix, validated by application models."""

from copy import deepcopy
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agent.persona import ATTRIBUTE_KEYS
from app.agent.trip_dates import resolve_departure
from app.models.scheduling_policy import SchedulingPolicy
from app.routers.algorithm_lab import LabInputs
from app.routing.lab_presets import ENDPOINTS

PERSONAS = {
    "nature": dict.fromkeys(ATTRIBUTE_KEYS, 0.0)
    | {
        "nature": 0.35,
        "hiking_outdoors": 0.25,
        "scenery": 0.25,
        "adventure": 0.10,
        "crowd_avoidance": 0.05,
    },
    "entertainment": dict.fromkeys(ATTRIBUTE_KEYS, 0.0)
    | {
        "culture_arts": 0.30,
        "nightlife": 0.25,
        "food": 0.20,
        "shopping": 0.15,
        "unique_local_experiences": 0.10,
    },
}
CORRIDORS = {
    "short-1d": ("la", "san-diego", 1, 180, "short-1d"),
    "medium-2d": ("sf", "boise", 2, 180, "medium-2d"),
    "long-3d": ("sf", "denver", 3, 180, "long-3d"),
    "coast-5d": ("sf", "nyc", 5, 180, "coast-5d"),
    "tight-2d": ("sf", "boise", 2, 60, "medium-2d"),
}


class Scenario(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    trip_type: str
    persona: str
    target_days: int = Field(strict=True, ge=1, le=30)
    stops_per_day: int = Field(strict=True, ge=1, le=3)
    fixture: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,80}$")
    evaluation_clock: datetime
    inputs: LabInputs
    diagnostic_reason: str | None = None

    @model_validator(mode="after")
    def controlled(self):
        if self.inputs.num_stops != self.target_days * self.stops_per_day:
            raise ValueError("total attraction count must equal target days × density")
        if set(self.inputs.persona_weights) != set(ATTRIBUTE_KEYS):
            raise ValueError("all canonical persona weights must be explicit")
        if not self.evaluation_clock.tzinfo or self.departure() <= self.evaluation_clock:
            raise ValueError("freeze an aware evaluation clock before departure")
        if self.inputs.evening_interests:
            raise ValueError("core daytime comparisons require empty optional evenings")
        return self

    def departure(self):
        local = f"{self.inputs.departure_date}T{self.inputs.departure_time}"
        return datetime.fromisoformat(
            resolve_departure(
                local, ENDPOINTS[self.inputs.start_id]["timezone"], now=self.evaluation_clock
            )
        )


def core_scenarios():
    rows = []
    for trip_type, (start, end, days, budget, fixture) in CORRIDORS.items():
        for density in (1, 2, 3):
            for persona, weights in PERSONAS.items():
                rows.append(
                    {
                        "id": f"{trip_type}-s{density}-{persona}",
                        "trip_type": trip_type,
                        "persona": persona,
                        "target_days": days,
                        "stops_per_day": density,
                        "fixture": fixture,
                        "evaluation_clock": "2026-10-16T00:00:00+00:00",
                        "inputs": {
                            "start_id": start,
                            "destination_id": end,
                            "departure_date": "2026-10-17",
                            "departure_time": "08:00",
                            "num_stops": days * density,
                            "budget": budget,
                            "traveler_count": 2,
                            "hotel_rooms": [{"adults": 2, "child_ages": []}],
                            "car_status": "skipped",
                            "car": None,
                            "persona_weights": deepcopy(weights),
                            "scheduling_policy": SchedulingPolicy(
                                latest_destination_arrival="21:00"
                            ).model_dump(),
                            "evening_interests": [],
                        },
                    }
                )
    return rows


def coast_diagnostics():
    rows = []
    for original in core_scenarios():
        if original["trip_type"] != "coast-5d":
            continue
        for days in (7, 10):
            row = deepcopy(original)
            row["id"] = original["id"].replace("coast-5d", f"coast-{days}d")
            row["trip_type"] = f"coast-{days}d"
            row["target_days"] = days
            row["inputs"]["num_stops"] = days * row["stops_per_day"]
            row["diagnostic_reason"] = (
                "Extended target using the same coast-5d source capture; unsupported count/transport outcomes remain visible."
            )
            rows.append(row)
    return rows
