"""Bounded read-only route hints; never eligibility, quotes or a saved itinerary."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.guided_planning import AlternativePlace, Latitude, Longitude
from app.models.scheduling_policy import SchedulingPolicy


class RoutePreparationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    geometry: list[tuple[Longitude, Latitude]] = Field(min_length=2, max_length=10000)
    driving_seconds: float = Field(ge=0, le=63 * 86400, allow_inf_nan=False, strict=True)
    departure_clock: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")
    scheduling_policy: SchedulingPolicy = Field(default_factory=SchedulingPolicy)


class TentativeStayArea(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    coordinates: tuple[Latitude, Longitude]
    label: str
    route_fraction: float = Field(ge=0, le=1)
    driving_seconds_before: float = Field(ge=0)
    meal_allowance_seconds: int = Field(ge=0)
    day_index: int = Field(ge=0)
    pause_clock: str
    tentative: Literal[True] = True
    hotel_quotes_checked: Literal[False] = False
    availability_checked: Literal[False] = False
    clock_basis: Literal["departure_wall_clock_estimate"] = "departure_wall_clock_estimate"
    notice: str


class RoutePreparationResponse(BaseModel):
    places: list[AlternativePlace] = Field(default_factory=list, max_length=12)
    possible_overnight_areas: list[TentativeStayArea] = Field(default_factory=list, max_length=3)
    sections_checked: int = Field(ge=0, le=6)
    sections_failed: int = Field(ge=0, le=6)
    catalog_status: Literal["ready", "partial", "unavailable"]
    notice: str
