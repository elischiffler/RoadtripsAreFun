"""AI proposals checked against place records before persona scoring.

Public async entry points are ``attraction_candidates`` and ``hotel_candidates``.
The provider seams make all proposal and identity checks testable without network
access. Neither AI coordinates nor AI prices are accepted as source data.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date, datetime
from typing import Any, Literal, Protocol

from geopy.distance import geodesic
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.agent.persona import ATTRIBUTE_KEYS, normalize_weights
from app.agent.progress import emit, stage
from app.agent.provider_diagnostics import retry_async
from app.agent.providers import LLMProvider, build_default_chain
from app.agent.schemas import LLMMessage
from app.catalog import repository
from app.routing import config
from app.routing.discovery import (
    DiscoveryPlan,
    DiscoveryResult,
    SearchQuery,
    balanced_pool,
    category_order,
)
from app.routing.explanation import record_explanation
from app.routing.geometry import RouteMeasure
from app.routing.occupancy import MAX_ROOMS, HotelRoom
from app.routing.profiles import AttributeRatings, crossmatch, eligible_utility
from app.routing.run_metrics import increment, timed
from app.routing.runtime import (
    in_run,
    joined,
    limited,
    run_resource,
    singleflight,
    threaded,
)
from app.routing.sources.visit_durations import estimate_durations
from app.routing.trip_calendar import TripCalendar
from app.routing.visit_calendar import calendar_eligible
from app.routing.visit_duration import MIN_VISIT_SECONDS

MAX_ATTRACTIONS = 60
MAX_HOTELS = 10
MAX_PROPOSALS_PER_QUERY = 5
MAX_HOTEL_PROPOSALS = 15
_ATTRACTION_RADIUS_MI = 5.0
_HOTEL_RADIUS_MI = 30.0


class CandidateProviderError(RuntimeError):
    """Required AI or place provider is unavailable or returned unusable data."""


class CandidateRatingError(CandidateProviderError):
    """Source places exist, but bounded AI attempts produced no usable ratings."""

    provider = "ai_ratings"
    provider_code = "INVALID_ATTRIBUTE_RATINGS"
    public_message = "AI returned no complete ratings matching the catalog places."
    retryable = False


class ProposedPlace(BaseModel):
    model_config = ConfigDict(extra="ignore")  # AI utility/price is ignored

    name: str
    attribute_ratings: AttributeRatings

    @field_validator("name")
    @classmethod
    def _named(cls, value: str) -> str:
        """Trim an estimated place name and reject empty names or names longer than 180 characters."""
        value = value.strip()
        if not value or len(value) > 180:
            raise ValueError("place name must be nonempty and bounded")
        return value


class VerifiedPlace(BaseModel):
    """Validated source identity and coordinates, without a live availability claim."""

    provider_id: str
    name: str
    coordinates: list[float]
    address: str | None = None
    url: str | None = None
    categories: list[str] = []
    activities: list[str] = Field(default_factory=list, max_length=20)
    description: str | None = Field(default=None, max_length=2000)
    provider_rank: int = 0
    source: str | None = None
    source_release: str | None = None
    source_attribution: str | None = None
    source_updated_at: str | None = None
    source_provenance: list[dict[str, Any]] = []

    @field_validator("provider_id", "name")
    @classmethod
    def _nonempty(cls, value: str) -> str:
        """Trim a provider ID or place name and reject an empty result."""
        value = value.strip()
        if not value:
            raise ValueError("verified place requires ID and name")
        return value

    @field_validator("coordinates")
    @classmethod
    def _coordinates(cls, value: list[float]) -> list[float]:
        """Validate a finite [lat, lon] pair within geographic bounds and return floats."""
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
        """Require a finite, strictly positive hotel quote."""
        if not math.isfinite(value) or value <= 0:
            raise ValueError("hotel price must be finite and positive")
        return value


class PlaceProvider(Protocol):
    async def attractions_near(self, point: list[float]) -> list[VerifiedPlace]:
        """Return catalog source records near the supplied [lat, lon] point."""
        ...

    async def hotels_near(
        self,
        point: list[float],
        check_in: date,
        price_range: tuple[tuple[float, float], str],
        room: HotelRoom,
    ) -> list[VerifiedHotel]:
        """Return dated hotel offers near a point for the requested room occupants."""
        ...


def _name_key(name: str) -> str:
    """Normalize case, punctuation, and spacing for matching provider names to AI proposals."""
    return " ".join(re.findall(r"\w+", name.casefold()))


def _point(value: list[float]) -> list[float]:
    """Validate a [lat, lon] search point using the provider-coordinate rules."""
    return VerifiedPlace(provider_id="point", name="point", coordinates=value).coordinates


def _distance_miles(first: list[float], second: list[float]) -> float:
    """Return the geodesic distance in miles between two [lat, lon] points."""
    return geodesic(first, second).miles


def _parse_proposals(
    text: str, limit: int, *, diagnostics: dict | None = None
) -> list[ProposedPlace]:
    """Parse AI JSON into at most limit validated name-and-rating proposals.

    Optional JSON fences are removed; malformed responses and invalid entries are skipped.
    """
    diagnostics = diagnostics if diagnostics is not None else {}
    diagnostics.update(status="valid", received=0, valid=0, invalid=0, incomplete_vectors=0)
    if not isinstance(text, str):
        diagnostics["status"] = "invalid_shape"
        return []
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        diagnostics["status"] = "invalid_json"
        return []
    if isinstance(payload, dict):
        payload = payload.get("candidates")
    if not isinstance(payload, list):
        diagnostics["status"] = "invalid_shape"
        return []
    diagnostics["received"] = len(payload)
    proposals = []
    for item in payload[:limit]:
        try:
            proposals.append(ProposedPlace.model_validate(item))
        except (TypeError, ValueError):
            diagnostics["invalid"] += 1
            ratings = item.get("attribute_ratings") if isinstance(item, dict) else None
            if not isinstance(ratings, dict) or set(ATTRIBUTE_KEYS) - ratings.keys():
                diagnostics["incomplete_vectors"] += 1
            continue
    diagnostics["valid"] = len(proposals)
    diagnostics["status"] = (
        "empty_response"
        if not payload
        else "invalid_entries"
        if not proposals
        else "partial"
        if diagnostics["invalid"]
        else "valid"
    )
    return proposals


async def _propose(
    ai: LLMProvider,
    kind: str,
    point: list[float],
    limit: int,
    names: list[str] | None = None,
    *,
    diagnostics: dict | None = None,
    repair: bool = False,
) -> list[ProposedPlace]:
    """Request estimated place ratings, optionally restricted to source-record names.

    Returns a bounded list of valid proposals. AI provider failures raise
    CandidateProviderError; identity and offer verification happen separately.
    """
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
    if repair:
        prompt += (
            " The previous response contained no usable ratings for the supplied names. "
            "Return the exact supplied names and all 14 numeric attribute_ratings in [0,1]. "
            "Do not omit fields or add places. Return the requested JSON object only."
        )
    if names is not None:
        prompt += " Rate only these source-record names, preserving each exactly: " + json.dumps(
            names
        )

    async def generate():
        """Return the AI response using bounded worker execution and transient-failure retries."""
        with timed("generation"):
            return await retry_async(
                lambda: threaded(
                    "ai",
                    getattr(ai, "complete_once", ai.complete),
                    [
                        LLMMessage(role="system", content="Return strict JSON only."),
                        LLMMessage(role="user", content=prompt),
                    ],
                    [],
                ),
                "ai.ratings",
            )

    try:
        response = await singleflight(
            ("ratings", kind, tuple(point), tuple(names or []), repair), generate
        )
    except Exception as exc:
        raise CandidateProviderError("AI candidate provider unavailable") from exc
    return _parse_proposals(response.content, limit, diagnostics=diagnostics)


def _candidate(
    place: VerifiedPlace, proposal: ProposedPlace, weights: dict[str, float]
) -> dict[str, Any]:
    """Build one candidate record from provider facts, AI ratings, and trip weights.

    Returns identity and location fields, estimated category ratings, backend
    utility, and score contributions. AI prices, coordinates, and final scores
    are not used as provider facts.
    """
    ratings = proposal.attribute_ratings.model_dump()
    match = crossmatch(weights, ratings, already_normalized=True)
    profile = LocationProfile(
        **place.model_dump(
            include={
                "provider_id",
                "name",
                "coordinates",
                "address",
                "url",
                "categories",
                "activities",
                "description",
                "provider_rank",
                "source",
                "source_release",
                "source_attribution",
                "source_updated_at",
                "source_provenance",
            }
        ),
        attribute_ratings=proposal.attribute_ratings,
        provenance={
            "identity_source": place.provider_id.split(":", 1)[0],
            "ratings_source": "AI estimates; source records supply identity, not live verification",
            "verified_at": None,
        },
    )
    provider_fields = place.model_dump(exclude={"check_in_date", "price", "stars", "review_count"})
    return {**provider_fields, **profile.model_dump(), **match.model_dump()}


@in_run
async def attraction_candidates(
    raw_route: Any,
    plan: DiscoveryPlan,
    effective_weights: dict[str, float],
    *,
    ai: LLMProvider | None = None,
    places: PlaceProvider | None = None,
) -> DiscoveryResult:
    """Discover attractions along the baseline route and calculate their match scores.

    Inputs are the route, a bounded discovery plan, and effective interest weights.
    Returns a section-balanced candidate shortlist and discovery diagnostics.
    Road detour measurements are added by the planner after discovery completes.
    """
    weights = normalize_weights(effective_weights)
    if not plan.requested_stops:
        return DiscoveryResult([], {"plan": plan.snapshot(), "stop_reason": "zero_requested"})
    ai = ai or run_resource("rating_provider", build_default_chain)
    places = places or LivePlaceProvider()
    measure = RouteMeasure(raw_route)
    raw, rated, attempted, queried = {}, {}, set(), []
    observations, rounds = [], []
    used_coordinates = set()
    explanation = {
        "plan": plan.snapshot(),
        "queries": observations,
        "rounds": rounds,
        "rating_attempts": [],
        "eligibility_policy": "positive_utility",
        "calendar_eligibility_policy": "requested_trip_full_dwell_before_discovery_quotas"
        if plan.trip_calendar
        else "structurally_usable_source_calendar",
        "calendar_excluded_provider_ids": [],
    }
    record_explanation(discovery=explanation)
    ready = list(plan.queries)

    async def query(query):
        """Search one route point and return validated places with route projections."""
        emit(
            "attractions.query",
            "started",
            query=query.id,
            section=query.section_id,
            queries=plan.maximum_searches,
            adaptive=True,
        )
        point = _point(query.coordinates)

        async def lookup():
            """Fetch nearby provider records with query diagnostics, concurrency limits, and retries."""
            with stage("attractions.provider", query=query.id, section=query.section_id):
                return await retry_async(
                    lambda: limited(
                        "nearby",
                        lambda: (
                            places.attractions_near(
                                point, require_visit_calendar=True, trip_calendar=plan.trip_calendar
                            )
                            if isinstance(places, LivePlaceProvider)
                            else places.attractions_near(point)
                        ),
                    )
                )

        records = await singleflight(
            (
                "nearby",
                tuple(point),
                plan.trip_calendar.departure.isoformat() if plan.trip_calendar else None,
            ),
            lookup,
        )
        output, calendar_excluded = [], list(getattr(records, "calendar_excluded", ()))
        for rank, record in enumerate(records):
            try:
                place = VerifiedPlace.model_validate(record)
            except ValueError:
                continue
            if _distance_miles(point, place.coordinates) > _ATTRACTION_RADIUS_MI:
                continue
            if not await calendar_ok(place.model_dump(), before_estimate=True):
                calendar_excluded.append(place.provider_id)
                continue
            projection = measure.project(place.coordinates, query.progress_seconds)
            output.append(
                {
                    "place": place,
                    "section_id": plan.section(projection["route_progress_seconds"]),
                    "source_query_ids": [query.id],
                    "projection": projection,
                    "provider_rank": place.provider_rank or rank,
                    "fallback_visit_fits": await plan.trip_calendar.eligible(place.model_dump())
                    if plan.trip_calendar
                    else True,
                }
            )
        emit(
            "attractions.query",
            query=query.id,
            section=query.section_id,
            queries=plan.maximum_searches,
            adaptive=True,
            candidates=len(output),
        )
        return output, calendar_excluded

    async def calendar_ok(record, *, before_estimate=False):
        fits = (
            await plan.trip_calendar.eligible(
                record, dwell=MIN_VISIT_SECONDS if before_estimate else None
            )
            if plan.trip_calendar
            else calendar_eligible(record)
        )
        if not fits and not before_estimate:
            explanation["calendar_excluded_provider_ids"] = sorted(
                set(explanation["calendar_excluded_provider_ids"]) | {record["provider_id"]}
            )
        return fits

    async def rate(batch):
        """Rate a batch of verified places and return candidates with match scores."""
        point = batch[0]["place"].coordinates
        with stage(
            "attractions.ratings",
            candidates=len(batch),
            sections=sorted({item["section_id"] for item in batch}),
            queryIds=sorted({query for item in batch for query in item["source_query_ids"]}),
        ):
            attempts = []
            for attempt in range(2):
                validation = {}
                proposals = await _propose(
                    ai,
                    "attractions",
                    point,
                    MAX_PROPOSALS_PER_QUERY,
                    names=[item["place"].name for item in batch],
                    diagnostics=validation,
                    repair=bool(attempt),
                )
                by_name = {}
                for proposal in proposals:
                    by_name.setdefault(_name_key(proposal.name), proposal)
                expected = {_name_key(item["place"].name) for item in batch}
                matched = expected & by_name.keys()
                validation.update(
                    attempt=attempt + 1,
                    matched_sources=len(matched),
                    unmatched_names=len(by_name.keys() - expected),
                    missing_sources=len(expected - by_name.keys()),
                    match_status="matched"
                    if matched == expected
                    else "partial"
                    if matched
                    else "name_mismatch"
                    if by_name
                    else "no_valid_ratings",
                    source_query_ids=sorted(
                        {q for item in batch for q in item["source_query_ids"]}
                    ),
                )
                attempts.append(validation)
                if matched:
                    break
            if not matched:
                return [], attempts
        output = []
        for item in batch:
            place = item["place"]
            proposal = by_name.get(_name_key(place.name))
            if proposal is not None:
                candidate = _candidate(place, proposal, weights)
                candidate.update(
                    section_id=item["section_id"],
                    source_query_ids=item["source_query_ids"],
                    **item["projection"],
                )
                output.append(candidate)
        return await estimate_durations(output, weights, ai), attempts

    while ready:
        frozen_queries = []
        for query_item in ready:
            coordinate = tuple(round(v, 7) for v in query_item.coordinates)
            if coordinate in used_coordinates:
                continue
            used_coordinates.add(coordinate)
            frozen_queries.append(query_item)
        if not frozen_queries:
            break
        query_results = await joined([query(item) for item in frozen_queries])
        # Completion order never determines identity, category quotas or rating order.
        for query_item, (records, calendar_excluded) in zip(frozen_queries, query_results):
            queried.append(query_item)
            observations.append(
                {
                    **query_item.__dict__,
                    "verified_count": len(records) + len(calendar_excluded),
                    "calendar_eligible_count": len(records),
                    "calendar_excluded_count": len(calendar_excluded),
                }
            )
            explanation["calendar_excluded_provider_ids"] = sorted(
                set(explanation["calendar_excluded_provider_ids"]) | set(calendar_excluded)
            )
            for item in records:
                key = item["place"].provider_id
                if key in raw:
                    raw[key]["source_query_ids"] = sorted(
                        set(raw[key]["source_query_ids"] + item["source_query_ids"])
                    )
                else:
                    raw[key] = item
        ranked = []
        for section in range(plan.section_count):
            for order, item in enumerate(
                category_order([item for item in raw.values() if item["section_id"] == section])
            ):
                item["variety_order"] = order
                ranked.append(item)
        pool = balanced_pool(
            ranked,
            plan.raw_pool_cap,
            plan.section_count,
            lambda item: (
                not item["fallback_visit_fits"],
                item["variety_order"],
                item["place"].provider_id,
            ),
        )
        raw = {item["place"].provider_id: item for item in pool}
        remaining = plan.rating_cap - len(attempted)
        # Reserve a second candidate-cap of ratings for refinement.
        capacity = min(remaining, plan.candidate_cap)
        frozen = balanced_pool(
            [item for item in pool if item["place"].provider_id not in attempted],
            capacity,
            plan.section_count,
            lambda item: (
                not item["fallback_visit_fits"],
                item["variety_order"],
                item["place"].provider_id,
            ),
        )
        attempted.update(item["place"].provider_id for item in frozen)
        batches = [
            frozen[i : i + MAX_PROPOSALS_PER_QUERY]
            for i in range(0, len(frozen), MAX_PROPOSALS_PER_QUERY)
        ]
        round_record = {
            "queries": [item.id for item in frozen_queries],
            "rating_pool": [item["place"].provider_id for item in frozen],
        }
        rounds.append(round_record)
        results = await joined([rate(batch) for batch in batches])
        for batch_result, rating_attempts in results:
            explanation["rating_attempts"].extend(rating_attempts)
            for candidate in batch_result:
                rated[candidate["provider_id"]] = candidate
                emit(
                    "attractions.collected",
                    name=candidate["name"][:100],
                    collected=len(rated),
                    section=candidate["section_id"],
                )
        if frozen and not rated:
            explanation.update(
                stop_reason="rating_validation_failed",
                outcome="invalid_ratings",
                raw_pool_count=len(raw),
                successful_ratings=0,
                distinct_rated=len(attempted),
                eligible_count=0,
                shortlist_count=0,
            )
            with stage("attractions.ratings", candidates=len(frozen)):
                raise CandidateRatingError(CandidateRatingError.public_message)
        eligible = [
            item
            for item in rated.values()
            if eligible_utility(item["utility"]) and await calendar_ok(item)
        ]
        counts = [
            sum(item["section_id"] == i for item in eligible) for i in range(plan.section_count)
        ]
        round_record["eligible_by_section"] = counts
        emit(
            "attractions.round",
            eligible=len(eligible),
            rated=len(attempted),
            completed=len(queried),
            queries=plan.maximum_searches,
            adaptive=True,
        )
        if len(eligible) >= 3 * plan.requested_stops and all(counts):
            explanation["stop_reason"] = "eligible_target_and_sections_reached"
            break
        if len(attempted) >= plan.rating_cap:
            explanation["stop_reason"] = "rating_budget_exhausted"
            break
        if len(queried) >= plan.maximum_searches:
            explanation["stop_reason"] = "search_budget_exhausted"
            break
        ready = []
        for section in sorted(range(plan.section_count), key=lambda i: (counts[i], i)):
            lo = plan.baseline_seconds * section / plan.section_count
            hi = plan.baseline_seconds * (section + 1) / plan.section_count
            positions = sorted(
                [lo, hi] + [item.progress_seconds for item in queried if item.section_id == section]
            )
            intervals = sorted(
                zip(positions, positions[1:]), key=lambda pair: (-(pair[1] - pair[0]), pair[0])
            )
            for left, right in intervals:
                midpoint = (left + right) / 2
                coords = measure.position(midpoint)
                if tuple(round(v, 7) for v in coords) not in used_coordinates:
                    ready.append(
                        SearchQuery(f"s{section}-r{len(rounds)}", section, midpoint, coords)
                    )
                    break
            if len(queried) + len(ready) >= plan.maximum_searches:
                break
    explanation.setdefault("stop_reason", "no_distinct_search_points")
    eligible = [
        item
        for item in rated.values()
        if eligible_utility(item["utility"]) and await calendar_ok(item)
    ]
    for key, item in rated.items():
        if key in raw:
            item["source_query_ids"] = raw[key]["source_query_ids"]
    shortlist = balanced_pool(
        eligible,
        plan.candidate_cap,
        plan.section_count,
        lambda item: (-item["utility"], item["provider_id"]),
    )
    explanation.update(
        distinct_rated=len(attempted),
        successful_ratings=len(rated),
        raw_pool_count=len(raw),
        eligible_count=len(eligible),
        shortlist_count=len(shortlist),
        rated_candidates=list(rated.values()),
        sparse_sections=[
            i
            for i in range(plan.section_count)
            if not any(item["section_id"] == i for item in eligible)
        ],
        coverage_note="Five-mile nearby samples; intervals between samples are unsearched, not continuous coverage.",
        outcome="no_catalog_candidates"
        if not raw
        else "no_positive_utility"
        if not eligible
        else "eligible_candidates",
    )
    gaps = []
    for section in range(plan.section_count):
        positions = sorted(
            [
                plan.baseline_seconds * section / plan.section_count,
                plan.baseline_seconds * (section + 1) / plan.section_count,
            ]
            + [item.progress_seconds for item in queried if item.section_id == section]
        )
        gaps.append(
            {
                "section_id": section,
                "largest_unsearched_interval_seconds": max(
                    (b - a for a, b in zip(positions, positions[1:])), default=0
                ),
            }
        )
    explanation["unsearched_gaps"] = gaps
    return DiscoveryResult(shortlist, explanation)


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
    ai = ai or run_resource("rating_provider", build_default_chain)
    places = places or LivePlaceProvider()
    if isinstance(places, LivePlaceProvider):
        places.require_hotels()
    records = await places.hotels_near(point, check_in, price_range, room)
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


class CalendarFilteredPlaces(list):
    """Query-local exclusions, without mutable state shared by parallel queries."""

    def __init__(self, records, excluded):
        super().__init__(records)
        self.calendar_excluded = tuple(excluded)


class LivePlaceProvider:
    """Versioned catalog identities and independent dated hotel prices."""

    @staticmethod
    def require_hotels() -> None:
        """Require the geocoding key used to verify Google Hotels locations."""
        if not config.OPENCAGE_KEY:
            raise CandidateProviderError("Google Hotels location verification is not configured")

    async def attractions_near(
        self,
        point: list[float],
        *,
        require_visit_calendar: bool = False,
        trip_calendar: TripCalendar | None = None,
    ) -> list[VerifiedPlace]:
        """Read bounded source facts; these are not live venue verification."""
        if trip_calendar is not None:
            return await self._trip_attractions(point, trip_calendar)
        increment("catalog")
        try:
            calendar_filter = {"require_visit_calendar": True} if require_visit_calendar else {}
            records = await threaded(
                "catalog",
                repository.nearby,
                point,
                ["daytime"],
                radius_miles=_ATTRACTION_RADIUS_MI,
                limit=MAX_ATTRACTIONS,
                **calendar_filter,
            )
        except Exception:
            # Database exceptions can contain connection details. Do not retain them
            # in the public diagnostic exception chain.
            raise CandidateProviderError("Places catalog lookup unavailable") from None
        output = []
        for record in records[:MAX_ATTRACTIONS]:
            try:
                place = VerifiedPlace.model_validate(record)
                if (
                    "daytime" in place.categories
                    and _distance_miles(point, place.coordinates) <= _ATTRACTION_RADIUS_MI
                    and (not require_visit_calendar or calendar_eligible(place.model_dump()))
                ):
                    output.append(place)
            except (TypeError, ValueError):
                continue
        return output

    async def _trip_attractions(self, point, trip_calendar):
        """Bounded pages; only valid full-dwell candidates consume result slots."""
        output, tight, excluded, cursor = [], [], [], None
        while True:
            increment("catalog")
            try:
                page = await threaded(
                    "catalog",
                    repository.nearby_page,
                    point,
                    ["daytime"],
                    radius_miles=_ATTRACTION_RADIUS_MI,
                    limit=MAX_ATTRACTIONS,
                    require_visit_calendar=True,
                    cursor=cursor,
                )
            except Exception:
                raise CandidateProviderError("Places catalog lookup unavailable") from None
            for record in page.records:
                try:
                    place = VerifiedPlace.model_validate(record)
                except (TypeError, ValueError):
                    continue
                if (
                    "daytime" not in place.categories
                    or _distance_miles(point, place.coordinates) > _ATTRACTION_RADIUS_MI
                ):
                    continue
                if not await trip_calendar.eligible(place.model_dump(), dwell=MIN_VISIT_SECONDS):
                    excluded.append(place.provider_id)
                    continue
                if await trip_calendar.eligible(place.model_dump()):
                    output.append(place)
                elif len(tight) < MAX_ATTRACTIONS:
                    tight.append(place)
                if len(output) == MAX_ATTRACTIONS:
                    return CalendarFilteredPlaces(output, excluded)
            cursor = page.next_cursor
            if cursor is None:
                return CalendarFilteredPlaces((output + tight)[:MAX_ATTRACTIONS], excluded)

    async def hotels_near(
        self,
        point: list[float],
        check_in: date,
        price_range: tuple[tuple[float, float], str],
        room: HotelRoom,
    ) -> list[VerifiedHotel]:
        """Fetch and validate Google Hotels offers for a location, date, and room.

        The price range is advisory, so usable offers above the target are retained.
        """
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


@in_run
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
    ai = ai or run_resource("rating_provider", build_default_chain)
    places = places or LivePlaceProvider()

    async def room_lookup(room):
        """Fetch scored offers for one room, sharing identical requests within the current run."""
        key = (
            "room",
            tuple(overnight_position),
            str(check_in_date),
            room.adults,
            tuple(room.child_ages),
        )
        return await singleflight(
            key,
            lambda: _room_candidates(
                overnight_position,
                check_in_date,
                price_range,
                effective_weights,
                room,
                ai=ai,
                places=places,
            ),
        )

    room_results = await joined([room_lookup(room) for room in rooms])
    if any(not candidates for candidates in room_results):
        return []
    by_room = [{item["provider_id"]: item for item in candidates} for candidates in room_results]
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
