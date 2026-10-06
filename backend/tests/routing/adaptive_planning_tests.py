"""Budget, geometry, quality, live-road barriers and concurrency acceptance."""

import asyncio
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest

from app.agent.persona import ATTRIBUTE_KEYS, default_weights
from app.agent.progress import reporting
from app.agent.provider_diagnostics import collecting_attempts, retry_async
from app.agent.providers import SupabaseServiceAuth
from app.agent.schemas import LLMResponse
from app.routing.base import PlanningError, PlanOptions
from app.routing.cp_sat_scheduler import schedule_cp_sat_route
from app.routing.cp_sat_selection import select_attractions
from app.routing.discovery import balanced_pool, make_discovery_plan
from app.routing.explanation import capture_explanation
from app.routing.geometry import RouteMeasure, find_position
from app.routing.occupancy import HotelRoom
from app.routing.planners.cp_sat import CPSatPlanner
from app.routing.run_metrics import measuring
from app.routing.runtime import joined, limited, run_context, singleflight, threaded
from app.routing.sources.mapbox import UnusableRoadRoute
from app.routing.sources.persona_candidates import attraction_candidates
from tests.routing.conftest import build_route


def corridor(hours=8, miles=500, coords=None):
    route = build_route(hours * 3600, miles * 1609.344)
    coords = coords or [[0, 0], [4, 0]]
    route.geometry.coordinates = coords
    route.legs[0].steps[0].geometry.coordinates = coords
    return route


class EchoAI:
    def __init__(self, utility=0.8, delay=0):
        self.utility, self.delay, self.calls = utility, delay, []

    def complete(self, messages, tools):
        names = json.loads(messages[-1].content.split("exactly: ")[1])
        self.calls.append(names)
        assert len(names) <= 5
        time.sleep(self.delay)
        return LLMResponse(
            content=json.dumps(
                {
                    "candidates": [
                        {
                            "name": name,
                            "attribute_ratings": dict.fromkeys(ATTRIBUTE_KEYS, self.utility),
                        }
                        for name in names
                    ]
                }
            )
        )


class Places:
    def __init__(self, per_query=20, initial_empty=None, delay=0):
        self.per_query = per_query
        self.initial_empty = initial_empty or set()
        self.delay = delay
        self.calls = []

    async def attractions_near(self, point):
        self.calls.append(tuple(point))
        await asyncio.sleep(self.delay * (1 + (point[1] % 0.1)))
        if tuple(point) in self.initial_empty:
            return []
        key = f"{point[1]:.8f}"
        return [
            {
                "provider_id": f"terra:{key}:{i}",
                "name": f"Place {key}:{i}",
                "coordinates": point,
                "categories": ["museum" if i % 2 else "park"],
                "provider_rank": i,
            }
            for i in range(self.per_query)
        ]


@pytest.mark.parametrize("hours,miles,stops", [(0, 0, 0), (1, 50, 1), (8, 500, 2), (80, 4000, 10)])
def test_budget_formulas_and_round_robin_sections(hours, miles, stops):
    plan = make_discovery_plan(corridor(hours, miles), stops)
    sections = max(1, min(12, math.ceil(hours / 2)))
    assert plan.section_count == sections
    assert plan.candidate_cap == min(60, max(18, 6 * stops + 2 * sections))
    assert plan.rating_cap == 2 * plan.candidate_cap
    assert plan.raw_pool_cap == 3 * plan.candidate_cap
    if not stops:
        assert plan.queries == [] and plan.maximum_searches == 0
        return
    initial = min(36, max(2 * sections, 3 * stops, math.ceil(hours)))
    assert len(plan.queries) == plan.initial_searches == initial
    assert plan.maximum_searches == min(60, max(initial + sections, math.ceil(miles / 10)))
    assert [query.section_id for query in plan.queries[:sections]] == list(range(sections))


