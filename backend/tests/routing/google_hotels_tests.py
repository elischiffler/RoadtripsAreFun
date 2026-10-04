"""Representative HTML contracts, independent of Google/network availability."""

from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from app.routing.sources import google_hotels as source

CHECK_IN = date(2026, 11, 20)
CONTROLS = """
<div data-value="2026-11-20"><input aria-label="Check-in"></div>
<div data-value="2026-11-21"><input aria-label="Check-out"></div>
<div data-adults="2" data-children=""></div><span jsname="nxRoyb">USD</span>
"""
CARD = """<div jsname="mutHjb"><h2>Example Hotel</h2>
<a href="/travel/hotels/entity/ExampleID?tracking=ignored">Details</a>
<div>$100 nightly</div><div>$120 total</div><div>1 night with taxes + fees</div>
</div>"""
DETAIL = """<h1>Example Hotel</h1>
<div class="K4nuhf"><span class="CFH2De">100 Main St, Denver, CO</span></div>"""


class Geocoder:
    def reverse(self, point, timeout):
        assert point == [39.74, -104.99] and timeout == 5
        return SimpleNamespace(
            raw={"components": {"city": "Denver", "state": "Colorado", "country": "USA"}}
        )

    def geocode(self, address, timeout):
        assert address == "100 Main St, Denver, CO" and timeout == 5
        return SimpleNamespace(latitude=39.74, longitude=-104.99)


def provider(
    search=CONTROLS + CARD,
    detail=CONTROLS + '<span jsname="nxRoyb">USD</span>' + DETAIL,
    *,
    status=200,
    geocoder=None,
):
    requests = []

    def handle(request):
        requests.append(request)
        assert request.url.params["curr"] == "USD"
        assert request.url.params["ts"] == source.stay_token(CHECK_IN)
        body = search if request.url.path == "/travel/search" else detail
        return httpx.Response(
            status, text=body, headers={"content-type": "text/html; charset=utf-8"}
        )

    return source.GoogleHotelProvider(
        geocoder or Geocoder(), transport=httpx.MockTransport(handle)
    ), requests


async def test_verified_dated_total_and_booking_link():
    places, requests = provider()
    records = await places.hotels_near([39.74, -104.99], CHECK_IN)
    assert len(requests) == 2
    assert "Denver, Colorado, USA" in requests[0].url.params["q"]
    assert records[0]["price"] == 120  # Total incl taxes/fees, never the base rate.
    assert records[0]["check_in_date"] == CHECK_IN
    assert records[0]["coordinates"] == [39.74, -104.99]
    url = httpx.URL(records[0]["url"])
    assert url.host == "www.google.com" and url.params["ts"] == source.stay_token(CHECK_IN)
    assert "tracking" not in url.params


@pytest.mark.parametrize(
    "changed",
    [
        CONTROLS.replace("2026-11-20", "2026-11-02") + CARD,
        CONTROLS.replace('data-adults="2"', 'data-adults="1"') + CARD,
        CONTROLS.replace('data-children=""', 'data-children="5"') + CARD,
        CONTROLS.replace(">USD<", ">CAD<") + CARD,
        "<html>unusual traffic, complete a CAPTCHA</html>",
        "",
    ],
)
async def test_rejects_unconfirmed_stay_and_challenges(changed):
    places, requests = provider(search=changed)
    with pytest.raises(source.GoogleHotelLookupError):
        await places.hotels_near([39.74, -104.99], CHECK_IN)
    assert len(requests) == 1


@pytest.mark.parametrize(
    "changed",
    [
        CARD.replace("$120 total", "$120 nightly"),
        CARD.replace("$120 total", "$1,2 total"),
        CARD.replace("$120 total", "$90 total"),
        CARD.replace("1 night with taxes + fees", "2 nights"),
        CARD.replace(
            "/travel/hotels/entity/ExampleID?tracking=ignored",
            "https://evil.test/travel/hotels/entity/ExampleID",
        ),
        CARD.replace("$120 total", "$120 total</div><div>$125 total"),
    ],
)
async def test_rejects_ambiguous_prices_and_unsafe_links(changed):
    places, requests = provider(search=CONTROLS + changed)
    with pytest.raises(source.GoogleHotelLookupError, match="no verifiable"):
        await places.hotels_near([39.74, -104.99], CHECK_IN)
    assert len(requests) == 1


async def test_detail_must_confirm_same_stay_and_identity():
    places, _ = provider(detail=(CONTROLS + DETAIL).replace("2026-11-21", "2026-11-22"))
    with pytest.raises(source.GoogleHotelLookupError, match="dates"):
        await places.hotels_near([39.74, -104.99], CHECK_IN)
    places, _ = provider(detail=CONTROLS + DETAIL.replace("Example Hotel", "Different Hotel"))
    with pytest.raises(source.GoogleHotelLookupError, match="no verifiable"):
        await places.hotels_near([39.74, -104.99], CHECK_IN)


async def test_radius_and_duplicate_identity():
    class DistantGeocoder(Geocoder):
        def geocode(self, address, timeout):
            return SimpleNamespace(latitude=35.3, longitude=-120.6)

    places, _ = provider(geocoder=DistantGeocoder())
    with pytest.raises(source.GoogleHotelLookupError, match="no verifiable"):
        await places.hotels_near([39.74, -104.99], CHECK_IN)
    places, requests = provider(search=CONTROLS + CARD * 20)
    assert len(await places.hotels_near([39.74, -104.99], CHECK_IN)) == 1
    assert len(requests) == 2


async def test_http_failure_and_overall_deadline(monkeypatch):
    places, _ = provider(status=429)
    with pytest.raises(source.GoogleHotelLookupError, match="temporarily unavailable"):
        await places.hotels_near([39.74, -104.99], CHECK_IN)
    monkeypatch.setattr(source, "LOOKUP_TIMEOUT", 0)
    places, _ = provider()
    with pytest.raises(source.GoogleHotelLookupError, match="temporarily unavailable"):
        await places.hotels_near([39.74, -104.99], CHECK_IN)


def test_stay_token_changes_at_month_and_year_boundaries():
    assert source.stay_token(date(2026, 12, 31)) != source.stay_token(date(2027, 1, 1))
