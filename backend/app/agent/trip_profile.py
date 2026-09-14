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

Updates are partial: the ``update_trip_profile`` tool sends a
:class:`TripProfileUpdate` (all fields optional); :meth:`TripProfile.merged_with`
applies only the provided fields and re-validates the result.
"""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, field_validator, model_validator

logger = logging.getLogger(__name__)

# Bounds mirrored from the routing contract (num_stops is validated 1..10).
MIN_STOPS = 1
MAX_STOPS = 10


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


# The coordinate fields that may arrive stringified from the model.
_COORD_FIELDS = ("start_coords", "destination_coords")


def _coerce_stringified_coords(data):
    """Normalize model-supplied coordinate values, in place.

    Two model quirks are handled here (a ``before`` validator):

    1. A JSON-string array — ``"destination_coords": "[36.17, -115.14]"`` — is
       parsed into a real list so the common case works without a retry.
    2. A non-numeric PLACEHOLDER string — ``"[await result]"``, ``"<coords>"``,
       ``"[lat, lon]"`` — which happens when the model tries to fill coords
       before it has a ``validate_location`` result. There is no correct
       conversion for these, so we DROP just that field (logged) rather than
       failing the whole ``update_trip_profile`` call. That way a valid sibling
       field (e.g. ``start_address``) in the same update still saves, and the
       model simply hasn't recorded coordinates yet.

    A string that parses to a list but is an invalid coordinate (out of range,
    wrong length) is left intact so the strict field validator rejects it loudly
    — we only drop values that are clearly placeholders, never plausible data.
    """
    if not isinstance(data, dict):
        return data
    for key in _COORD_FIELDS:
        value = data.get(key)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except ValueError:
                # Not JSON at all -> a placeholder, not coordinates. Drop it so
                # the rest of the update can still apply.
                logger.warning(
                    "trip_profile: dropping non-coordinate %s placeholder %r "
                    "(no validate_location result yet).",
                    key,
                    value,
                )
                data.pop(key, None)
                continue
            data[key] = parsed
    return data


class TripProfile(BaseModel):
    """The complete, validated per-chat trip profile.

    All fields optional (a brand-new chat has an empty trip profile). Reads off
    this model are safe to feed into the routing / car APIs.
    """

    start_address: str | None = None
    start_coords: list[float] | None = None  # [lat, lon]
    destination_address: str | None = None
    destination_coords: list[float] | None = None  # [lat, lon]
    num_stops: int | None = None  # 1..10
    budget: float | None = None  # nightly hotel budget, USD
    start_date: str | None = None  # ISO-8601 trip start (free-form; validated on use)
    car: Car | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_coords(cls, data):
        return _coerce_stringified_coords(data)

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
        if v < 0:
            raise ValueError("budget must be non-negative")
        return v

    @field_validator("start_address", "destination_address", "start_date")
    @classmethod
    def _blanks(cls, v):
        return _blank_to_none(v)

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
        return TripProfile.model_validate(data)

    def is_empty(self) -> bool:
        """True when nothing has been gathered for this trip yet."""
        d = self.model_dump(exclude_none=True)
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
    """Partial trip-profile update sent by the ``update_trip_profile`` tool.

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

    @model_validator(mode="before")
    @classmethod
    def _coerce_flat_car(cls, data):
        """Fold flat ``car_year`` / ``car_make`` / ``car_model`` into ``car``."""
        if not isinstance(data, dict):
            return data
        flat = {
            "year": data.get("car_year"),
            "make": data.get("car_make"),
            "model": data.get("car_model"),
        }
        if any(v is not None for v in flat.values()) and not data.get("car"):
            data = {k: v for k, v in data.items() if k not in ("car_year", "car_make", "car_model")}
            data["car"] = {k: v for k, v in flat.items() if v is not None}
        return data

    @model_validator(mode="before")
    @classmethod
    def _coerce_coords(cls, data):
        """Parse stringified coordinate arrays (a common model output) into lists."""
        return _coerce_stringified_coords(data)

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
        if v < 0:
            raise ValueError("budget must be non-negative")
        return v

    @model_validator(mode="after")
    def _at_least_one(self):
        if not self.model_dump(exclude_unset=True):
            raise ValueError("update_trip_profile requires at least one field")
        return self
