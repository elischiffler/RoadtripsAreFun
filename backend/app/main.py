from fastapi import FastAPI, HTTPException
from typing import Any
import requests
from pydantic import BaseModel, ValidationError

app = FastAPI()


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


class Mapbox_notification(BaseModel):
    details: dict[str, str]
    subtype: str
    type: str
    geometry_index_end: int
    geometry_index_start: int


class Mapbox_admin(BaseModel):
    iso_3166_1_alpha3: str
    iso_3166_1: str


class Mapbox_geo(BaseModel):
    coordinates: list[list[float]]
    type: str


class Mapbox_Maneuver(BaseModel):
    type: str
    instruction: str
    modifier: str = None
    bearing_after : int
    bearing_before : int
    location : list[float]



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


class Mapbox_leg(BaseModel):
    notifications: list[Mapbox_notification] = None
    via_waypoints: list[Any]
    admins: list[Mapbox_admin]
    weight: float
    duration: float
    steps: list[Mapbox_step]
    distance: float
    summary: str


class MapBox_Route(BaseModel):
    weight_name: str
    weight: float
    duration: float
    distance: float
    legs: list[Mapbox_leg]
    geometry: Mapbox_geo


class MapBox(BaseModel):
    routes: list[MapBox_Route]
    waypoints: list[dict]
    code: str
    uuid: str



@app.get("/")
async def root() -> str:
    return "Hello world"


@app.get("/get-route", response_model=Route)
async def get_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> Any:
    # Creating the get request for matbox
    url = f'https://api.mapbox.com/directions/v5/mapbox/driving/{start_lon},{start_lat};{end_lon},{end_lat}'
    params = {
        'alternatives': 'false',
        'geometries': 'geojson',
        'language': 'en',
        'overview': 'full',
        'steps': 'true',
        'access_token': 'pk.eyJ1IjoiYWlkYW4xMzgiLCJhIjoiY2x5cDdzODVkMDFyYjJrcHd3Z3puY2o1eSJ9.FMN-O1YsLaTjFsL4VfnufA'
    }

    try:
        response = requests.get(url, params=params)

        # Need to get the distance(meters), duration(seconds), steps for the route
        json_data = response.json() if response and response.status_code == 200 else None
        MapBox.model_validate(json_data)
        if json_data and 'routes' in json_data:
            distance, duration = 0, 0
            steps = []
            for route in json_data['routes']:
                distance, duration = route['distance'], route['duration']
                for leg in route['legs']:
                    for step in leg['steps']:
                        # Each step has a distance, duration, instruction, and location for future use
                        steps.append(Route_Step(distance=step['distance'],
                                                duration=step['duration'],
                                                instruction=step['maneuver']['instruction'],
                                                location=step['maneuver']['location']))
            return Route(coordinates=[[start_lat,start_lon], [end_lat,end_lon]],
                         distance=distance,
                         duration=duration,
                         route=steps)
        else:
            raise (HTTPException(status_code=404, detail='No routes found'))
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Mapbox request failed: {str(e)}")
    except (KeyError, ValueError,  ValidationError) as e:
        raise HTTPException(status_code=500, detail=f"Error processing Mapbox response: {str(e)}")
