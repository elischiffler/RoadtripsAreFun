"""Shared fixtures/fakes for planner-level tests.

These tests exercise the planners in isolation by injecting a fake
``RoutingServices`` — no network, no OR-Tools-vs-API coupling. This is the
template every future algorithm reuses.
"""

from datetime import datetime
from typing import Any

import pytest

from app.models.routing_models.routing_models import MapBox
from app.routing.geometry import find_position
from app.routing.pricing import get_price_range
from app.routing.services import RoutingServices

MapBox_route = MapBox.MapBox_Route


def build_route(duration: float = 50000.0, distance: float = 4500000.0) -> MapBox_route:
    """A minimal single-leg Mapbox route spanning LA-ish to NY-ish."""
    start = [-117.93, 33.72]
    end = [-74.16, 40.65]
    mid = [(start[0] + end[0]) / 2, (start[1] + end[1]) / 2]
    data = {
        "code": "Ok",
        "uuid": "test-uuid",
        "waypoints": [
            {"name": "Start", "location": start, "distance": 0},
            {"name": "End", "location": end, "distance": 0},
        ],
        "routes": [
            {
                "weight_name": "auto",
                "weight": duration,
                "duration": duration,
                "distance": distance,
                "geometry": {"coordinates": [start, mid, end], "type": "LineString"},
                "legs": [
                    {
                        "weight": duration,
                        "duration": duration,
                        "distance": distance,
                        "summary": "",
                        "steps": [
                            {
                                "distance": distance,
                                "duration": duration,
                                "weight": duration,
                                "mode": "driving",
                                "driving_side": "right",
                                "name": "",
                                "intersections": [],
                                "maneuver": {
                                    "type": "depart",
                                    "instruction": "Drive east",
                                    "bearing_after": 90,
                                    "bearing_before": 0,
                                    "location": start,
                                },
                                "geometry": {"coordinates": [start, end], "type": "LineString"},
                            }
                        ],
                    }
                ],
            }
        ],
    }
    return MapBox.model_validate(data).routes[0]


class FakeServices:
    """Factory for a RoutingServices bundle backed by in-memory fakes."""

    def __init__(self, hotel_price: float = 120.0, num_attractions: int = 6):
        self.hotel_price = hotel_price
        self.num_attractions = num_attractions
        self.find_stop_calls = 0
        self.find_hotel_calls = 0
        # Optional per-candidate-index (1-based) detour_meters overrides for tests.
        self.detour_overrides: dict[int, float] = {}

    async def find_stop(self, category: str, lat: float, lon: float, radius: int) -> dict[str, Any]:
        self.find_stop_calls += 1
        return {
            "coordinates": [float(lat), float(lon)],
            "name": f"Attraction @ {lat:.2f},{lon:.2f}",
            "type": "stop",
            "url": "http://example.com/a",
            "address": "1 Attraction Way",
        }

    async def find_hotel(self, lat, lon, price_range, check_in, radius: int = 30):
        self.find_hotel_calls += 1
        return {
            "coordinates": [float(lat), float(lon)],
            "name": "Fake Hotel",
            "type": "hotel",
            "price": self.hotel_price,
            "address": "1 Hotel Rd",
            "url": "http://example.com/h",
        }

    async def gather_candidates(self, route, num_candidates: int, radius: int = 30):
        # Return `num_attractions` candidates spread across the route duration.
        # `detour_overrides` lets a test set a specific detour_meters per candidate
        # index (1-based); anything unset defaults to a small, cheap detour.
        out: list[dict[str, Any]] = []
        duration = route.duration
        n = min(self.num_attractions, max(num_candidates, 0))
        for i in range(1, n + 1):
            elapsed = duration * i / (n + 1)
            lat, lon = find_position(route.geometry.coordinates, route.legs[0].steps, elapsed)
            out.append(
                {
                    "coordinates": [lat, lon],
                    "name": f"Candidate {i}",
                    "type": "stop",
                    "url": "http://example.com/c",
                    "address": f"{i} Candidate St",
                    "elapsed_time": elapsed,
                    "rank": i,  # lower i = better rank
                    "detour_meters": self.detour_overrides.get(i, 1000.0),
                }
            )
        return out

    def bundle(self) -> RoutingServices:
        return RoutingServices(
            find_stop=self.find_stop,
            find_hotel=self.find_hotel,
            find_position=find_position,
            get_price_range=get_price_range,
            gather_candidates=self.gather_candidates,
        )


@pytest.fixture
def fake_services():
    return FakeServices()


@pytest.fixture
def route():
    return build_route()


@pytest.fixture
def start_date():
    return datetime(2025, 6, 1, 9, 0, 0)