async def test_balanced_raw_rating_and_shortlist_include_late_sections():
    route = corridor()
    plan = make_discovery_plan(route, 2)
    ai, places = EchoAI(), Places()
    result = await attraction_candidates(route, plan, default_weights(), ai=ai, places=places)
    counts = [sum(item["section_id"] == i for item in result.candidates) for i in range(4)]
    assert counts == [5] * 4
    assert len(places.calls) == plan.initial_searches
    assert len(ai.calls) == 4
    assert result.explanation["raw_pool_count"] == plan.raw_pool_cap
    assert result.explanation["stop_reason"] == "eligible_target_and_sections_reached"
    assert {tuple(item["categories"]) for item in result.candidates} == {("museum",), ("park",)}
    assert all(
        item["source_query_ids"] and item["route_progress_seconds"] > 0
        for item in result.candidates
    )


async def test_refines_empty_section_first_at_largest_interval_midpoint():
    route = corridor()
    plan = make_discovery_plan(route, 2)
    empty = {tuple(query.coordinates) for query in plan.queries if query.section_id == 3}
    ai, places = EchoAI(), Places(per_query=1, initial_empty=empty)
    result = await attraction_candidates(route, plan, default_weights(), ai=ai, places=places)
    queries = result.explanation["queries"]
    assert queries[plan.initial_searches]["section_id"] == 3
    assert queries[plan.initial_searches]["progress_seconds"] == pytest.approx(22800)
    assert len(places.calls) == len(set(places.calls))
    assert result.explanation["sparse_sections"] == []
    assert len(result.explanation["rounds"]) == 2


async def test_sparse_sections_and_search_exhaustion_are_explicit():
    route = corridor()
    plan = make_discovery_plan(route, 2)
    ai, places = EchoAI(), Places(per_query=0)
    result = await attraction_candidates(route, plan, default_weights(), ai=ai, places=places)
    assert not result.candidates and not ai.calls
    assert len(places.calls) == plan.maximum_searches
    assert result.explanation["sparse_sections"] == [0, 1, 2, 3]
    assert result.explanation["stop_reason"] == "search_budget_exhausted"
    assert all(
        gap["largest_unsearched_interval_seconds"] > 0
        for gap in result.explanation["unsearched_gaps"]
    )
    assert "not continuous coverage" in result.explanation["coverage_note"]


async def test_rating_budget_exhausts_without_rerating_identity():
    route = corridor()
    plan = make_discovery_plan(route, 2)
    ai, places = EchoAI(0.4), Places()
    result = await attraction_candidates(route, plan, default_weights(), ai=ai, places=places)
    names = [name for batch in ai.calls for name in batch]
    assert len(names) == len(set(names)) == plan.rating_cap
    assert result.explanation["stop_reason"] == "rating_budget_exhausted"
    assert not result.candidates


def test_unused_section_quotas_redistribute_and_category_missing_stays_missing():
    records = [
        {"section_id": section, "rank": i}
        for section, count in [(0, 1), (3, 8)]
        for i in range(count)
    ]
    result = balanced_pool(records, 6, 4, lambda item: item["rank"])
    assert len(result) == 6
    assert sum(item["section_id"] == 3 for item in result) == 5


def test_curved_projection_and_step_time_mapping():
    route = corridor(1, coords=[[0, 0], [1, 0], [1, 1]])
    measure = RouteMeasure(route)
    assert measure.project([0.5, 1])["route_progress_seconds"] == pytest.approx(2700, abs=8)
    assert measure.position(2700) == pytest.approx([0.5, 1], abs=0.003)
    step = route.legs[0].steps[0]
    step.geometry.coordinates = [[0, 0], [1, 0]]
    step.duration = 900
    second = step.model_copy(deep=True)
    second.geometry.coordinates = [[1, 0], [1, 1]]
    second.duration = 2700
    route.legs[0].steps = [step, second]
    assert RouteMeasure(route).project([0.5, 1])["route_progress_seconds"] == pytest.approx(2250)


