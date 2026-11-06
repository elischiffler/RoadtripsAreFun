"""Bounded read-only browsing contracts for the ordinary signed-in trip flow."""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field

Latitude = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=-90, le=90)]
Longitude = Annotated[float, Field(strict=True, allow_inf_nan=False, ge=-180, le=180)]
PlaceId = Annotated[str, Field(strict=True, min_length=1, max_length=512)]


class RouteAlternativesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    points: list[tuple[Latitude, Longitude]] = Field(min_length=1, max_length=8)
    exclude_ids: list[PlaceId] = Field(default_factory=list, max_length=100)


class AlternativePlace(BaseModel):
    id: PlaceId
    provider_id: PlaceId
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
