from typing import Any, Optional

from pydantic import BaseModel

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

class Mapbox_waypoint(BaseModel):
    name: str
    location: list[float]
    distance: Optional[float] = None
    metadata: Optional[dict[str, Any]] = None

class Mapbox_geo(BaseModel):
    coordinates: list[list[float]]
    type: str

class MapBox(BaseModel):
    class MapBox_Route(BaseModel):
        class Mapbox_leg(BaseModel):
            class Mapbox_notification(BaseModel):
                details: Optional[dict[str, str]] = None
                subtype: Optional[str] = None
                type: str
                geometry_index_end: Optional[int] = None
                geometry_index_start: Optional[int] = None
                geometry_index: Optional[int] = None

            class Mapbox_admin(BaseModel):
                iso_3166_1_alpha3: str
                iso_3166_1: str

            class Mapbox_step(BaseModel):
                class Mapbox_Maneuver(BaseModel):
                    type: str
                    instruction: str
                    modifier: Optional[str] = None
                    bearing_after: int
                    bearing_before: int
                    location: list[float]
                intersections: list[Any]
                exits: Optional[str] = None
                destinations: Optional[str] = None
                maneuver: Mapbox_Maneuver
                name: str
                duration: float
                distance: float
                driving_side: str
                weight: float
                mode: str
                geometry: Mapbox_geo
                ref: Optional[str] = None

            notifications: Optional[list[Mapbox_notification]] = []
            via_waypoints: Optional[list[Any]] = []
            admins: list[Mapbox_admin]
            weight: float
            duration: float
            steps: list[Mapbox_step]
            distance: float
            summary: str
        weight_name: str
        weight: float
        duration: float
        distance: float
        legs: list[Mapbox_leg]
        geometry: Mapbox_geo
        waypoints: Optional[Mapbox_waypoint] = []

    routes: list[MapBox_Route]
    waypoints: list[Mapbox_waypoint]
    code: str
    uuid: str
