"""Bounded optional discovery; provider records only, never model-invented hours."""

import asyncio
import math
import re
from datetime import UTC, datetime
from typing import Literal

import httpx
from geopy.distance import geodesic
from pydantic import BaseModel, ConfigDict, model_validator

from app.agent.progress import emit
from app.models.routing_models.trip_advisor_models import Terra_Page_Nearby_Location
from app.models.scheduling_policy import advance, seconds_until
from app.routing import config
from app.routing.sources.attractions import _auth_headers
from app.routing.sources.persona_candidates import VerifiedPlace

MAX_DISTANCE_KM = 2
MAX_TRAVEL_SECONDS = 15 * 60  # Each direction, verified by driving directions.
REST_SECONDS = 30 * 60
VISIT_SECONDS = 60 * 60
DISCOVERY_BUDGET_SECONDS = 8


class OpeningInterval(BaseModel):
    """A provider's date-specific open interval, with an explicit UTC offset."""

    opens: datetime
    closes: datetime

    @model_validator(mode="after")
    def _aware_ordered(self):
        if self.opens.tzinfo is None or self.closes.tzinfo is None or self.opens >= self.closes:
            raise ValueError("Opening intervals must be dated, aware and ordered")
        return self


class EveningPlace(VerifiedPlace):
    model_config = ConfigDict(extra="forbid")
    category: Literal["food", "culture", "nightlife"] | None = None
    closed: bool = False
    # None is unknown, [] means verified closed on this date.
    opening_intervals: list[OpeningInterval] | None = None


class LiveEveningProvider:
    async def nearby(self, hotel, interests, arrival):
        del arrival
        if not config.TRIPADVISOR_API:
            return []
        categories = []
        if set(interests) & {"food", "nightlife"}:
            categories.append("RESTAURANT")
        if set(interests) & {"culture", "nightlife"}:
            categories.append("ATTRACTION")
        records = []
        async with httpx.AsyncClient(timeout=3) as client:
            for category in categories:
                response = await client.get(
                    f"{config.TRIPADVISOR_BASE_URL}/locations/nearby",
                    params={
                        "lat": hotel[0],
                        "lon": hotel[1],
                        "radius": MAX_DISTANCE_KM,
                        "unit": "KM",
                        "category": category,
                        "sort": "distance",
                        "size": 10,
                    },
                    headers=_auth_headers(),
                )
                response.raise_for_status()
                page = Terra_Page_Nearby_Location.model_validate(response.json())
                for entry in page.data[:10]:
                    place = entry.location
                    if not place or not place.id or not place.coordinates:
                        continue
                    extra = place.model_extra or {}
                    status = extra.get("status", {})
                    categories_data = extra.get("categories") or []
                    labels = " ".join(
                        str(item.get("display_name", "")) + " " + str(item.get("hierarchy", ""))
                        for item in categories_data
                        if isinstance(item, dict)
                    ).lower()
                    kind = None
                    if re.search(r"\b(nightlife|bars|nightclubs?|dance clubs|discos)\b", labels):
                        kind = "nightlife"
                    elif any(
                        label in labels
                        for label in ("museum", "theater", "theatre", "gallery", "culture")
                    ):
                        kind = "culture"
                    elif category == "RESTAURANT" and "Eat & Drink" in [
                        item.get("top_level_category")
                        for item in categories_data
                        if isinstance(item, dict)
                    ]:
                        kind = "food"
                    try:
                        records.append(
                            EveningPlace(
                                provider_id=f"terra:{place.id}",
                                name=place.primary_name(),
                                coordinates=[
                                    place.coordinates.latitude,
                                    place.coordinates.longitude,
                                ],
                                address=place.formatted_address(),
                                url=place.web_url(),
                                category=kind,
                                closed=isinstance(status, dict)
                                and status.get("value") in {"CLOSED", "TEMPORARILY_CLOSED"},
                                # Terra supplies weekly periods, not date-specific exceptions.
                                # Do not promise that a weekly schedule proves this dated visit.
                                opening_intervals=None,
                            )
                        )
                    except (ValueError, TypeError):
                        continue
        return records

    async def travel(self, hotel, venue):
        """One bounded round-trip directions request, no route-waypoint mutation."""
        if not config.MAPBOX_API:
            raise ValueError("Optional travel directions are unavailable")
        points = ";".join(f"{lon},{lat}" for lat, lon in (hotel, venue, hotel))
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(
                f"https://api.mapbox.com/directions/v5/mapbox/driving/{points}",
                params={"access_token": config.MAPBOX_API, "overview": "false", "steps": "false"},
            )
        response.raise_for_status()
        legs = response.json()["routes"][0]["legs"]
        if len(legs) != 2:
            raise ValueError("Incomplete optional round-trip directions")
        return [leg["duration"] for leg in legs]


def evening_interests(explicit, weights):
    if explicit is not None:
        return list(dict.fromkeys(explicit))
    # The equal default persona is not evidence of interest in evening outings.
    keys = {"food": "food", "culture": "culture_arts", "nightlife": "nightlife"}
    selected = [
        interest for interest, key in keys.items() if (weights or {}).get(key, 0) > 1 / 14 + 1e-6
    ]
    return sorted(selected, key=lambda interest: -(weights or {})[keys[interest]])


