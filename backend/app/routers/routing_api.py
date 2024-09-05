from datetime import datetime, timedelta
from geopy.geocoders import OpenCage
from fastapi import APIRouter, HTTPException, Request, Response
import requests
from requests.exceptions import RequestException
from pydantic import ValidationError
from app.models.routing_models.routing_models import MapBox, Route, Route_Step, Route_Payload
from app.models.routing_models.trip_advisor_models import Trip_Advisor_Location_Search, Trip_Advisor_Information
from app.models.routing_models.amadeus_models import Amadeus_Access, Amadeus_Hotel_Search, Amadeus_Hotel_Offers, \
    Amadeus_Hotel_Ratings
from app.utils.geolocation_helpers import get_location
from dotenv import load_dotenv
from typing import Dict, Any, List, Tuple, Optional
import os
import logging
from lxml import html
import random

# Define the types for convenience
Mapbox_step = MapBox.MapBox_Route.Mapbox_leg.Mapbox_step
MapBox_route = MapBox.MapBox_Route

# Load environment variables
load_dotenv()

# Setup logging (for debugging)
logging.basicConfig(level=logging.INFO)

# Get API tokens
mapbox_access_token = os.getenv('MAPBOX_API')
tripadvisor_access_token = os.getenv('TRIPADVISOR_API')

# Grab app from APIRouter
router = APIRouter()

open_cage_key = os.getenv('OPENCAGE_KEY')

geolocator = OpenCage(api_key=open_cage_key, user_agent="RP-Hotels")  # Initialize a global geolocator


@router.get('/get-initial-route')
async def get_initial_route(start_lat: float,
                            start_lon: float,
                            end_lat: float,
                            end_lon: float) -> MapBox_route:
    try:
        # Construct initial route without stops
        initial_route = await _call_route(start_lat, start_lon, end_lat, end_lon)
        return initial_route
    except RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Mapbox request failed: {str(exception)}")
    except ValidationError as exception:
        raise HTTPException(status_code=502, detail=f'Improper Mapbox response: {str(exception)}')
    except (KeyError, ValueError) as exception:
        raise HTTPException(status_code=500, detail=f"Error processing Mapbox response: {str(exception)}")


@router.post("/generate-final-route", response_model=Route)
async def get_final_route(request: Request) -> Route:
    """
    Retrieves a route from Mapbox API, adds intermediate stops, and returns the detailed route information.

    Parameters:
        - request (Request): A JSON payload containing data of the initial route, number of stops, budget, and
        start date

    Returns:
        - Route: Detailed route information including coordinates, distance, duration, and step-by-step instructions.

    Raises:
        - HTTPException: For errors related to Mapbox requests or response processing.
    """

    try:
        # Validate provided payload and use data to initialize variables
        json_data = await request.json()
        payload = Route_Payload.model_validate(json_data)
        initial_route = payload.initial_route
        start_lon, start_lat = initial_route.geometry.coordinates[0]
        end_lon, end_lat = initial_route.geometry.coordinates[-1]
        num_stops = payload.num_stops
        start = payload.start
        budget = payload.budget
        print(budget)

        # Check for num_stops positive or zero
        if not isinstance(num_stops, int) or num_stops < 0:
            raise ValueError("Number of stops must be a non-negative integer")

        # Use initial route to find stopping points
        stopping_points, total_cost = await _add_stops(initial_route, num_stops, date=start, budget=budget)
        print("got stopping points")

        coordinates = []
        for stop in stopping_points:
            coordinates.append(stop['coordinates'])

        # Construct waypoints string and make new route with stopping points
        waypoints = ';'.join([f"{lon},{lat}" for lat, lon in coordinates])
        route = await _call_route(start_lat, start_lon, end_lat, end_lon, waypoints)
        distance, duration = route.distance, route.duration
        geometry = route.geometry
        steps = []

        idx = 0
        for leg in route.legs:

            # Add the duration to each stop
            if idx < len(stopping_points) and stopping_points[idx]['type'] != 'generic':
                stopping_points[idx]['duration'] = leg.duration  # For each stopping point add the duration to each
                if stopping_points[idx].get('address') is None:
                    location = get_location(geocoder=geolocator,
                                            coords=stopping_points[idx]['coordinates'])
                    if location:
                        stopping_points[idx]['address'] = location.address  # Add the address to each
            else:
                location = geolocator.reverse(f"{end_lat}, {end_lon}")
                # Include the duration to get to the end
                stopping_points.append({'name': 'Arrive at your destination',
                                        'duration': leg.duration,
                                        'type': 'end',
                                        'address': location.address})
            idx += 1
            for step in leg.steps:  # Not really doing anything
                # Each step has a distance, duration, instruction, and location
                steps.append(Route_Step(distance=step.distance,
                                        duration=step.duration,
                                        instruction=step.maneuver.instruction,
                                        location=step.maneuver.location))
        # Add all stopping coordinates to a single variable
        coordinates = [[start_lat, start_lon]] + coordinates + [[end_lat, end_lon]]
        print('Route budget:', total_cost)
        return Route(coordinates=coordinates,
                     distance=distance,
                     duration=duration,
                     steps=steps,
                     stops=stopping_points,
                     geometry=geometry,
                     cost=total_cost)

    except RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Mapbox request failed: {str(exception)}")
    except ValidationError as exception:
        raise HTTPException(status_code=502, detail=f'Improper Mapbox response: {str(exception)}')
    except (KeyError, ValueError) as exception:
        raise HTTPException(status_code=502, detail=f"Unexpected value or key: {str(exception)}")


