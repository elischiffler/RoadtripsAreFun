"""One bounded visit duration shared by planning, validation and presentation.

Missing metadata retains the two-hour policy used by saved trips. Explicit but
malformed metadata fails validation rather than shortening an already planned
visit. These are planning estimates, never published venue facts.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, ValidationError

from app.routing.base import PlanningError

MIN_VISIT_SECONDS = 15 * 60
MAX_VISIT_SECONDS = 6 * 3600
LEGACY_VISIT_SECONDS = 2 * 3600
DURATION_SCHEMA = "roadtrips-visit-duration/1"


class VisitDuration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["roadtrips-visit-duration/1"] = DURATION_SCHEMA
    seconds: StrictInt = Field(ge=MIN_VISIT_SECONDS, le=MAX_VISIT_SECONDS)
    source: Literal["ai_estimate", "conservative_fallback"]
    reason: Literal["estimated", "invalid_output", "provider_failure", "missing_estimate"]


def visit_seconds(record: dict) -> int:
    if "visit_duration" not in record or record["visit_duration"] is None:
        return LEGACY_VISIT_SECONDS
    try:
        return VisitDuration.model_validate(record["visit_duration"]).seconds
    except (ValidationError, TypeError, ValueError):
        raise PlanningError("Invalid visit duration; replan this route", 422) from None


def dwell_source(record: dict) -> str:
    visit_seconds(record)
    return (record.get("visit_duration") or {}).get("source", "planner_policy")


def fallback_duration(reason: str) -> VisitDuration:
    # Reserve at least the old policy dwell when the optional estimator fails.
    # A fallback must still pass every opening window and driving deadline.
    return VisitDuration(
        seconds=LEGACY_VISIT_SECONDS, source="conservative_fallback", reason=reason
    )