def current_suggestions(hotel):
    """Do not display stale visits when an itinerary's departure was overridden."""
    arrival = datetime.fromisoformat(hotel["arrival_time"])
    deadline = datetime.fromisoformat(hotel["deadline"])
    for suggestion in hotel.get("evening_suggestions", []):
        try:
            outward, inward = suggestion["travel_seconds"]
            earliest = advance(arrival, REST_SECONDS + outward)
            if suggestion.get("visit_time"):
                visit = datetime.fromisoformat(suggestion["visit_time"])
                returned = datetime.fromisoformat(suggestion["return_time"])
                if (
                    seconds_until(earliest, visit) < 0
                    or seconds_until(advance(visit, VISIT_SECONDS + inward), returned) < 0
                    or seconds_until(returned, deadline) < 0
                ):
                    continue
            elif seconds_until(advance(earliest, VISIT_SECONDS + inward), deadline) < 0:
                continue
        except (KeyError, ValueError, TypeError):
            continue
        yield {**suggestion, "return_by": deadline.isoformat()}


async def enrich_evenings(
    stops, interests, *, provider=None, budget_seconds=DISCOVERY_BUDGET_SECONDS
):
    """Attach at most two alternatives per hotel; failures leave route success intact."""
    if not interests:
        return
    provider = provider or LiveEveningProvider()
    try:
        async with asyncio.timeout(budget_seconds):
            for hotel in stops:
                if hotel["type"] != "hotel":
                    continue
                arrival = datetime.fromisoformat(hotel["arrival_time"])
                deadline = datetime.fromisoformat(hotel["deadline"])
                hotel["evening_suggestions"] = []
                if seconds_until(arrival, deadline) < REST_SECONDS + VISIT_SECONDS:
                    continue
                emit("evening.discovery", "started")
                try:
                    async with asyncio.timeout(4):
                        await _hotel_suggestions(hotel, arrival, deadline, interests, provider)
                except Exception:
                    # Optional provider failures never change hotel cost, warning,
                    # completion status, requested attractions or route waypoints.
                    hotel["evening_discovery_status"] = "unavailable"
                emit("evening.discovery", options=len(hotel["evening_suggestions"]))
    except TimeoutError:
        emit("evening.discovery", options=0)


async def _hotel_suggestions(hotel, arrival, deadline, interests, provider):
    records = await provider.nearby(hotel["coordinates"], interests, arrival)
    places = []
    for record in records[:20]:
        try:
            places.append(EveningPlace.model_validate(record))
        except (ValueError, TypeError):
            continue
    places.sort(
        key=lambda place: (
            interests.index(place.category) if place.category in interests else len(interests),
            geodesic(hotel["coordinates"], place.coordinates).km,
            place.provider_id,
        )
    )
    seen = set()
    for place in places:
        if (
            place.closed
            or place.provider_id in seen
            or not place.url
            or not place.url.startswith(("https://", "http://"))
        ):
            continue
        if place.category is not None and place.category not in interests:
            continue
        distance = geodesic(hotel["coordinates"], place.coordinates).km
        if distance > MAX_DISTANCE_KM:
            continue
        seen.add(place.provider_id)
        try:
            outward, inward = await provider.travel(hotel["coordinates"], place.coordinates)
        except Exception:
            continue
        if any(
            isinstance(seconds, bool)
            or not isinstance(seconds, (int, float))
            or not math.isfinite(seconds)
            or not 0 <= seconds <= MAX_TRAVEL_SECONDS
            for seconds in (outward, inward)
        ):
            continue
        visit_start = advance(arrival, REST_SECONDS + outward)
        visit_end = advance(visit_start, VISIT_SECONDS)
        return_time = advance(visit_end, inward)
        if seconds_until(return_time, deadline) < -1e-6:
            continue
        known_hours = place.opening_intervals is not None
        if known_hours:
            windows = [
                window
                for window in place.opening_intervals
                if window.opens.astimezone(UTC) <= visit_start.astimezone(UTC)
                and visit_end.astimezone(UTC) <= window.closes.astimezone(UTC)
            ]
            if not windows:
                continue
        scheduled = known_hours and place.category is not None
        hotel["evening_suggestions"].append(
            {
                **place.model_dump(mode="json", exclude={"opening_intervals", "closed"}),
                "optional": True,
                "status": "open_for_proposed_visit" if scheduled else "tentative",
                "notice": "Optional — choose one; no reservation included"
                if scheduled
                else "Check opening hours"
                + (" and venue category" if place.category is None else ""),
                "visit_time": visit_start.isoformat() if scheduled else None,
                "return_time": return_time.isoformat() if scheduled else None,
                "return_by": deadline.isoformat(),
                "distance_km": round(distance, 2),
                "travel_seconds": [outward, inward],
            }
        )
        if len(hotel["evening_suggestions"]) == 2:
            break
