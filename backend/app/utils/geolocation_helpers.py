import geopy
from typing import List, Optional


def get_location(geocoder: geopy.geocoders,
                 coords: Optional[List[float]] = None,
                 address: Optional[str] = None) -> geopy.location.Location:
    location = None
    if coords:
        coordinates = f"{coords[0]}, {coords[1]}"
        location = geocoder.reverse(coordinates)
    elif address:
        location = geocoder.geocode(address)
    return location