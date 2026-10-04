"""Optional provider discovery never alters route feasibility or daytime counts."""

import asyncio

import httpx
import pytest

from app.models.itinerary_models import Itinerary_Payload
from app.models.routing_models.routing_models import Route
from app.models.scheduling_policy import SchedulingPolicy
from app.routers.itinerary_api import build_itinerary
from app.routing.sources import evenings
from app.routing.travel_timing import apply_timing
from tests.routing.flexible_hotel_tests import START, ZONE, point, saved_route


def venue(**patch):
    return {
        "provider_id": "terra:123",
        "name": "Local cafe",
        "coordinates": [34.001, -118],
        "url": "https://example.test/cafe",
        "category": "food",
        "address": "1 Cafe Way",
        "opening_intervals": [
            {"opens": "2035-11-21T17:00:00-08:00", "closes": "2035-11-21T20:00:00-08:00"}
        ],
        **patch,
    }


class Provider:
    def __init__(self, records=None, *, duration=600, failure=False, delay=0):
        self.records = records if records is not None else [venue()]
        self.duration, self.failure, self.delay = duration, failure, delay
        self.calls = []

    async def nearby(self, coords, interests, arrival):
        self.calls.append((coords, interests, arrival))
        await asyncio.sleep(self.delay)
        if self.failure:
            raise RuntimeError("optional provider failed")
        return self.records

    async def travel(self, hotel, place):
        return [self.duration, self.duration]


def planned_hotel(hour=18):
    stop = point((hour - 9) * 3600, "hotel")
    stop["price"] = 150
    stop["warning"] = "Above nightly target"
    apply_timing([stop], START, SchedulingPolicy(late_driving=True), ZONE)
    return stop


