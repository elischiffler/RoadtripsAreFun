from pydantic import BaseModel
from typing import Any, Optional

class Route_Step(BaseModel):
        distance: float
        duration: float
        instruction: str
        location: list[float]
        
class Route(BaseModel):
    coordinates: list[list[float]]
    distance: float
    duration: float
    route: list[Route_Step]


class Mapbox_Maneuver(BaseModel):
    type: str
    instruction: str
    modifier: str = None
    bearing_after : int
    bearing_before : int
    location : list[float]
class Mapbox_geo(BaseModel):
    coordinates: list[list[float]]
    type: str

class MapBox(BaseModel):
    class MapBox_Route(BaseModel):
        class Mapbox_leg(BaseModel):
            class Mapbox_step(BaseModel):
                intersections: list[Any]
                exits: str = None
                destinations: str = None
                maneuver: dict
                name: str
                duration: float
                distance: float
                driving_side: str
                weight: float
                mode: str
                geometry: Mapbox_geo
            class Mapbox_admin(BaseModel):
                iso_3166_1_alpha3: str
                iso_3166_1: str
            class Mapbox_notification(BaseModel):
                details: dict[str, str]
                subtype: str
                type: str
                geometry_index_end: int
                geometry_index_start: int
            notifications: Optional[list[Mapbox_notification]] = []
            via_waypoints: list[Any]
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
    routes: list[MapBox_Route]
    waypoints: list[dict]
    code: str
    uuid: str