async def _call_route(start_lat: float, start_lon: float, end_lat: float, end_lon: float,
                      waypoints: str = None) -> MapBox_route:
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


async def _add_stops(route: MapBox_route, num_stops: int, date: datetime, budget: float, daily_start: int = 9,
                     daily_end: int = 16) -> \
        tuple[list[dict[str, list[float] | str] | dict[str, Any]], int]:
    """
    Determines stopping points along the route based on the specified number of stops.

    Parameters:
    - route (MapBox_route): The route object containing route details.
    - num_stops (int): Number of intermediate stops to include.
    - date (datetime): Takes in the start date of the trip
    - daily_start (int): The hour of each day the user wants to start driving.
    - daily_end (int): The hour of each day the user wants to end driving.

    Returns:
    - list[Dict[str, Any]]: List of details for the stopping points.
    """
    stopping_points = []
    interval = route.duration / (num_stops + 1)  # Divide trip up into segments for finding stops in seconds
    end_hotel_search = route.duration - 3600 * 4  # Stop looking for hotels if within the last 4 hours of the trip (Latest you could get there is 8pm)
    end_stop_search = route.duration - 1800 # Stop looking for attractions within the last 30 minutes of trip
    current_time = date.hour * 3600  # Initialize the current time of the day in seconds
    steps = route.legs[0].steps  # Only one leg in the initial route
    coordinates = route.geometry.coordinates  # Get all coordinates of the route
    current_day = 1  # Initialize number of days in route
    total_time = 0  # Total time traveled to the destination
    time_till_stop = interval  # Track the time until next stop
    driving_interval = daily_end - daily_start

    price_range = _get_price_range(remaining_budget=budget,  # Get an initial price range for the hotels
                                   duration_left=route.duration,
                                   stops_left=num_stops,
                                   daily_drive_time=driving_interval, )
    total_cost = 0  # Initialize value to track cost

    # Add stopping places until the trip is over
    for _ in range(num_stops + 1):
        # Check whether the daily end or the next stop comes first
        while total_time < end_hotel_search and current_time + time_till_stop >= (daily_end * 3600):
            time_traveled = (daily_end * 3600) - current_time  # Calculate time traveled that day
            total_time += time_traveled  # Add the time traveled toward the next stop that day
            date += timedelta(seconds=time_traveled)
            time_till_stop -= time_traveled  # Remove the amount of time traveled in the day from time to the stop
            hotel_lat, hotel_lon = _find_position(coordinates, steps, total_time)  # figure out the location at 5PM
            attempts = 12  # 12 attempts (6 hours) to find a hotel before raising an error with the route
            while attempts > 0:
                try:
                    print('finding hotel...', hotel_lat, hotel_lon)
                    stopping_points.append(await _find_hotel(hotel_lat,
                                                             hotel_lon,
                                                             price_range,
                                                             date))  # Append a found hotel
                    break
                except HTTPException as exception:
                    if exception.status_code == 404:  # Handle a not found error occurring
                        attempts -= 1  # subtract an attempt
                        if attempts == 0:
                            raise exception  # Raise an error after 3 tries
                        total_time += 1800  # Increase total drive time by 30 minutes
                        print(total_time)
                        time_till_stop -= 3600  # Decrease time till stop by 30 minutes
                        date += timedelta(seconds=1800)  # Increase the datetime
                        hotel_lat, hotel_lon = _find_position(coordinates, steps,
                                                              total_time)  # Find the new position after driving
                    else:
                        raise exception
            print('found hotel!')
            total_cost += stopping_points[-1]['price']  # Add the cost of the hotel
            print(f"budget - total cost: {budget}-{total_cost} = {budget - total_cost}")
            print(f"remaining duration: {route.duration - total_time}")
            print(f"number of stops left: {num_stops}")
            # Recalculate a price range for the next hotel
            price_range = _get_price_range(remaining_budget=budget - total_cost,
                                           duration_left=route.duration - total_time,
                                           stops_left=num_stops,
                                           daily_drive_time=driving_interval)
            print(price_range)
            current_day += 1  # increment the days that have passed
            current_time = 3600 * daily_start  # set the current time to be the desired start time the next day
            date = datetime(date.year, date.month, date.day + 1, daily_start, 0, 0)  # New day

        # Ensure we are within the route duration and not looking past 9 pm for a stop
        if (total_time + time_till_stop < end_stop_search) and current_time < (21*3600) and num_stops > 0:
            total_time += time_till_stop  # Increment the total time by time traveled to stop
            current_lat, current_lon = _find_position(coordinates, steps, total_time)  # Find the next stop position
            print('finding stop...', current_lat, current_lon)
            current_time += time_till_stop + (3600 * 2)  # Current time includes distance and time spent at stop
            stopping_points.append(
                await _find_stop('attractions', current_lat, current_lon, 30))  # Add the stop to the list
            print('found stop!')
            num_stops -= 1  # Decrement the number of stops
            date += timedelta(hours=2,
                              seconds=interval)  # Allocate two hours detours per stop/ increment for the time to drive to the location
            time_till_stop = interval  # Reset the time to the next stop
    return stopping_points, total_cost


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


