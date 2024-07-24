from fastapi import FastAPI, HTTPException
from typing import Any
import requests
from pydantic import ValidationError
from app.models.routing_models import MapBox, Route, Route_Step,  Trip_Advisor_Location_Search, Trip_Advisor_Information
from dotenv import load_dotenv
import os
import logging


Mapbox_step = MapBox.MapBox_Route.Mapbox_leg.Mapbox_step
MapBox_route = MapBox.MapBox_Route
load_dotenv()


# Setup logging (for debugging)
logging.basicConfig(level=logging.INFO)

#Get APIs
mapbox_access_token = os.getenv('MAPBOX_API')
tripadvisor_access_token = os.getenv('TRIPADVISOR_API')

#Initialize FastAPI
app = FastAPI()



@app.get("/get-route", response_model=Route)
async def get_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float) -> Route:
    try:
        #Construct initial route without stops
        route = await _call_route(start_lat, start_lon, end_lat, end_lon)

        #Use initial route to find stopping points
        num_stops = 5 #Initialize number of stops
        stopping_points = await _add_stop(route, num_stops)

        # Construct waypoints string and make new route with stopping points
        waypoints = ';'.join([f"{lon},{lat}" for lat, lon in stopping_points])
        route = await _call_route(start_lat, start_lon, end_lat, end_lon, waypoints)

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
async def _call_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float, waypoints: str = None) -> MapBox_route:
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
        'access_token': mapbox_access_token
    }

    response = requests.get(url, params=params)
    json_data = response.json()
    data = MapBox.model_validate(json_data)
    route = data.routes[0]  # The first route returned is considered the most recommended
    return route


async def _add_stop(route: MapBox_route, num_stops: int) -> list[list[float]]:
    #Conversion rate: 3600 seconds -> 1 hour

    #Create stopping point list
    stopping_points = []
    count = 1
    interval = route.duration / (num_stops + 1)
    current_time = 0
    steps = route.legs[0].steps
    coordinates = route.geometry.coordinates
    
    #Add stopping places until the trip is over
    while count <= num_stops:
        if current_time > interval * count:
            current_lat, current_lon = _find_position(coordinates, steps, current_time)
            stopping_points.append(await _find_stop('attractions',current_lat, current_lon, 30))
            count += 1

        #Increment time
        current_time += 50 

    return stopping_points


#Function that will calculate the current postion of user
def _find_position(coordinates: list[list[float]], steps: list[Mapbox_step], elapsed_time: float) -> list[float]:
    accumulated_time = 0
    for step in steps:
        step_duration = step.duration
        if accumulated_time + step_duration >= elapsed_time:
            ratio = (elapsed_time - accumulated_time) / step_duration
            start_coord = step.geometry.coordinates[0]
            end_coord = step.geometry.coordinates[-1]
            lat = start_coord[1] + ratio * (end_coord[1] - start_coord[1])
            lon = start_coord[0] + ratio * (end_coord[0] - start_coord[0])
            return [lat, lon]
        accumulated_time += step_duration
    return coordinates[-1]

#Find a nearby stop and return its coordinates
async def _find_stop(category: str, lat: str, lon: str, radius: str) -> list[float]:
    nearby_search_url = f"https://api.content.tripadvisor.com/api/v1/location/nearby_search?latLong={lat}%2C{lon}&key={tripadvisor_access_token}&category={category}&radius={radius}&radiusUnit=mi&language=en"
    headers = {"accept": "application/json"}
    try:
        response = requests.get(nearby_search_url, headers=headers)
        json_data = response.json()
        locations = Trip_Advisor_Location_Search.model_validate(json_data)
        if len(locations.data) > 0:
            location = locations.data[0]  # Get the first location from the response
            location_id = location.location_id
            coordinates = await _get_details(location_id)
            if coordinates is not None:
                return coordinates
            else:
                raise HTTPException(status_code=500, detail="Location data is missing latitude or longitude")
        else:
            raise HTTPException(status_code=404, detail="No locations found")
    except requests.exceptions.RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Tripadvisor request failed: {str(exception)}")
    except ValidationError as exception:
        raise HTTPException(status_code=501, detail=f'Improper TripAdvisor response: {str(exception)}')
    
#Grab details about the chosen location
async def _get_details(location_id:str) -> list[float]:
    location_details_url = f"https://api.content.tripadvisor.com/api/v1/location/{location_id}/details?key={tripadvisor_access_token}&language=en&currency=USD"
    headers = {"accept": "application/json"}

    response = requests.get(location_details_url, headers=headers)
    json_data = response.json()
    details = Trip_Advisor_Information.model_validate(json_data)

    lat = details.latitude
    lon = details.longitude
    return [lat,lon]