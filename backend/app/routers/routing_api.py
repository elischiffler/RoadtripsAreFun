from fastapi import FastAPI, HTTPException
from typing import Any, Optional, Tuple
import requests
from pydantic import ValidationError
from app.models.routing_models import MapBox, Route, Route_Step
from dotenv import load_dotenv
from app.routers.add_stop import add_stop
import os

MapBox_route = MapBox.MapBox_Route
load_dotenv()

#get mapbox API
access_token = os.getenv('MAPBOX_API')

#Initializing FastAPI
app = FastAPI()



@app.get("/get-route", response_model=Route)
async def get_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> Any:
    try:
        #Construct initial route without stops
        route = await call_route(start_lat, start_lon, end_lat, end_lon)

        #Use initial route to find stopping points
        stopping_points = await add_stop(route.legs[0].steps, route.geometry.coordinates, route.duration, departure_time=36000)

        # Construct waypoints string and make new route with stopping points
        waypoints = ';'.join([f"{lon},{lat}" for lat, lon in stopping_points])
        route = await call_route(start_lat, start_lon, end_lat, end_lon, waypoints)

        distance, duration = route.distance, route.duration
        steps = []
        
        for leg in route.legs:
            for step in leg.steps:
                # Each step has a distance, duration, instruction, and location
                steps.append(Route_Step(distance=step.distance,
                                        duration=step.duration,
                                        instruction=step.maneuver.instruction,
                                        location=step.maneuver.location))
        return Route(coordinates=[[start_lat, start_lon]] + stopping_points + [[end_lat, end_lon]],
                     distance=distance,
                     duration=duration,
                     steps=steps)
    except requests.exceptions.RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Mapbox request failed: {str(exception)}")
    except ValidationError as exception:
        raise HTTPException(status_code=501, detail=f'Improper Mapbox response: {str(exception)}')
    except (KeyError, ValueError) as exception:
        raise HTTPException(status_code=502, detail=f"Error processing Mapbox response: {str(exception)}")
    
#Will find a route based on parameters
async def call_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float, waypoints: str = None) -> MapBox_route:
    url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{start_lon},{start_lat}"
    if waypoints:
        url += f";{waypoints}"
    url += f";{end_lon},{end_lat}"
    params = {
        'alternatives': 'false',
        'geometries': 'geojson',
        'language': 'en',
        'overview': 'full',
        'steps': 'true',
        'access_token': access_token
    }

    response = requests.get(url, params=params)
    response.raise_for_status()  # Raise an exception for HTTP errors
    json_data = response.json()
    data = MapBox.model_validate(json_data)
    route = data.routes[0]  # The first route returned is considered the most recommended
    return route