async def _find_stop(category: str, lat: str, lon: str, radius: str) -> Dict[str, Any]:
    """
    Finds a nearby location of a specific category using the TripAdvisor API and returns its coordinates.

    Parameters:
    - category (str): Category of the location to search for (e.g., 'attractions').
    - lat (str): Latitude of the search location.
    - lon (str): Longitude of the search location.
    - radius (str): Search radius in miles.

    Returns:
    - Dict[str, Any]: Details of an attraction with a name and location.

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
            details = await _get_details(location_id)
            if details is not None:
                return details
            else:
                raise HTTPException(status_code=500, detail="Location data is missing latitude or longitude")
        else:
            raise HTTPException(status_code=404, detail="No locations found")

    except RequestException as exception:
        raise HTTPException(status_code=500, detail=f"TripAdvisor request failed: {str(exception)}")
    except ValidationError as exception:
        raise HTTPException(status_code=502, detail=f'Improper TripAdvisor response: {str(exception)}')


async def _get_details(location_id: str) -> Dict[str, Any]:
    """
    Retrieves detailed information about a location from the TripAdvisor API using its location ID.

    Parameters:
    - location_id (str): The ID of the location to retrieve details for.

    Returns:
    - Dict[str, Any]: Details of an attraction with a name and location.

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
    name = details.name
    url = details.web_url
    address = details.address_obj.address_string
    print("stop category: ", details.subcategory)
    print("stop group", details.groups)
    return {'coordinates': [lat, lon], 'name': name, 'type': 'stop', 'url': url, 'address': address}


