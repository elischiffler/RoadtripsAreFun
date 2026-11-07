"""Bounded read-only browsing contracts for the ordinary signed-in trip flow."""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.place_context import PlaceContext

Latitude = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=-90, le=90)]
Longitude = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=-180, le=180)]
PlaceId = Annotated[str, Field(strict=True, min_length=1, max_length=512)]


class RouteAlternativesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points: list[tuple[Latitude, Longitude]] = Field(default_factory=list, max_length=8)
    geometry: list[tuple[Longitude, Latitude]] | None = Field(
        default=None, min_length=2, max_length=10000
    )
    exclude_coordinates: list[tuple[Latitude, Longitude]] = Field(
        default_factory=list, max_length=100
    )

    @model_validator(mode="after")
    def has_route(self):
        if not self.points and self.geometry is None:
            raise ValueError("Route geometry or search points are required")
        return self

    exclude_ids: list[PlaceId] = Field(default_factory=list, max_length=100)


class AlternativePlace(BaseModel):
    id: PlaceId
    provider_id: PlaceId
    place_context: PlaceContext | None = None
    offset_miles: float | None = None
    route_fraction: float | None = None
    detour_minutes: float | None = None
    source: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=1000)
    coordinates: tuple[Latitude, Longitude]
    address: str | None = Field(default=None, max_length=2000)
    url: str | None = Field(default=None, max_length=4096)
    categories: list[str] = Field(default_factory=list, max_length=32)
    source_attribution: str | None = Field(default=None, max_length=8000)
    source_release: str | None = Field(default=None, max_length=1000)
    source_updated_at: str | None = Field(default=None, max_length=1000)
    source_provenance: list[dict[str, Any]] = Field(default_factory=list, max_length=8)


class RouteAlternativesResponse(BaseModel):
    places: list[AlternativePlace] = Field(max_length=12)
    notice: str
    coverage: dict[str, Any] | None = None
