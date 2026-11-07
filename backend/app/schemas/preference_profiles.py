"""Explicit reusable trip choices. No endpoints, dates, occupants or inferred memory."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.agent.persona import ATTRIBUTE_KEYS, normalize_weights
from app.agent.trip_profile import Car
from app.models.scheduling_policy import SchedulingPolicy


class PreferenceChoices(BaseModel):
    model_config = ConfigDict(extra="forbid")

    car_status: Literal["skipped", "provided"]
    car: Car | None = None
    scheduling_policy: SchedulingPolicy = Field(default_factory=SchedulingPolicy)
    # This is the traveler-reviewed final per-trip vector, never account memory.
    persona_weights: dict[str, float]

    @field_validator("persona_weights", mode="before")
    @classmethod
    def weights(cls, value):
        # Check before coercion so booleans/strings cannot become numeric weights.
        return normalize_weights(value)

    @model_validator(mode="after")
    def consistent_car(self):
        if (self.car_status == "provided") != (self.car is not None):
            raise ValueError("Provide a car exactly when car_status is provided")
        if self.car and (len(self.car.make) > 100 or len(self.car.model) > 100):
            raise ValueError("Car make and model must be at most 100 characters")
        if set(self.persona_weights) != set(ATTRIBUTE_KEYS):
            raise ValueError("All interests are required")
        return self


class PreferenceProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80)
    choices: PreferenceChoices

    @field_validator("name")
    @classmethod
    def clean_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Enter a profile name")
        return value


class PreferenceProfile(PreferenceProfileInput):
    id: UUID
