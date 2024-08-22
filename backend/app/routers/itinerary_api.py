from fastapi import APIRouter, HTTPException, Request
from app.models.itinerary_models import itinerary_payload, itinerary_day
from datetime import timedelta
from typing import List, Dict, Any
from pydantic import ValidationError

# Initialize FastAPI
router = APIRouter()


@router.post("/generate-itinerary")
async def generate_itinerary(request: Request) -> List[itinerary_day]:
    try:
        # Convert json payload back to route
        json_data = await request.json()
        data = itinerary_payload.model_validate(json_data)

        # initialize current_time to be the specified start_time
        current_time = data.start_time

        # initialize a list of stops with a generic message and specified start time
        stop_list = [
            {'date': current_time.strftime('%A, %B %d %Y'), 'time': current_time.strftime('%H:%M'),
             'name': 'Depart from your starting location'}]
        # loop through the stops and get the time for each
        for stop in data.route.stops:
            # Add the time of the stop to the current time
            current_time = current_time + timedelta(seconds=stop['duration'])
            # Add the stop to stop_list
            stop_list.append(
                {'date': current_time.strftime('%A, %B %d %Y'),  # Weekday, Month Day Year
                 'time': current_time.strftime('%H:%M'),  # Hour:Minutes
                 'name': stop['name']})
        # Organize the stops by date
        itinerary = await _day_itinerary(stop_list)
        return itinerary
    except ValidationError as error:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {error}")
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Error generating itinerary: {error}")


async def _day_itinerary(itinerary: List[Dict[str, Any]]) -> List[itinerary_day]:
    try:
        day_itinerary = []
        curr_day = {'date': itinerary[0]['date'], 'stops': []}
        # iterate through all stops
        for stop in itinerary:
            # Check if the date matches and if so add to the same day
            if stop['date'] == curr_day['date']:
                curr_day['stops'].append({'name': stop['name'], 'time': stop['time']})
            # If date doesn't match it is a new day
            else:
                day_itinerary.append(curr_day)  # Add the fully complete date itinerary to the final list
                # change the current day to be a new day with the information of the current stop
                curr_day = {'date': stop['date'],
                            'stops': [{'name': stop['name'],
                                       'time': stop['time']}]}
        day_itinerary.append(itinerary_day.model_validate(curr_day))
        return day_itinerary
    except ValidationError as error:
        raise HTTPException(status_code=500, detail=f"Error with date validation: {error}")
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=401, detail=f"Error processing input itinerary: {error}")
