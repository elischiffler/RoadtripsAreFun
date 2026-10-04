from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.agent.persona import validate_weight_update
from app.models.scheduling_policy import EveningInterest, SchedulingPolicy


class Mapbox_geo(BaseModel):
    coordinates: list[list[float]]
    type: str | None = None


class Route_Step(BaseModel):
    distance: float
    duration: float
    instruction: str
    location: list[float]


class Route(BaseModel):
    coordinates: list[list[float]]
    distance: float
    duration: float
    steps: list[Route_Step]
    stops: list[dict[str, Any]] | None = None  # TODO use or remove this
    geometry: Mapbox_geo
    cost: float
    warnings: list[str] | None = None
    # None identifies legacy saved routes, which retain their original 09:00 restart.
    scheduling_policy: SchedulingPolicy | None = None
    start_timezone: str | None = None

    class Stop(BaseModel):
        name: str
        coordinates: list[list[float]] | None = []
        duration: float
        type: str


# Mapbox Base Models
class Mapbox_waypoint(BaseModel):
    name: str
    location: list[float]
    distance: float | None = None
    metadata: dict[str, Any] | None = None


class MapBox(BaseModel):
    class MapBox_Route(BaseModel):
        class Mapbox_leg(BaseModel):
            class Mapbox_notification(BaseModel):
                details: dict[str, str] | None = None
                subtype: str | None = None
                type: str
                geometry_index_end: int | None = None
                geometry_index_start: int | None = None
                geometry_index: int | None = None

            class Mapbox_admin(BaseModel):
                iso_3166_1_alpha3: str
                iso_3166_1: str

            class Mapbox_step(BaseModel):
                class Mapbox_Maneuver(BaseModel):
                    type: str
                    instruction: str
                    modifier: str | None = None
                    bearing_after: int
                    bearing_before: int
                    location: list[float]

                intersections: list[Any]
                exits: str | None = None
                destinations: str | None = None
                maneuver: Mapbox_Maneuver | None = None
                name: str | None = None
                duration: float
                distance: float
                driving_side: str | None = None
                weight: float | None = None
                mode: str | None = None
                geometry: Mapbox_geo
                ref: str | None = None

            notifications: list[Mapbox_notification] | None = []
            via_waypoints: list[Any] | None = []
            admins: list[Mapbox_admin] | None = []
            weight: float
            duration: float
            steps: list[Mapbox_step]
            distance: float
            summary: str

        weight_name: str
        weight: float
        duration: float  # Total length in seconds
        distance: float  # Total distance in meters
        legs: list[Mapbox_leg]  # A leg represents a route between two destinations of the journey
        geometry: Mapbox_geo | None = None  # Contains every coordinate of the route
        waypoints: list[Mapbox_waypoint] | None = []  # Contains start, end, and stops locations

    routes: list[MapBox_Route]
    waypoints: list[Mapbox_waypoint]
    code: str
    uuid: str


class Route_Payload(BaseModel):
    initial_route: MapBox.MapBox_Route
    num_stops: int
    budget: float
    start: datetime | None = datetime(2024, 9, 21, 9, 0, 0)
    # Which routing algorithm to run. None -> the ROUTING_ALGORITHM env / default.
    algorithm: str | None = None
    persona_weights: dict[str, float] | None = None
    scheduling_policy: SchedulingPolicy = Field(default_factory=SchedulingPolicy)
    start_timezone: str | None = None
    evening_interests: list[EveningInterest] | None = None

    @field_validator("persona_weights", mode="before")
    @classmethod
    def _persona_weights(cls, value):
        return validate_weight_update(value) if value is not None else None
