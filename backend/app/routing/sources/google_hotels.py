"""Bounded Google Hotels HTML lookup for one night, confirmed adults in one room, USD.

Accept only displayed totals whose returned stay controls match the request.
No JavaScript execution, challenge bypass, or invented prices on failure.
"""

from __future__ import annotations

import asyncio
import base64
import math
import re
from datetime import date, timedelta
from urllib.parse import urlencode, urlsplit

import httpx
from geopy.distance import geodesic
from geopy.exc import GeopyError
from lxml import html
from lxml.etree import LxmlError

from app.agent.progress import emit, stage
from app.routing.occupancy import HotelRoom
from app.routing.run_metrics import increment

BASE = "https://www.google.com"
MAX_DETAILS = 6
MAX_HTML_BYTES = 5 * 1024 * 1024
LOOKUP_TIMEOUT = 60
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class GoogleHotelLookupError(RuntimeError):
    """A lookup cannot supply verified dated hotel prices."""


def _varint(value: int) -> bytes:
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def _field(number: int, value: int | bytes) -> bytes:
    if isinstance(value, bytes):
        return _varint(number * 8 + 2) + _varint(len(value)) + value
    return _varint(number * 8) + _varint(value)


def stay_token(check_in: date, room: HotelRoom) -> str:
    """Google's undocumented protobuf `ts` parameter; response checks are mandatory."""

    def day(value: date) -> bytes:
        return _field(1, value.year) + _field(2, value.month) + _field(3, value.day)

    duration = (
        _field(1, day(check_in)) + _field(2, day(check_in + timedelta(days=1))) + _field(3, 1)
    )
    payload = (
        _field(1, 1)
        + _field(
            2,
            _field(1, _field(1, 3)) * room.adults
            + b"".join(_field(1, _field(1, 2) + _field(2, age)) for age in room.provider_child_ages)
            + _field(2, 1),
        )
        + _field(3, _field(2, _field(2, duration) + _field(6, _field(1, 1))))
        + _field(5, _field(1, _field(7, b"USD")))
    )
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def _params(check_in: date, room: HotelRoom) -> dict[str, str]:
    return {"ts": stay_token(check_in, room), "hl": "en", "gl": "us", "curr": "USD"}


def _key(name: str) -> str:
    return " ".join(re.findall(r"\w+", name.casefold()))


def _validate_stay(root, check_in: date, room: HotelRoom) -> None:
    for label, expected in (("Check-in", check_in), ("Check-out", check_in + timedelta(days=1))):
        values = root.xpath(
            f'//input[@aria-label="{label}"]/ancestor::*[@data-value][1]/@data-value'
        )
        if not values or set(values) != {expected.isoformat()}:
            raise GoogleHotelLookupError("Google Hotels did not confirm the requested stay dates.")
    guests = root.xpath("//*[@data-adults]")
    if not guests or any(
        e.get("data-adults") != str(room.adults)
        or e.get("data-children", "") != ",".join(map(str, room.provider_child_ages))
        for e in guests
    ):
        raise GoogleHotelLookupError(
            "Google Hotels did not confirm requested adults and child ages."
        )
    currencies = root.xpath('//span[@jsname="nxRoyb"]/text()')
    if not currencies or set(currencies) != {"USD"}:
        raise GoogleHotelLookupError("Google Hotels did not confirm USD prices.")


def _entity_path(href: str) -> str | None:
    url = urlsplit(href)
    if url.netloc and (url.netloc != "www.google.com" or url.scheme != "https"):
        return None
    match = re.fullmatch(r"(/travel/hotels/entity/[A-Za-z0-9_-]{1,200})(?:/reviews)?", url.path)
    return match[1] if match else None


def _price(card, suffix: str) -> float | None:
    values = set()
    for text in card.xpath(".//text()"):
        match = re.fullmatch(
            r"\$((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?) " + suffix, str(text).strip()
        )
        if match:
            values.add(float(match[1].replace(",", "")))
    if len(values) != 1:
        return None
    value = values.pop()
    return value if math.isfinite(value) and value > 0 else None


