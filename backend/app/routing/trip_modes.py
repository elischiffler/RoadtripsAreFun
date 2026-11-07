"""Complete-candidate eligibility and explicit unsupported accommodation rhythms."""

import math
from datetime import UTC, datetime

from app.models.trip_mode import OneDayProof
from app.routing.base import PlanningError

ONE_DAY_SECONDS = 12 * 60 * 60


class OneDayIneligible(PlanningError):
    def __init__(
        self,
        reason="The complete candidate does not fit in less than 12 hours without an overnight stay.",
    ):
        super().__init__(reason, 422)


class UnsupportedOvernightRhythm(PlanningError):
    def __init__(self):
        super().__init__(
            "The requested overnight rhythm cannot be validated by the nightly hotel source", 422
        )


class RhythmAvailabilityConflict(PlanningError):
    def __init__(self):
        super().__init__(
            "A road leg falls outside driving availability in its next stop's local time. Choose a later departure or edit the daily rhythm.",
            422,
        )


class RhythmClockConflict(PlanningError):
    def __init__(self):
        super().__init__(
            "A driving or sleep boundary falls in an ambiguous or missing local hour. Choose a different hour for this date.",
            422,
        )


class DepartureOutsideRhythm(PlanningError):
    def __init__(self):
        super().__init__("Departure is outside the configured driving availability", 422)


def require_overnight_rhythm(policy):
    rhythm = policy.daily_schedule
    if rhythm and not rhythm.supports_overnight_quotes:
        raise UnsupportedOvernightRhythm()


def one_day_elapsed(route) -> float:
    if any(stop.get("type") == "hotel" for stop in route.stops or []):
        raise OneDayIneligible("A one-day candidate cannot contain an overnight hotel stay.")
    if not route.stops or route.stops[-1].get("type") != "end":
        raise OneDayIneligible(
            "A complete, timed destination is required before one-day eligibility can be assessed."
        )
    start = route.departure_time
    try:
        end = datetime.fromisoformat(route.stops[-1]["departure_time"])
        if start is None or start.tzinfo is None or end.tzinfo is None:
            raise ValueError("aware instants required")
        elapsed = (end.astimezone(UTC) - start.astimezone(UTC)).total_seconds()
    except (KeyError, TypeError, ValueError):
        raise OneDayIneligible(
            "Verified dated timing is required before one-day eligibility can be assessed."
        ) from None
    if not math.isfinite(elapsed) or elapsed < 0:
        raise OneDayIneligible("The complete candidate has invalid elapsed timing.")
    return elapsed


def require_one_day(route):
    elapsed = one_day_elapsed(route)
    if elapsed >= ONE_DAY_SECONDS:
        route.one_day_proof = None
        raise OneDayIneligible()
    route.one_day_proof = OneDayProof(elapsed_seconds=elapsed, validated_at=datetime.now(UTC))
    return elapsed
