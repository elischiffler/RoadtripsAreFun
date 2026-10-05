"""Pure trip/location crossmatching; subjective ratings are never provider facts."""

import math

from pydantic import BaseModel, ConfigDict, create_model, field_validator

from app.agent.persona import ATTRIBUTE_KEYS, normalize_weights


class _RatingFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before", check_fields=False)
    @classmethod
    def unit_interval(cls, value):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("attribute ratings must be numbers in [0, 1]")
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("attribute ratings must be numbers in [0, 1]")
        return float(value)


# Generate the typed fields from the authoritative interest vocabulary.
AttributeRatings = create_model(
    "AttributeRatings", __base__=_RatingFields, **dict.fromkeys(ATTRIBUTE_KEYS, (float, ...))
)


class MatchContribution(BaseModel):
    attribute: str
    weight: float
    rating: float
    contribution: float


class ProfileMatch(BaseModel):
    utility: float
    contributions: list[MatchContribution]


def crossmatch(
    weights: dict[str, float], ratings: dict[str, float], *, already_normalized: bool = False
) -> ProfileMatch:
    """Return the same normalized dot product used as the solver's input."""
    normalized = normalize_weights(weights)
    if already_normalized:
        if not math.isclose(math.fsum(weights.values()), 1.0, abs_tol=1e-12):
            raise ValueError("effective weights must sum to one")
        # Live candidate sources already normalized once. Preserve their exact
        # floating-point arithmetic before integer objective rounding.
        normalized = weights
    values = AttributeRatings.model_validate(ratings).model_dump()
    contributions = [
        MatchContribution(
            attribute=key,
            weight=normalized[key],
            rating=values[key],
            contribution=normalized[key] * values[key],
        )
        for key in ATTRIBUTE_KEYS
    ]
    return ProfileMatch(
        utility=min(1.0, max(0.0, math.fsum(item.contribution for item in contributions))),
        contributions=contributions,
    )
