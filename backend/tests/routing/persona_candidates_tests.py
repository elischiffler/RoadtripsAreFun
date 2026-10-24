import json
from datetime import date

import pytest

from app.agent.persona import ATTRIBUTE_KEYS, default_weights
from app.agent.progress import reporting
from app.agent.schemas import LLMResponse
from app.routing.discovery import DiscoveryPlan, SearchQuery
from app.routing.occupancy import HotelRoom
from app.routing.sources import persona_candidates as source


def _ratings(value=0.8):
    return {key: value for key in ATTRIBUTE_KEYS}


class FakeAI:
    name = "fake"

    def __init__(self, proposals):
        self.proposals = proposals
        self.calls = 0

    def complete(self, _messages, _tools):
        self.calls += 1
        return LLMResponse(content=json.dumps({"candidates": self.proposals}), provider="fake")


class FakePlaces:
    def __init__(self, attractions=None, hotels=None):
        self.attractions = attractions or []
        self.hotels = hotels or []
        self.calls = 0

    async def attractions_near(self, _point):
        self.calls += 1
        return self.attractions

    async def hotels_near(self, _point, _date, _range, room):
        self.calls += 1
        return self.hotels


async def discover(raw_route, points, weights, **kwargs):
    from tests.routing.conftest import build_route

    route = build_route(3600)
    lat, lon = points[0]
    coords = [[lon, lat], [lon + 0.05, lat]]
    route.geometry.coordinates = coords
    route.legs[0].steps[0].geometry.coordinates = coords
    queries = [SearchQuery(f"q{i}", 0, 0, point) for i, point in enumerate(points)]
    plan = DiscoveryPlan(1, 3600, 1, 18, len(points), len(points), 36, 54, queries)
    return (await source.attraction_candidates(route, plan, weights, **kwargs)).candidates


@pytest.mark.asyncio
async def test_attractions_verify_identity_coordinates_ratings_and_utility():
    proposals = [
        {"name": "Real Museum", "attribute_ratings": _ratings(0.7), "utility": 1},
        {"name": "Invented Place", "attribute_ratings": _ratings()},
        {"name": "Real Museum", "attribute_ratings": _ratings()},
        {"name": "Bad Ratings", "attribute_ratings": {"food": 1.2}},
    ]
    places = FakePlaces(
        attractions=[
            source.VerifiedPlace(
                provider_id="overture:7",
                name="Real Museum",
                coordinates=[40, -74],
                address="7 Main",
            ),
            source.VerifiedPlace(
                provider_id="overture:8", name="Bad Ratings", coordinates=[40, -74]
            ),
        ]
    )
    result = await discover(
        object(), [[40, -74]], default_weights(), ai=FakeAI(proposals), places=places
    )
    assert len(result) == 1
    assert result[0]["provider_id"] == "overture:7"
    assert result[0]["coordinates"] == [40, -74]
    assert result[0]["utility"] == pytest.approx(0.7)
    assert result[0]["address"] == "7 Main"


@pytest.mark.asyncio
async def test_attractions_reject_distant_malformed_and_cap_output():
    class IndexedPlaces(FakePlaces):
        async def attractions_near(self, point):
            self.calls += 1
            return [
                {"provider_id": f"overture:{self.calls}", "name": "Park", "coordinates": point},
                {"provider_id": "bad", "name": "Park", "coordinates": [999, 0]},
            ]

    ai = FakeAI([{"name": "Park", "attribute_ratings": _ratings()}])
    places = IndexedPlaces()
    result = await discover(None, [[40, -74]] * 30, default_weights(), ai=ai, places=places)
    assert len(result) == 3
    # Each rating batch also requests an optional duration estimate. This fake
    # returns only ratings, so duration validation falls back to two hours.
    assert ai.calls == 6 and places.calls == 3

    distant = FakePlaces(
        attractions=[
            source.VerifiedPlace(provider_id="overture:9", name="Park", coordinates=[41, -74])
        ]
    )
    assert not await discover(None, [[40, -74]], default_weights(), ai=ai, places=distant)


