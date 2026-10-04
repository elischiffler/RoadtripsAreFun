from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import ValidationError

from app.agent.progress import stage
from app.models.itinerary_models import Itinerary_Day, Itinerary_Payload
from app.models.scheduling_policy import advance, local_time
from app.routing.base import PlanningError
from app.routing.sources.evenings import current_suggestions
from app.routing.travel_timing import apply_timing
from app.utils.auth import require_authenticated_user

# Initialize FastAPI
router = APIRouter(dependencies=[Depends(require_authenticated_user)])


@router.post("/generate-itinerary")
async def generate_itinerary(request: Request) -> list[Itinerary_Day]:
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
        data = Itinerary_Payload.model_validate(json_data)  # Validate the frontend payload
        return await build_itinerary(data)
    except ValidationError as error:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {error}")
    except KeyError as error:
        raise HTTPException(status_code=501, detail=f"Missing expected data: {error}")
    except ValueError as error:
        raise HTTPException(status_code=502, detail=f"Error processing data: {error}")
    except PlanningError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail)


async def build_itinerary(data: Itinerary_Payload) -> list[Itinerary_Day]:
    with stage("itinerary.build"):
        return await _build_itinerary(data)


async def _build_itinerary(data: Itinerary_Payload) -> list[Itinerary_Day]:
    """Build a day-by-day itinerary from a validated :class:`Itinerary_Payload`.

    The core itinerary logic, factored out of :func:`generate_itinerary` so both
    the HTTP router and the chat-agent tool (``generate_itinerary``) share one
    implementation and the same stop-dict expectations. Callers are responsible
    for validating the payload and mapping any raised exceptions.

    Args:
        data: A validated payload with a route (its ``stops``) and a start time.

    Returns:
        List[Itinerary_Day]: the itinerary organized by date.

    Raises:
        HTTPException: if the route is incomplete or the data can't be processed.
    """
    # An omitted departure must reuse the planned travel day, including on
    # direct HTTP calls. Recover policy routes saved before departure_time was
    # added from the actual first arrival; legacy routes retain their old default.
    current_time = data.start_time or data.route.departure_time
    if current_time is None and data.route.scheduling_policy and data.route.stops:
        first = data.route.stops[0]
        if first.get("arrival_time"):
            current_time = advance(
                datetime.fromisoformat(first["arrival_time"]), -first["duration"]
            )
    current_time = current_time or datetime(2024, 9, 21, 9)
    if data.route.scheduling_policy is not None:
        if data.route.start_timezone:
            current_time = local_time(current_time, ZoneInfo(data.route.start_timezone))
        apply_timing(
            data.route.stops or [],
            current_time,
            data.route.scheduling_policy,
            data.route.start_timezone,
        )

    # initialize a list of stops with a generic message and specified start time
    stop_list = [
        {
            "date": current_time.strftime("%A, %B %d %Y"),
            "time": current_time.strftime("%I:%M %p"),
            "name": "Depart from your starting location",
        }
    ]
    # loop through the stops and get the time for each
    for stop in data.route.stops:
        # Add the time to get to the stop to the current time
        current_time = (
            datetime.fromisoformat(stop["arrival_time"])
            if data.route.scheduling_policy is not None
            else advance(current_time, stop["duration"])
        )
        destination = {
            "date": current_time.strftime("%A, %B %d %Y"),  # Weekday, Month Day Year
            "time": current_time.strftime("%I:%M %p"),  # Hour:Minutes
            "name": stop["name"],
            "url": stop.get("url"),
            "price": stop.get("price"),
            "traveler_count": stop.get("traveler_count"),
            "hotel_rooms": stop.get("hotel_rooms"),
            "room_offers": stop.get("room_offers"),
            "price_scope": stop.get("price_scope"),
            "address": stop.get("address"),
            "kind": "arrival",
            "timezone": stop.get("timezone"),
            "notice": " · ".join(
                value for value in (stop.get("late_check_in_notice"), stop.get("warning")) if value
            )
            or None,
        }
        # Add the stop to stop_list
        stop_list.append(destination)
        if stop["type"] == "hotel":  # If the stop is a hotel
            for suggestion in current_suggestions(stop) if data.route.scheduling_policy else []:
                visit = (
                    datetime.fromisoformat(suggestion["visit_time"])
                    if suggestion.get("visit_time")
                    else current_time
                )
                stop_list.append(
                    {
                        "date": visit.strftime("%A, %B %d %Y"),
                        "time": visit.strftime("%I:%M %p")
                        if suggestion.get("visit_time")
                        else "Unscheduled",
                        "name": suggestion["name"],
                        "url": suggestion.get("url"),
                        "address": suggestion.get("address"),
                        "kind": "evening",
                        "optional": True,
                        "status": suggestion["status"],
                        "notice": suggestion["notice"],
                        "timezone": stop.get("timezone"),
                        "return_by": datetime.fromisoformat(suggestion["return_by"]).strftime(
                            "%I:%M %p"
                        ),
                        "return_time": datetime.fromisoformat(suggestion["return_time"]).strftime(
                            "%I:%M %p"
                        )
                        if suggestion.get("return_time")
                        else None,
                    }
                )
            if data.route.scheduling_policy is not None:
                current_time = datetime.fromisoformat(stop["departure_time"])
            else:
                # Explicit backward compatibility for routes saved before the policy.
                current_time = (current_time + timedelta(days=1)).replace(
                    hour=9, minute=0, second=0, microsecond=0
                )
            stop_list.append(
                {
                    "date": current_time.strftime("%A, %B %d %Y"),  # Weekday, Month Day Year
                    "time": current_time.strftime("%I:%M %p"),  # Hour:Minutes
                    "name": "Depart from your hotel",
                }
            )
        elif stop["type"] == "stop":
            current_time = advance(current_time, 7200)
            stop_list.append(
                {
                    "date": current_time.strftime("%A, %B %d %Y"),  # Weekday, Month Day Year
                    "time": current_time.strftime("%I:%M %p"),  # Hour:Minutes
                    "name": "Depart from the stop",
                }
            )
    if len(stop_list) >= 2:
        # Organize the stops by date
        return await _day_itinerary(stop_list)
    raise HTTPException(status_code=400, detail="Incomplete route provided")