def test_crossings_repeated_coordinates_zero_duration_and_endpoint_order():
    route = corridor(1, coords=[[0, 0], [1, 1], [0, 1], [1, 0], [1, 0]])
    measure = RouteMeasure(route)
    early = measure.project([0.5, 0.5], 0)["route_progress_seconds"]
    late = measure.project([0.5, 0.5], 3600)["route_progress_seconds"]
    assert early < late
    zero = route.legs[0].steps[0].model_copy(deep=True)
    zero.duration = 0
    zero.geometry.coordinates = [[0, 0], [0, 0]]
    route.legs[0].steps.insert(0, zero)
    assert RouteMeasure(route).project([0.5, 0.5], 3600)["route_progress_seconds"] == pytest.approx(
        late
    )
    assert find_position(route.geometry.coordinates, route.legs[0].steps, 9999) == [0, 1]
    assert find_position(route.geometry.coordinates, route.legs[0].steps, 0) == [0, 0]


def candidate(key, progress, utility=0.9, detour=0):
    return {
        "provider_id": key,
        "name": key,
        "coordinates": [0, 0],
        "utility": utility,
        "route_progress_seconds": progress,
        "detour_seconds": detour,
        "section_id": 0,
    }


def test_balanced_selection_accepts_ten_points_but_prioritizes_larger_quality_loss():
    records = [
        candidate("best", 100, 0.95),
        candidate("cluster", 200, 0.95),
        candidate("balanced", 6000, 0.75),
    ]
    with capture_explanation() as explanation:
        selected = select_attractions(records, [], 2, 9000)
    assert {item.candidate["name"] for item in selected} == {"cluster", "balanced"}
    assert explanation["solver"]["quality_loss"] == pytest.approx(0.10)
    records[-1]["utility"] = 0.749
    selected = select_attractions(records, [], 2, 9000)
    assert {item.candidate["name"] for item in selected} == {"best", "cluster"}


def test_both_endpoint_gaps_detour_cost_and_fixed_count():
    records = [
        candidate("edge", 100),
        candidate("middle", 4500, detour=100),
        candidate("almost", 4400),
    ]
    with capture_explanation() as explanation:
        selected = select_attractions(records, [], 1, 9000)
    assert selected[0].candidate["name"] == "middle"  # 0 gap deviation + 100 < 200
    solver = explanation["solver"]
    assert solver["spacing_deviation_seconds"] == 0
    assert solver["estimated_detour_seconds"] == solver["objective_value"] == 100
    records[1]["detour_seconds"] = 201
    assert select_attractions(records, [], 1, 9000)[0].candidate["name"] == "almost"
    assert len(select_attractions(records, [], 10, 9000)) == 3


async def test_road_checks_exclude_no_route_and_clamp_only_measured_negative(fake_services):
    route = corridor()
    services = fake_services.bundle()
    candidates = [candidate("negative", 100), candidate("unusable", 200), candidate("bad", 300)]
    for i, item in enumerate(candidates):
        item["coordinates"] = [0, i]

    async def roads(*args):
        waypoint = args[-1]
        if waypoint == "1,0":
            raise UnusableRoadRoute()
        result = route.model_copy(deep=True)
        result.duration -= 10
        result.legs *= 2
        if waypoint == "2,0":
            result.legs[0].duration = float("nan")
        return result

    services.candidate_route = roads
    with capture_explanation() as explanation:
        result = await CPSatPlanner._verify_detours(route, candidates, services)
    assert len(result) == 1 and result[0]["detour_seconds"] == 0
    assert result[0]["detour_raw_seconds"] == -10
    assert len(explanation["road_checks"]) == 3

    async def unavailable(*args):
        raise httpx.ConnectError("offline")

    services.candidate_route = unavailable
    with pytest.raises(httpx.ConnectError):
        await CPSatPlanner._verify_detours(route, candidates, services)


