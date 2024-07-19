from fastapi import FastAPI, HTTPException
from typing import Any
import requests
from pydantic import ValidationError
from app.models.routing_models import MapBox, Route, Route_Step

app = FastAPI()


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
        data = MapBox.model_validate(json_data)
        steps = []
        route = data.routes[0]  # The first route returned is considered the most recommended
        distance, duration = route.distance, route.duration
        for leg in route.legs:
            for step in leg.steps:
                # Each step has a distance, duration, instruction, and location for future use
                steps.append(Route_Step(distance=step.distance,
                                        duration=step.duration,
                                        instruction=step.maneuver.instruction,
                                        location=step.maneuver.location))
        return Route(coordinates=[[start_lat, start_lon], [end_lat, end_lon]],
                     distance=distance,
                     duration=duration,
                     steps=steps)
    except requests.exceptions.RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Mapbox request failed: {str(exception)}")
    except ValidationError as exception:
        raise (HTTPException(status_code=500, detail=f'Improper Mapbox response: {str(exception)}'))
    except (KeyError, ValueError) as exception:
        raise HTTPException(status_code=500, detail=f"Error processing Mapbox response: {str(exception)}")
