"""Authentic CC0 place facts with controlled AI vectors and corridor timing.

This is an offline eligibility regression, not a live road or model observation.
"""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agent.persona import ATTRIBUTE_KEYS, default_weights
from app.agent.schemas import LLMResponse
from app.routing.cp_sat_selection import select_attractions
from app.routing.discovery import make_discovery_plan
from app.routing.explanation import capture_explanation
from app.routing.sources import persona_candidates as source


class RatingAI:
    def __init__(self, vector, *, responses=None, wrong_name=False):
        self.vector, self.responses, self.wrong_name = vector, responses, wrong_name
        self.calls = 0

    def complete(self, messages, tools):
        index = self.calls
        self.calls += 1
        if self.responses is not None:
            return LLMResponse(content=self.responses[min(index, len(self.responses) - 1)])
        marker = "Rate only these source-record names, preserving each exactly: "
        names = json.loads(messages[-1].content.split(marker, 1)[1])
        return LLMResponse(
            content=json.dumps(
                {
                    "candidates": [
                        {
                            "name": "Unmatched name" if self.wrong_name else name,
                            "attribute_ratings": self.vector,
                        }
                        for name in names
                    ]
                }
            )
        )


class Places:
    def __init__(self, places):
        self.places = places

    async def attractions_near(self, point):
        return [p for p in self.places if source._distance_miles(point, p["coordinates"]) <= 5]


@pytest.fixture
def boulder():
    fixture = json.loads(
        (Path(__file__).parents[1] / "fixtures/catalog/boulder-reviewed-12.json").read_text()
    )
    assert (
        fixture["source_archive_sha256"]
        == "5dfb978b50c8d238eda2362dcd99b1a1b2328bbe2fc8827803fdc99bb48ff5c4"
    )
    places = fixture["places"]
    assert len(places) == 12 and all(p["provider_id"].startswith("boulder:") for p in places)
    south = min(places, key=lambda p: p["coordinates"][0])["coordinates"]
    north = max(places, key=lambda p: p["coordinates"][0])["coordinates"]
    route = SimpleNamespace(
        duration=3600.0,
        distance=15000.0,
        legs=[],
        geometry=SimpleNamespace(coordinates=[[south[1], south[0]], [north[1], north[0]]]),
    )
    return places, route, make_discovery_plan(route, 2)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "vector",
    [
        dict.fromkeys(ATTRIBUTE_KEYS, 0.5),
        dict(
            zip(
                ATTRIBUTE_KEYS, [0.9, 0.95, 0.95, 0.1, 0.3, 0.2, 0, 0, 0.3, 0.7, 0.7, 0.7, 0.8, 0.6]
            )
        ),
    ],
)
async def test_authentic_boulder_positive_matches_survive_discovery_and_selection(boulder, vector):
    places, route, plan = boulder
    found = await source.attraction_candidates(
        route, plan, default_weights(), ai=RatingAI(vector), places=Places(places)
    )
    assert found.explanation["raw_pool_count"] == 12
    assert len(found.candidates) == 12
    original = {p["provider_id"]: p for p in places}
    expected_utility = sum(vector.values()) / len(ATTRIBUTE_KEYS)
    for candidate in found.candidates:
        assert candidate["utility"] == pytest.approx(expected_utility)
        assert candidate["attribute_ratings"] == vector
        for key in ("name", "coordinates", "source_attribution", "source_provenance"):
            assert candidate[key] == original[candidate["provider_id"]][key]
    road_checked = [{**candidate, "detour_seconds": 0.0} for candidate in found.candidates]
    with capture_explanation() as explanation:
        selected = select_attractions(
            road_checked, [q.coordinates for q in plan.queries], 2, route.duration
        )
    assert len(selected) == 2
    assert explanation["solver"]["eligibility_policy"] == "positive_utility"
    assert explanation["solver"]["utility_threshold_inclusive"] is False
    assert found.explanation["outcome"] == "eligible_candidates"


@pytest.mark.asyncio
async def test_complete_zero_matches_are_distinct_from_missing_catalog_or_invalid_ratings(boulder):
    places, route, plan = boulder
    found = await source.attraction_candidates(
        route,
        plan,
        default_weights(),
        ai=RatingAI(dict.fromkeys(ATTRIBUTE_KEYS, 0)),
        places=Places(places),
    )
    assert found.candidates == []
    assert found.explanation["successful_ratings"] == 12
    assert found.explanation["outcome"] == "no_positive_utility"
    assert all(a["attempt"] == 1 for a in found.explanation["rating_attempts"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind", ["partial", "out_of_range", "boolean", "wrong_name", "json", "empty"]
)
async def test_unusable_ratings_have_bounded_repair_and_explicit_failure(boulder, kind):
    places, route, plan = boulder
    place = places[0]
    vector = dict.fromkeys(ATTRIBUTE_KEYS, 0.5)
    responses = None
    if kind == "partial":
        vector = {"nature": 0.9}
    if kind == "out_of_range":
        vector["nature"] = 1.1
    if kind == "boolean":
        vector["nature"] = True
    if kind == "json":
        responses = ["invalid private-response"]
    if kind == "empty":
        responses = ['{"candidates": []}']
    ai = RatingAI(vector, responses=responses, wrong_name=kind == "wrong_name")
    with capture_explanation() as explanation:
        with pytest.raises(source.CandidateRatingError) as error:
            await source.attraction_candidates(
                route, plan, default_weights(), ai=ai, places=Places([place])
            )
    discovery = explanation["discovery"]
    assert ai.calls == 2
    assert discovery["outcome"] == "invalid_ratings"
    assert discovery["raw_pool_count"] == 1
    assert discovery["successful_ratings"] == 0
    assert len(discovery["rating_attempts"]) == 2
    assert error.value.provider_code == "INVALID_ATTRIBUTE_RATINGS"
    assert "private-response" not in str(error.value)
    if kind == "partial":
        assert discovery["rating_attempts"][0]["incomplete_vectors"] == 1
    if kind == "wrong_name":
        assert discovery["rating_attempts"][0]["match_status"] == "name_mismatch"


@pytest.mark.asyncio
async def test_one_format_repair_can_recover_without_changing_source_facts(boulder):
    places, route, plan = boulder
    place = places[0]
    valid = json.dumps(
        {
            "candidates": [
                {"name": place["name"], "attribute_ratings": dict.fromkeys(ATTRIBUTE_KEYS, 0.5)}
            ]
        }
    )
    ai = RatingAI(None, responses=["not JSON", valid])
    found = await source.attraction_candidates(
        route, plan, default_weights(), ai=ai, places=Places([place])
    )
    assert ai.calls == 2 and len(found.candidates) == 1
    assert found.candidates[0]["coordinates"] == place["coordinates"]
    assert [a["status"] for a in found.explanation["rating_attempts"]] == ["invalid_json", "valid"]


@pytest.mark.asyncio
async def test_absent_catalog_coverage_does_not_request_ai_place_facts(boulder):
    _, route, plan = boulder
    ai = RatingAI(None, responses=["invalid"])
    found = await source.attraction_candidates(
        route, plan, default_weights(), ai=ai, places=Places([])
    )
    assert ai.calls == 0 and found.candidates == []
    assert found.explanation["outcome"] == "no_catalog_candidates"
    assert found.explanation["rating_attempts"] == []
