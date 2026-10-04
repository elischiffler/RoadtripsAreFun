"""Request, returned controls, room quote aggregation and dated link agreement."""

from datetime import date

import httpx
import pytest

from app.agent.persona import default_weights
from app.routing.occupancy import HotelRoom
from app.routing.sources.google_hotels import GoogleHotelLookupError, stay_token
from app.routing.sources.persona_candidates import hotel_candidates
from tests.routing.google_hotels_tests import CARD, CHECK_IN, CONTROLS, DETAIL, provider
from tests.routing.persona_candidates_tests import FakeAI, _ratings


@pytest.mark.parametrize(
    "room",
    [
        HotelRoom(adults=1, child_ages=[]),
        HotelRoom(adults=2, child_ages=[]),
        HotelRoom(adults=3, child_ages=[]),
        HotelRoom(adults=2, child_ages=[5]),
        HotelRoom(adults=1, child_ages=[0, 17]),
    ],
)
async def test_search_detail_and_dated_link_use_same_adults_and_child_ages(room):
    controls = CONTROLS.replace('data-adults="2"', f'data-adults="{room.adults}"').replace(
        'data-children=""', 'data-children="' + ",".join(map(str, room.provider_child_ages)) + '"'
    )
    places, requests = provider(search=controls + CARD, detail=controls + DETAIL, room=room)
    records = await places.hotels_near([39.74, -104.99], CHECK_IN, room)
    assert records[0]["room"] == room.model_dump()
    assert len(requests) == 2
    assert {request.url.params["ts"] for request in requests} == {stay_token(CHECK_IN, room)}
    assert httpx.URL(records[0]["url"]).params["ts"] == stay_token(CHECK_IN, room)
    assert records[0]["price"] == 120


@pytest.mark.parametrize(
    "mismatch", ['data-adults="1" data-children="5"', 'data-adults="2" data-children="6"']
)
async def test_child_occupancy_mismatch_fails_closed_on_details(mismatch):
    room = HotelRoom(adults=2, child_ages=[5])
    controls = CONTROLS.replace('data-children=""', 'data-children="5"')
    detail = CONTROLS.replace('data-adults="2" data-children=""', mismatch) + DETAIL
    places, _ = provider(search=controls + CARD, detail=detail, room=room)
    with pytest.raises(GoogleHotelLookupError, match="child ages"):
        await places.hotels_near([39.74, -104.99], CHECK_IN, room)


def test_child_protobuf_matches_observed_google_age_band_encoding():
    import base64

    from app.routing.sources.google_hotels import _field

    room = HotelRoom(adults=5, child_ages=[12])
    token = stay_token(date(2026, 11, 2), room)
    raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    guests = _field(1, _field(1, 3)) * 5 + _field(1, _field(1, 2) + _field(2, 12)) + _field(2, 1)
    assert _field(2, guests) in raw
    assert stay_token(CHECK_IN, HotelRoom(adults=2, child_ages=[0])) == stay_token(
        CHECK_IN, HotelRoom(adults=2, child_ages=[1])
    )


class RoomPlaces:
    def __init__(self, *, mismatch=False, missing=False):
        self.calls = []
        self.mismatch = mismatch
        self.missing = missing

    async def hotels_near(self, point, check_in, price_range, room):
        self.calls.append(room)
        if self.missing and len(self.calls) == 2:
            return []
        return [
            {
                "provider_id": "google:example",
                "name": "Example Hotel",
                "coordinates": point,
                "check_in_date": check_in,
                "room": HotelRoom(adults=6, child_ages=[]).model_dump()
                if self.mismatch
                else room.model_dump(),
                "price_scope": "one_room_one_night_including_taxes_fees",
                "price": 120 if len(self.calls) == 1 else 175,
                "url": "https://www.google.com/travel/hotels/entity/example?ts="
                + stay_token(check_in, room),
            }
        ]


@pytest.mark.parametrize("identical", [False, True])
async def test_multi_room_prices_are_independent_verified_quotes_with_each_link(identical):
    rooms = [HotelRoom(adults=2, child_ages=[5]), HotelRoom(adults=1, child_ages=[])]
    if identical:
        rooms[1] = rooms[0]
    places = RoomPlaces()
    ai = FakeAI([{"name": "Example Hotel", "attribute_ratings": _ratings()}])
    records = await hotel_candidates(
        [40, -74], CHECK_IN, ((0, 200), "0-200"), default_weights(), rooms, ai=ai, places=places
    )
    assert len(places.calls) == 2
    hotel = records[0]
    assert hotel["price"] == 295  # Even identical allocations are separately requested.
    assert hotel["url"] is None
    assert hotel["price_scope"] == "independent_room_quotes_not_combined_inventory"
    assert hotel["hotel_rooms"] == [room.model_dump() for room in rooms]
    for room, offer in zip(rooms, hotel["room_offers"]):
        assert offer["room"] == room.model_dump()
        assert httpx.URL(offer["url"]).params["ts"] == stay_token(CHECK_IN, room)


@pytest.mark.parametrize("failure", ["mismatch", "missing"])
async def test_no_multi_room_quote_if_one_room_cannot_be_verified(failure):
    rooms = [HotelRoom(adults=2, child_ages=[]), HotelRoom(adults=1, child_ages=[7])]
    places = RoomPlaces(**{failure: True})
    result = await hotel_candidates(
        [40, -74],
        CHECK_IN,
        ((0, 200), "0-200"),
        default_weights(),
        rooms,
        ai=FakeAI([{"name": "Example Hotel", "attribute_ratings": _ratings()}]),
        places=places,
    )
    assert result == []


def test_budget_remains_per_room_even_when_aggregate_is_below_total_target():
    from app.routing.cp_sat_scheduler import _over_budget

    hotel = {"price": 190, "room_offers": [{"price": 150}, {"price": 40}]}
    assert _over_budget(hotel, 100, 2)
    assert not _over_budget(hotel, 150, 2)
