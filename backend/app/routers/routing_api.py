from datetime import datetime, timedelta
from geopy.geocoders import Nominatim
from fastapi import APIRouter, HTTPException, Request
import requests
from requests.exceptions import RequestException
from pydantic import ValidationError
from app.models.routing_models.routing_models import MapBox, Route, Route_Step, Route_Payload
from app.models.routing_models.trip_advisor_models import Trip_Advisor_Location_Search, Trip_Advisor_Information
from app.models.routing_models.amadeus_models import Amadeus_Access, Amadeus_Hotel_Search, Amadeus_Hotel_Offers, \
    Amadeus_Hotel_Ratings
from dotenv import load_dotenv
from typing import Dict, Any
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


@router.get('/get-initial-route')
async def get_initial_route(start_lat: float,
                            start_lon: float,
                            end_lat: float,
                            end_lon: float) -> MapBox_route:
    try:
        # Construct initial route without stops
        initial_route = await _call_route(start_lat, start_lon, end_lat, end_lon)
        print("got initial route")
        duration = initial_route.duration
        # Return the duration
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
    - start_lat (float): Latitude of the starting point.
    - start_lon (float): Longitude of the starting point.
    - end_lat (float): Latitude of the destination point.
    - end_lon (float): Longitude of the destination point.
    - num_stops (int): Number of intermediate stops to include in the route.
    - start(datetime): Start date of the route.

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
        start=payload.start
        budget=payload.budget

        # Check for num_stops positive or zero
        if not isinstance(num_stops, int) or num_stops < 0:
            raise ValueError("Number of stops must be a non-negative integer")

        # Use initial route to find stopping points
        stopping_points = await _add_stops(initial_route, num_stops, date=start, budget=budget)
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
        geolocator = Nominatim(user_agent="RP-Hotels")  # Initialize a geolocator

        idx = 0
        for leg in route.legs:

            # Add the duration to each stop
            if idx < len(stopping_points) and stopping_points[idx]['type'] != 'generic':
                stopping_points[idx]['duration'] = leg.duration
                temp_coordinates = stopping_points[idx]['coordinates']
                location = geolocator.reverse(f"{temp_coordinates[0]}, {temp_coordinates[1]}")  # Reverse geolocate
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
            for step in leg.steps:
                # Each step has a distance, duration, instruction, and location
                steps.append(Route_Step(distance=step.distance,
                                        duration=step.duration,
                                        instruction=step.maneuver.instruction,
                                        location=step.maneuver.location))
        # Add all stopping coordinates to a single variable
        coordinates = [[start_lat, start_lon]] + coordinates + [[end_lat, end_lon]]
        print('ready to return')
        return Route(coordinates=coordinates,
                     distance=distance,
                     duration=duration,
                     steps=steps,
                     stops=stopping_points,
                     geometry=geometry)

    except RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Mapbox request failed: {str(exception)}")
    except ValidationError as exception:
        raise HTTPException(status_code=502, detail=f'Improper Mapbox response: {str(exception)}')
    except (KeyError, ValueError) as exception:
        raise HTTPException(status_code=502, detail=f"Error processing Mapbox response: {str(exception)}")


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
        list[Dict[str, Any]]:
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
    end_search = route.duration - 3600  # Stop looking for stops if within the last hour of the trip
    current_time = date.hour * 3600  # Initialize the current time of the day in seconds
    steps = route.legs[0].steps  # Only one leg in the initial route
    coordinates = route.geometry.coordinates  # Get all coordinates of the route
    current_day = 0  # Initialize number of days in route
    total_time = 0  # Total time traveled to the destination
    time_till_stop = interval  # Track the time until next stop
    estimate_of_days = route.duration // ((daily_end - daily_start) * 3600)  # Estimate for days the route will take
    if estimate_of_days > 0:
        price_range = _get_price_range(budget, budget / estimate_of_days, num_stops)  # TODO Implement budget
    else:
        price_range = _get_price_range(budget, budget, num_stops)

    # Add stopping places until the trip is over
    for _ in range(num_stops + 1):
        # Check whether the daily end or the next stop comes first
        while total_time < end_search and current_time + time_till_stop >= (
                daily_end * 3600):  # Check if next stop or daily end comes next
            time_traveled = (daily_end * 3600) - current_time  # Calculate time traveled that day
            total_time += time_traveled  # Add the time traveled toward the next stop that day
            date += timedelta(seconds=time_traveled)
            print('finding hotel...')
            time_till_stop -= time_traveled  # Remove the amount of time traveled in the day from time to the stop
            hotel_lat, hotel_lon = _find_position(coordinates, steps, total_time)  # figure out the location at 5PM
            stopping_points.append(await _find_hotel(hotel_lat,
                                                     hotel_lon,
                                                     price_range,
                                                     date))  # Append a found hotel
            print('found hotel!')
            current_day += 1  # increment the days that have passed
            current_time = 3600 * daily_start  # set the current time to be the desired start time the next day
            date = datetime(date.year, date.month, date.day + 1, daily_start, 0, 0)  # New day

        if total_time + time_till_stop < end_search:  # Ensure we are within the route duration
            total_time += time_till_stop  # Increment the total time by time traveled to stop
            print('finding stop...')
            print(total_time)
            print(route.duration)
            current_lat, current_lon = _find_position(coordinates, steps, total_time)  # Find the next stop position
            print(current_lat, current_lon)
            current_time += time_till_stop + (3600 * 2)  # Current time includes distance and time spent at stop
            stopping_points.append(
                await _find_stop('attractions', current_lat, current_lon, 30))  # Add the stop to the list
            print('found stop!')
            date += timedelta(hours=2,
                              seconds=interval)  # Allocate two hours detours per stop/ increment for the time to drive to the location
            time_till_stop = interval  # Reset the time to the next stop
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
        print(params)
        response = requests.get(nearby_search_url, params=params)
        json_data = response.json()
        print(response.status_code)
        locations = Trip_Advisor_Location_Search.model_validate(json_data)
        print('validated')
        if len(locations.data) > 0:
            location = locations.data[0]  # Get the first location from the response
            location_id = location.location_id
            print('getting details')
            details = await _get_details(location_id)
            print('got details')
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
    name = details.name.lower()
    return {'coordinates': [lat, lon], 'name': name.capitalize(), 'type': 'stop'}