@pytest.mark.asyncio
async def test_nearby_open_options_are_alternatives_after_rest_with_return_bound():
    provider = Provider(
        [
            venue(),
            venue(provider_id="terra:124", name="Gallery", category="culture"),
            venue(provider_id="terra:125"),
        ]
    )
    hotel = planned_hotel()
    await evenings.enrich_evenings([hotel], ["food", "culture"], provider=provider)
    suggestions = hotel["evening_suggestions"]
    assert len(suggestions) == 2
    assert provider.calls[0][0] == hotel["coordinates"]
    assert all(s["visit_time"] == "2035-11-21T18:40:00-08:00" for s in suggestions)
    assert all(s["return_time"] == "2035-11-21T19:50:00-08:00" for s in suggestions)
    assert hotel["price"] == 150 and hotel["warning"] == "Above nightly target"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "patch",
    [
        {"coordinates": [35, -118]},
        {"closed": True},
        {"opening_intervals": []},
        {
            "opening_intervals": [
                {"opens": "2035-11-21T09:00:00-08:00", "closes": "2035-11-21T17:00:00-08:00"}
            ]
        },
        {"category": "nightlife"},
        {"url": None},
    ],
)
async def test_distant_closed_wrong_interest_or_missing_link_is_skipped(patch):
    hotel = planned_hotel()
    await evenings.enrich_evenings([hotel], ["food"], provider=Provider([venue(**patch)]))
    assert hotel["evening_suggestions"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("category", ["food", None])
async def test_unknown_hours_or_category_only_tentative_and_survive_reload(category):
    hotel = planned_hotel()
    await evenings.enrich_evenings(
        [hotel], ["food"], provider=Provider([venue(category=category, opening_intervals=None)])
    )
    option = hotel["evening_suggestions"][0]
    assert option["visit_time"] is None and option["return_time"] is None
    assert option["status"] == "tentative" and "Check opening hours" in option["notice"]
    route = saved_route([hotel, point(3600)], SchedulingPolicy(late_driving=True))
    reloaded = Route.model_validate_json(route.model_dump_json())
    assert reloaded.stops[0]["evening_suggestions"] == hotel["evening_suggestions"]
    itinerary = await build_itinerary(Itinerary_Payload(route=reloaded, start_time=START))
    options = [s for day in itinerary for s in day.stops if s.optional]
    assert len(options) == 1 and options[0].time == "Unscheduled"
    assert sum(stop["type"] == "stop" for stop in reloaded.stops) == 0
    assert reloaded.cost == 100 and reloaded.stops[0]["price"] == 150


@pytest.mark.asyncio
@pytest.mark.parametrize("hour", [23, 24])
async def test_late_arrival_suppresses_discovery(hour):
    provider = Provider()
    hotel = planned_hotel(hour)
    await evenings.enrich_evenings([hotel], ["nightlife"], provider=provider)
    assert provider.calls == [] and hotel["evening_suggestions"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("duration", [901, float("nan"), -1])
async def test_travel_duration_must_be_bounded_and_valid(duration):
    hotel = planned_hotel()
    await evenings.enrich_evenings([hotel], ["food"], provider=Provider(duration=duration))
    assert hotel["evening_suggestions"] == []


@pytest.mark.asyncio
async def test_return_must_fit_normal_cutoff():
    hotel = point(9.25 * 3600, "hotel")
    apply_timing([hotel], START, SchedulingPolicy(), ZONE)
    await evenings.enrich_evenings([hotel], ["food"], provider=Provider())
    assert hotel["evening_suggestions"] == []  # 18:15 + rest/visit/drives -> 20:05.


@pytest.mark.asyncio
async def test_no_interest_no_results_and_optional_failure_leave_success_intact():
    provider = Provider()
    hotel = planned_hotel()
    await evenings.enrich_evenings([hotel], [], provider=provider)
    assert provider.calls == []
    for provider in (Provider([]), Provider(failure=True), Provider(delay=1)):
        await evenings.enrich_evenings([hotel], ["food"], provider=provider, budget_seconds=0.02)
        assert hotel["evening_suggestions"] == []
        assert hotel["type"] == "hotel" and hotel["warning"] == "Above nightly target"


def test_equal_persona_is_not_explicit_evening_interest():
    assert (
        evenings.evening_interests(
            None, dict.fromkeys(["food", "culture_arts", "nightlife"], 1 / 14)
        )
        == []
    )
    assert evenings.evening_interests(None, {"food": 0.5, "nightlife": 0.1}) == [
        "food",
        "nightlife",
    ]
    assert evenings.evening_interests([], {"food": 1}) == []


@pytest.mark.asyncio
async def test_live_adapter_uses_provider_category_status_and_never_treats_weekly_hours_as_dated(
    monkeypatch,
):
    requests = []

    def response(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "location": {
                            "id": 1,
                            "names": [{"value": "Local cafe", "primary": True}],
                            "coordinates": {"latitude": 34.001, "longitude": -118},
                            "urls": {"tripadvisor": {"main": "https://example.test/cafe"}},
                            "categories": [
                                {"top_level_category": "Eat & Drink", "display_name": "Restaurants"}
                            ],
                            "status": {"value": "OPEN"},
                            "opening_hours": {
                                "timezone": ZONE,
                                "periods": [
                                    {
                                        "day_of_week": "Wednesday",
                                        "opens": "17:00",
                                        "closes": "23:00",
                                    }
                                ],
                            },
                        }
                    }
                ]
            },
        )

    client = httpx.AsyncClient
    monkeypatch.setattr(
        evenings.httpx,
        "AsyncClient",
        lambda **kwargs: client(transport=httpx.MockTransport(response), **kwargs),
    )
    monkeypatch.setattr(evenings.config, "TRIPADVISOR_API", "fixture")
    records = await evenings.LiveEveningProvider().nearby([34, -118], ["food"], START)
    assert len(records) == 1 and records[0].category == "food"
    assert records[0].opening_intervals is None
    assert requests[0].url.params["radius"] == "2" and requests[0].url.params["unit"] == "KM"


@pytest.mark.asyncio
async def test_departure_override_hides_a_stale_evening_visit():
    hotel = planned_hotel()
    await evenings.enrich_evenings([hotel], ["food"], provider=Provider())
    route = saved_route([hotel, point(3600)], SchedulingPolicy(late_driving=True))
    itinerary = await build_itinerary(
        Itinerary_Payload(route=route, start_time=START.replace(hour=10))
    )
    assert not any(stop.optional for day in itinerary for stop in day.stops)
    assert hotel["evening_suggestions"]