async def test_schedule_uses_measured_progress_and_half_detour_before_after(
    fake_services, start_date
):
    route = corridor(1)
    services = fake_services.bundle()

    async def no_hotels(*args):
        return []

    services.cp_sat_hotels = no_hotels
    records = [(2700, candidate("a", 2700, detour=600)), (900, candidate("b", 900, detour=600))]
    stops, _ = await schedule_cp_sat_route(
        route,
        records,
        PlanOptions(
            2, 100, start_date, traveler_count=2, hotel_rooms=[HotelRoom(adults=2, child_ages=[])]
        ),
        services,
    )
    assert [stop["name"] for stop in stops] == ["b", "a"]
    # Query indices/point counts are absent from this contract.
    assert all(stop["type"] == "stop" for stop in stops)


async def test_serial_vs_concurrent_workload_is_deterministic_and_at_least_30_percent_faster():
    route = corridor()

    async def run(cap):
        places, ai = Places(delay=0.04), EchoAI(delay=0.04)
        started = time.perf_counter()
        with measuring() as data:
            async with run_context({"nearby": cap, "ai": min(cap, 2)}):
                result = await attraction_candidates(
                    route, make_discovery_plan(route, 2), default_weights(), ai=ai, places=places
                )
        return result, data, time.perf_counter() - started, len(places.calls), len(ai.calls)

    serial, sd, st, sc, sa = await run(1)
    concurrent, cd, ct, cc, ca = await run(4)
    assert concurrent == serial
    assert (sc, sa) == (cc, ca) == (8, 4)
    assert ct < st * 0.70
    assert cd["providers"]["nearby"]["peak_active"] == 4
    assert cd["providers"]["ai"]["peak_active"] == 2
    assert sd["providers"]["nearby"]["peak_active"] == 1
    print(
        f"controlled elapsed serial={st:.3f}s concurrent={ct:.3f}s reduction={1 - ct / st:.1%}; calls={cc + ca}"
    )


@pytest.mark.parametrize(
    "kind,run_cap,process_cap",
    [
        ("nearby", 4, 8),
        ("mapbox", 4, 8),
        ("ai", 2, 4),
        ("hotels", 2, 2),
        ("geocoding", 2, 4),
        ("solver", 2, 2),
    ],
)
def test_process_caps_across_private_event_loops(kind, run_cap, process_cap):
    active, peak = 0, 0
    lock = threading.Lock()
    barrier = threading.Barrier(3)

    async def work():
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        await asyncio.sleep(0.035)
        with lock:
            active -= 1

    def run():
        barrier.wait()

        async def execute():
            with measuring() as data:
                async with run_context():
                    await joined([limited(kind, work) for _ in range(8)])
                    assert data["providers"][kind]["peak_active"] <= run_cap

        asyncio.run(execute())

    with ThreadPoolExecutor(3) as pool:
        list(pool.map(lambda _: run(), range(3)))
    assert peak == process_cap and active == 0


async def test_cancelled_sync_work_retains_capacity_until_real_completion():
    started, finish = threading.Event(), threading.Event()

    def block():
        started.set()
        finish.wait(2)
        return "late"

    with measuring() as data:
        async with run_context({"geocoding": 1}):
            first = asyncio.create_task(threaded("geocoding", block))
            while not started.is_set():
                await asyncio.sleep(0.005)
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            second_started = threading.Event()
            second = asyncio.create_task(threaded("geocoding", second_started.set))
            await asyncio.sleep(0.03)
            assert not second_started.is_set()
            assert data["providers"]["geocoding"]["active"] == 1
            finish.set()
            await second
    assert data["providers"]["geocoding"]["active"] == 0