async def _find_hotel(lat: float, lon: float, price_range: str, check_in: datetime, radius: int = 30) -> \
        dict[str, list[float] | str]:
    """
    Finds a hotel location for a given position and radius.

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
        print(json_data)
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
            # Get the cheapest offer that matches the user's preference per hotel
            offers = await _get_offers(access_token=access_token,
                                       hotel_ids=id_list,
                                       check_in=check_in,
                                       check_out=datetime(check_in.year, check_in.month, check_in.day + 1, 9,
                                                          0,
                                                          0),  # The next day at 9 AM
                                       price_range=price_range)
            print(offers.keys())
            highest_rated = await _get_hotel_ratings(offers.keys())  # Look for ratings on the hotels with valid offers
            best_offer = offers[highest_rated[0]]  # Use the hotelId returned with highest_rated to get its offer info
            location = hotel_info[
                best_offer['hotel_id']]  # Retrieve the saved hotel_info from the hotel_id of the found offer
            location['price'] = best_offer['price']  # Add pricing to the already saved info hotel info
            location['name'] = best_offer['name']  # Add the name to location info
            location['rating'] = highest_rated[1]
            # Returns a dictionary with a coordinates, name, type, price, and rating of the hotel
            return location
        else:
            raise HTTPException(status_code=404, detail="No hotels found")
    except RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Amadeus request failed: {str(exception)}")
    except ValidationError as exception:
        raise HTTPException(status_code=502, detail=f'Improper Amadeus response: {str(exception)}')


async def _get_offers(access_token: str, hotel_ids: list[str], check_in: datetime, check_out: datetime,
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
    hotel_price_url = "https://test.api.amadeus.com/v2/shopping/hotel-offers"
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
        print(json_data)
        json_data = {
            "data": [
                {
                    "type": "hotel-offers",
                    "hotel": {
                        "type": "hotel",
                        "hotelId": "MCLONGHM",
                        "chainCode": "MC",
                        "dupeId": "700031300",
                        "name": "JW Marriott Grosvenor House London",
                        "cityCode": "LON",
                        "latitude": 51.50988,
                        "longitude": -0.15509
                    },
                    "available": True,
                    "offers": [
                        {
                            "id": "TSXOJ6LFQ2",
                            "checkInDate": "2023-11-22",
                            "checkOutDate": "2023-11-23",
                            "rateCode": "V  ",
                            "rateFamilyEstimated": {
                                "code": "PRO",
                                "type": "P"
                            },
                            "room": {
                                "type": "ELE",
                                "typeEstimated": {
                                    "category": "EXECUTIVE_ROOM",
                                    "beds": 1,
                                    "bedType": "DOUBLE"
                                },
                                "description": {
                                    "text": "Prepay Non-refundable Non-changeable, prepay in full\nExecutive King Room, Executive Lounge Access,\n1 King, 35sqm/377sqft-40sqm/430sqft, Wireless",
                                    "lang": "EN"
                                }
                            },
                            "guests": {
                                "adults": 1
                            },
                            "price": {
                                "currency": "GBP",
                                "base": "716.00",
                                "total": "716.00",
                                "variations": {
                                    "average": {
                                        "base": "716.00"
                                    },
                                    "changes": [
                                        {
                                            "startDate": "2023-11-22",
                                            "endDate": "2023-11-23",
                                            "total": "716.00"
                                        }
                                    ]
                                }
                            },
                            "policies": {
                                "paymentType": "deposit",
                                "cancellation": {
                                    "description": {
                                        "text": "NON-REFUNDABLE RATE"
                                    },
                                    "type": "FULL_STAY"
                                }
                            },
                            "self": "https://test.api.amadeus.com/v3/shopping/hotel-offers/TSXOJ6LFQ2"
                        }
                    ],
                    "self": "https://test.api.amadeus.com/v3/shopping/hotel-offers?hotelIds=MCLONGHM&adults=1&checkInDate=2023-11-22&paymentPolicy=NONE&roomQuantity=1"
                }
            ]
        }
        offers = Amadeus_Hotel_Offers.model_validate(json_data)
        if len(offers.data) > 0:  # Ensure at least one hotel is returned
            valid_offers = {}  # A dict to track valid offers
            for hotel in offers.data:
                min_offer = 1000000  # Set a min to be impossibly expensive
                offer_list = hotel.offers  # List of offers from a single hotel
                hotel_name = hotel.hotel.name
                hotel_id = hotel.hotel.hotelId  # Amadeus ID of the hotel
                print(hotel_name, hotel_id)
                for offer in offer_list:  # Retrieve the offer price
                    total = float(offer.price.total)  # Convert the str into a float
                    if total < min_offer:
                        min_offer = total  # Track the cheapest offer that fits the user's criteria per hotel
                # TODO get ranking info and add to temp_offer then return the hotel with the highest ranking in valid offers
                temp_offer = {
                    'name': hotel_name,
                    'price': min_offer,
                }
                valid_offers[hotel_id] = temp_offer
            print(valid_offers)
            return valid_offers
        else:
            raise HTTPException(status_code=404, detail="No offers found for this price range")
    except ValidationError as exception:
        raise HTTPException(status_code=502, detail=f"Amadeus request validation failed: {str(exception)}")
    except RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Amadeus request failed: {str(exception)}")


def _get_price_range(budget: float, current_cost: float, stops_left: int) -> str:
    remaining_avg = (budget - current_cost) / stops_left
    if remaining_avg > 100:
        return f"{remaining_avg - 100:.2f}-{remaining_avg + 100:.2f}"
    else:
        return f"0-{remaining_avg + 100:.2f}"


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


async def _get_hotel_ratings(hotel_ids: list[str]) -> tuple:
    """Return a list of tuples of hotelIds and ratings sorted from highest to lowest rating"""
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
        json_data = {
            "data": [
                {
                    "type": "hotelSentiment",
                    "numberOfReviews": 218,
                    "numberOfRatings": 278,
                    "hotelId": "ADNYCCTB",
                    "overallRating": 93,
                    "sentiments": {
                        "sleepQuality": 87,
                        "service": 98,
                        "facilities": 90,
                        "roomComforts": 92,
                        "valueForMoney": 87,
                        "catering": 89,
                        "location": 98,
                        "pointsOfInterest": 91,
                        "staff": 100
                    }
                },
                {
                    "type": "hotelSentiment",
                    "numberOfReviews": 2667,
                    "numberOfRatings": 2666,
                    "hotelId": "TELONMFS",
                    "overallRating": 81,
                    "sentiments": {
                        "sleepQuality": 78,
                        "service": 80,
                        "facilities": 75,
                        "roomComforts": 87,
                        "valueForMoney": 75,
                        "catering": 81,
                        "location": 89,
                        "internet": 72,
                        "pointsOfInterest": 81,
                        "staff": 89
                    }
                }
            ],
            "meta": {
                "count": 1,
                "links": {
                    "self": "https://test.api.amadeus.com/v2/e-reputation/hotel-sentiments?hotelIds=ADNYCCTB,TELONMFS,XXXYYY01"
                }
            },
            "warnings": [
                {
                    "code": 913,
                    "title": "PROPERTIES NOT FOUND",
                    "detail": "Some of the requested properties were not found in our database.",
                    "source": {
                        "parameter": "hotelIds",
                        "pointer": "XXXYYY01"
                    }
                }
            ]
        }
        sentiments = Amadeus_Hotel_Ratings.model_validate(json_data).data  # all the returned hotel sentiments
        ratings = []  # List to store the returned hotel ratings
        for hotel in sentiments:
            hotel_id = hotel.hotelId
            rating = hotel.overallRating
            ratings.append((hotel_id, rating))
        ratings.sort(key=lambda x: x[1], reverse=True)
        print(ratings)
        return ratings[0]
    except ValidationError as exception:
        raise HTTPException(status_code=500, detail=f'Improper Amadeus response: {str(exception)}')
