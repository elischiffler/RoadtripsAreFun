"""Explicit account-only candidate assessment and mode-confirmation contracts."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.route_preparation import TentativeStayArea
from app.models.routing_models.routing_models import Route, Route_Payload
from app.routing.occupancy import HotelRooms, TravelerCount, require_occupancy


class AssessmentRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID


class CandidateRequest(Route_Payload):
    request_id: UUID
    reserve_meal_slots: Literal[True] = True
    budget: float = Field(default=0, ge=0, allow_inf_nan=False)


class OneDayAssessment(BaseModel):
    eligible: bool
    elapsed_seconds: float | None = None
    threshold_seconds: int = 43200
    reason_code: str | None = None
    reason: str | None = None


class CandidateResponse(BaseModel):
    candidate_id: str
    input_key: str
    expires_at: datetime
    one_day: OneDayAssessment
    candidate_route: Route | None = None
    possible_overnight_areas: list[TentativeStayArea] = Field(default_factory=list, max_length=3)


class CandidateConfirmation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    trip_mode: Literal["one_day", "overnight"]
    budget: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    traveler_count: TravelerCount | None = None
    hotel_rooms: HotelRooms | None = None

    @model_validator(mode="after")
    def mode_inputs(self):
        if self.trip_mode == "overnight":
            require_occupancy(self.traveler_count, self.hotel_rooms)
            if self.budget is None:
                raise ValueError("Provide a nightly room budget for the overnight option")
        elif self.budget is not None or self.hotel_rooms is not None:
            raise ValueError("One-day confirmation does not take hotel inputs")
        return self
