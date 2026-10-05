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
from datetime import date, datetime
from typing import Any, Literal, Protocol
from urllib.parse import urlparse

import httpx
from geopy.distance import geodesic
from pydantic import BaseModel, ConfigDict, field_validator

from app.agent.persona import ATTRIBUTE_KEYS, normalize_weights
from app.agent.progress import emit, stage
from app.agent.provider_diagnostics import retry_async
from app.agent.providers import LLMProvider, build_default_chain
from app.agent.schemas import LLMMessage
from app.routing import config
from app.routing.occupancy import MAX_ROOMS, HotelRoom
from app.routing.profiles import AttributeRatings, crossmatch
from app.routing.run_metrics import increment, timed
from app.routing.sources.attractions import _auth_headers, _raise_for_status

MAX_ATTRACTIONS = 30
MAX_HOTELS = 10
MAX_PROPOSALS_PER_QUERY = 5
MAX_HOTEL_PROPOSALS = 15
_ATTRACTION_RADIUS_MI = 5.0
_HOTEL_RADIUS_MI = 30.0


class CandidateProviderError(RuntimeError):
    """Required AI or place provider is unavailable or returned unusable data."""


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


class LocationProfile(VerifiedPlace):
    """Reusable place attributes, separate from the active trip's match score."""

    attribute_ratings: AttributeRatings
    provenance: dict[str, str | None]


class VerifiedHotel(VerifiedPlace):
    """Hotel with a provider offer for the requested check-in date."""

    price: float
    check_in_date: date
    room: HotelRoom
    price_scope: Literal["one_room_one_night_including_taxes_fees"]
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
        self,
        point: list[float],
        check_in: date,
        price_range: tuple[tuple[float, float], str],
        room: HotelRoom,
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
    ai: LLMProvider, kind: str, point: list[float], limit: int, names: list[str] | None = None
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
    if names is not None:
        prompt += (
            " Rate only these provider-verified names, preserving each exactly: "
            + json.dumps(names)
        )
    try:
        with timed("generation"):
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
    match = crossmatch(weights, ratings, already_normalized=True)
    profile = LocationProfile(
        **place.model_dump(include={"provider_id", "name", "coordinates", "address", "url"}),
        attribute_ratings=proposal.attribute_ratings,
        provenance={
            "identity_source": place.provider_id.split(":", 1)[0],
            "ratings_source": "AI estimates; provider verifies identity, not ratings",
            "verified_at": None,
        },
    )
    result = place.model_dump(exclude={"check_in_date", "price", "stars", "review_count"})
    result.update(profile.model_dump())
    result.update(match.model_dump())
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
    for query_index, raw_point in enumerate(query_points, start=1):
        emit(
            "attractions.query",
            "started",
            query=query_index,
            queries=len(query_points),
            collected=len(results),
        )
        point = _point(raw_point)
        with stage("attractions.provider", query=query_index, queries=len(query_points)):
            records = await retry_async(lambda: places.attractions_near(point))
        verified_records = []
        for record in records:
            try:
                verified = VerifiedPlace.model_validate(record)
            except ValueError:
                continue
            if (
                verified.provider_id not in seen
                and _distance_miles(point, verified.coordinates) <= _ATTRACTION_RADIUS_MI
            ):
                verified_records.append(verified)
        records = verified_records[:MAX_PROPOSALS_PER_QUERY]
        if not records:
            emit(
                "attractions.query",
                query=query_index,
                queries=len(query_points),
                candidates=0,
                collected=len(results),
            )
            continue
        # Ground ratings in the live provider's names, as hotel ratings already are.
        # Independent AI suggestions rarely matched the provider's actual nearby list.
        with stage(
            "attractions.ratings",
            query=query_index,
            queries=len(query_points),
            candidates=len(records),
        ):
            proposals = await _propose(
                ai,
                "attractions",
                point,
                MAX_PROPOSALS_PER_QUERY,
                names=[record.name for record in records],
            )
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
                emit(
                    "attractions.collected",
                    name=verified.name[:100],
                    collected=len(results),
                    query=query_index,
                    queries=len(query_points),
                )
                break
            if len(results) >= MAX_ATTRACTIONS:
                emit(
                    "attractions.query",
                    query=query_index,
                    queries=len(query_points),
                    candidates=len(records),
                    collected=len(results),
                )
                return results
        emit(
            "attractions.query",
            query=query_index,
            queries=len(query_points),
            candidates=len(records),
            collected=len(results),
        )
    return results


