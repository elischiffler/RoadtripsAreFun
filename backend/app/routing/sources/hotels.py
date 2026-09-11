"""Hotel discovery.

Primary source is Google Hotels scraping (``find_google_hotels``), with a
Google Places nearby-city lookup to build the search query and an optional
Amadeus fallback (disabled by default via ``AMADEUS_ENABLED``).

``find_hotel`` is the entry point planners call through ``RoutingServices``.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

import requests
from fastapi import HTTPException
from pydantic import ValidationError
from requests.exceptions import RequestException

from app.models.routing_models.amadeus_models import (
    Amadeus_Access,
    Amadeus_Hotel_Offers,
    Amadeus_Hotel_Ratings,
    Amadeus_Hotel_Search,
)
from app.models.routing_models.google_places_models import GooglePlaces
from app.routers.routing_fns.webscraping_fns import find_google_hotels
from app.routing import config
from app.utils.geolocation_helpers import get_location


async def find_hotel(
    lat: float,
    lon: float,
    price_range: tuple[tuple[float, float], str],
    check_in: datetime,
    radius: int = 30,
) -> dict[str, list[float] | str]:
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
    # Get a geolocated location
    location = get_location(geocoder=config.geolocator, coords=[lat, lon])

    # Ensure we could geolocate the provided coordinates
    if location is None:
        raise HTTPException(status_code=404, detail="No location found")

    # Split the location string into its components
    location_array = location.address.split(", ")
    try:
        # Get a nearby city partial address using Google Places API
        query = await get_nearby_city(lat, lon)
        # Ensure we have all the necessary information to get a valid hotel query
        if query is None or len(location_array) < 2:
            raise HTTPException(status_code=404, detail="No cities found")
        # Add state and country information to the returned city address
        query += f", {location_array[-2]}, {location_array[-1]}"

    # Catch all possible exceptions when using the Google API
    except (ValidationError, HTTPException, AttributeError):
        # If the API fails use the geolocated address for a rough estimate of the address
        query = location.address
        if len(location_array) >= 4:  # Check if the address includes the highway you are on
            query = ", ".join(
                location_array[1:]
            )  # Remove the most specific detail to not get an invalid google search

    # Now that you have a query try to webscrape
    try:
        valid_hotel = find_google_hotels(
            query=query,
            price_range=price_range[0],
            coords=(lat, lon),
            radius=radius,
            geolocator=config.geolocator,
        )
        # Ensure a valid hotel is found and its within the search radius
        if valid_hotel:
            valid_hotel["type"] = "hotel"
            return valid_hotel
        else:
            raise HTTPException(status_code=404, detail="No hotels found")
    except HTTPException as exception:
        # Only fall back to Amadeus when it is explicitly enabled and the scraper
        # returned "not found" (404). Any other error propagates unchanged.
        if config.AMADEUS_ENABLED and exception.status_code == 404:
            return await _find_hotel_amadeus(lat, lon, price_range, check_in, radius)
        else:
            raise exception


async def _find_hotel_amadeus(
    lat: float,
    lon: float,
    price_range: tuple[tuple[float, float], str],
    check_in: datetime,
    radius: int,
) -> dict[str, list[float] | str]:
    """Amadeus hotel-search fallback (only reached when AMADEUS_ENABLED=true)."""
    try:
        # If scraping fails use the Amadeus API
        access_token = await get_amadeus_token(
            os.getenv("AMADEUS_KEY"), os.getenv("AMADEUS_SECRET")
        )
        hotels_list_url = (
            "https://test.api.amadeus.com/v1/reference-data/locations/hotels/by-geocode"
        )
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "latitude": lat,
            "longitude": lon,
            "radius": radius,
            "radiusUnit": "MILE",
            "ratings": ["2", "3", "4", "5"],  # Indicates hotel star level
        }
        response = requests.get(hotels_list_url, params=params, headers=headers)
        json_data = response.json()
        # If no hotel is found search for one with a larger radius
        if response.status_code == 400 and json_data["errors"][0]["code"] == 895:
            return await find_hotel(lat, lon, price_range, check_in, radius + 10)
        hotels = Amadeus_Hotel_Search.model_validate(json_data)  # Validate the response
        hotel_list = hotels.data
        if len(hotel_list) > 0:
            hotel_info = {}  # Store hotel info keyed by hotelId
            id_list = []  # List of hotel id's to send for to get offers
            for hotel in hotel_list:  # Loop through nearby hotels for coordinates, id, and name
                coordinates = [
                    hotel.geoCode["latitude"],
                    hotel.geoCode["longitude"],
                ]  # Get coordinates for routing
                hotel_id = hotel.hotelId  # Amadeus's unique hotel ID
                id_list.append(hotel_id)  # Add the id to the id_list
                name = hotel.name.lower()
                hotel_info[hotel_id] = {
                    "coordinates": coordinates,
                    "name": name.capitalize(),
                    "type": "hotel",
                }  # Add relevant info from the search to hotel_info
            # Get a dict of offers using hotelIds as keys
            offers = await get_amadeus_offers(
                access_token=access_token,
                hotel_ids=id_list,
                check_in=check_in,
                # Check out the next day at 9 AM. Use timedelta so month/year
                # boundaries (e.g. Jan 31 -> Feb 1) don't raise a ValueError.
                check_out=(check_in + timedelta(days=1)).replace(
                    hour=9, minute=0, second=0, microsecond=0
                ),
                price_range=price_range[1],
            )

            # Look for ratings on the hotels with valid offers
            highest_rated = await get_amadeus_ratings(offers.keys())

            # Use the hotelId returned with highest_rated to get its offer info
            best_offer = offers[highest_rated[0]]
            location = hotel_info[best_offer["hotel_id"]]
            location["price"] = best_offer["price"]  # Add pricing to the saved hotel info
            location["name"] = best_offer["name"]  # Add the name to location info
            location["stars"] = round(
                highest_rated[1] / 20, 2
            )  # Get a star value by dividing the 0-100 rating
            # Returns a dictionary with coordinates, name, type, price, and rating of the hotel
            return location
        else:
            raise HTTPException(status_code=404, detail="No hotels found")
    except RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Amadeus request failed: {str(exception)}")
    except ValidationError as exception:
        raise HTTPException(status_code=502, detail=f"Improper Amadeus response: {str(exception)}")


async def get_amadeus_offers(
    access_token: str,
    hotel_ids: list[str],
    check_in: datetime,
    check_out: datetime,
    price_range: str,
    adults: int = 2,
) -> dict[str, Any]:
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
    check_in_date = check_in.strftime("%Y-%m-%d")
    check_out_date = check_out.strftime("%Y-%m-%d")
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "hotelIds": hotel_ids,
        "adults": adults,  # TODO allow for guests to specify the number of ppl
        "checkInDate": check_in_date,  # TODO allow user to specify a trip start date
        "checkOutDate": check_out_date,
        "priceRange": price_range,
        "currency": "USD",
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
                        min_offer = total  # Track the cheapest offer that fits per hotel
                temp_offer = {
                    "hotel_id": hotel_id,
                    "name": hotel_name,
                    "price": min_offer,
                }
                valid_offers[hotel_id] = temp_offer
            return valid_offers
        else:
            raise HTTPException(status_code=404, detail="No offers found for this price range")
    except ValidationError as exception:
        raise HTTPException(
            status_code=502, detail=f"Error validating Amadeus offer response: {str(exception)}"
        )
    except RequestException as exception:
        raise HTTPException(status_code=500, detail=f"Amadeus request failed: {str(exception)}")


async def get_amadeus_ratings(hotel_ids: list[str]) -> tuple:
    """
    Return a list of tuples of hotelIds and ratings sorted from highest to lowest rating

    Args:
        - hotel_ids: A list of amadeus hotel IDs

    Returns:
        - tuple: A tuple containing the hotelId and rating for the highest rated hotel from the list

    """
    try:
        access_token = await get_amadeus_token(
            os.getenv("AMADEUS_KEY"), os.getenv("AMADEUS_SECRET")
        )
        hotels_list_url = "https://test.api.amadeus.com/v2/e-reputation/hotel-sentiments"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"hotelIds": hotel_ids}
        response = requests.get(hotels_list_url, params=params, headers=headers)
        json_data = response.json()
        sentiments = Amadeus_Hotel_Ratings.model_validate(
            json_data
        ).data  # all the returned hotel sentiments
        ratings = []  # List to store the returned hotel ratings
        if len(sentiments) > 0:
            for hotel in sentiments:
                hotel_id = hotel.hotelId
                rating = hotel.overallRating
                ratings.append((hotel_id, rating))
            ratings.sort(key=lambda x: x[1], reverse=True)
            return ratings[0]
        else:
            raise HTTPException(status_code=404, detail="No hotels found for the provided ids")
    except ValidationError as exception:
        raise HTTPException(status_code=502, detail=f"Improper Amadeus response: {str(exception)}")
    except (KeyError, ValueError) as exception:
        raise HTTPException(status_code=500, detail=f"Unable to parse response: {str(exception)}")


async def get_amadeus_token(API_KEY: str, API_SECRET: str) -> str:
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
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    data = {"grant_type": "client_credentials", "client_id": API_KEY, "client_secret": API_SECRET}
    try:
        response = requests.post(url, headers=headers, data=data)
        json_data = response.json()
        response_data = Amadeus_Access.model_validate(json_data)
        if response_data.access_token is not None:
            return response_data.access_token
        else:
            raise HTTPException(status_code=404, detail="No Amadeus access token returned")
    except ValidationError as exception:
        raise HTTPException(status_code=502, detail=f"Improper Amadeus response: {str(exception)}")


async def get_nearby_city(lat: float, lon: float, radius: float | None = 50000) -> str:
    """
    Uses Google Places Nearby search to find a nearby city name from a given location

    Args:
        - lat(float): Latitude of the search area
        - lon(float): Longitude of the search area
        - radius(int): Radius in miles to search for hotels

    Returns:
        - str: A nearby city name

    Raises:
        - HTTPException: For errors related to an unexpected response from Google Places API.

    """
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lon}",
        "radius": radius,  # In meters
        "keyword": "city",
        "key": config.GOOGLE_PLACES_API,
    }
    try:
        response = requests.get(url, params=params)
        json_data = response.json()
        places = GooglePlaces.model_validate(json_data).results
        if len(places) > 0:
            # Iterate through all the returned places
            for place in places:
                # Check if a nearby location name is found
                if place.vicinity:
                    return place.vicinity
        else:
            raise HTTPException(status_code=404, detail="No places found for the provided location")

    except ValidationError as exception:
        raise HTTPException(
            status_code=500, detail=f"Improper Google Places response: {str(exception)}"
        )
    except RequestException as exception:
        raise HTTPException(
            status_code=502, detail=f"Google Places request failed: {str(exception)}"
        )