async def test_failure_cancels_siblings_and_run_singleflight_avoids_extra_requests():
    cancelled = asyncio.Event()

    async def slow():
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    async def fail():
        await asyncio.sleep(0.01)
        raise PlanningError("fail")

    with pytest.raises(PlanningError):
        await joined([slow(), fail()])
    assert cancelled.is_set()
    calls = []

    async def request():
        calls.append(1)
        await asyncio.sleep(0.01)
        return 7

    async with run_context():
        assert await joined([singleflight(("same", 1), request) for _ in range(10)]) == [7] * 10
    assert calls == [1]
    async with run_context():
        await singleflight(("same", 1), request)
    assert calls == [1, 1]  # Fresh across runs.


async def test_retry_after_releases_http_capacity_during_backoff(monkeypatch):
    waits, calls = [], []
    real_sleep = asyncio.sleep

    async def pause(seconds):
        waits.append(seconds)
        await real_sleep(0)

    monkeypatch.setattr("app.agent.provider_diagnostics.asyncio.sleep", pause)

    async def request():
        calls.append(1)
        if len(calls) < 3:
            response = httpx.Response(
                429,
                headers={"Retry-After": "2"},
                request=httpx.Request("GET", "https://example.test"),
            )
            response.raise_for_status()
        return 1

    with collecting_attempts() as attempts:
        async with run_context({"nearby": 1}):
            assert await retry_async(lambda: limited("nearby", request)) == 1
    assert waits == [2, 2] and len(calls) == 3
    assert attempts[-1]["outcome"] == "recovered"


def test_concurrent_authentication_and_refresh_are_single_flight(monkeypatch):
    auth = SupabaseServiceAuth("https://auth.test", "key", "user", "pass")
    grants = []

    def grant(kind, body):
        grants.append(kind)
        time.sleep(0.03)
        auth._access_token = "token"
        auth._refresh_token = "refresh"
        auth._expires_at = time.monotonic() + 3600
        return "token"

    monkeypatch.setattr(auth, "_grant", grant)
    with ThreadPoolExecutor(8) as pool:
        assert list(pool.map(lambda _: auth.get_token(), range(8))) == ["token"] * 8
    assert grants == ["password"]
    auth._expires_at = 0
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(lambda _: auth.get_token(), range(8)))
    assert grants == ["password", "refresh_token"]


def test_progress_sequences_stay_ordered_across_threads():
    from contextvars import copy_context

    from app.agent.progress import emit

    events = []
    with reporting(events.append), ThreadPoolExecutor(8) as pool:
        contexts = [copy_context() for _ in range(100)]
        list(pool.map(lambda context: context.run(emit, "test"), contexts))
    assert [event["sequence"] for event in events] == list(range(1, 101))


async def test_discovery_rating_and_road_solver_dependency_barriers(
    fake_services, start_date, monkeypatch
):
    route = corridor(1)
    plan = make_discovery_plan(route, 2)
    completed_queries = []

    class BarrierPlaces(Places):
        async def attractions_near(self, point):
            result = await super().attractions_near(point)
            completed_queries.append(tuple(point))
            return result

    class BarrierAI(EchoAI):
        def complete(self, messages, tools):
            assert len(completed_queries) == plan.initial_searches
            return super().complete(messages, tools)

    places, ai = BarrierPlaces(per_query=1, delay=0.01), BarrierAI(delay=0.01)
    discovered = await attraction_candidates(route, plan, default_weights(), ai=ai, places=places)
    services = fake_services.bundle()
    roads_complete = []

    async def discovery(*args):
        return discovered

    async def road(*args):
        await asyncio.sleep(0.01)
        roads_complete.append(args[-1])
        result = route.model_copy(deep=True)
        result.legs *= 2
        return result

    original = CPSatPlanner._select

    def select(*args):
        assert len(roads_complete) == len(discovered.candidates)
        return original(*args)

    async def schedule(*args):
        assert len(roads_complete) == len(discovered.candidates)
        return [], 0

    services.cp_sat_candidates, services.candidate_route = discovery, road
    services.cp_sat_hotels = schedule
    monkeypatch.setattr(CPSatPlanner, "_select", staticmethod(select))
    monkeypatch.setattr("app.routing.planners.cp_sat.schedule_cp_sat_route", schedule)
    await CPSatPlanner().plan(route, PlanOptions(2, 100, start_date), services)