async def _room_candidates(
    overnight_position: list[float],
    check_in_date: date | datetime,
    price_range: tuple[tuple[float, float], str],
    effective_weights: dict[str, float],
    room: HotelRoom,
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
    records = await retry_async(
        lambda: places.hotels_near(point, check_in, price_range, room), "hotels.lookup"
    )
    if not records:
        return []
    names = [
        record.name if isinstance(record, VerifiedHotel) else record.get("name", "")
        for record in records[:MAX_HOTEL_PROPOSALS]
    ]
    with stage("hotels.ratings", hotels=len(names)):
        proposals = await _propose(ai, "hotels", point, MAX_HOTEL_PROPOSALS, names=names)
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
                or verified.room != room
                or _name_key(verified.name) != _name_key(proposal.name)
                or verified.provider_id in seen
                or _distance_miles(point, verified.coordinates) > _HOTEL_RADIUS_MI
            ):
                continue
            seen.add(verified.provider_id)
            candidate = _candidate(verified, proposal, weights)
            candidate.update(
                type="hotel", price=verified.price, check_in_date=verified.check_in_date.isoformat()
            )
            candidate["stars"] = verified.stars
            candidate["review_count"] = verified.review_count
            results.append(candidate)
            break
        if len(results) >= MAX_HOTELS:
            break
    return results


class LivePlaceProvider:
    """Terra identities and configurable dated hotel prices."""

    @staticmethod
    def require_attractions() -> None:
        if not config.TRIPADVISOR_API:
            raise CandidateProviderError("TripAdvisor Terra is not configured")

    @staticmethod
    def require_hotels() -> None:
        if not config.OPENCAGE_KEY:
            raise CandidateProviderError("Google Hotels location verification is not configured")

    async def attractions_near(self, point: list[float]) -> list[VerifiedPlace]:
        self.require_attractions()
        try:
            async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT) as client:
                increment("tripadvisor")
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
            # Some live nearby responses include other categories despite the
            # ATTRACTION filter. Require the provider's attraction listing type.
            listing = urlparse(location.web_url() or "")
            if not listing.path.startswith("/Attraction_Review-"):
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
        self,
        point: list[float],
        check_in: date,
        price_range: tuple[tuple[float, float], str],
        room: HotelRoom,
    ) -> list[VerifiedHotel]:
        del price_range  # Advisory budget: keep usable over-budget hotels.
        self.require_hotels()
        from app.routing.sources.google_hotels import GoogleHotelLookupError, GoogleHotelProvider

        try:
            records = await GoogleHotelProvider(config.geolocator).hotels_near(
                point, check_in, room
            )
            return [VerifiedHotel.model_validate(record) for record in records]
        except GoogleHotelLookupError as exc:
            raise CandidateProviderError(str(exc)) from exc


async def hotel_candidates(
    overnight_position: list[float],
    check_in_date: date | datetime,
    price_range: tuple[tuple[float, float], str],
    effective_weights: dict[str, float],
    hotel_rooms: list[HotelRoom],
    *,
    ai: LLMProvider | None = None,
    places: PlaceProvider | None = None,
) -> list[dict[str, Any]]:
    """Intersect independently verified room quotes at the same hotel.

    No claim of simultaneous room inventory: every quote keeps its own link.
    """
    rooms = [HotelRoom.model_validate(room) for room in hotel_rooms]
    if not 1 <= len(rooms) <= MAX_ROOMS:
        raise ValueError("Hotel lookup supports 1-4 rooms")
    by_room = []
    for room in rooms:
        candidates = await _room_candidates(
            overnight_position,
            check_in_date,
            price_range,
            effective_weights,
            room,
            ai=ai,
            places=places,
        )
        if not candidates:
            return []
        by_room.append({item["provider_id"]: item for item in candidates})
    results = []
    for key, first in by_room[0].items():
        if not all(key in lookup for lookup in by_room):
            continue
        offers = [
            {
                "room": room.model_dump(),
                "price": lookup[key]["price"],
                "url": lookup[key]["url"],
                "check_in_date": lookup[key]["check_in_date"],
                "price_scope": lookup[key]["price_scope"],
            }
            for room, lookup in zip(rooms, by_room)
        ]
        results.append(
            {
                **{field: value for field, value in first.items() if field != "room"},
                "traveler_count": sum(room.adults + len(room.child_ages) for room in rooms),
                "hotel_rooms": [room.model_dump() for room in rooms],
                "room_offers": offers,
                "price": sum(offer["price"] for offer in offers),
                "url": offers[0]["url"] if len(offers) == 1 else None,
                "price_scope": "one_room_one_night_including_taxes_fees"
                if len(offers) == 1
                else "independent_room_quotes_not_combined_inventory",
            }
        )
    return results