async def _find_hotel(lat: float, lon: float, price_range: Tuple[Tuple[float, float], str], check_in: datetime,
                      radius: int = 30) -> \
        dict[str, list[float] | str]:
    """
    Finds a hotel location for a given position and radius. Each hotel will have a name, coordinates, address, type,
    price, stars, review_count.

    Args:
    - lat(float): Latitude of the search area
    - lon(float): Longitude of the search area
    - radius(int): Radius in miles to search for hotels

    Returns:
    - dict[str, list[float] | str]: A dictionary containing the hotel description and navigation

    Raises:
    - HTTPException: For errors related to TripAdvisor requests or response processing.

    """
    try:
        # Webscrape first
        print(price_range)
        query = get_location(geocoder=geolocator, coords=[lat, lon]).address
        valid_hotel = find_google_hotels(query=query, price_range=price_range[0])
        if valid_hotel:
            valid_hotel['type'] = 'hotel'
            return valid_hotel

        # If scraping fails use the Amadeus API
        access_token = await _get_amadeus_token(os.getenv('AMADEUS_KEY'), os.getenv('AMADEUS_SECRET'))
        hotels_list_url = "https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-geocode"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        params = {
            'latitude': lat,
            'longitude': lon,
            'radius': radius,
            'radiusUnit': 'MILE',
            'ratings': ['2', '3', '4', '5'],  # Indicates hotel star level
        }
        response = requests.get(hotels_list_url, params=params, headers=headers)
        json_data = response.json()
        # If no hotel is found search for one with a larger radius
        if response.status_code == 400 and json_data['errors'][0]['code'] == 895:
            return await _find_hotel(lat, lon, price_range, check_in, radius + 10)
        hotels = Amadeus_Hotel_Search.model_validate(json_data)  # Validate the response
        hotel_list = hotels.data
        if len(hotel_list) > 0:
            # Put price function here
            hotel_info = {}  # Initialize a dictionary to store hotel info with the key being the hotelId
            id_list = []  # List of hotel id's to send for to get offers
            for hotel in hotel_list:  # Loop through all nearby hotels for coordinates, id, and name
                coordinates = [hotel.geoCode['latitude'], hotel.geoCode['longitude']]  # Get coordinates for routing
                hotel_id = hotel.hotelId  # Amadeus's unique hotel ID
                id_list.append(hotel_id)  # Add the id to the id_list
                name = hotel.name.lower()
                hotel_info[hotel_id] = {'coordinates': coordinates, 'name': name.capitalize(),
                                        'type': 'hotel'}  # Add relevant info from the search to hotel_info
            # Get a dict of offers using hotelIds as keys
            offers = await _get_amadeus_offers(access_token=access_token,
                                               hotel_ids=id_list,
                                               check_in=check_in,
                                               check_out=datetime(check_in.year, check_in.month, check_in.day + 1, 9,
                                                                  0,
                                                                  0),  # The next day at 9 AM
                                               price_range=price_range[1])
            highest_rated = await _get_amadeus_ratings(offers.keys())  # Look for ratings on the hotels with valid offers
            best_offer = offers[highest_rated[0]]  # Use the hotelId returned with highest_rated to get its offer info
            location = hotel_info[
                best_offer['hotel_id']]  # Retrieve the saved hotel_info from the hotel_id of the found offer
            location['price'] = best_offer['price']  # Add pricing to the already saved info hotel info
            location['name'] = best_offer['name']  # Add the name to location info
            location['stars'] = round(highest_rated[1] / 20, 2)  # Get a star value by dividing the 0-100 rating
            # Returns a dictionary with a coordinates, name, type, price, and rating of the hotel
            return location
        else:
            raise HTTPException(status_code=404, detail="No hotels found")
    except RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Amadeus request failed: {str(exception)}")
    except ValidationError as exception:
        raise HTTPException(status_code=502, detail=f'Improper Amadeus response: {str(exception)}')


