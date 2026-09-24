import geopy
from fastapi import HTTPException
from geopy.exc import GeopyError


def get_location(
    geocoder: geopy.geocoders, coords: list[float] | None = None, address: str | None = None
) -> geopy.location.Location:
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
