from fastapi import APIRouter, HTTPException, Request
from app.models.itinerary_models import itinerary_payload, itinerary_day
from datetime import timedelta, datetime
from typing import List, Dict, Any
from pydantic import ValidationError

# Initialize FastAPI
router = APIRouter()


@router.post("/generate-itinerary")
async def generate_itinerary(request: Request) -> List[itinerary_day]:
    """
    Receives a json payload from the frontend and uses the data to generate an itinerary organized by date

    Args:
        request(_fastapi.Request): a JSON payload with the format of an itinerary_payload

    Returns:
        List[itinerary_day]: a list of itinerary days each containing information about a stop

    Raises:
        HTTPException: if the payload is malformed or error

    """
    try:
        # Convert json payload back to route
        json_data = await request.json()
        data = itinerary_payload.model_validate(json_data)

        # initialize current_time to be the specified start_time
        current_time = data.start_time

        # initialize a list of stops with a generic message and specified start time
        stop_list = [
            {'date': current_time.strftime('%A, %B %d %Y'),
             'time': current_time.strftime('%H:%M'),
             'name': 'Depart from your starting location'}]
        # loop through the stops and get the time for each
        print(data.route.stops)
        for stop in data.route.stops:
            # Add the time of to get to the stop to the current time
            current_time += timedelta(seconds=stop['duration'])
            # Add the stop to stop_list
            stop_list.append(
                {'date': current_time.strftime('%A, %B %d %Y'),  # Weekday, Month Day Year
                 'time': current_time.strftime('%H:%M'),  # Hour:Minutes
                 'name': stop['name']})
            if stop['length'] == 12: # If the stop is a hotel
                current_time = datetime(current_time.year, # set current time to be next day at 9AM
                                        current_time.month,
                                        current_time.day+1,
                                        9,
                                        0,
                                        0)
            else:
                current_time += timedelta(hours=stop['length']) # Increment current time by the length of stop
        if len(stop_list) >=2:
            # Organize the stops by date
            itinerary = await _day_itinerary(stop_list)
            return itinerary
        else:
            raise HTTPException(status_code=400, detail="Incomplete route provided")
    except ValidationError as error:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {error}")
    except KeyError as error:
        raise HTTPException(status_code=500, detail=f"Missing expected data: {error}")
    except ValueError as error:
        raise HTTPException(status_code=500, detail=f"Error processing data: {error}")


async def _day_itinerary(itinerary: List[Dict[str, Any]]) -> List[itinerary_day]:
    """
    Processes a list of stops sorting them into itinerary_day objects using their dates

    Args:
        itinerary(List[Dict[str, Any]]): An in order list of stops that contain name and date-time:

    Returns:
        List[itinerary_day]: a list of itinerary days each containing stops and time the user will arrive

    Raises:
        HTTPException: if the itinerary is not properly formatted or errors parsing data

    """
    try:
        day_itinerary = []
        curr_day = {'date': itinerary[0]['date'], 'stops': []}
        # iterate through all stops
        for stop in itinerary:
            # Check if the date matches and if so add stop to the same day
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