async def find_amadeus_hotels():
    pass


async def _get_amadeus_offers(access_token: str, hotel_ids: list[str], check_in: datetime, check_out: datetime,
                              price_range: str,
                              adults: int = 2) -> dict[str, Any]:
    """
    Returns pricing info on the highest rated hotel that is within a given price range

    Args:
        - access_token(str): Amadeus access token
        - hotel_ids(list[str]): List of hotels ids
        - check_in(datetime): Check in date and time
        - check_out(datetime): Check out date and time
        - price_range(str): Price range for hotels
        - adults(int): Number of adults

    Returns
        - dict[str, Any]: A dictionary containing the hotel description and pricing information

    Raises
        - HTTPException: For errors related to Amadeus requests or response processing.

    """
    hotel_price_url = "https://test.api.amadeus.com/v3/shopping/hotel-offers"
    check_in_date = check_in.strftime('%Y-%m-%d')
    check_out_date = check_out.strftime('%Y-%m-%d')
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        'hotelIds': hotel_ids,
        'adults': adults,  #TODO allow for guests to specify the number of ppl
        'checkInDate': check_in_date,  #TODO allow user to specify a trip start date
        'checkOutDate': check_out_date,
        'priceRange': price_range,
        'currency': 'USD',
    }
    try:
        response = requests.get(hotel_price_url, params=params, headers=headers)
        json_data = response.json()
        offers = Amadeus_Hotel_Offers.model_validate(json_data)
        if len(offers.data) > 0:  # Ensure at least one hotel is returned
            valid_offers = {}  # A dict to track valid offers
            for hotel in offers.data:
                min_offer = 1000000  # Set a min to be impossibly expensive
                offer_list = hotel.offers  # List of offers from a single hotel
                hotel_name = hotel.hotel.name
                hotel_id = hotel.hotel.hotelId  # Amadeus ID of the hotel
                for offer in offer_list:  # Retrieve the offer price
                    total = float(offer.price.total)  # Convert the str into a float
                    if total < min_offer:
                        min_offer = total  # Track the cheapest offer that fits the user's criteria per hotel
                temp_offer = {
                    'name': hotel_name,
                    'price': min_offer,
                }
                valid_offers[hotel_id] = temp_offer
            return valid_offers
        else:
            raise HTTPException(status_code=404, detail="No offers found for this price range")
    except ValidationError as exception:
        raise HTTPException(status_code=502, detail=f"Error validating Amadeus offer response: {str(exception)}")
    except RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Amadeus request failed: {str(exception)}")


async def _get_amadeus_ratings(hotel_ids: list[str]) -> tuple:
    """
    Return a list of tuples of hotelIds and ratings sorted from highest to lowest rating

    Args:
        - hotel_ids: A list of amadeus hotel IDs

    Returns:
        - tuple: A tuple containing the hotelId and rating for the highest rated hotel from the list

    """
    try:
        access_token = await _get_amadeus_token(os.getenv('AMADEUS_KEY'), os.getenv('AMADEUS_SECRET'))
        hotels_list_url = "https://test.api.amadeus.com/v2"
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        params = {
            "hotelIds": hotel_ids
        }
        response = requests.get(hotels_list_url, params=params, headers=headers)
        json_data = response.json()
        sentiments = Amadeus_Hotel_Ratings.model_validate(json_data).data  # all the returned hotel sentiments
        ratings = []  # List to store the returned hotel ratings
        if len(sentiments) > 0:
            for hotel in sentiments:
                hotel_id = hotel.hotelId
                rating = hotel.overallRating
                ratings.append((hotel_id, rating))
            ratings.sort(key=lambda x: x[1], reverse=True)
            print(ratings)
            return ratings[0]
        else:
            raise HTTPException(status_code=404, detail="No hotels found for the provided ids")
    except ValidationError as exception:
        raise HTTPException(status_code=502, detail=f'Improper Amadeus response: {str(exception)}')
    except (KeyError, ValueError) as exception:
        raise HTTPException(status_code=500, detail=f'Unable to parse response: {str(exception)}')


