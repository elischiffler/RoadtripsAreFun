"""Bounded provider candidates; precision scores do not prove traveler intent."""

import re
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.agent.trip_dates import timezone_from_location
from app.utils.geolocation_helpers import get_location


class LocationCandidate(BaseModel):
    id: str
    address: str = Field(min_length=1, max_length=1000)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    timezone: str | None = None

    @field_validator("address")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Empty address")
        return value


class PendingLocation(BaseModel):
    query: str = Field(max_length=1000)
    candidates: list[LocationCandidate] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def prefer_matching_address(self):
        """Prefer an address starting with the supplied place/region; keep every choice."""
        query_words = re.findall(r"\w+", self.query.casefold())
        if query_words:
            self.candidates.sort(
                key=lambda candidate: (
                    re.findall(r"\w+", candidate.address.casefold())[: len(query_words)]
                    != query_words
                )
            )
        return self


LocationField = Literal["start_address", "destination_address"]


class LocationConfirmation(BaseModel):
    field: LocationField
    candidateId: str = Field(min_length=1, max_length=100)


def resolve_location(geocoder, address: str, *, lookup=get_location) -> PendingLocation:
    if not isinstance(address, str) or not address.strip() or len(address) > 1000:
        raise ValueError("Provide a city and state or a specific address.")
    query = address.strip()
    matches = lookup(geocoder=geocoder, address=query, exactly_one=False)
    if matches is None:
        matches = []
    elif not isinstance(matches, list):
        matches = [matches]
    candidates = []
    seen = set()
    for location in matches[:5]:
        try:
            candidate = LocationCandidate(
                id=str(uuid4()),
                address=location.address,
                latitude=location.latitude,
                longitude=location.longitude,
                timezone=timezone_from_location(location),
            )
        except (ValidationError, AttributeError, TypeError, ValueError):
            continue
        key = (
            candidate.address.casefold(),
            round(candidate.latitude, 5),
            round(candidate.longitude, 5),
        )
        if key not in seen:
            seen.add(key)
            candidates.append(candidate)
    return PendingLocation(query=query, candidates=candidates)


def needs_confirmation(resolution: PendingLocation) -> bool:
    return len(resolution.candidates) != 1 or bool(re.fullmatch(r"[A-Za-z]{2,3}", resolution.query))