@pytest.mark.asyncio
async def test_hotel_requires_matching_identity_date_and_provider_price():
    ai = FakeAI([{"name": "Hotel One", "attribute_ratings": _ratings(0.6), "price": 1}])
    places = FakePlaces(
        hotels=[
            source.VerifiedHotel(
                provider_id="google:H1",
                name="Hotel One",
                coordinates=[40, -74],
                check_in_date=date(2026, 10, 1),
                price=225,
                room=HotelRoom(adults=2, child_ages=[]),
                price_scope="one_room_one_night_including_taxes_fees",
            ),
            source.VerifiedHotel(
                provider_id="google:H1",
                name="Hotel One",
                coordinates=[40, -74],
                check_in_date=date(2026, 10, 1),
                price=225,
                room=HotelRoom(adults=2, child_ages=[]),
                price_scope="one_room_one_night_including_taxes_fees",
            ),
        ]
    )
    result = await source.hotel_candidates(
        [40, -74],
        date(2026, 10, 1),
        ((100, 200), "100-200"),
        default_weights(),
        ai=ai,
        places=places,
        hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
    )
    assert len(result) == 1
    assert result[0]["type"] == "hotel"
    assert result[0]["price"] == 225  # verified offer; AI price is ignored
    assert result[0]["utility"] == pytest.approx(0.6)
    assert not await source.hotel_candidates(
        [40, -74],
        date(2026, 10, 2),
        ((100, 200), "100-200"),
        default_weights(),
        ai=ai,
        places=places,
        hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
    )


@pytest.mark.asyncio
async def test_hotel_output_cap_and_unconfigured_dated_provider(monkeypatch):
    proposals = [{"name": f"Hotel {index}", "attribute_ratings": _ratings()} for index in range(15)]
    hotels = [
        source.VerifiedHotel(
            provider_id=f"google:H{index}",
            name=f"Hotel {index}",
            coordinates=[40, -74],
            check_in_date=date(2026, 10, 1),
            price=100 + index,
            room=HotelRoom(adults=2, child_ages=[]),
            price_scope="one_room_one_night_including_taxes_fees",
        )
        for index in range(15)
    ]
    result = await source.hotel_candidates(
        [40, -74],
        date(2026, 10, 1),
        ((0, 200), "0-200"),
        default_weights(),
        ai=FakeAI(proposals),
        places=FakePlaces(hotels=hotels),
        hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
    )
    assert len(result) == source.MAX_HOTELS
    monkeypatch.setattr(source.config, "OPENCAGE_KEY", None)
    with pytest.raises(source.CandidateProviderError, match="location verification"):
        await source.hotel_candidates(
            [40, -74],
            date(2026, 10, 1),
            ((0, 200), "0-200"),
            default_weights(),
            ai=FakeAI(proposals),
            hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
        )


@pytest.mark.asyncio
async def test_unavailable_providers_fail_clearly():
    class BrokenAI(FakeAI):
        def complete(self, *_):
            raise RuntimeError("offline")

    with pytest.raises(source.CandidateProviderError, match="AI candidate"):
        await discover(
            None,
            [[40, -74]],
            default_weights(),
            ai=BrokenAI([]),
            places=FakePlaces(
                attractions=[
                    source.VerifiedPlace(
                        provider_id="overture:verified", name="Real Museum", coordinates=[40, -74]
                    )
                ]
            ),
        )

    class BrokenPlaces(FakePlaces):
        async def attractions_near(self, _point):
            raise source.CandidateProviderError("Catalog unavailable")

    with pytest.raises(source.CandidateProviderError, match="Catalog unavailable"):
        await discover(
            None,
            [[40, -74]],
            default_weights(),
            ai=FakeAI([{"name": "Park", "attribute_ratings": _ratings()}]),
            places=BrokenPlaces(),
        )


