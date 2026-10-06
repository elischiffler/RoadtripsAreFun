"""CP-SAT selection and scheduling with provider-verified fake records."""

from datetime import date

import pytest
from ortools.sat.python import cp_model

from app.routing.base import PlanningError, PlanOptions
from app.routing.cp_sat_scheduler import schedule_cp_sat_route
from app.routing.discovery import DiscoveryResult
from app.routing.geometry import project_place
from app.routing.occupancy import HotelRoom
from app.routing.planners.cp_sat import CPSatPlanner
from app.routing.registry import available_planners

_PERSONA_KEYS = (
    "scenery",
    "nature",
    "hiking_outdoors",
    "food",
    "history",
    "culture_arts",
    "nightlife",
    "shopping",
    "beaches_water",
    "adventure",
    "relaxation",
    "unique_local_experiences",
    "family_friendliness",
    "crowd_avoidance",
)


def attraction(provider_id, coordinates, utility):
    return {
        "provider_id": provider_id,
        "name": provider_id,
        "coordinates": coordinates,
        "address": None,
        "url": None,
        "attribute_ratings": dict.fromkeys(_PERSONA_KEYS, 0.5),
        "utility": utility,
        "route_progress_seconds": max(0, coordinates[1]),
        "detour_seconds": 0,
    }


def hotel(provider_id, coordinates, price, utility):
    return {
        "provider_id": provider_id,
        "name": provider_id,
        "coordinates": coordinates,
        "address": None,
        "url": None,
        "type": "hotel",
        "hotel_rooms": [{"adults": 2, "child_ages": []}],
        "room_offers": [],
        "price_scope": "one_room_one_night_including_taxes_fees",
        "price": price,
        "utility": utility,
    }


def configure(fake_services, attractions=(), hotels=()):
    calls = {"attractions": [], "hotels": []}

    async def candidates(route, plan, weights):
        calls["attractions"].append((route, [q.coordinates for q in plan.queries], weights))
        return DiscoveryResult(
            [{**item, **project_place(route, item["coordinates"])} for item in attractions], {}
        )

    async def hotel_candidates(position, check_in, price_range, weights, hotel_rooms):
        calls["hotels"].append((position, check_in, price_range, weights))
        return list(hotels)

    services = fake_services.bundle()

    async def roads(*args):
        baseline = calls["attractions"][-1][0].model_copy(deep=True)
        baseline.legs = [baseline.legs[0], baseline.legs[0]]
        return baseline

    services.candidate_route = roads
    services.cp_sat_candidates = candidates
    services.cp_sat_hotels = hotel_candidates
    return services, calls


def short_route(route, seconds):
    route.duration = seconds
    route.legs[0].duration = seconds
    route.legs[0].steps[0].duration = seconds
    return route


@pytest.mark.asyncio
async def test_zero_stops_has_no_candidate_call_or_hotel(route, start_date, fake_services):
    services, calls = configure(fake_services)
    result = await CPSatPlanner().plan(
        short_route(route, 3600),
        PlanOptions(
            0, 100, start_date, traveler_count=2, hotel_rooms=[HotelRoom(adults=2, child_ages=[])]
        ),
        services,
    )
    assert result.stopping_points == []
    assert calls == {"attractions": [], "hotels": []}
    assert "cp_sat" in available_planners()


@pytest.mark.asyncio
async def test_sparse_and_weak_candidates_are_not_forced(route, start_date, fake_services):
    short_route(route, 3600)
    services, calls = configure(fake_services)
    point = services.find_position(route.geometry.coordinates, route.legs[0].steps, 3600 / 7)
    services, calls = configure(
        fake_services,
        [attraction("weak", point, 0.59), attraction("good", point, 0.85)],
    )
    result = await CPSatPlanner().plan(
        route,
        PlanOptions(
            3, 100, start_date, traveler_count=2, hotel_rooms=[HotelRoom(adults=2, child_ages=[])]
        ),
        services,
    )
    assert [stop["name"] for stop in result.stopping_points] == ["good"]
    assert len(calls["attractions"][0][1]) == 9
    assert calls["attractions"][0][1][0] != calls["attractions"][0][1][1]


def test_same_position_places_can_be_selected_and_identity_deduplicates():
    points = [[0, -1], [0, 1]]
    selected = CPSatPlanner._select(
        [
            attraction("b", [0, 0], 0.9),
            attraction("a", [0, -1], 0.8),
            attraction("b", [0, 1], 1.0),
            attraction("c", [0, 1], 0.7),
        ],
        points,
        3,
        10,
    )
    assert [(slot, item["provider_id"]) for slot, item in selected] == [
        (0, "a"),
        (0, "b"),
        (1, "c"),
    ]


def test_stable_selection_with_duplicate_slot_and_order():
    points = [[0, 0], [0, 2], [0, 4]]
    records = [
        attraction("z", [0, 4], 0.9),
        attraction("b", [0, 0], 0.8),
        attraction("a", [0, 0], 0.8),
        attraction("m", [0, 2], 0.95),
    ]
    outputs = [
        [(slot, item["provider_id"]) for slot, item in CPSatPlanner._select(records, points, 3, 10)]
        for _ in range(3)
    ]
    assert outputs == [outputs[0]] * 3
    assert len(outputs[0]) == 3


