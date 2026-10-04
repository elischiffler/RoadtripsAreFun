"""The per-chat trip profile — the data object the AI fills in during a chat.

``TripProfile`` is the structured, per-``(user_id, chat_id)`` record of a single
trip's details. It is THE object the agent reads and writes as the conversation
gathers the trip: start, destination, number of stops, nightly hotel budget,
optional start date, and an optional car (used to default fuel-cost estimates).
Unlike a cross-chat user profile, a fresh chat starts with an empty trip profile.

Every field is validated, so anything read off the profile is safe to pass into
``Route_Payload`` / the car API (e.g. defaulting ``num_stops`` / ``budget`` when
the traveler doesn't restate them later in the same chat).

Persistence reuses the existing ``chat_memory`` table: the whole trip profile
round-trips through a single per-chat row (``mem_type='trip'``, real ``chat_id``),
mirroring how the previous user profile used a single ``fact`` row.
``from_json`` / ``to_json`` do the mapping so the DB layer only ever sees JSON.

Updates are partial: validated trip details and trip-only persona changes use
:class:`TripProfileUpdate` (all fields optional); :meth:`TripProfile.merged_with`
applies only the provided fields and re-validates the result.
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator

from app.agent.persona import validate_weight_update
from app.agent.trip_dates import normalize_departure_time
from app.utils.location_resolution import PendingLocation

logger = logging.getLogger(__name__)

# Bounds mirrored from the routing contract (num_stops is validated 1..10).
MIN_STOPS = 1
MAX_STOPS = 10
CarStatus = Literal["unanswered", "skipped", "provided"]


class Car(BaseModel):
    """A vehicle for the trip, for fuel-cost estimation."""

    year: int
    make: str
    model: str

    @field_validator("year")
    @classmethod
    def _year_sane(cls, v: int) -> int:
        # FuelEconomy.gov data starts at 1984; guard obviously-bad years.
        if not (1984 <= v <= 2100):
            raise ValueError("car.year must be between 1984 and 2100")
        return v

    @field_validator("make", "model")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("car.make and car.model must be non-empty")
        return v


def _validate_coords(v: list[float] | None) -> list[float] | None:
    """Validate a ``[lat, lon]`` pair (the app-wide coordinate convention)."""
    if v is None:
        return None
    if len(v) != 2:
        raise ValueError("coordinates must be a [lat, lon] pair")
    lat, lon = float(v[0]), float(v[1])
    if not (math.isfinite(lat) and math.isfinite(lon)):
        raise ValueError("coordinates must be finite")
    if not (-90.0 <= lat <= 90.0):
        raise ValueError("latitude must be between -90 and 90")
    if not (-180.0 <= lon <= 180.0):
        raise ValueError("longitude must be between -180 and 180")
    return [lat, lon]


def _blank_to_none(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip()
    return v or None


class TripProfile(BaseModel):
    """The complete, validated per-chat trip profile.

    All fields optional (a brand-new chat has an empty trip profile). Reads off
    this model are safe to feed into the routing / car APIs.
    """

    start_address: str | None = None
    start_coords: list[float] | None = None  # [lat, lon]
    start_timezone: str | None = None  # IANA name from the start geocode
    destination_address: str | None = None
    destination_coords: list[float] | None = None  # [lat, lon]
    num_stops: int | None = None  # 1..10
    budget: float | None = None  # nightly hotel budget, USD
    start_date: str | None = None  # canonical ISO-8601 departure with UTC offset
    departure_time: str | None = None  # selected local HH:MM, retained before date
    car: Car | None = None
    persona_weights: dict[str, float] | None = None  # partial, per-trip override
    car_status: CarStatus = "unanswered"
    pending_locations: dict[Literal["start_address", "destination_address"], PendingLocation] = (
        Field(default_factory=dict)
    )

    @model_validator(mode="before")
    @classmethod
    def _coerce_coords(cls, data):
        # Existing profiles predate the separately saved time choice. Recover
        # their selected local time from the canonical departure when possible.
        if isinstance(data, dict) and data.get("start_date") and not data.get("departure_time"):
            try:
                departure = datetime.fromisoformat(data["start_date"])
                data = {**data, "departure_time": departure.strftime("%H:%M")}
            except (TypeError, ValueError):
                pass
        # Profiles saved before car_status existed may already have a car.
        if isinstance(data, dict) and "car_status" not in data and data.get("car"):
            data = {**data, "car_status": "provided"}
        # Older saved profiles may contain coordinates serialized as JSON strings.
        # New updates must use geocoded numeric arrays and are validated strictly.
        if isinstance(data, dict):
            for key in ("start_coords", "destination_coords"):
                if isinstance(data.get(key), str):
                    try:
                        data = {**data, key: json.loads(data[key])}
                    except ValueError:
                        pass
        return data

    @model_validator(mode="after")
    def _car_consistent(self):
        if (self.car_status == "provided") != (self.car is not None):
            raise ValueError("car_status must be provided exactly when car details are present")
        return self

    @field_validator("start_coords", "destination_coords")
    @classmethod
    def _coords(cls, v):
        return _validate_coords(v)

    @field_validator("num_stops")
    @classmethod
    def _stops(cls, v):
        if v is None:
            return None
        if not (MIN_STOPS <= v <= MAX_STOPS):
            raise ValueError(f"num_stops must be between {MIN_STOPS} and {MAX_STOPS}")
        return v

    @field_validator("budget")
    @classmethod
    def _budget(cls, v):
        if v is None:
            return None
        v = float(v)
        if not math.isfinite(v) or v < 0:
            raise ValueError("budget must be non-negative")
        return v

    @field_validator("start_address", "destination_address", "start_date")
    @classmethod
    def _blanks(cls, v):
        return _blank_to_none(v)

    @field_validator("departure_time")
    @classmethod
    def _departure_time(cls, v):
        return normalize_departure_time(v) if v is not None else None

    @field_validator("persona_weights", mode="before")
    @classmethod
    def _persona_weights(cls, v):
        return validate_weight_update(v) if v is not None else None

    @field_validator("start_timezone")
    @classmethod
    def _timezone(cls, v):
        if v is None:
            return None
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, TypeError) as exc:
            raise ValueError("start_timezone must be a valid IANA timezone") from exc
        return v

    def merged_with(self, update: TripProfileUpdate) -> TripProfile:
        """Return a new trip profile with ``update``'s provided fields applied.

        Scalars overwrite. Only fields the update actually set are touched
        (``exclude_unset``), so a single field can be sent without clobbering the
        rest. The result is re-validated.
        """
        provided = update.model_dump(exclude_unset=True)
        data = self.model_dump()
        for key, value in provided.items():
            if value is None:
                continue
            data[key] = value
        if "car" in provided and provided["car"] is not None:
            data["car_status"] = "provided"
        elif provided.get("car_status") in {"skipped", "unanswered"}:
            data["car"] = None
        return TripProfile.model_validate(data)

    def is_empty(self) -> bool:
        """True when nothing has been gathered for this trip yet."""
        if self.car_status != "unanswered":
            return False
        d = self.model_dump(exclude_none=True)
        d.pop("car_status", None)
        return not any(v for v in d.values())

    # --- JSON mapping (stored as one per-chat 'trip' memory row) -----------

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"))

    @classmethod
    def from_json(cls, raw: str | None) -> TripProfile:
        """Build a trip profile from its stored JSON string.

        Invalid/empty JSON degrades to an empty profile (logged) rather than
        raising, so a corrupt row never breaks a turn.
        """
        if not raw:
            return cls()
        try:
            return cls.model_validate(json.loads(raw))
        except Exception as exc:
            logger.warning("TripProfile.from_json: invalid stored trip profile: %s", exc)
            return cls()


class TripProfileUpdate(BaseModel):
    """Validated partial trip-profile update.

    Every field optional; ``model_dump(exclude_unset=True)`` in
    :meth:`TripProfile.merged_with` distinguishes "not provided" from "set to
    null". Reuses ``TripProfile``'s validators by mirroring its field types.

    The car may be given either as a nested ``car`` object OR as flat
    ``car_year`` / ``car_make`` / ``car_model`` fields — models reliably emit the
    flat form — so a ``before`` validator folds them into ``car``.
    """

    start_address: str | None = None
    start_coords: list[float] | None = None
    destination_address: str | None = None
    destination_coords: list[float] | None = None
    num_stops: int | None = None
    budget: float | None = None
    start_date: str | None = None
    car: Car | None = None
    persona_weights: dict[str, float] | None = None
    car_status: CarStatus | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_flat_car(cls, data):
        """Fold flat ``car_year`` / ``car_make`` / ``car_model`` into ``car``."""
        if not isinstance(data, dict):
            return data
        data = data.copy()
        flat = {
            "year": data.get("car_year"),
            "make": data.get("car_make"),
            "model": data.get("car_model"),
        }
        if any(v is not None for v in flat.values()) and not data.get("car"):
            data = {k: v for k, v in data.items() if k not in ("car_year", "car_make", "car_model")}
            data["car"] = {k: v for k, v in flat.items() if v is not None}
        return data

    @model_validator(mode="after")
    def _car_update_consistent(self):
        if self.car is not None and self.car_status in {"skipped", "unanswered"}:
            raise ValueError("choose either car details or a skipped/unanswered car status")
        return self

    @field_validator("start_coords", "destination_coords")
    @classmethod
    def _coords(cls, v):
        return _validate_coords(v)

    @field_validator("num_stops")
    @classmethod
    def _stops(cls, v):
        if v is None:
            return None
        if not (MIN_STOPS <= v <= MAX_STOPS):
            raise ValueError(f"num_stops must be between {MIN_STOPS} and {MAX_STOPS}")
        return v

    @field_validator("budget")
    @classmethod
    def _budget(cls, v):
        if v is None:
            return None
        v = float(v)
        if not math.isfinite(v) or v < 0:
            raise ValueError("budget must be non-negative")
        return v

    @field_validator("persona_weights", mode="before")
    @classmethod
    def _persona_weights(cls, v):
        return validate_weight_update(v) if v is not None else None

    @model_validator(mode="after")
    def _at_least_one(self):
        if not self.model_dump(exclude_unset=True):
            raise ValueError("update_trip_profile requires at least one field")
        return self
