"""Synthetic fixtures verify geometry and integrity; never empirical observations."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agent.persona import ATTRIBUTE_KEYS
from app.research import corridor_inputs, preparation
from app.research.design import Design, plan
from app.routing.corridor import CorridorConfig, RouteCorridor
from app.routing.cp_sat_selection import SelectionConfig, select_attractions
from app.routing.sources.persona_candidates import ProposedPlace


def route(coords=None):
    return SimpleNamespace(
        duration=7200,
        legs=[],
        geometry=SimpleNamespace(coordinates=coords or [[-120, 35], [-118, 35]]),
    )


def place(index, coordinates=None):
    return {
        "provider_id": f"fixture-{index:03}",
        "name": f"Fixture {index}",
        "coordinates": coordinates or [35, -119],
        "categories": ["daytime"],
    }


def test_bell_has_exact_endpoints_midpoint_and_mirror_symmetry():
    config = CorridorConfig()
    assert config.radius_miles(0) == config.radius_miles(1) == 5
    assert config.radius_miles(0.5) == 25
    for fraction in (0.1, 0.2, 0.3, 0.4):
        assert config.radius_miles(fraction) == pytest.approx(config.radius_miles(1 - fraction))
    assert config.radius_miles(0.1) < config.radius_miles(0.2) < config.radius_miles(0.3)
    assert CorridorConfig(10, 10).radius_miles(0.3) == 10


@pytest.mark.parametrize(
    "kwargs",
    [
        {"endpoint_miles": 0},
        {"midpoint_miles": 4},
        {"sigma": 0},
        {"sigma": float("nan")},
        {"endpoint_miles": True},
    ],
)
def test_invalid_widths_cannot_collect_places(kwargs):
    with pytest.raises(ValueError):
        CorridorConfig(**kwargs)


def test_continuous_route_includes_mid_segment_places_and_widens_at_middle():
    corridor = RouteCorridor(route())
    # About 14 miles north: included halfway along the road, excluded near its start.
    assert corridor.project([35.2, -119])["inside_corridor"]
    assert not corridor.project([35.2, -120])["inside_corridor"]
    assert not corridor.project([35.5, -119])["inside_corridor"]
    assert corridor.project([35, -119])["route_distance_fraction"] == pytest.approx(0.5)
    assert corridor.project([35, -119])["route_progress_seconds"] == pytest.approx(3600)


def test_route_polyline_not_start_end_chord_and_distance_not_time_progress():
    bent = route([[-120, 35], [-120, 36], [-119, 36]])
    corridor = RouteCorridor(bent, CorridorConfig(1, 1))
    assert corridor.project([35.5, -120])["inside_corridor"]
    assert not corridor.project([35.5, -119.5])["inside_corridor"]
    segments = [
        SimpleNamespace(duration=1, geometry=SimpleNamespace(coordinates=[[-120, 35], [-119, 35]])),
        SimpleNamespace(
            duration=99, geometry=SimpleNamespace(coordinates=[[-119, 35], [-118, 35]])
        ),
    ]
    timed = route()
    timed.legs = [SimpleNamespace(steps=segments)]
    midpoint = RouteCorridor(timed).project([35, -119])
    assert midpoint["route_distance_fraction"] == pytest.approx(0.5)
    assert midpoint["corridor_radius_miles"] == pytest.approx(25)
    assert midpoint["route_progress_seconds"] == pytest.approx(72)


def test_over_one_hundred_matches_reach_the_solver_without_truncation():
    records = [place(i, [35, -120 + i / 60]) for i in range(121)]
    corridor = RouteCorridor(route())
    pool = corridor.select(list(reversed(records)))
    assert len(pool) == 121
    assert pool == corridor.select(records)
    for row in pool:
        row.update(utility=0.9 if row["provider_id"] == "fixture-120" else 0.1, detour_seconds=0)
    selected = select_attractions(
        pool, [], 1, 7200, config=SelectionConfig(candidate_limit=None, quality_loss=0)
    )
    assert selected[0].candidate["provider_id"] == "fixture-120"


async def test_rating_batches_fill_every_missing_place_and_persist_actual_model(monkeypatch):
    records = [place(i) for i in range(12)]
    storage, calls = {}, []

    def put(entries, provider):
        assert provider == "fixture/fixture-model"
        for source, ratings in entries:
            storage[source.provider_id] = {
                "attribute_ratings": ratings,
                "provider": provider,
                "rated_at": "fixture-time",
            }
        return {source.provider_id: storage[source.provider_id] for source, _ in entries}

    async def propose(_ai, _kind, _point, limit, **kwargs):
        calls.append(kwargs["names"])
        assert limit == len(kwargs["names"]) <= 5
        kwargs["diagnostics"].update(provider="fixture", model="fixture-model")
        return [
            ProposedPlace(name=name, attribute_ratings=dict.fromkeys(ATTRIBUTE_KEYS, 0.5))
            for name in kwargs["names"]
        ]

    monkeypatch.setattr(corridor_inputs, "_propose", propose)
    cache = SimpleNamespace(get_many=lambda _: {}, put_many=put)
    inputs = plan(Design())["cases"][0]["inputs"]
    candidates, diagnostics = await corridor_inputs.rated_pool(
        route(), inputs, {"generation": "fixture", "records": records}, ai=object(), cache=cache
    )
    assert len(candidates) == len(storage) == 12
    assert len(calls) == 3
    assert diagnostics["trait_cache"]["stored"] == 12
    assert all(
        row["provenance"]["ratings_provider"] == "fixture/fixture-model" for row in candidates
    )


async def test_missing_traits_fail_instead_of_dropping_a_geographic_match(monkeypatch):
    async def missing(*args, **kwargs):
        kwargs["diagnostics"].update(provider="fixture", model="fixture-model")
        return []

    monkeypatch.setattr(corridor_inputs, "_propose", missing)
    with pytest.raises(ValueError, match="Not all corridor places"):
        await corridor_inputs.rated_pool(
            route(),
            plan(Design())["cases"][0]["inputs"],
            {"generation": "fixture", "records": [place(1)]},
            ai=object(),
            cache=SimpleNamespace(get_many=lambda _: {}, put_many=lambda *_: {}),
        )


async def test_same_route_is_prepared_once_across_stop_counts_and_personas(tmp_path, monkeypatch):
    monkeypatch.setattr(preparation.store, "directory", lambda: tmp_path)
    study = {"id": "fixture-study"}
    (tmp_path / study["id"]).mkdir()
    monkeypatch.setattr(
        preparation, "routing_snapshot", lambda: {"generation": "fixture", "records": []}
    )
    base = plan(Design(trips=["short-1d"]))["cases"][0]
    first = deepcopy(base) | {"id": 1}
    second = deepcopy(base) | {"id": 2}
    first["inputs"]["persona_weights"] = dict.fromkeys(ATTRIBUTE_KEYS, 0) | {"nature": 1}
    second["inputs"].update(
        num_stops=3, persona_weights=dict.fromkeys(ATTRIBUTE_KEYS, 0) | {"history": 1}
    )
    ratings = dict.fromkeys(ATTRIBUTE_KEYS, 0.1) | {"nature": 0.9}
    source = {
        "runtime_seconds": 3,
        "error": None,
        "explanation": {"candidates": [place(1) | {"attribute_ratings": ratings}]},
    }
    collected = AsyncMock(return_value=source)
    monkeypatch.setattr(preparation, "collect_inputs", collected)
    a = await preparation.inputs(first, study)
    b = await preparation.inputs(second, study)
    collected.assert_awaited_once()
    assert a["explanation"]["candidates"][0]["utility"] == 0.9
    assert b["explanation"]["candidates"][0]["utility"] == 0.1
    assert a["preparation"]["hash"] == b["preparation"]["hash"]
    assert b["preparation"]["reused"] and b["runtime_seconds"] == 0
    assert b["input_snapshot"]["num_stops"] == 3
    next((tmp_path / study["id"]).glob("route-*.json")).unlink()
    with pytest.raises(ValueError, match="live calls were not repeated"):
        await preparation.inputs(second, study)
    collected.assert_awaited_once()