@pytest.mark.parametrize("status", [cp_model.FEASIBLE, cp_model.OPTIMAL])
def test_usable_solver_statuses_return_only_selected(monkeypatch, status):
    class FakeSolver:
        parameters = type("Parameters", (), {})()

        def Solve(self, model):
            return status

        def Value(self, variable):
            return 1

    monkeypatch.setattr(cp_model, "CpSolver", FakeSolver)
    selected = CPSatPlanner._select([attraction("a", [0, 0], 0.9)], [[0, 0]], 1, 10)
    assert selected[0][1]["provider_id"] == "a"


@pytest.mark.parametrize("status", [cp_model.UNKNOWN, cp_model.INFEASIBLE])
def test_unsolved_status_never_returns_candidates(monkeypatch, status):
    class FakeSolver:
        parameters = type("Parameters", (), {})()

        def Solve(self, model):
            return status

    monkeypatch.setattr(cp_model, "CpSolver", FakeSolver)
    with pytest.raises(PlanningError):
        CPSatPlanner._select([attraction("a", [0, 0], 0.9)], [[0, 0]], 1, 10)


@pytest.mark.asyncio
async def test_stop_at_assigned_drive_position_then_day_rollover(route, start_date, fake_services):
    short_route(route, 13 * 3600)
    position = fake_services.bundle().find_position(
        route.geometry.coordinates, route.legs[0].steps, route.duration * 6 / 7
    )
    services, calls = configure(
        fake_services,
        attractions=[attraction("late", position, 0.9)],
        hotels=[hotel("h", [35, -100], 100, 0.5)],
    )
    result = await CPSatPlanner().plan(
        route,
        PlanOptions(
            1, 500, start_date, traveler_count=2, hotel_rooms=[HotelRoom(adults=2, child_ages=[])]
        ),
        services,
    )
    assert [item["type"] for item in result.stopping_points] == ["hotel", "stop"]
    assert result.stopping_points[1]["coordinates"] == position
    assert len(calls["hotels"]) == 1
    assert calls["hotels"][0][0] == services.find_position(
        route.geometry.coordinates, route.legs[0].steps, 9 * 3600
    )
    assert calls["hotels"][0][1] == date(2025, 6, 1)


@pytest.mark.asyncio
async def test_hotel_retry_and_in_budget_preference(route, start_date, fake_services):
    short_route(route, 13 * 3600)
    services, calls = configure(fake_services)

    async def find_hotels(position, check_in, price_range, weights, hotel_rooms):
        calls["hotels"].append((position, check_in, price_range, weights))
        if len(calls["hotels"]) == 1:
            return []
        return [
            hotel("expensive", position, 500, 1.0),
            hotel("affordable", position, 100, 0.2),
        ]

    services.cp_sat_hotels = find_hotels
    result = await schedule_cp_sat_route(
        route,
        [],
        PlanOptions(
            0, 200, start_date, traveler_count=2, hotel_rooms=[HotelRoom(adults=2, child_ages=[])]
        ),
        services,
    )
    assert result[0][0]["name"] == "affordable"
    assert result[1] == 100
    assert len(calls["hotels"]) == 2
    assert calls["hotels"][0][0] != calls["hotels"][1][0]


@pytest.mark.asyncio
async def test_over_budget_hotel_keeps_actual_price(route, start_date, fake_services):
    short_route(route, 13 * 3600)
    services, _ = configure(fake_services, hotels=[hotel("high", [35, -100], 400, 0.8)])
    stops, cost = await schedule_cp_sat_route(
        route,
        [],
        PlanOptions(
            0, 100, start_date, traveler_count=2, hotel_rooms=[HotelRoom(adults=2, child_ages=[])]
        ),
        services,
    )
    assert cost == 400
    assert stops[0]["price"] == 400
    assert "$100 per-room nightly target" in stops[0]["warning"]


@pytest.mark.asyncio
async def test_multi_night_budget_remains_a_per_room_nightly_target(
    route, start_date, fake_services
):
    short_route(route, 35 * 3600)
    services, calls = configure(fake_services)

    async def find_hotels(position, check_in, price_range, weights, hotel_rooms):
        calls["hotels"].append((position, check_in, price_range, weights))
        return [hotel(f"night-{check_in}", position, 400, 0.8)]

    services.cp_sat_hotels = find_hotels
    stops, cost = await schedule_cp_sat_route(
        route,
        [],
        PlanOptions(
            0, 100, start_date, traveler_count=2, hotel_rooms=[HotelRoom(adults=2, child_ages=[])]
        ),
        services,
    )
    hotels = [stop for stop in stops if stop["type"] == "hotel"]
    assert len(hotels) >= 3
    assert cost == 400 * len(hotels)
    assert all(call[2] == ((0.0, 100), "0-100.00") for call in calls["hotels"])
    assert all("$100 per-room nightly target" in stop["warning"] for stop in hotels)


@pytest.mark.asyncio
async def test_missing_hotel_fails_after_bounded_retries(route, start_date, fake_services):
    short_route(route, 13 * 3600)
    services, calls = configure(fake_services)
    with pytest.raises(PlanningError, match="No verified hotel"):
        await schedule_cp_sat_route(
            route,
            [],
            PlanOptions(
                0,
                100,
                start_date,
                traveler_count=2,
                hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
            ),
            services,
        )
    assert 1 <= len(calls["hotels"]) <= 6
