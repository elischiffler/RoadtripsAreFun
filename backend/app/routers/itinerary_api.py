from fastapi import APIRouter, HTTPException, Request
from app.models.itinerary_models import itinerary_payload
from datetime import timedelta

# Initialize FastAPI
router = APIRouter()


@router.post("/generate-itinerary")
async def generate_itinerary(request: Request):
    try:
        # Convert json payload back to route
        json_data = await request.json()
        data = itinerary_payload.model_validate(json_data)
        current_time = data.start_time
        itinerary = [
            {'date-time': {'date': current_time.strftime('%A, %B %d %Y'), 'time': current_time.strftime('%H:%M')},
             'name': 'Depart from your starting location'}]
        for stop in data.stops:
            # Add the time of the stop to the current time
            current_time = current_time + timedelta(seconds=stop.duration)
            itinerary.append(
                {'date-time': {'date': current_time.strftime('%A, %B %d %Y'), 'time': current_time.strftime('%H:%M')},
                 'name': stop.name})
        return itinerary
    except Exception as e:
        pass
