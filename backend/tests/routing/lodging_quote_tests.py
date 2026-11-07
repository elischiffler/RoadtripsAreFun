"""Full-stay provider dates/totals cannot alias legacy one-night requests."""

from datetime import date, timedelta

import httpx
import pytest
from pydantic import ValidationError

from app.agent.persona import default_weights
from app.routing.occupancy import HotelRoom
from app.routing.runtime import in_run
from app.routing.sources import google_hotels as source
from app.routing.sources import persona_candidates as candidates
from tests.routing.google_hotels_tests import CARD, CONTROLS, DETAIL, Geocoder
from tests.routing.persona_candidates_tests import FakeAI, FakePlaces, _ratings

FIRST = date(2030, 6, 1)
LAST = date(2030, 6, 3)
ROOM = HotelRoom(adults=2, child_ages=[])


def raw_offer(check_in=FIRST, check_out=LAST, room=ROOM, price=201.37):
    nights = (check_out - check_in).days
    return {
        "provider_id": "google:ExampleID",
        "name": "Example Hotel",
        "coordinates": [39.74, -104.99],
        "url": f"https://hotel.example/?in={check_in}&out={check_out}",
        "room": room.model_dump(),
        "price": price,
        "check_in_date": check_in,
        "check_out_date": check_out,
        "price_scope": "one_room_one_night_including_taxes_fees"
        if nights == 1
        else "one_room_stay_including_taxes_fees",
    }


def source_provider(*, wrong_date=False, wrong_nights=False):
    controls = CONTROLS.replace("2026-11-20", FIRST.isoformat()).replace(
        "2026-11-21", (LAST - timedelta(days=1) if wrong_date else LAST).isoformat()
    )
    card = CARD.replace("$120 total", "$201.37 total").replace(
        "1 night with taxes + fees",
        "1 night with taxes + fees" if wrong_nights else "2 nights with taxes + fees",
    )
    requests = []

    def fetch(request):
        requests.append(request)
        assert request.url.params["ts"] == source.stay_token(FIRST, ROOM, LAST)
        return httpx.Response(
            200,
            text=controls + (card if request.url.path == "/travel/search" else DETAIL),
            headers={"content-type": "text/html"},
        )

    return source.GoogleHotelProvider(Geocoder(), transport=httpx.MockTransport(fetch)), requests


@pytest.mark.asyncio
async def test_real_html_adapter_requires_exact_range_and_reads_full_stay_total_once():
    provider, requests = source_provider()
    rows = await provider.hotels_near([39.74, -104.99], FIRST, ROOM, check_out_date=LAST)
    assert len(rows) == 1 and rows[0]["price"] == 201.37
    assert rows[0]["check_in_date"] == FIRST and rows[0]["check_out_date"] == LAST
    assert rows[0]["price_scope"] == "one_room_stay_including_taxes_fees"
    assert httpx.URL(rows[0]["url"]).params["ts"] == source.stay_token(FIRST, ROOM, LAST)
    assert len(requests) == 2
    assert source.stay_token(FIRST, ROOM) != source.stay_token(FIRST, ROOM, LAST)


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["dates", "nights"])
async def test_html_never_relabels_one_night_dates_or_total_as_two_nights(defect):
    provider, _ = source_provider(wrong_date=defect == "dates", wrong_nights=defect == "nights")
    with pytest.raises(source.GoogleHotelLookupError):
        await provider.hotels_near([39.74, -104.99], FIRST, ROOM, check_out_date=LAST)


def test_verified_scope_rejects_single_night_scope_for_multi_night_dates():
    offer = raw_offer()
    offer["price_scope"] = "one_room_one_night_including_taxes_fees"
    with pytest.raises(ValidationError):
        candidates.VerifiedHotel.model_validate(offer)


