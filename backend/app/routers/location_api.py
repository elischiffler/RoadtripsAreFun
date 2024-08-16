from fastapi import APIRouter, HTTPException
from geopy.geocoders import Nominatim

# Initialize FastAPI
router = APIRouter()

@router.get("/validate-location")
def validate_location(address: str | None = None, coordinates: str | None = None) -> str:
    try:
        # check if a valid query is being sent
        if address is None and coordinates is None:
            raise ValueError("Must provide either address or coordinates")
        if address and coordinates:
            raise ValueError("Address and coordinates cannot be both specified")

        # initialize an open street map geolocator
        geolocator = Nominatim(user_agent="rp-routing")

        # geolocate by either a string describing a location or exact coordinates
        if address:
            location = geolocator.geocode(address)
        else:
            location = geolocator.reverse(coordinates)

        # return the str address if location is valid
        if location is None:
            raise HTTPException(status_code=404, detail="Location not found")
        return location.address
    except ValueError as exception:
        raise HTTPException(status_code=400, detail=f"Invalid input format: {str(exception)}")