async def _get_amadeus_token(API_KEY: str, API_SECRET: str) -> str:
    """
    A function to get the amadeus access token to use its API

    Args:
    - API_KEY: The API key generated from an Amadeus account
    - API_SECRET: The API secret generated from an Amadeus account

    Returns:
    - str: The Amadeus access token

    Raises:
    - HTTPException: For errors related to an unexpected response from Amadeus.
    """
    url = "https://test.api.amadeus.com/v1/security/oauth2/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {
        "grant_type": "client_credentials",
        "client_id": API_KEY,
        "client_secret": API_SECRET
    }
    try:
        response = requests.post(url, headers=headers, data=data)
        json_data = response.json()
        response_data = Amadeus_Access.model_validate(json_data)
        if response_data.access_token is not None:
            return response_data.access_token
        else:
            raise HTTPException(status_code=404, detail="No Amadeus access token returned")
    except ValidationError as exception:
        raise HTTPException(status_code=502, detail=f'Improper Amadeus response: {str(exception)}')


def find_google_hotels(query: str, price_range: Tuple[float, float]) -> Dict[str, Any] | None:
    """
    Handles the parsing of a Google hotels for the best hotel given the users preferences

    Args:
        - query: The search parameter for google
        - price_range: a tuple containing max and min pricing

    Returns:
        - Dict[str, Any]: Relevant hotel information

    Raises:
        - HTTPException: When no hotel information is found
    """
    url = 'https://www.google.com/travel/search'  # Link to google hotels
    response = _get_html_response(query=query, url=url)
    if response.status_code == 200:
        listings = _parse_google_response(response.text)  # Convert the response to a string to parse
        if len(listings) > 0:  # Ensure listings were found
            # Filter hotels out of budget
            valid_hotels = list(filter(lambda listing: price_range[0] <= listing['price'] <= price_range[1], listings))
            while len(valid_hotels) > 0:  # Search through all hotel offerings
                print("advanced search...", valid_hotels)
                ideal_hotel = _get_advanced_listing(
                    valid_hotels.pop())  # Get detailed information on the highest rated hotel
                if ideal_hotel is not None:  # Ensure advanced information was found
                    return ideal_hotel
        raise HTTPException(status_code=404,
                            detail="No valid hotels found for the given parameters")  # To handle research


def _get_html_response(url: str, query: Optional[str] = None) -> Response:
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:85.0) Gecko/20100101 Firefox/85.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/88.0.4324.96 Safari/537.36',
    ]  # A small list containing reliable user agents
    if query:
        params = {
            'q': query,
        }
    else:
        params = None

    headers = {
        'user-agent': random.choice(user_agents),  # select a random reliable user-agent
        'authority': 'www.google.com',
        'method': 'GET',
        'scheme': 'https',
        'accept-language': 'en-US,en;q=0.9',
        'cache-control': 'max-age=0',
        'upgrade-insecure-requests': '1',
        'DNT': "1"  # Do not track the request header
    }

    print("search query:", query)
    response = requests.get(url, params=params, headers=headers)
    return response


