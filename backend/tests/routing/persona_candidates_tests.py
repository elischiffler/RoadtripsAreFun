import json
from datetime import date

import pytest

from app.agent.persona import ATTRIBUTE_KEYS, default_weights
from app.agent.progress import reporting
from app.agent.schemas import LLMResponse
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
                provider_id="terra:7", name="Real Museum", coordinates=[40, -74], address="7 Main"
            ),
            source.VerifiedPlace(provider_id="terra:8", name="Bad Ratings", coordinates=[40, -74]),
        ]
    )
    result = await source.attraction_candidates(
        object(), [[40, -74]], default_weights(), ai=FakeAI(proposals), places=places
    )
    assert len(result) == 1
    assert result[0]["provider_id"] == "terra:7"
    assert result[0]["coordinates"] == [40, -74]
    assert result[0]["utility"] == pytest.approx(0.7)
    assert result[0]["address"] == "7 Main"


@pytest.mark.asyncio
async def test_attractions_reject_distant_malformed_and_cap_output():
    class IndexedPlaces(FakePlaces):
        async def attractions_near(self, point):
            self.calls += 1
            return [
                {"provider_id": f"terra:{self.calls}", "name": "Park", "coordinates": point},
                {"provider_id": "bad", "name": "Park", "coordinates": [999, 0]},
            ]

    ai = FakeAI([{"name": "Park", "attribute_ratings": _ratings()}])
    places = IndexedPlaces()
    result = await source.attraction_candidates(
        None, [[40, -74]] * 30, default_weights(), ai=ai, places=places
    )
    assert len(result) == 30
    assert ai.calls == 30 and places.calls == 30
    with pytest.raises(ValueError, match="at most 30"):
        await source.attraction_candidates(None, [[40, -74]] * 31, default_weights(), ai=ai)

    distant = FakePlaces(
        attractions=[
            source.VerifiedPlace(provider_id="terra:9", name="Park", coordinates=[41, -74])
        ]
    )
    assert not await source.attraction_candidates(
        None, [[40, -74]], default_weights(), ai=ai, places=distant
    )


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
        await source.attraction_candidates(
            None,
            [[40, -74]],
            default_weights(),
            ai=BrokenAI([]),
            places=FakePlaces(
                attractions=[
                    source.VerifiedPlace(
                        provider_id="terra:verified", name="Real Museum", coordinates=[40, -74]
                    )
                ]
            ),
        )

    class BrokenPlaces(FakePlaces):
        async def attractions_near(self, _point):
            raise source.CandidateProviderError("Terra unavailable")

    with pytest.raises(source.CandidateProviderError, match="Terra unavailable"):
        await source.attraction_candidates(
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
            assert "provider-verified names" in messages[-1].content
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
            source.VerifiedPlace(provider_id="terra:7", name="Real Museum", coordinates=[40, -74]),
        ]
    )
    with reporting(events.append):
        result = await source.attraction_candidates(
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
    assert searches[-1]["collected"] == 1
    assert searches[-1]["query"] == searches[-1]["queries"] == 2
    assert events.index(collected[0]) < events.index(searches[1])


@pytest.mark.asyncio
async def test_attraction_ratings_are_grounded_in_nearby_provider_names():
    class GroundedAI(FakeAI):
        def complete(self, messages, tools):
            assert "Rate only these provider-verified names" in messages[-1].content
            assert "Real Museum" in messages[-1].content
            assert "Distant attraction" not in messages[-1].content
            return super().complete(messages, tools)

    records = [
        source.VerifiedPlace(provider_id="terra:near", name="Real Museum", coordinates=[40, -74]),
        source.VerifiedPlace(
            provider_id="terra:far", name="Distant attraction", coordinates=[50, -74]
        ),
    ]
    candidates = await source.attraction_candidates(
        None,
        [[40, -74]],
        default_weights(),
        ai=GroundedAI([{"name": "Real Museum", "attribute_ratings": _ratings()}]),
        places=FakePlaces(attractions=records),
    )
    assert [candidate["provider_id"] for candidate in candidates] == ["terra:near"]


@pytest.mark.asyncio
async def test_live_attractions_reject_hotel_and_restaurant_listings(monkeypatch):
    import httpx

    entries = [
        {
            "location": {
                "id": index,
                "names": [{"value": name, "primary": True}],
                "coordinates": {"latitude": 40, "longitude": -74},
                "urls": {
                    "tripadvisor": {"main": f"https://www.tripadvisor.com/{kind}-g1-d{index}"}
                },
            }
        }
        for index, (name, kind) in enumerate(
            [
                ("Museum", "Attraction_Review"),
                ("Hotel", "Hotel_Review"),
                ("Cafe", "Restaurant_Review"),
            ],
            start=1,
        )
    ]

    def respond(request):
        assert request.url.params["category"] == "ATTRACTION"
        return httpx.Response(200, json={"data": entries})

    client_type = httpx.AsyncClient
    monkeypatch.setattr(source.LivePlaceProvider, "require_attractions", lambda self: None)
    monkeypatch.setattr(source, "_auth_headers", lambda: {})
    monkeypatch.setattr(
        source.httpx,
        "AsyncClient",
        lambda **kwargs: client_type(transport=httpx.MockTransport(respond), **kwargs),
    )
    records = await source.LivePlaceProvider().attractions_near([40, -74])
    assert [record.name for record in records] == ["Museum"]
