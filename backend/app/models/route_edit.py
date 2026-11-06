"""Bounded edit previews; persistence remains an explicit caller action."""

import json
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from app.models.guided_planning import Latitude, Longitude, PlaceId
from app.models.itinerary_models import Itinerary_Day
from app.models.routing_models.routing_models import Mapbox_geo, Route, Route_Step
from app.models.trip_limits import MAPBOX_MAX_COORDINATES

Coordinate = tuple[Latitude, Longitude]
_coordinate = TypeAdapter(Coordinate)


class EditGeometry(Mapbox_geo):
    model_config = ConfigDict(extra="forbid")
    coordinates: list[tuple[Longitude, Latitude]] = Field(min_length=2, max_length=100000)


class EditableRoute(Route):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    coordinates: list[Coordinate] = Field(min_length=2, max_length=MAPBOX_MAX_COORDINATES)
    geometry: EditGeometry
    stops: list[dict] = Field(min_length=1, max_length=MAPBOX_MAX_COORDINATES - 1)
    steps: list[Route_Step] = Field(max_length=10000)
    distance: float = Field(ge=0)
    duration: float = Field(ge=0)
    cost: float = Field(ge=0)

    @field_validator("stops")
    @classmethod
    def valid_stops(cls, values):
        if len(json.dumps(values, allow_nan=False)) > 500000:
            raise ValueError("Saved stop metadata is too large")
        for stop in values:
            _coordinate.validate_python(stop.get("coordinates"))
            if stop.get("type") not in {"stop", "hotel", "end"}:
                raise ValueError("Unsupported saved stop type; replan this trip")
            if not isinstance(stop.get("name"), str) or not 1 <= len(stop["name"]) <= 1000:
                raise ValueError("Each stop requires a bounded name")
            duration = stop.get("duration")
            if (
                isinstance(duration, bool)
                or not isinstance(duration, (float, int))
                or not math.isfinite(duration)
                or duration < 0
            ):
                raise ValueError("Each stop requires a finite nonnegative leg duration")
        return values

    @model_validator(mode="after")
    def consistent_route(self):
        if self.stops[-1]["type"] != "end" or any(s["type"] == "end" for s in self.stops[:-1]):
            raise ValueError("Route requires exactly one terminal destination")
        if len(self.coordinates) != len(self.stops) + 1 or any(
            tuple(stop["coordinates"]) != coordinate
            for stop, coordinate in zip(self.stops, self.coordinates[1:], strict=True)
        ):
            raise ValueError("Saved route coordinates and stop sequence disagree")
        return self


class RouteEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    route: EditableRoute
    provider_id: PlaceId
    action: Literal["add", "replace"]
    stop_index: int = Field(strict=True, ge=0, le=MAPBOX_MAX_COORDINATES - 2)
    include_meal_slots: bool = Field(default=False, strict=True)


class RouteEditResponse(BaseModel):
    route: Route
    itinerary: list[Itinerary_Day]
    notice: str = "Preview only. Save to apply this itinerary. Hotel quotes and reservations have not been refreshed."
