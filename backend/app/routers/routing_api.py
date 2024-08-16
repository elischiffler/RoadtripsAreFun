from fastapi import APIRouter, HTTPException
import requests
from requests.exceptions import RequestException
from pydantic import ValidationError
from app.models.routing_models import MapBox, Route, Route_Step, Trip_Advisor_Location_Search, Trip_Advisor_Information
from dotenv import load_dotenv
import os
import logging

# Define the types for convenience
Mapbox_step = MapBox.MapBox_Route.Mapbox_leg.Mapbox_step
MapBox_route = MapBox.MapBox_Route

# Load environment variables
load_dotenv()

# Setup logging (for debugging)
logging.basicConfig(level=logging.INFO)

# Get APIs
mapbox_access_token = os.getenv('MAPBOX_API')
tripadvisor_access_token = os.getenv('TRIPADVISOR_API')

# Grab app from APIRouter
router = APIRouter()

@router.get("/get-route", response_model=Route)
async def get_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float, num_stops: int = 5) -> Route:
    """
    Retrieves a route from Mapbox API, adds intermediate stops, and returns the detailed route information.

    Parameters:
    - start_lat (float): Latitude of the starting point.
    - start_lon (float): Longitude of the starting point.
    - end_lat (float): Latitude of the destination point.
    - end_lon (float): Longitude of the destination point.
    - num_stops (int): Number of intermediate stops to include in the route.

    Returns:
    - Route: Detailed route information including coordinates, distance, duration, and step-by-step instructions.

    Raises:
    - HTTPException: For errors related to Mapbox requests or response processing.
    """
    #Check for num_stops positive or zero
    if not isinstance(num_stops, int) or num_stops < 0:
        raise ValueError("Number of stops must be a non-negative integer")
    
    try:
        # Construct initial route without stops
        route = await _call_route(start_lat, start_lon, end_lat, end_lon)

        # Use initial route to find stopping points
        stopping_points = await _add_stops(route, num_stops)

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
        
        #Add all stopping coordinates to a single variable
        coordinates = [[start_lat, start_lon]] + stopping_points + [[end_lat, end_lon]]

        return Route(coordinates=coordinates,
                     distance=distance,
                     duration=duration,
                     steps=steps)
    
    except RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Mapbox request failed: {str(exception)}")
    except ValidationError as exception:
        raise HTTPException(status_code=501, detail=f'Improper Mapbox response: {str(exception)}')
    except (KeyError, ValueError) as exception:
        raise HTTPException(status_code=502, detail=f"Error processing Mapbox response: {str(exception)}")
    

async def _call_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float, waypoints: str = None) -> MapBox_route:
    """
    Calls the Mapbox Directions API to get a route between start and end points, optionally including waypoints.

    Parameters:
    - start_lat (float): Latitude of the starting point.
    - start_lon (float): Longitude of the starting point.
    - end_lat (float): Latitude of the destination point.
    - end_lon (float): Longitude of the destination point.
    - waypoints (str, optional): Semicolon-separated list of waypoints to include in the route.

    Returns:
    - MapBox_route: The route object containing route details.

    Raises:
    - HTTPException: For errors related to the Mapbox API request or response.
    """
    call_route_url = f"https://api.mapbox.com/directions/v5/mapbox/driving/{start_lon},{start_lat}"
    if waypoints:
        call_route_url += f";{waypoints}"
    call_route_url += f";{end_lon},{end_lat}"
    params = {
        'alternatives': 'false',
        'geometries': 'geojson',
        'language': 'en',
        'overview': 'full',
        'steps': 'true',
        'access_token': mapbox_access_token
    }

    response = requests.get(call_route_url, params=params)
    json_data = response.json()
    data = MapBox.model_validate(json_data)
    route = data.routes[0]  #TODO can change the index for different routes (0 is recommended route)
    return route


