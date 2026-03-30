import geopy
from typing import List, Optional
from geopy.exc import GeopyError
from fastapi import HTTPException


def get_location(geocoder: geopy.geocoders,
                 coords: Optional[List[float]] = None,
                 address: Optional[str] = None) -> geopy.location.Location:
    try:
        location = None
        if coords:
            coordinates = f"{coords[0]}, {coords[1]}"
            location = geocoder.reverse(coordinates, timeout=10)
        elif address:
            location = geocoder.geocode(address, timeout=10)
        return location
    except GeopyError as e:
        raise HTTPException(status_code=502, detail=f"Geocoding service error: {str(e)}")