@pytest.mark.parametrize("cap", [1, 2])
async def test_hotel_details_wait_for_listing_and_overlap_without_parent_permit(cap):
    from app.routing.sources.google_hotels import GoogleHotelProvider
    from tests.routing.google_hotels_tests import CARD, CHECK_IN, CONTROLS, DETAIL, Geocoder

    listing_finished, active, peak = False, 0, 0
    calls = []

    async def handle(request):
        nonlocal listing_finished, active, peak
        calls.append(request.url.path)
        if request.url.path == "/travel/search":
            await asyncio.sleep(0.01)
            listing_finished = True
            body = (
                CONTROLS
                + CARD
                + CARD.replace("ExampleID", "SecondID").replace("Example Hotel", "Second Hotel")
            )
        else:
            assert listing_finished
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0.03)
            active -= 1
            body = CONTROLS + DETAIL
            if request.url.path.endswith("SecondID"):
                body = body.replace("Example Hotel", "Second Hotel")
        return httpx.Response(200, text=body, headers={"content-type": "text/html"})

    provider = GoogleHotelProvider(Geocoder(), transport=httpx.MockTransport(handle))
    async with run_context({"hotels": cap}):
        records = await asyncio.wait_for(
            provider.hotels_near([39.74, -104.99], CHECK_IN, HotelRoom(adults=2, child_ages=[])), 2
        )
    assert len(records) == 2 and len(calls) == 3
    assert peak == cap and active == 0


async def test_room_allocations_overlap_then_intersect_in_request_order(monkeypatch):
    from datetime import date

    from app.routing.sources import persona_candidates as source

    rooms = [HotelRoom(adults=1, child_ages=[]), HotelRoom(adults=2, child_ages=[])]
    active, peak = 0, 0

    async def lookup(point, check_in, price_range, weights, room, **kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02 if room.adults == 1 else 0.01)
        active -= 1
        return [
            {
                "provider_id": "shared",
                "name": "Shared Hotel",
                "room": room.model_dump(),
                "price": 50 * room.adults,
                "url": "https://example.test",
                "check_in_date": check_in,
                "price_scope": "one_room_one_night_including_taxes_fees",
            }
        ]

    monkeypatch.setattr(source, "_room_candidates", lookup)
    result = await source.hotel_candidates(
        [0, 0], date(2026, 11, 20), ((0, 200), "USD"), default_weights(), rooms, ai=EchoAI()
    )
    assert peak == 2 and active == 0
    assert result[0]["price"] == 150
    assert [offer["room"]["adults"] for offer in result[0]["room_offers"]] == [1, 2]


async def test_zero_stops_skips_discovery_and_solver_job(fake_services, start_date, monkeypatch):
    services = fake_services.bundle()

    async def discovery(*args):
        pytest.fail("Zero-stop trips must not discover attractions")

    def select(*args):
        pytest.fail("Zero-stop trips must not queue a solver job")

    async def schedule(*args):
        return [], 0

    services.cp_sat_candidates = discovery
    services.cp_sat_hotels = schedule
    monkeypatch.setattr(CPSatPlanner, "_select", staticmethod(select))
    monkeypatch.setattr("app.routing.planners.cp_sat.schedule_cp_sat_route", schedule)
    with capture_explanation() as explanation, measuring() as data:
        await CPSatPlanner().plan(corridor(1), PlanOptions(0, 100, start_date), services)
    assert explanation["solver"]["status"] == "NOT_RUN"
    assert explanation["discovery"]["stop_reason"] == "zero_requested"
    assert "solver" not in data["providers"]