@pytest.mark.asyncio
async def test_google_adapter_supplies_verified_names_prices_and_links(monkeypatch):
    from app.routing.sources.google_hotels import GoogleHotelLookupError, GoogleHotelProvider

    monkeypatch.setattr(source.config, "OPENCAGE_KEY", "fixture")

    async def fetched(self, point, check_in, room):
        return [
            {
                "provider_id": "google:H1",
                "name": "Hotel One",
                "coordinates": point,
                "room": {"adults": 2, "child_ages": []},
                "price_scope": "one_room_one_night_including_taxes_fees",
                "check_in_date": check_in,
                "price": 120,
                "url": "https://www.google.com/travel/hotels/entity/H1?dated=fixture",
            }
        ]

    monkeypatch.setattr(GoogleHotelProvider, "hotels_near", fetched)

    class RatingAI(FakeAI):
        def complete(self, messages, tools):
            assert "source-record names" in messages[-1].content
            assert '["Hotel One"]' in messages[-1].content
            return super().complete(messages, tools)

    ai = RatingAI([{"name": "Hotel One", "attribute_ratings": _ratings(), "price": 1}])
    result = await source.hotel_candidates(
        [40, -74],
        date(2026, 11, 20),
        ((50, 150), "USD"),
        default_weights(),
        ai=ai,
        hotel_rooms=[HotelRoom(adults=2, child_ages=[])],
    )
    assert result[0]["price"] == 120
    assert result[0]["url"].startswith("https://www.google.com/travel/hotels/entity/H1")

    async def failed(self, point, check_in, room):
        raise GoogleHotelLookupError("Google Hotels did not confirm USD prices.")

    monkeypatch.setattr(GoogleHotelProvider, "hotels_near", failed)
    with pytest.raises(source.CandidateProviderError, match="USD prices"):
        await source.LivePlaceProvider().hotels_near(
            [40, -74], date(2026, 11, 20), ((50, 150), "USD"), HotelRoom(adults=2, child_ages=[])
        )


async def test_collection_progress_only_reports_verified_unique_matches():
    events = []
    ai = FakeAI(
        [
            {"name": "Real Museum", "attribute_ratings": _ratings()},
            {"name": "Invented Place", "attribute_ratings": _ratings()},
        ]
    )
    places = FakePlaces(
        attractions=[
            source.VerifiedPlace(
                provider_id="overture:7", name="Real Museum", coordinates=[40, -74]
            ),
        ]
    )
    with reporting(events.append):
        result = await discover(
            {},
            [[40, -74], [40, -74]],
            default_weights(),
            ai=ai,
            places=places,
        )
    collected = [event for event in events if event["stage"] == "attractions.collected"]
    assert len(result) == len(collected) == 1
    assert collected[0]["name"] == "Real Museum"
    assert collected[0]["collected"] == 1
    searches = [event for event in events if event["stage"] == "attractions.query"]
    assert sum(event["state"] == "started" for event in searches) == 2
    assert all("section" in event for event in searches)
    assert any(event["stage"] == "attractions.round" for event in events)


@pytest.mark.asyncio
async def test_attraction_ratings_are_grounded_in_nearby_provider_names():
    class GroundedAI(FakeAI):
        def complete(self, messages, tools):
            assert "Rate only these source-record names" in messages[-1].content
            assert "Real Museum" in messages[-1].content
            assert "Distant attraction" not in messages[-1].content
            return super().complete(messages, tools)

    records = [
        source.VerifiedPlace(
            provider_id="overture:near", name="Real Museum", coordinates=[40, -74]
        ),
        source.VerifiedPlace(
            provider_id="overture:far", name="Distant attraction", coordinates=[50, -74]
        ),
    ]
    candidates = await discover(
        None,
        [[40, -74]],
        default_weights(),
        ai=GroundedAI([{"name": "Real Museum", "attribute_ratings": _ratings()}]),
        places=FakePlaces(attractions=records),
    )
    assert [candidate["provider_id"] for candidate in candidates] == ["overture:near"]