@pytest.mark.asyncio
async def test_default_one_night_request_rejects_explicit_two_night_record():
    ai = FakeAI([{"name": "Example Hotel", "attribute_ratings": _ratings()}])
    result = await candidates.hotel_candidates(
        [39.74, -104.99],
        FIRST,
        ((0, 200), "0-200"),
        default_weights(),
        [ROOM],
        ai=ai,
        places=FakePlaces(hotels=[raw_offer()]),
    )
    assert result == []


@pytest.mark.asyncio
async def test_room_intersection_requires_every_room_same_range_and_full_total():
    rooms = [ROOM, HotelRoom(adults=1, child_ages=[7])]

    class Places:
        async def hotels_near(self, point, check_in, price_range, room, *, check_out_date=None):
            return [
                raw_offer(check_in, check_out_date, room, 201.37 if room.adults == 2 else 149.53)
            ]

    ai = FakeAI([{"name": "Example Hotel", "attribute_ratings": _ratings()}])
    result = await candidates.hotel_candidates(
        [39.74, -104.99],
        FIRST,
        ((0, 400), "0-400"),
        default_weights(),
        rooms,
        check_out_date=LAST,
        ai=ai,
        places=Places(),
    )
    assert len(result) == 1 and result[0]["price"] == pytest.approx(350.90)
    assert result[0]["price_scope"] == "independent_room_quotes_not_combined_inventory"
    assert all(
        o["check_out_date"] == LAST.isoformat() and o["check_in_date"] == FIRST.isoformat()
        for o in result[0]["room_offers"]
    )
    assert [o["room"] for o in result[0]["room_offers"]] == [r.model_dump() for r in rooms]

    class Wrong(Places):
        async def hotels_near(self, point, check_in, price_range, room, *, check_out_date=None):
            return [
                raw_offer(
                    check_in,
                    check_out_date if room.adults == 2 else check_out_date - timedelta(days=1),
                    room,
                )
            ]

    assert (
        await candidates.hotel_candidates(
            [39.74, -104.99],
            FIRST,
            ((0, 400), "0-400"),
            default_weights(),
            rooms,
            check_out_date=LAST,
            ai=ai,
            places=Wrong(),
        )
        == []
    )


@pytest.mark.asyncio
async def test_checkout_is_in_room_cache_key_within_same_planning_run():
    class Places:
        def __init__(self):
            self.lookups = []

        async def hotels_near(self, point, check_in, price_range, room, *, check_out_date=None):
            self.lookups.append(check_out_date)
            return [
                raw_offer(
                    check_in,
                    check_out_date,
                    room,
                    101.11 if check_out_date == FIRST + timedelta(days=1) else 201.37,
                )
            ]

    places = Places()
    ai = FakeAI([{"name": "Example Hotel", "attribute_ratings": _ratings()}])

    @in_run
    async def scenarios():
        output = []
        for last in (FIRST + timedelta(days=1), LAST, LAST):
            output.append(
                await candidates.hotel_candidates(
                    [39.74, -104.99],
                    FIRST,
                    ((0, 400), "0-400"),
                    default_weights(),
                    [ROOM],
                    check_out_date=last,
                    ai=ai,
                    places=places,
                )
            )
        return output

    result = await scenarios()
    assert places.lookups == [FIRST + timedelta(days=1), LAST]
    assert [r[0]["price"] for r in result] == [101.11, 201.37, 201.37]
    assert (
        result[0][0]["room_offers"][0]["check_out_date"]
        != result[1][0]["room_offers"][0]["check_out_date"]
    )


def test_lodging_conflict_has_only_the_fixed_public_error_contract():
    from app.core.candidate_errors import ERRORS, CandidateHTTPError, public_candidate_error
    from app.routers.planning_candidates import public_failure
    from app.routing.lodging import LodgingCoverageConflict

    error = LodgingCoverageConflict()
    error.detail = "PRIVATE PROVIDER DIAGNOSTIC"
    with pytest.raises(CandidateHTTPError) as caught:
        public_failure(error)
    assert public_candidate_error(caught.value) == (
        422,
        "lodging_stay_conflict",
        ERRORS["lodging_stay_conflict"][1],
    )
    assert "PRIVATE" not in caught.value.detail