async def _add_stops(route: MapBox_route, num_stops: int) -> list[list[float]]:
    """
    Determines stopping points along the route based on the specified number of stops.

    Parameters:
    - route (MapBox_route): The route object containing route details.
    - num_stops (int): Number of intermediate stops to include.

    Returns:
    - list[list[float]]: List of coordinates for the stopping points.
    """
    stopping_points = []
    interval = route.duration / (num_stops + 1)
    current_time = interval
    steps = route.legs[0].steps
    coordinates = route.geometry.coordinates
    
    # Add stopping places until the trip is over
    for _ in range(num_stops):
        if current_time < route.duration:  # Ensure we are within the route duration
            current_lat, current_lon = _find_position(coordinates, steps, current_time)
            stopping_points.append(await _find_stop('attractions', current_lat, current_lon, 30))
            current_time += interval  # Increment time for the next stop

    return stopping_points


def _find_position(coordinates: list[list[float]], steps: list[Mapbox_step], elapsed_time: float) -> list[float]:
    """
    Calculates the position along a route based on elapsed time and step information.

    Parameters:
    - coordinates (list[list[float]]): List of coordinates representing the route geometry.
    - steps (list[Mapbox_step]): List of steps representing the route.
    - elapsed_time (float): Elapsed time since the start of the route.

    Returns:
    - list[float]: Latitude and longitude of the position at the given elapsed time.
    """
    accumulated_time = 0  # Initialize accumulated travel time
    for step in steps:
        step_duration = step.duration  # Duration of the current step

        # Check if the elapsed time falls within the current step
        if accumulated_time + step_duration >= elapsed_time:

            # Get a ratio for interpolation
            ratio = (elapsed_time - accumulated_time) / step_duration

            # Get the starting and ending coordinates of the current step
            start_coord = step.geometry.coordinates[0]
            end_coord = step.geometry.coordinates[-1]

            # Interpolate the latitude and longitude based on the ratio
            lat = start_coord[1] + ratio * (end_coord[1] - start_coord[1])
            lon = start_coord[0] + ratio * (end_coord[0] - start_coord[0])

            # Return the interpolated coordinates
            return [lat, lon]
        
        # Update the accumulated travel time 
        accumulated_time += step_duration

    # If the elapsed time exceeds the total duration, return the last coordinate
    return coordinates[-1]


async def _find_stop(category: str, lat: str, lon: str, radius: str) -> list[float]:
    """
    Finds a nearby location of a specific category using the TripAdvisor API and returns its coordinates.

    Parameters:
    - category (str): Category of the location to search for (e.g., 'attractions').
    - lat (str): Latitude of the search location.
    - lon (str): Longitude of the search location.
    - radius (str): Search radius in miles.

    Returns:
    - list[float]: Coordinates (latitude and longitude) of the nearest location.

    Raises:
    - HTTPException: For errors related to TripAdvisor requests or response processing.
    """
    nearby_search_url = "https://api.content.tripadvisor.com/api/v1/location/nearby_search"
    params = {
        'latLong': f"{lat}%2C{lon}",
        'key': tripadvisor_access_token,
        'category': category,
        'radius': radius,
        'radiusUnit': 'mi',
        'language': 'en'
    }

    try:
        response = requests.get(nearby_search_url, params=params)
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
    except RequestException as exception:
        raise HTTPException(status_code=500, detail=f"TripAdvisor request failed: {str(exception)}")
    except ValidationError as exception:
        raise HTTPException(status_code=501, detail=f'Improper TripAdvisor response: {str(exception)}')

                            
async def _get_details(location_id: str) -> list[float]:
    """
    Retrieves detailed information about a location from the TripAdvisor API using its location ID.

    Parameters:
    - location_id (str): The ID of the location to retrieve details for.

    Returns:
    - list[float]: Coordinates (latitude and longitude) of the location.

    Raises:
    - HTTPException: For errors related to TripAdvisor requests or response processing.
    """
    location_details_url = f"https://api.content.tripadvisor.com/api/v1/location/{location_id}/details"
    params = {
        'key': tripadvisor_access_token,
        'language': 'en',
        'currency': 'USD'
    }

    response = requests.get(location_details_url, params=params)
    json_data = response.json()
    details = Trip_Advisor_Information.model_validate(json_data)

    lat = details.latitude
    lon = details.longitude
    return [lat, lon]
