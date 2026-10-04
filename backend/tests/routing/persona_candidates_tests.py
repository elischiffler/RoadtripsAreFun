import json
from datetime import date

import httpx
import pytest

from app.agent.persona import ATTRIBUTE_KEYS, default_weights
from app.agent.schemas import LLMResponse
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

    async def hotels_near(self, _point, _date, _range):
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
                provider_id="amadeus:H1",
                name="Hotel One",
                coordinates=[40, -74],
                check_in_date=date(2026, 10, 1),
                price=225,
            ),
            source.VerifiedHotel(
                provider_id="amadeus:H1",
                name="Hotel One",
                coordinates=[40, -74],
                check_in_date=date(2026, 10, 1),
                price=225,
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
    )


@pytest.mark.asyncio
async def test_hotel_output_cap_and_unconfigured_dated_provider(monkeypatch):
    proposals = [{"name": f"Hotel {index}", "attribute_ratings": _ratings()} for index in range(15)]
    hotels = [
        source.VerifiedHotel(
            provider_id=f"amadeus:H{index}",
            name=f"Hotel {index}",
            coordinates=[40, -74],
            check_in_date=date(2026, 10, 1),
            price=100 + index,
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
    )
    assert len(result) == source.MAX_HOTELS
    monkeypatch.setattr(source.config, "HOTEL_PROVIDER", "amadeus")
    monkeypatch.setattr(source.config, "AMADEUS_ENABLED", False)
    with pytest.raises(source.CandidateProviderError, match="Dated Amadeus"):
        await source.hotel_candidates(
            [40, -74],
            date(2026, 10, 1),
            ((0, 200), "0-200"),
            default_weights(),
            ai=FakeAI(proposals),
        )


@pytest.mark.asyncio
async def test_unavailable_providers_fail_clearly():
    class BrokenAI(FakeAI):
        def complete(self, *_):
            raise RuntimeError("offline")

    with pytest.raises(source.CandidateProviderError, match="AI candidate"):
        await source.attraction_candidates(
            None, [[40, -74]], default_weights(), ai=BrokenAI([]), places=FakePlaces()
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
async def test_amadeus_price_is_dated_offer_only(monkeypatch):
    monkeypatch.setattr(source.config, "HOTEL_PROVIDER", "amadeus")
    monkeypatch.setattr(source.config, "AMADEUS_ENABLED", True)
    monkeypatch.setenv("AMADEUS_KEY", "test-key")
    monkeypatch.setenv("AMADEUS_SECRET", "test-secret")

    def respond(request):
        path = request.url.path
        if path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "fake"})
        if path.endswith("/by-geocode"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "hotelId": "H1",
                            "name": "Hotel One",
                            "geoCode": {"latitude": 40, "longitude": -74},
                        }
                    ]
                },
            )
        assert request.url.params["checkInDate"] == "2026-10-01"
        assert request.url.params["checkOutDate"] == "2026-10-02"
        assert request.url.params["currency"] == "USD"
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "hotel": {"hotelId": "H1"},
                        "offers": [
                            {
                                "checkInDate": "2026-10-02",
                                "checkOutDate": "2026-10-03",
                                "price": {"currency": "USD", "total": "1"},
                            },
                            {
                                "checkInDate": "2026-10-01",
                                "checkOutDate": "2026-10-02",
                                "price": {"currency": "EUR", "total": "2"},
                            },
                            {
                                "checkInDate": "2026-10-01",
                                "checkOutDate": "2026-10-02",
                                "price": {"currency": "USD", "total": "189.50"},
                            },
                        ],
                    }
                ]
            },
        )

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        source.httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    hotels = await source.LivePlaceProvider().hotels_near(
        [40, -74], date(2026, 10, 1), ((0, 200), "0-200")
    )
    assert len(hotels) == 1
    assert hotels[0].provider_id == "amadeus:H1"
    assert hotels[0].price == 189.5


@pytest.mark.asyncio
async def test_google_adapter_supplies_verified_names_prices_and_links(monkeypatch):
    from app.routing.sources.google_hotels import GoogleHotelLookupError, GoogleHotelProvider

    monkeypatch.setattr(source.config, "HOTEL_PROVIDER", "google")
    monkeypatch.setattr(source.config, "OPENCAGE_KEY", "fixture")

    async def fetched(self, point, check_in):
        return [
            {
                "provider_id": "google:H1",
                "name": "Hotel One",
                "coordinates": point,
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
        [40, -74], date(2026, 11, 20), ((50, 150), "USD"), default_weights(), ai=ai
    )
    assert result[0]["price"] == 120
    assert result[0]["url"].startswith("https://www.google.com/travel/hotels/entity/H1")

    async def failed(self, point, check_in):
        raise GoogleHotelLookupError("Google Hotels did not confirm USD prices.")

    monkeypatch.setattr(GoogleHotelProvider, "hotels_near", failed)
    with pytest.raises(source.CandidateProviderError, match="USD prices"):
        await source.LivePlaceProvider().hotels_near(
            [40, -74], date(2026, 11, 20), ((50, 150), "USD")
        )