def _parse_google_response(response: str) -> List[Dict[str, Any]]:
    """
    Parses an HTML response for hotel information
    Parameters
        - response: The HTML response in string format

    Returns
        - List[Dict[str, Any]]: List of hotel information sorted by rating

    """
    parser = html.fromstring(response)
    hotels_list = parser.xpath("//div[@jsname='mutHjb']")  # Get a list of divs which contain the specified jsname
    listings = []
    for hotel in hotels_list:
        name = hotel.xpath(".//h2[@class='BgYkof ogfYpf ykx2he']/text()")  # Get this classes text value
        google_url = hotel.xpath(".//a[@class='PVOOXe']/@href")  # Get the google listing link for later scraping
        rank_details = hotel.xpath(".//span[@class='ta47le ']/@aria-label")
        pricing_details = hotel.xpath(  # List includes extraneous information unreliably
            ".//span[@jsaction='mouseenter:JttVIc;mouseleave:VqIRre;']//text()"
        )
        if len(pricing_details) == 4:  # Ensure all pricing info is being returned
            price = int(pricing_details[0].replace('$', ''))  # Format and convert the price for further processing
            stars, review_count = _str_to_rating(rank_details[0])  # Extract rank information
            listings.append({  # Add a hotel with all its relevant information
                "name": name[0],
                "url": f"https://www.google.com{google_url[0]}",
                "price": price,
                "stars": stars,
                "review_count": review_count,
            })
    if len(listings) > 0:
        listings.sort(key=lambda listing: listing["stars"])  # Sort hotels lowest rated to highest
    return listings


def _get_advanced_listing(hotel: Dict[str, Any]) -> Dict[str, Any] | None:
    """
    Scrapes a given hotel listing for an accurate website url and location info
    Args:
        hotel(Dict[str, Any]): The hotel information that will be updated

    Returns:
        Dict[str, Any]: The updated hotel listing

    """
    response = _get_html_response(url=hotel['url'])  # Use the already found direct google url
    if response.status_code == 200:
        parser = html.fromstring(response.text)  # Format the data for parsing
        details = parser.xpath("//div[@class='iInyCf QqZUDd Zuc8V BLvVUb HoSN7e']")  # Div with relevant info
        if len(details) > 0:  # Ensure details were found
            details = details[0]  # set the details to be the first instance
            hotel_location_path = details.xpath(".//div[@class='K4nuhf']")[
                0]  # Exact container that will always have location
            address = hotel_location_path.xpath(".//span[@class='CFH2De']/text()")[
                0]  # Get the full address from the website page
            location = get_location(geocoder=geolocator, address=address)  # Geolocate for additional area info
            coordinates = [location.latitude, location.longitude]  # Get the coordinates of the hotel
            # Add new values to the dictionary
            hotel['coordinates'], hotel['address'] = coordinates, address
            return hotel  # Return the updated data
        return None


def _get_price_range(remaining_budget: float, duration_left: float, stops_left: int, daily_drive_time: int) -> tuple[
    tuple[float, float], str]:
    """
    Function to dynamically calculate a price range based on remaining trip length and budget

    Args:
        - remaining_budget(float): The remaining budget for the trip
        - duration_left(float): The driving duration of the trip
        - stops_left(int): The number of stops left for the trip
        - daily_drive_time(int): The daily drive time for the trip

    Returns:
        - tuple[tuple[float, float], str]: The dynamic price range for the next hotel

    """
    # Found the full days of driving left in the trip
    days_left = (duration_left + stops_left * (2 * 3600)) // (daily_drive_time * 3600)
    if days_left == 0:
        remaining_avg = remaining_budget
    else:
        remaining_avg = remaining_budget / days_left  # Get a new avg cost of hotels by taking away the current price
    min_cost, max_cost = remaining_avg - 75, remaining_avg + 75  # 100 dollar deviations from price avg for a reasonable range
    if remaining_avg > 100:
        return (min_cost, max_cost), f"{min_cost:.2f}-{max_cost:.2f}"
    else:
        return (0, max_cost), f"0-{max_cost:.2f}"


def _str_to_rating(rating: str) -> Tuple[float, int]:
    """
    Parses scraped rating information for relevant number

    Args:
        rating(str): Scraped unprocessed data for ratings

    Returns:
        Tuple[float, int]: The number of stars (0-5) and user review count

    """
    details = rating.split()
    stars = float(details[0])  # Get the star rating
    review_count = int(details[6].replace(',', ''))  # Remove commas to get review count as an integer
    return stars, review_count
