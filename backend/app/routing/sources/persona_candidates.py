"""AI proposals checked against place records before persona scoring.

Public async entry points are ``attraction_candidates`` and ``hotel_candidates``.
The provider seams make all proposal and identity checks testable without network
access. Neither AI coordinates nor AI prices are accepted as source data.
"""

from __future__ import annotations

import asyncio
import json
import math
import re
from datetime import date, datetime, timedelta
from typing import Any, Protocol

import httpx
from geopy.distance import geodesic
from pydantic import BaseModel, ConfigDict, field_validator

from app.agent.persona import ATTRIBUTE_KEYS, normalize_weights
from app.agent.providers import LLMProvider, build_default_chain
from app.agent.schemas import LLMMessage
from app.routing import config
from app.routing.sources.attractions import _auth_headers, _raise_for_status

MAX_ATTRACTIONS = 30
MAX_HOTELS = 10
MAX_PROPOSALS_PER_QUERY = 5
MAX_HOTEL_PROPOSALS = 15
MAX_HOTEL_PROVIDER_RESULTS = 20
_ATTRACTION_RADIUS_MI = 5.0
_HOTEL_RADIUS_MI = 30.0


class CandidateProviderError(RuntimeError):
    """Required AI or place provider is unavailable or returned unusable data."""


