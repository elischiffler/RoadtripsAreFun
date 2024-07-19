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


class Mapbox_geo(BaseModel):
    coordinates: list[list[float]]
    type: str

class MapBox(BaseModel):
    class MapBox_Route(BaseModel):
        class Mapbox_leg(BaseModel):
            class Mapbox_step(BaseModel):
                intersections: list[Any]
                name: str
                duration: float
                distance: float
                driving_side: str
                weight: float
                mode: str
                geometry: Mapbox_geo
            notifications: Optional[list[Mapbox_notification]] = []
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
    code: str
    uuid: str