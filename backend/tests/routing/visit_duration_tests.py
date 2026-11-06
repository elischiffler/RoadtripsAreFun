import copy
import json
from types import SimpleNamespace

import pytest

from app.routing.base import PlanningError
from app.routing.runtime import run_context
from app.routing.sources.visit_durations import DurationCache, _parse, estimate_durations
from app.routing.visit_duration import VisitDuration, fallback_duration, visit_seconds


def candidate(identifier="fixture:museum", **fields):
    return {
        "provider_id": identifier,
        "name": "Synthetic history museum",
        "address": "Fixture address",
        "categories": ["daytime", "culture"],
        "activities": ["exhibits"],
        "utility": 0.7,
        "attribute_ratings": {"culture": 0.9},
        "contributions": [
            {"attribute": "culture", "weight": 1, "rating": 0.7, "contribution": 0.7}
        ],
        **fields,
    }


class AI:
    name = "offline-duration-control"

    def __init__(self, content=None, *, fail=False):
        self.content = content
        self.fail = fail
        self.prompts = []

    def complete(self, messages, tools):
        self.prompts.append(messages[-1].content)
        if self.fail:
            raise RuntimeError("synthetic outage")
        return SimpleNamespace(content=self.content)


@pytest.mark.parametrize(
    "minutes", [None, True, "90", 14, 361, 0, -1, 1e99, float("nan"), float("inf"), 90.5]
)
def test_output_bounds_reject_invalid_minutes(minutes):
    assert (
        _parse(json.dumps({"estimates": [{"provider_id": "p", "minutes": minutes}]}), {"p"}) == {}
    )


def test_round_up_boundaries_duplicates_unknown_ids_and_bounded_response():
    def parse(rows):
        return _parse(json.dumps({"estimates": rows}), {"p", "q"})

    assert parse([{"provider_id": "p", "minutes": 15}])["p"].seconds == 900
    assert parse([{"provider_id": "p", "minutes": 16}])["p"].seconds == 1200
    assert parse([{"provider_id": "p", "minutes": 360}])["p"].seconds == 21600
    assert parse([{"provider_id": "x", "minutes": 30}]) == {}
    assert parse([{"provider_id": "p", "minutes": 30}] * 2) == {}
    assert _parse(" " * 20000, {"p"}) == {}
    assert _parse('```json\n{"estimates":[]}\n```', {"p"}) == {}


@pytest.mark.asyncio
async def test_estimates_use_place_activity_preferences_and_match_context_without_mutation():
    place = candidate()
    original = copy.deepcopy(place)
    ai = AI(json.dumps({"estimates": [{"provider_id": place["provider_id"], "minutes": 91}]}))
    result = await estimate_durations([place], {"culture": 1.0}, ai, cache=DurationCache())
    assert result[0]["visit_duration"]["seconds"] == 5700
    assert result[0]["visit_duration"]["source"] == "ai_estimate"
    prompt = ai.prompts[0]
    for expected in [
        place["name"],
        "exhibits",
        "traveler_preferences",
        "utility_context",
        "contributions",
        "MUST NOT alone",
    ]:
        assert expected in prompt
    assert place == original


@pytest.mark.asyncio
@pytest.mark.parametrize("fail,reason", [(False, "invalid_output"), (True, "provider_failure")])
async def test_optional_failure_is_cached_with_conservative_fallback(fail, reason):
    now = [0]
    cache = DurationCache(clock=lambda: now[0])
    ai = AI("invalid", fail=fail)
    place = candidate()
    first = await estimate_durations([place], {}, ai, cache=cache)
    second = await estimate_durations([place], {}, ai, cache=cache)
    assert first == second
    assert first[0]["visit_duration"] == fallback_duration(reason).model_dump()
    assert len(ai.prompts) == 1
    now[0] = 301
    await estimate_durations([place], {}, ai, cache=cache)
    assert len(ai.prompts) == 2


@pytest.mark.asyncio
async def test_cache_separates_preferences_place_details_and_utility_and_expires():
    now = [0]
    cache = DurationCache(clock=lambda: now[0])
    ai = AI('{"estimates":[{"provider_id":"fixture:museum","minutes":60}]}')
    place = candidate()
    first = await estimate_durations([place], {"culture": 1}, ai, cache=cache)
    await estimate_durations([place], {"culture": 1}, ai, cache=cache)
    assert len(ai.prompts) == 1
    first[0]["visit_duration"]["seconds"] = 900
    assert (await estimate_durations([place], {"culture": 1}, ai, cache=cache))[0][
        "visit_duration"
    ]["seconds"] == 3600
    for changed, weights in [
        (place, {"nature": 1}),
        ({**place, "activities": ["walk"]}, {"culture": 1}),
        ({**place, "utility": 0.3}, {"culture": 1}),
    ]:
        await estimate_durations([changed], weights, ai, cache=cache)
    assert len(ai.prompts) == 4
    now[0] = 86401
    await estimate_durations([place], {"culture": 1}, ai, cache=cache)
    assert len(ai.prompts) == 5


def test_cache_capacity_and_legacy_trips_are_preserved():
    cache = DurationCache(capacity=1)
    value = fallback_duration("missing_estimate")
    cache.put("a", value)
    cache.put("b", value)
    assert cache.get("a") is None and cache.get("b") == value
    assert visit_seconds({"name": "Saved trip"}) == 7200
    assert visit_seconds({"visit_duration": value.model_dump()}) == 7200
    for value in [
        0,
        {},
        {"seconds": True},
        VisitDuration(seconds=900, source="ai_estimate", reason="estimated").model_dump()
        | {"seconds": 899},
    ]:
        with pytest.raises(PlanningError, match="Invalid visit duration"):
            visit_seconds({"visit_duration": value})


@pytest.mark.asyncio
async def test_request_singleflight_deduplicates_and_batch_limit():
    import asyncio

    ai = AI('{"estimates":[{"provider_id":"fixture:museum","minutes":60}]}')
    cache = DurationCache()
    async with run_context():
        first, second = await asyncio.gather(
            *[estimate_durations([candidate()], {}, ai, cache=cache) for _ in range(2)]
        )
    assert first == second and len(ai.prompts) == 1
    with pytest.raises(ValueError, match="five"):
        await estimate_durations([candidate()] * 6, {}, ai)