async def _day_itinerary(itinerary: list[dict[str, Any]]) -> list[Itinerary_Day]:
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
        curr_day = {"date": itinerary[0]["date"], "stops": []}
        # iterate through all stops
        for stop in itinerary:
            point = {
                "name": stop["name"],
                "time": stop["time"],
                "address": stop.get("address"),
                "url": stop.get("url"),
                "price": stop.get("price"),
                "kind": stop.get("kind"),
                "timezone": stop.get("timezone"),
                "notice": stop.get("notice"),
                "optional": stop.get("optional", False),
                "status": stop.get("status"),
                "return_by": stop.get("return_by"),
                "return_time": stop.get("return_time"),
                "traveler_count": stop.get("traveler_count"),
                "hotel_rooms": stop.get("hotel_rooms"),
                "room_offers": stop.get("room_offers"),
                "price_scope": stop.get("price_scope"),
            }
            # Check if the date matches and if so add stop to the same day
            if stop["date"] == curr_day["date"]:
                curr_day["stops"].append(point)
            # If date doesn't match it is a new day
            else:
                day_itinerary.append(
                    Itinerary_Day.model_validate(curr_day)
                )  # Add the validated itinerary day to the itinerary list
                # change the current day to be a new day with the information of the current stop
                curr_day = {"date": stop["date"], "stops": [point]}

        day_itinerary.append(Itinerary_Day.model_validate(curr_day))
        return day_itinerary
    except ValidationError as error:
        raise HTTPException(status_code=500, detail=f"Error with date validation: {error}")
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=401, detail=f"Error processing input itinerary: {error}")