class AttributeRatings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenery: float
    nature: float
    hiking_outdoors: float
    food: float
    history: float
    culture_arts: float
    nightlife: float
    shopping: float
    beaches_water: float
    adventure: float
    relaxation: float
    unique_local_experiences: float
    family_friendliness: float
    crowd_avoidance: float

    @field_validator("*", mode="before")
    @classmethod
    def _unit_interval(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("attribute ratings must be numbers in [0, 1]")
        value = float(value)
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("attribute ratings must be numbers in [0, 1]")
        return value


class ProposedPlace(BaseModel):
    model_config = ConfigDict(extra="ignore")  # AI utility/price is ignored

    name: str
    attribute_ratings: AttributeRatings

    @field_validator("name")
    @classmethod
    def _named(cls, value: str) -> str:
        value = value.strip()
        if not value or len(value) > 180:
            raise ValueError("place name must be nonempty and bounded")
        return value


class VerifiedPlace(BaseModel):
    """Identity and coordinates returned by a place provider."""

    provider_id: str
    name: str
    coordinates: list[float]
    address: str | None = None
    url: str | None = None

    @field_validator("provider_id", "name")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("verified place requires ID and name")
        return value

    @field_validator("coordinates")
    @classmethod
    def _coordinates(cls, value: list[float]) -> list[float]:
        if len(value) != 2 or not all(math.isfinite(v) for v in value):
            raise ValueError("coordinates must be a finite [lat, lon] pair")
        lat, lon = value
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("coordinates outside geographic bounds")
        return [float(lat), float(lon)]


class VerifiedHotel(VerifiedPlace):
    """Hotel with a provider offer for the requested check-in date."""

    price: float
    check_in_date: date
    stars: float | None = None
    review_count: int | None = None

    @field_validator("price")
    @classmethod
    def _price(cls, value: float) -> float:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("hotel price must be finite and positive")
        return value


class PlaceProvider(Protocol):
    async def attractions_near(self, point: list[float]) -> list[VerifiedPlace]: ...

    async def hotels_near(
        self, point: list[float], check_in: date, price_range: tuple[tuple[float, float], str]
    ) -> list[VerifiedHotel]: ...


def _name_key(name: str) -> str:
    return " ".join(re.findall(r"\w+", name.casefold()))


def _point(value: list[float]) -> list[float]:
    return VerifiedPlace(provider_id="point", name="point", coordinates=value).coordinates


def _distance_miles(first: list[float], second: list[float]) -> float:
    return geodesic(first, second).miles


def _parse_proposals(text: str, limit: int) -> list[ProposedPlace]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return []
    if isinstance(payload, dict):
        payload = payload.get("candidates")
    if not isinstance(payload, list):
        return []
    proposals = []
    for item in payload[:limit]:
        try:
            proposals.append(ProposedPlace.model_validate(item))
        except (TypeError, ValueError):
            continue
    return proposals


async def _propose(
    ai: LLMProvider, kind: str, point: list[float], limit: int
) -> list[ProposedPlace]:
    example = json.dumps(
        {
            "candidates": [
                {"name": "place name", "attribute_ratings": dict.fromkeys(ATTRIBUTE_KEYS, 0.5)}
            ]
        }
    )
    prompt = (
        f"Suggest at most {limit} real named {kind} near latitude {point[0]}, "
        f"longitude {point[1]}. Rate each attribute from 0 to 1 for each place. "
        f"Return only JSON in this exact shape: {example}. "
        "Do not include prices, coordinates, or a final utility score."
    )
    try:
        response = await asyncio.to_thread(
            ai.complete,
            [
                LLMMessage(role="system", content="Return strict JSON only."),
                LLMMessage(role="user", content=prompt),
            ],
            [],
        )
    except Exception as exc:
        raise CandidateProviderError("AI candidate provider unavailable") from exc
    return _parse_proposals(response.content, limit)


def _candidate(
    place: VerifiedPlace, proposal: ProposedPlace, weights: dict[str, float]
) -> dict[str, Any]:
    ratings = proposal.attribute_ratings.model_dump()
    utility = math.fsum(weights[key] * ratings[key] for key in ATTRIBUTE_KEYS)
    result = place.model_dump(exclude={"check_in_date", "price", "stars", "review_count"})
    result.update(attribute_ratings=ratings, utility=min(1.0, max(0.0, utility)))
    return result


async def attraction_candidates(
    raw_route: Any,
    query_points: list[list[float]],
    effective_weights: dict[str, float],
    *,
    ai: LLMProvider | None = None,
    places: PlaceProvider | None = None,
) -> list[dict[str, Any]]:
    """Return at most 30 unique Terra-verified attraction candidates.

    ``raw_route`` is accepted for the planner's fixed injected signature; query
    points have already been sampled in drive-time order by the solver.
    """
    del raw_route
    weights = normalize_weights(effective_weights)
    if not query_points:
        return []
    if len(query_points) > MAX_ATTRACTIONS:
        raise ValueError("at most 30 attraction query points are allowed")
    ai = ai or build_default_chain()
    places = places or LivePlaceProvider()
    if isinstance(places, LivePlaceProvider):
        places.require_attractions()
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_point in query_points:
        point = _point(raw_point)
        proposals = await _propose(ai, "attractions", point, MAX_PROPOSALS_PER_QUERY)
        if not proposals:
            continue
        records = await places.attractions_near(point)
        for proposal in proposals:
            name = _name_key(proposal.name)
            for record in records:
                try:
                    verified = VerifiedPlace.model_validate(record)
                except ValueError:
                    continue
                if (
                    _name_key(verified.name) != name
                    or verified.provider_id in seen
                    or _distance_miles(point, verified.coordinates) > _ATTRACTION_RADIUS_MI
                ):
                    continue
                seen.add(verified.provider_id)
                results.append(_candidate(verified, proposal, weights))
                break
            if len(results) >= MAX_ATTRACTIONS:
                return results
    return results


async def hotel_candidates(
    overnight_position: list[float],
    check_in_date: date | datetime,
    price_range: tuple[tuple[float, float], str],
    effective_weights: dict[str, float],
    *,
    ai: LLMProvider | None = None,
    places: PlaceProvider | None = None,
) -> list[dict[str, Any]]:
    """Return bounded, provider-matched hotels with dated USD offer prices."""
    point = _point(overnight_position)
    weights = normalize_weights(effective_weights)
    check_in = check_in_date.date() if isinstance(check_in_date, datetime) else check_in_date
    if not isinstance(check_in, date):
        raise ValueError("check_in_date must be a date")
    low, high = price_range[0]
    if not all(math.isfinite(v) for v in (low, high)) or low < 0 or high < low:
        raise ValueError("invalid hotel price range")
    ai = ai or build_default_chain()
    places = places or LivePlaceProvider()
    if isinstance(places, LivePlaceProvider):
        places.require_hotels()
    proposals = await _propose(ai, "hotels", point, MAX_HOTEL_PROPOSALS)
    if not proposals:
        return []
    records = await places.hotels_near(point, check_in, price_range)
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for proposal in proposals:
        for record in records:
            try:
                verified = VerifiedHotel.model_validate(record)
            except ValueError:
                continue
            if (
                verified.check_in_date != check_in
                or _name_key(verified.name) != _name_key(proposal.name)
                or verified.provider_id in seen
                or _distance_miles(point, verified.coordinates) > _HOTEL_RADIUS_MI
            ):
                continue
            seen.add(verified.provider_id)
            candidate = _candidate(verified, proposal, weights)
            candidate.update(type="hotel", price=verified.price)
            candidate["stars"] = verified.stars
            candidate["review_count"] = verified.review_count
            results.append(candidate)
            break
        if len(results) >= MAX_HOTELS:
            break
    return results


class LivePlaceProvider:
    """Terra identities and Amadeus dated hotel offers; no scraper prices."""

    @staticmethod
    def require_attractions() -> None:
        if not config.TRIPADVISOR_API:
            raise CandidateProviderError("TripAdvisor Terra is not configured")

    @staticmethod
    def require_hotels() -> None:
        import os

        if (
            not config.AMADEUS_ENABLED
            or not os.getenv("AMADEUS_KEY")
            or not os.getenv("AMADEUS_SECRET")
        ):
            raise CandidateProviderError("Dated Amadeus hotel offers are not configured")

    async def attractions_near(self, point: list[float]) -> list[VerifiedPlace]:
        self.require_attractions()
        try:
            async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
                response = await client.get(
                    f"{config.TRIPADVISOR_BASE_URL}/locations/nearby",
                    params={
                        "lat": point[0],
                        "lon": point[1],
                        "radius": 5,
                        "unit": "MI",
                        "category": "ATTRACTION",
                        "sort": "rating,desc",
                    },
                    headers=_auth_headers(),
                )
            _raise_for_status(response)
            from app.models.routing_models.trip_advisor_models import Terra_Page_Nearby_Location

            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
                raise ValueError("Terra nearby response has no locations list")
            page = Terra_Page_Nearby_Location.model_validate(payload)
        except Exception as exc:
            raise CandidateProviderError("TripAdvisor Terra attraction lookup failed") from exc
        records = []
        for entry in page.data[:30]:
            location = entry.location
            if location is None or location.id is None or location.coordinates is None:
                continue
            try:
                records.append(
                    VerifiedPlace(
                        provider_id=f"terra:{location.id}",
                        name=location.primary_name(),
                        coordinates=[location.coordinates.latitude, location.coordinates.longitude],
                        address=location.formatted_address(),
                        url=location.web_url(),
                    )
                )
            except (TypeError, ValueError):
                continue
        return records

    async def hotels_near(
        self, point: list[float], check_in: date, price_range: tuple[tuple[float, float], str]
    ) -> list[VerifiedHotel]:
        del price_range  # Advisory budget: request all offers, including over-budget.
        import os

        self.require_hotels()
        base = "https://test.api.amadeus.com"
        try:
            async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
                auth = await client.post(
                    f"{base}/v1/security/oauth2/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": os.environ["AMADEUS_KEY"],
                        "client_secret": os.environ["AMADEUS_SECRET"],
                    },
                )
                auth.raise_for_status()
                token = auth.json()["access_token"]
                headers = {"Authorization": f"Bearer {token}"}
                search = await client.get(
                    f"{base}/v1/reference-data/locations/hotels/by-geocode",
                    params={
                        "latitude": point[0],
                        "longitude": point[1],
                        "radius": 30,
                        "radiusUnit": "MILE",
                    },
                    headers=headers,
                )
                if search.status_code == 404:
                    return []
                search.raise_for_status()
                locations = search.json().get("data", [])
                if not isinstance(locations, list):
                    raise ValueError("Amadeus hotel search returned no list")
                by_id = {
                    item["hotelId"]: item
                    for item in locations[:MAX_HOTEL_PROVIDER_RESULTS]
                    if isinstance(item, dict) and item.get("hotelId")
                }
                if not by_id:
                    return []
                offers = await client.get(
                    f"{base}/v3/shopping/hotel-offers",
                    params={
                        "hotelIds": ",".join(by_id),
                        "adults": 2,
                        "checkInDate": check_in.isoformat(),
                        "checkOutDate": (check_in + timedelta(days=1)).isoformat(),
                        "currency": "USD",
                    },
                    headers=headers,
                )
                if offers.status_code == 404:
                    return []
                offers.raise_for_status()
                offer_data = offers.json().get("data", [])
                if not isinstance(offer_data, list):
                    raise ValueError("Amadeus offers returned no list")
        except (httpx.HTTPError, AttributeError, KeyError, TypeError, ValueError) as exc:
            raise CandidateProviderError("Amadeus dated hotel lookup failed") from exc
        records = []
        for item in offer_data:
            if not isinstance(item, dict):
                continue
            hotel = item.get("hotel") or {}
            if not isinstance(hotel, dict):
                continue
            provider_id = hotel.get("hotelId")
            location = by_id.get(provider_id)
            if not location:
                continue
            valid_prices = []
            for offer in item.get("offers") or []:
                if not isinstance(offer, dict):
                    continue
                price = offer.get("price") or {}
                if not isinstance(price, dict):
                    continue
                if (
                    offer.get("checkInDate") != check_in.isoformat()
                    or offer.get("checkOutDate") != (check_in + timedelta(days=1)).isoformat()
                    or price.get("currency") != "USD"
                ):
                    continue
                try:
                    amount = float(price["total"])
                except (KeyError, TypeError, ValueError):
                    continue
                if math.isfinite(amount) and amount > 0:
                    valid_prices.append(amount)
            if not valid_prices:
                continue
            try:
                records.append(
                    VerifiedHotel(
                        provider_id=f"amadeus:{provider_id}",
                        name=location["name"],
                        coordinates=[
                            location["geoCode"]["latitude"],
                            location["geoCode"]["longitude"],
                        ],
                        address=", ".join(str(v) for v in location.get("address", {}).values())
                        or None,
                        price=min(valid_prices),
                        check_in_date=check_in,
                    )
                )
            except (AttributeError, KeyError, TypeError, ValueError):
                continue
        return records
