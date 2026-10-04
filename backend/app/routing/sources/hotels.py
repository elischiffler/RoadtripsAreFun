"""Hotel discovery.

Google Hotels scraping (``find_google_hotels``) uses a Google Places
nearby-city lookup to build the search query.

``find_hotel`` is the entry point planners call through ``RoutingServices``.
"""

from __future__ import annotations

import logging
from datetime import datetime

import requests
from fastapi import HTTPException
from pydantic import ValidationError
from requests.exceptions import RequestException

from app.models.routing_models.google_places_models import GooglePlaces
from app.routers.routing_fns.webscraping_fns import find_google_hotels
from app.routing import config
from app.utils.geolocation_helpers import get_location

logger = logging.getLogger(__name__)


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
        - HTTPException: For errors related to hotel scraping or response processing.

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

    valid_hotel = find_google_hotels(
        query=query,
        price_range=price_range[0],
        coords=(lat, lon),
        radius=radius,
        geolocator=config.geolocator,
    )
    if not valid_hotel:
        raise HTTPException(status_code=404, detail="No hotels found")
    valid_hotel["type"] = "hotel"
    return valid_hotel


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
        response = requests.get(url, params=params, timeout=config.HTTP_TIMEOUT)
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
        logger.error("get_nearby_city: improper Google Places response: %s", exception)
        raise HTTPException(status_code=502, detail="Improper Google Places response")
    except RequestException as exception:
        # The request URL carries the Google Places API key; log it, don't leak it.
        logger.error("get_nearby_city: Google Places request failed: %s", exception)
        raise HTTPException(status_code=502, detail="Google Places request failed")
