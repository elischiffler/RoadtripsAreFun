"""Dated room-quote coverage, separate from physical rest and hotel access hours."""

import math
from datetime import date, datetime, time, timedelta

from app.core.candidate_errors import ERRORS
from app.models.scheduling_policy import seconds_until
from app.routing.base import PlanningError

ARRIVAL_ENVELOPE = time(18)
DEPARTURE_ENVELOPE = time(9)
MAX_STAY_NIGHTS = 3  # A recurring 24-hour rhythm plus both conservative date buffers.


class LodgingCoverageConflict(PlanningError):
    def __init__(self):
        super().__init__(ERRORS["lodging_stay_conflict"][1], 422)


def current_local_date(zone):
    return datetime.now(zone).date()


def require_future_quote(first, zone):
    if first < current_local_date(zone):
        raise LodgingCoverageConflict()


def stay_dates(check_in: date, check_out: date | None = None):
    if type(check_in) is not date or (check_out is not None and type(check_out) is not date):
        raise ValueError("Hotel stay dates are required")
    check_out = check_out if check_out is not None else check_in + timedelta(days=1)
    if not 1 <= (check_out - check_in).days <= MAX_STAY_NIGHTS:
        raise ValueError("Hotel quotes require a bounded full dated stay")
    return check_out


def required_stay(arrival: datetime, departure: datetime):
    """Buffer outside the app's existing 18:00/09:00 planning envelope.

    These clocks are planning assumptions, never published hotel hours. A
    daytime rest gets prior/following nights with a full-stay quote; exact
    access and continuous occupancy still require provider confirmation.
    """
    if arrival.tzinfo is None or departure.tzinfo is None or seconds_until(arrival, departure) <= 0:
        raise LodgingCoverageConflict()
    first = arrival.date() - timedelta(days=arrival.time() < ARRIVAL_ENVELOPE)
    last = departure.date() + timedelta(days=departure.time() > DEPARTURE_ENVELOPE)
    last = max(last, first + timedelta(days=1))
    stay_dates(first, last)
    return first, last


def lodging_metadata(arrival, departure, check_in, check_out):
    return {
        "check_in_date": check_in.isoformat(),
        "check_out_date": check_out.isoformat(),
        "nights": (check_out - check_in).days,
        "planned_arrival": arrival.isoformat(),
        "planned_departure": departure.isoformat(),
        "access_status": "confirmation_required",
        "notice": (
            "Confirm check-in, checkout and continuous room access for the full quoted stay. "
            "Planned rest times, including daytime or after-midnight use, are not guaranteed."
        ),
    }


def validate_stored_stay(stop, arrival, departure):
    """Recompute coverage on rebuild/edit; never accept copied lodging metadata."""
    first, last = required_stay(arrival, departure)
    try:
        actual_first = date.fromisoformat(stop["check_in_date"])
        actual_last = date.fromisoformat(stop["check_out_date"])
        stay_dates(actual_first, actual_last)
    except (KeyError, TypeError, ValueError):
        raise LodgingCoverageConflict() from None
    if (actual_first, actual_last) != (first, last):
        raise LodgingCoverageConflict()
    rooms = stop.get("hotel_rooms")
    offers = stop.get("room_offers")
    nights = (last - first).days
    scope = (
        "one_room_one_night_including_taxes_fees"
        if nights == 1
        else "one_room_stay_including_taxes_fees"
    )
    if (
        not isinstance(rooms, list)
        or not rooms
        or not isinstance(offers, list)
        or len(offers) != len(rooms)
    ):
        raise LodgingCoverageConflict()
    total = 0.0
    for room, offer in zip(rooms, offers, strict=True):
        if not isinstance(offer, dict) or (
            offer.get("check_in_date") != first.isoformat()
            or offer.get("check_out_date") != last.isoformat()
            or offer.get("room") != room
            or offer.get("price_scope") != scope
            or type(offer.get("price")) not in (int, float)
            or not math.isfinite(offer["price"])
            or offer["price"] <= 0
        ):
            raise LodgingCoverageConflict()
        total += offer["price"]
    if (
        type(stop.get("price")) not in (int, float)
        or not math.isfinite(stop["price"])
        or not math.isclose(stop["price"], total, rel_tol=0, abs_tol=0.005)
        or stop.get("price_scope")
        != (scope if len(rooms) == 1 else "independent_room_quotes_not_combined_inventory")
    ):
        raise LodgingCoverageConflict()
    stop["lodging"] = lodging_metadata(arrival, departure, first, last)
    stop["check_in_timing_notice"] = stop["lodging"]["notice"]
