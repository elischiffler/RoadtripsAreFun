"""Hotel meal reservations obey explicit sleep without changing legacy clocks."""

from copy import deepcopy
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.models.itinerary_models import Itinerary_Payload
from app.models.scheduling_policy import SchedulingPolicy
from app.routers import itinerary_api
from app.routing.meal_reservations import MealScheduleConflict
from app.routing.travel_timing import apply_timing
from tests.one_day_rhythm_tests import policy, route
from tests.reserved_meal_tests import ZONE, endpoint, moment
from tests.routing_api.route_edit_tests import request, road, run, with_hotel


def hotel_stops():
    return [
        {"name": "Nightly quote", "type": "hotel", "duration": 3600, "timezone": ZONE},
        endpoint(3600),
    ]


def assert_awake_breakfast(hotel):
    breakfast = next(m for m in hotel["meal_breaks"] if m["meal_type"] == "breakfast")
    beginning = datetime.fromisoformat(breakfast["arrival_time"])
    finish = datetime.fromisoformat(breakfast["departure_time"])
    assert beginning.hour == 8 and beginning.minute == 0
    assert finish.hour == 8 and finish.minute == 30
    assert hotel["departure_time"][11:16] == "09:00"
    for meal in hotel["meal_breaks"]:
        start, end = map(datetime.fromisoformat, (meal["arrival_time"], meal["departure_time"]))
        assert datetime.fromisoformat(meal["window_start"]) <= start
        assert end <= datetime.fromisoformat(meal["window_end"])
        for block in hotel["daily_rhythm_blocks"]:
            if block["kind"] == "sleep":
                sleep_start, sleep_end = map(
                    datetime.fromisoformat, (block["arrival_time"], block["departure_time"])
                )
                assert end <= sleep_start or start >= sleep_end


def test_hotel_shifts_full_breakfast_into_awake_rest_without_changing_restart():
    stops = hotel_stops()
    apply_timing(stops, moment("17:00"), policy((9, 20), (22, 8)), ZONE, reserve_meal_slots=True)
    assert_awake_breakfast(stops[0])
    assert stops[-1]["arrival_time"] == "2027-06-02T10:00:00-07:00"


def test_hotel_rejects_breakfast_window_entirely_inside_sleep():
    with pytest.raises(MealScheduleConflict) as error:
        apply_timing(
            hotel_stops(),
            moment("17:00"),
            policy((10, 18), (20, 10)),
            ZONE,
            reserve_meal_slots=True,
        )
    assert error.value.status_code == 422


def test_breakfast_defers_to_next_drive_when_sleep_ends_at_restart():
    stops = hotel_stops()
    apply_timing(stops, moment("17:00"), policy((8, 20), (22, 8)), ZONE, reserve_meal_slots=True)
    assert not any(m["meal_type"] == "breakfast" for m in stops[0]["meal_breaks"])
    assert stops[0]["departure_time"] == "2027-06-02T08:00:00-07:00"
    breakfast = next(m for m in stops[1]["meal_breaks"] if m["meal_type"] == "breakfast")
    assert breakfast["arrival_time"] == "2027-06-02T08:30:00-07:00"
    assert breakfast["departure_time"] == "2027-06-02T09:00:00-07:00"
    assert stops[-1]["arrival_time"] == "2027-06-02T09:30:00-07:00"


def test_legacy_hotel_keeps_original_breakfast_time_without_rhythm():
    stops = hotel_stops()
    apply_timing(stops, moment("17:00"), SchedulingPolicy(), ZONE, reserve_meal_slots=True)
    breakfast = next(m for m in stops[0]["meal_breaks"] if m["meal_type"] == "breakfast")
    assert breakfast["arrival_time"] == "2027-06-02T07:00:00-07:00"
    assert "daily_rhythm_blocks" not in stops[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("possible", [True, False])
async def test_saved_itinerary_rebuild_rechecks_sleep_instead_of_trusting_breaks(
    monkeypatch, possible
):
    monkeypatch.setattr(itinerary_api, "refresh_for_timing", AsyncMock())
    selected = policy((9, 20), (22, 8)) if possible else policy((10, 18), (20, 10))
    planned = route(hotel_stops(), moment("17:00"), selected).model_copy(
        update={"trip_mode": "overnight"}
    )
    planned.stops[0]["meal_breaks"] = [{"meal_type": "breakfast", "arrival_time": "FORGED"}]
    if not possible:
        with pytest.raises(MealScheduleConflict):
            await itinerary_api.build_itinerary(Itinerary_Payload(route=planned))
        return
    days = await itinerary_api.build_itinerary(Itinerary_Payload(route=planned))
    assert_awake_breakfast(planned.stops[0])
    breakfast = next(s for d in days for s in d.stops if s.kind == "meal" and s.name == "Breakfast")
    assert breakfast.arrival_time == planned.stops[0]["meal_breaks"][-1]["arrival_time"]


@pytest.mark.asyncio
@pytest.mark.parametrize("possible", [True, False])
async def test_edited_route_rebuild_preserves_sleep_or_rejects_preview(possible):
    saved = with_hotel()
    saved["reserve_meal_slots"] = True
    saved["departure_time"] = "2030-06-01T15:00:00+00:00"
    selected = policy((9, 20), (22, 8)) if possible else policy((10, 18), (20, 10))
    saved["scheduling_policy"] = selected.model_dump()
    payload = request(route=saved, action="replace", stop_index=0, include_meal_slots=False)
    original = deepcopy(payload.model_dump())
    response = road(3, 0)
    response.legs[1].duration = response.legs[2].duration = 3600
    response.duration = 7200
    if not possible:
        with pytest.raises(MealScheduleConflict):
            await run(payload, response=response)
    else:
        result, _ = await run(payload, response=response)
        assert_awake_breakfast(result.route.stops[1])
        assert any(
            s.kind == "meal" and s.name == "Breakfast" for d in result.itinerary for s in d.stops
        )
    assert payload.model_dump() == original