@pytest.mark.asyncio
async def test_catalog_daytime_filters_bounds_and_preserves_attribution(monkeypatch):
    def nearby(point, categories, **kwargs):
        assert point == [40, -74] and categories == ["daytime"]
        assert kwargs == {"radius_miles": 5.0, "limit": 60}
        return [
            {
                "provider_id": "overture:1",
                "name": "Museum",
                "coordinates": [40, -74],
                "categories": ["daytime", "culture"],
                "source": "overture",
                "source_release": "2026-09-23.1",
                "source_attribution": "Overture contributors",
            },
            {
                "provider_id": "overture:2",
                "name": "Hotel",
                "coordinates": [40, -74],
                "categories": ["hotel"],
            },
            {
                "provider_id": "overture:3",
                "name": "Far",
                "coordinates": [45, -74],
                "categories": ["daytime"],
            },
        ]

    monkeypatch.setattr(source.repository, "nearby", nearby)
    records = await source.LivePlaceProvider().attractions_near([40, -74])
    assert [record.name for record in records] == ["Museum"]
    candidate = source._candidate(
        records[0],
        source.ProposedPlace(name="Museum", attribute_ratings=_ratings()),
        default_weights(),
    )
    assert candidate["source_release"] == "2026-09-23.1"
    assert candidate["source_attribution"] == "Overture contributors"
    assert candidate["provenance"]["verified_at"] is None


