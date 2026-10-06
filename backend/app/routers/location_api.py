import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, Request
from geopy.geocoders import OpenCage
from pydantic import ValidationError

from app.models.location_models import location_model, location_payload
from app.utils.auth import require_authenticated_user
from app.utils.geolocation_helpers import get_location
from app.utils.location_resolution import needs_confirmation, resolve_location

load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=True)

# Initialize FastAPI
router = APIRouter(dependencies=[Depends(require_authenticated_user)])

open_cage_key = os.getenv("OPENCAGE_KEY")
geolocator = OpenCage(api_key=open_cage_key, user_agent="rp-routing", timeout=10)


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

        # geolocate by either a string describing an address or exact coordinates
        if data.is_coordinates:
            location = get_location(geocoder=geolocator, coords=data.location.coordinates)
        else:
            resolution = resolve_location(geolocator, data.location.address, lookup=get_location)
            if not resolution.candidates:
                raise HTTPException(status_code=404, detail="Location not found")
            if needs_confirmation(resolution):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "location_confirmation_required",
                        "query": resolution.query,
                        "candidates": [
                            candidate.model_dump(exclude={"id"})
                            for candidate in resolution.candidates
                        ],
                    },
                )
            location = resolution.candidates[0]

        # return the str address if location is valid
        if location is None:
            raise HTTPException(status_code=404, detail="Location not found")
        return location_model(
            address=location.address, latitude=location.latitude, longitude=location.longitude
        )
    # Catch errors from validating the model
    except ValidationError as exception:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {str(exception)}")
    # Catch any errors accessing data that is unavailable or wrong type
    except (ValueError, KeyError) as exception:
        raise HTTPException(status_code=400, detail=f"Invalid input format: {str(exception)}")