class GoogleHotelProvider:
    def __init__(self, geocoder, *, transport=None):
        self.geocoder = geocoder
        self.transport = transport

    async def _page(self, client: httpx.AsyncClient, path: str, params: dict):
        increment("google_hotels")
        async with client.stream("GET", BASE + path, params=params) as response:
            response.raise_for_status()
            if "text/html" not in response.headers.get("content-type", ""):
                raise GoogleHotelLookupError("Google Hotels returned an unsupported response.")
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > MAX_HTML_BYTES:
                    raise GoogleHotelLookupError("Google Hotels returned an oversized response.")
        return html.fromstring(bytes(data))

    async def hotels_near(self, point: list[float], check_in: date, room: HotelRoom) -> list[dict]:
        try:
            async with asyncio.timeout(LOOKUP_TIMEOUT):
                with stage("hotels.lookup"):
                    return await self._lookup(point, check_in, room)
        except GoogleHotelLookupError:
            raise
        except (
            TimeoutError,
            httpx.HTTPError,
            GeopyError,
            LxmlError,
            ValueError,
            TypeError,
            AttributeError,
        ) as exc:
            raise GoogleHotelLookupError(
                "Google Hotels prices are temporarily unavailable. Please try again later."
            ) from exc

    async def _lookup(self, point: list[float], check_in: date, room: HotelRoom) -> list[dict]:
        increment("opencage")
        location = await asyncio.to_thread(self.geocoder.reverse, point, timeout=5)
        components = location.raw.get("components", {}) if location else {}
        city = next(
            (components[k] for k in ("city", "town", "village", "county") if components.get(k)),
            None,
        )
        if not city:
            raise GoogleHotelLookupError("The overnight city could not be verified.")
        query = ", ".join(
            str(v) for v in (city, components.get("state"), components.get("country")) if v
        )
        emit("hotels.search_area", city=str(city)[:100], checkIn=check_in.isoformat())
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20, connect=5),
            headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
            transport=self.transport,
            follow_redirects=False,
        ) as client:
            with stage("hotels.google_search"):
                root = await self._page(
                    client, "/travel/search", {**_params(check_in, room), "q": "hotels in " + query}
                )
            _validate_stay(root, check_in, room)
            cards = root.xpath('//div[@jsname="mutHjb"]')
            if not cards:
                raise GoogleHotelLookupError(
                    "Google Hotels returned no readable dated hotel listings."
                )
            records = []
            rejected = {
                "unusablePriceOrLink": 0,
                "identity": 0,
                "address": 0,
                "geocode": 0,
                "radius": 0,
            }
            emit("hotels.listings", candidates=len(cards))
            seen = set()
            details = 0
            for card in cards[:20]:
                names = card.xpath(".//h2//text()")
                name = " ".join(names).strip()
                paths = [path for href in card.xpath(".//a/@href") if (path := _entity_path(href))]
                price, nightly = _price(card, "total"), _price(card, "nightly")
                if (
                    not name
                    or not paths
                    or paths[0] in seen
                    or price is None
                    or nightly is None
                    or price < nightly
                    or "1 night with taxes + fees" not in card.text_content()
                ):
                    rejected["unusablePriceOrLink"] += 1
                    continue
                if details >= MAX_DETAILS:
                    break
                path = paths[0]
                seen.add(path)
                details += 1
                with stage("hotels.verify_listing", attempt=details):
                    detail = await self._page(client, path, _params(check_in, room))
                _validate_stay(detail, check_in, room)
                if _key(" ".join(detail.xpath("//h1//text()"))) != _key(name):
                    rejected["identity"] += 1
                    continue
                addresses = detail.xpath('//div[@class="K4nuhf"]/span[@class="CFH2De"]/text()')
                if not addresses:
                    rejected["address"] += 1
                    continue
                address = addresses[0].strip()
                increment("opencage")
                geo = await asyncio.to_thread(self.geocoder.geocode, address, timeout=5)
                if not geo:
                    rejected["geocode"] += 1
                    continue
                coordinates = [geo.latitude, geo.longitude]
                if geodesic(point, coordinates).miles > 30:
                    rejected["radius"] += 1
                    continue
                records.append(
                    {
                        "provider_id": "google:" + path.rsplit("/", 1)[1],
                        "name": name,
                        "coordinates": coordinates,
                        "address": address,
                        "url": BASE + path + "?" + urlencode(_params(check_in, room)),
                        "price": price,
                        "room": room.model_dump(),
                        "price_scope": "one_room_one_night_including_taxes_fees",
                        "check_in_date": check_in,
                    }
                )
                emit("hotels.collected", name=name[:100], hotels=len(records))
            emit("hotels.rejections", checked=details, verified=len(records), **rejected)
            if not records:
                if details > 0 and rejected["radius"] == details:
                    # Valid dated listings outside this point's radius are a spatial
                    # miss, not a provider failure. Let the scheduler backtrack to
                    # an earlier overnight point using its existing bounded retries.
                    emit("hotels.no_nearby", checked=details, radiusMiles=30)
                    return []
                raise GoogleHotelLookupError(
                    "Google Hotels returned no verifiable prices near the overnight stop."
                )
            emit("hotels.verified", hotels=len(records))
            return records
