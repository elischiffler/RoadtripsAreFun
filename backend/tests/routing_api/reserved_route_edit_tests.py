"""Combined route-edit and reserved-meal contracts through actual itinerary timing."""

from copy import deepcopy
from datetime import datetime

import pytest

from app.routing.meal_reservations import MealScheduleConflict
from tests.routing_api.route_edit_tests import request, run, saved_route


@pytest.mark.asyncio
async def test_edit_keeps_real_meal_reservations_and_recomputes_supplied_intervals():
    saved = saved_route()
    saved["reserve_meal_slots"] = True
    saved["stops"][0]["meal_breaks"] = [{"notice": "FORGED", "status": "reserved"}]
    # An itinerary-only display option cannot turn off a route's reserved clock.
    payload = request(route=saved, include_meal_slots=False)
    original = deepcopy(payload.model_dump())
    result, _ = await run(payload, duration=1800)
    assert payload.model_dump() == original
    assert result.route.reserve_meal_slots is True
    meals = [stop for day in result.itinerary for stop in day.stops if stop.kind == "meal"]
    assert len(meals) == 1 and meals[0].status == "reserved"
    assert meals[0].duration_seconds == 2700
    assert "FORGED" not in meals[0].notice
    beginning, end = map(datetime.fromisoformat, [meals[0].arrival_time, meals[0].departure_time])
    assert (end - beginning).total_seconds() == 2700
    for stop in result.route.stops:
        if stop["type"] == "stop":
            arrival, departure = map(
                datetime.fromisoformat, [stop["arrival_time"], stop["departure_time"]]
            )
            assert end <= arrival or beginning >= departure
    assert any(
        meal["arrival_time"] == meals[0].arrival_time
        and meal["departure_time"] == meals[0].departure_time
        for stop in result.route.stops
        for meal in stop["meal_breaks"]
    )


@pytest.mark.asyncio
async def test_edit_rejects_cutoff_that_only_meal_free_timing_can_meet():
    saved = saved_route()
    saved["reserve_meal_slots"] = True
    # Three 2h40m legs + two 2h visits end at the default 21:00 cutoff
    # without meals. The full reserved clock must reject this preview.
    with pytest.raises(MealScheduleConflict) as caught:
        await run(request(route=saved), duration=9600)
    assert caught.value.status_code == 422
