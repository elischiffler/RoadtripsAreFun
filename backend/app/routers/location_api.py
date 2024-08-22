from fastapi import APIRouter, HTTPException, Request
from geopy.geocoders import Nominatim
from app.models.location_models import location_payload, location_model
from pydantic import ValidationError

# Initialize FastAPI
router = APIRouter()

@router.post("/validate-location")
async def validate_location(request: Request) -> location_model:
    """
    Receives a json payload from the front end and validates the location specified within the payload

    Parameters:
        - request(_fastapi.Request): JSON payload received from front end in the format of location_model

    Returns:
        - str: Validated location address

    Raises:
        - HTTPException: For errors with the received payload or parsing data

    """
    try:
        # Convert json payload
        json_data = await request.json()
        data = location_payload.model_validate(json_data)

        # initialize an open street map geolocator
        geolocator = Nominatim(user_agent="rp-routing")

        # geolocate by either a string describing an address or exact coordinates
        if data.is_coordinates:
            coordinates = data.location.coordinates
            location = geolocator.reverse(f"{coordinates[0]}, {coordinates[1]}")
        else:
            location = geolocator.geocode(data.location.address)

        # return the str address if location is valid
        if location is None:
            raise HTTPException(status_code=404, detail="Location not found")
        return location_model(address=location.address,
                        latitude=location.latitude,
                        longitude=location.longitude)
    # Catch errors from validating the model
    except ValidationError as exception:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {str(exception)}")
    # Catch any errors accessing data that is unavailable or wrong type
    except (ValueError, KeyError) as exception:
        raise HTTPException(status_code=400, detail=f"Invalid input format: {str(exception)}")


