"""Validated optional car changes for an existing trip."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.agent.trip_profile import Car


class TripCarChoices(BaseModel):
    model_config = ConfigDict(extra="forbid")
    car_status: Literal["skipped", "provided"]
    car: Car | None = None

    @model_validator(mode="after")
    def consistent_car(self):
        if (self.car_status == "provided") != (self.car is not None):
            raise ValueError("Provide car details exactly when using a car")
        if self.car and (len(self.car.make) > 100 or len(self.car.model) > 100):
            raise ValueError("Car make and model must be at most 100 characters")
        return self


class TripCarUpdate(TripCarChoices):
    # Prevent a stale editor from changing a new trip that reused a legacy UI ID.
    expected_agent_chat_id: str | None = Field(default=None, min_length=1, max_length=128)