@pytest.mark.asyncio
async def test_catalog_error_does_not_leak_database_credentials(monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("postgresql://secret:password@private")

    monkeypatch.setattr(source.repository, "nearby", fail)
    with pytest.raises(source.CandidateProviderError, match="catalog lookup unavailable") as raised:
        await source.LivePlaceProvider().attractions_near([40, -74])
    assert raised.value.__suppress_context__
    assert "password" not in str(raised.value)


class MemoryTraitStore:
    def __init__(self):
        self.entries = {}
        self.saved = []

    def get_many(self, places):
        return {
            p.provider_id: self.entries[source.trait_cache.key(p)]
            for p in places
            if source.trait_cache.key(p) in self.entries
        }

    def put_many(self, entries, provider):
        self.saved.extend(p.provider_id for p, _ in entries)
        for place, ratings in entries:
            self.entries.setdefault(
                source.trait_cache.key(place),
                {
                    "attribute_ratings": ratings,
                    "provider": provider,
                    "rating_version": source.trait_cache.VERSION,
                    "rated_at": "2026-10-20T00:00:00+00:00",
                },
            )
        return self.get_many([p for p, _ in entries])


async def unchanged_duration(candidates, weights, ai):
    return candidates


@pytest.mark.asyncio
async def test_place_traits_are_reused_across_runs_but_utility_follows_each_persona():
    place = source.VerifiedPlace(provider_id="overture:cached", name="Park", coordinates=[40, -74])
    traits = _ratings(0.3) | {"nature": 0.9, "nightlife": 0.1}
    ai = FakeAI([{"name": "Park", "attribute_ratings": traits}])
    cache = MemoryTraitStore()
    nature = dict.fromkeys(ATTRIBUTE_KEYS, 0.0) | {"nature": 1.0}
    nightlife = dict.fromkeys(ATTRIBUTE_KEYS, 0.0) | {"nightlife": 1.0}
    first = await discover(
        object(),
        [[40, -74]],
        nature,
        ai=ai,
        places=FakePlaces([place]),
        trait_store=cache,
        duration_estimator=unchanged_duration,
    )
    second = await discover(
        object(),
        [[40, -74]],
        nightlife,
        ai=ai,
        places=FakePlaces([place]),
        trait_store=cache,
        duration_estimator=unchanged_duration,
    )
    assert ai.calls == 1 and cache.saved == [place.provider_id]
    assert first[0]["attribute_ratings"] == second[0]["attribute_ratings"] == traits
    assert first[0]["utility"] == 0.9 and second[0]["utility"] == 0.1
    assert second[0]["provenance"]["ratings_cache"] == "hit"
    assert second[0]["provenance"]["ratings_created_at"] == "2026-10-20T00:00:00+00:00"
    assert not any("utility" in entry for entry in cache.entries.values())


@pytest.mark.asyncio
async def test_only_missing_place_traits_are_sent_to_ai_and_source_facts_are_supplied():
    cached = source.VerifiedPlace(
        provider_id="overture:cached", name="Cached Park", coordinates=[40, -74]
    )
    missing = source.VerifiedPlace(
        provider_id="overture:new", name="New Park", coordinates=[40, -74]
    )
    cache = MemoryTraitStore()
    cache.put_many([(cached, _ratings(0.4))], "earlier")

    class MissAI(FakeAI):
        def complete(self, messages, tools):
            prompt = messages[-1].content
            assert json.loads(prompt.split("exactly: ")[1]) == ["New Park"]
            assert (
                "overture:new" in prompt and "independently of any traveler's preferences" in prompt
            )
            assert "Cached Park" not in prompt
            assert "Walking between shops or stalls is not hiking" in prompt
            assert "a farmers market is not the surrounding beach" in prompt
            return super().complete(messages, tools)

    ai = MissAI([{"name": "New Park", "attribute_ratings": _ratings(0.8)}])
    result = await discover(
        object(),
        [[40, -74]],
        default_weights(),
        ai=ai,
        places=FakePlaces([cached, missing]),
        trait_store=cache,
        duration_estimator=unchanged_duration,
    )
    assert ai.calls == 1 and len(result) == 2
    assert {p["provider_id"] for p in result} == {cached.provider_id, missing.provider_id}


@pytest.mark.asyncio
async def test_same_name_places_are_rated_separately_and_bad_ai_data_is_not_cached():
    places = [
        source.VerifiedPlace(provider_id=f"overture:{i}", name="Park", coordinates=[40, -74])
        for i in range(2)
    ]
    cache = MemoryTraitStore()

    class SeparateAI(FakeAI):
        def complete(self, messages, tools):
            assert len(json.loads(messages[-1].content.split("exactly: ")[1])) == 1
            self.proposals = [
                {"name": "Park", "attribute_ratings": _ratings(0.2 if self.calls == 0 else 0.8)}
            ]
            return super().complete(messages, tools)

    ai = SeparateAI([])
    result = await discover(
        object(),
        [[40, -74]],
        default_weights(),
        ai=ai,
        places=FakePlaces(places),
        trait_store=cache,
        duration_estimator=unchanged_duration,
    )
    assert ai.calls == 2
    assert {p["provider_id"]: p["attribute_ratings"]["nature"] for p in result} == {
        "overture:0": 0.2,
        "overture:1": 0.8,
    }
    cache = MemoryTraitStore()
    with pytest.raises(source.CandidateRatingError):
        await discover(
            object(),
            [[40, -74]],
            default_weights(),
            ai=FakeAI([{"name": "Invented Park", "attribute_ratings": _ratings()}]),
            places=FakePlaces(places[:1]),
            trait_store=cache,
            duration_estimator=unchanged_duration,
        )
    assert not cache.saved


@pytest.mark.asyncio
async def test_enabled_live_provider_automatically_uses_database_trait_store(monkeypatch):
    place = source.VerifiedPlace(
        provider_id="overture:auto", name="Saved Park", coordinates=[40, -74]
    )
    memory = MemoryTraitStore()
    memory.put_many([(place, _ratings(0.6))], "fixture:earlier")

    class LocalLive(source.LivePlaceProvider):
        async def attractions_near(self, point, **kwargs):
            return [place]

    monkeypatch.setattr(source, "LivePlaceProvider", LocalLive)
    monkeypatch.setenv("PLACE_TRAITS_CACHE_ENABLED", "true")
    monkeypatch.setattr(source.trait_cache, "get_many", memory.get_many)
    monkeypatch.setattr(source.trait_cache, "put_many", memory.put_many)
    ai = FakeAI([])
    result = await discover(
        object(), [[40, -74]], default_weights(), ai=ai, duration_estimator=unchanged_duration
    )
    assert ai.calls == 0 and result[0]["provenance"]["ratings_cache"] == "hit"
