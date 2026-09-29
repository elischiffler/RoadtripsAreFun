"""Authoritative account persona weights and per-trip override rules."""

from __future__ import annotations

import math
from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, field_validator

ATTRIBUTE_KEYS = (
    "scenery",
    "nature",
    "hiking_outdoors",
    "food",
    "history",
    "culture_arts",
    "nightlife",
    "shopping",
    "beaches_water",
    "adventure",
    "relaxation",
    "unique_local_experiences",
    "family_friendliness",
    "crowd_avoidance",
)
_KEY_SET = frozenset(ATTRIBUTE_KEYS)


def validate_weight_update(values: Mapping[str, float]) -> dict[str, float]:
    """Validate a supplied partial update before merging it with a baseline."""
    if not isinstance(values, Mapping) or not values:
        raise ValueError("persona weights must contain at least one attribute")
    unknown = set(values) - _KEY_SET
    if unknown:
        raise ValueError(f"unknown persona attributes: {', '.join(sorted(unknown))}")
    result = {}
    for key, value in values.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"persona weight {key} must be a finite number")
        number = float(value)
        if not math.isfinite(number) or number < 0:
            raise ValueError(f"persona weight {key} must be finite and non-negative")
        result[key] = number
    if not any(result.values()):
        raise ValueError("supplied persona weights cannot all be zero")
    return result


def normalize_weights(values: Mapping[str, float]) -> dict[str, float]:
    """Normalize a complete set of canonical weights to sum to one."""
    supplied = validate_weight_update(values)
    if set(supplied) != _KEY_SET:
        raise ValueError("persona weights must contain every canonical attribute")
    total = math.fsum(supplied.values())
    if not math.isfinite(total) or total <= 0:
        raise ValueError("persona weight total must be finite and positive")
    return {key: supplied[key] / total for key in ATTRIBUTE_KEYS}


def default_weights() -> dict[str, float]:
    """Equal account baseline when a user has not set a persona."""
    return {key: 1.0 / len(ATTRIBUTE_KEYS) for key in ATTRIBUTE_KEYS}


def merge_weights(baseline: Mapping[str, float], update: Mapping[str, float]) -> dict[str, float]:
    """Apply supplied fields to a complete baseline, then normalize."""
    current = normalize_weights(baseline)
    return normalize_weights({**current, **validate_weight_update(update)})


def effective_weights(
    baseline: Mapping[str, float] | None, trip_override: Mapping[str, float] | None = None
) -> dict[str, float]:
    """Trip fields take precedence; an absent override uses the account baseline."""
    account = normalize_weights(baseline) if baseline is not None else default_weights()
    return merge_weights(account, trip_override) if trip_override else account


class PersonaWeightUpdate(BaseModel):
    """Strict partial weights accepted from a chat update."""

    model_config = ConfigDict(extra="forbid")

    weights: dict[str, float]

    @field_validator("weights", mode="before")
    @classmethod
    def _validate_weights(cls, value):
        return validate_weight_update(value)


class AccountPersona(BaseModel):
    """One normalized, complete cross-chat baseline for an authenticated user."""

    model_config = ConfigDict(extra="forbid")

    weights: dict[str, float]

    @field_validator("weights", mode="before")
    @classmethod
    def _normalize(cls, value) -> dict[str, float]:
        return normalize_weights(value)

    @classmethod
    def default(cls) -> AccountPersona:
        return cls(weights=default_weights())

    def merged_with(self, update: PersonaWeightUpdate) -> AccountPersona:
        return AccountPersona(weights=merge_weights(self.weights, update.weights))
