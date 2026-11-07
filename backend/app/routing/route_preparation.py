"""Progressive admitted ideas and tentative stay areas, with no provider/AI work.

Area positions use existing road duration distributed by great-circle geometry
length. Meals consume planning allowances; sleep/rest delimit driving windows.
All clocks remain departure-wall-clock estimates, not local arrival proofs.
"""

import math

from pydantic import ValidationError

from app.agent.progress import emit
from app.models.route_preparation import (
    RoutePreparationRequest,
    RoutePreparationResponse,
    TentativeStayArea,
)
from app.routing import alternatives
from app.routing.meal_reservations import meal_windows
from app.routing.runtime import in_run, threaded
from app.routing.visit_calendar import calendar_eligible

MAX_SECTIONS = 6
MAX_PLACES = 12
MAX_AREAS = 3
AREA_NOTICE = (
    "Tentative stay search area from drive-only road timing, meal allowances and your daily hours. "
    "Visits, detours and local clock changes can move it. No hotels, quotes or availability checked."
)
NOTICE = (
    "Preparation only: admitted catalog ideas are unscheduled and stay areas are tentative. "
    "Sparse catalog samples can omit places; travel-date opening hours are not checked here. "
    "No trip eligibility, hotel availability or booking is established."
)


def _curve(geometry):
    points = [(lat, lon) for lon, lat in geometry]
    lengths = [alternatives._distance(a, b) for a, b in zip(points, points[1:])]
    return points, lengths, sum(lengths)


def _point(curve, fraction):
    points, lengths, total = curve
    target, elapsed = total * fraction, 0
    for i, length in enumerate(lengths):
        if elapsed + length >= target and length:
            return alternatives._interpolate(points[i], points[i + 1], (target - elapsed) / length)
        elapsed += length
    return points[-1]


def _drive_bounds(policy, now):
    """Return the enclosing driving block and next start in a nominal daily clock."""
    schedule = policy.daily_schedule
    if schedule:
        start, end = schedule.bounds("drive")
        period = math.floor((now - start * 60) / 1440)
        beginning, finish = start * 60 + period * 1440, end * 60 + period * 1440
        return (beginning, finish, beginning + 1440) if beginning <= now < finish else None
    start_h, start_m = map(int, policy.morning_restart.split(":"))
    end_h, end_m = map(int, policy.cutoff.split(":"))
    day = math.floor(now / 1440)
    beginning, finish = day * 1440 + start_h * 60 + start_m, day * 1440 + end_h * 60 + end_m
    return (beginning, finish, beginning + 1440) if beginning <= now < finish else None


def estimate_stay_areas(payload: RoutePreparationRequest):
    """At most three search hints. Never reserve a meal, place, room or extra stop."""
    if not payload.driving_seconds:
        return []
    curve = _curve(payload.geometry)
    if not curve[2]:
        return []
    hour, minute = map(int, payload.departure_clock.split(":"))
    now = hour * 60 + minute
    remaining, driven, allowance = payload.driving_seconds, 0.0, 0
    used, areas = set(), []
    windows = meal_windows(payload.scheduling_policy.daily_schedule)
    # Three areas need at most four driving periods. The larger fixed bound also
    # covers wrapped meal windows without an input-dependent unbounded loop.
    for _ in range(32):
        bounds = _drive_bounds(payload.scheduling_policy, now)
        if bounds is None and not payload.scheduling_policy.daily_schedule and not areas:
            # Legacy first departures can precede the normal morning restart.
            end_h, end_m = map(int, payload.scheduling_policy.cutoff.split(":"))
            if 0 <= now < end_h * 60 + end_m:
                start_h, start_m = map(int, payload.scheduling_policy.morning_restart.split(":"))
                bounds = (now, end_h * 60 + end_m, 1440 + start_h * 60 + start_m)
        if bounds is None:
            return areas  # Invalid departure is guidance for the real planner, not a guessed area.
        beginning, finish, restart = bounds
        meals = []
        for day in range(math.floor(beginning / 1440) - 2, math.floor(finish / 1440) + 2):
            for kind, opens, closes, duration in windows:
                start = min(day * 1440 + closes * 60, finish) - duration / 60
                if (
                    (day, kind) not in used
                    and start >= max(beginning, now, day * 1440 + opens * 60)
                    and start + duration / 60 <= finish
                ):
                    meals.append((start, day, kind, duration))
        for start, day, kind, duration in sorted(meals):
            distance = (start - now) * 60
            if remaining <= distance:
                return areas
            remaining -= distance
            driven += distance
            now = start + duration / 60
            allowance += duration
            used.add((day, kind))
        capacity = (finish - now) * 60
        if remaining <= capacity:
            return areas
        remaining -= capacity
        driven += capacity
        fraction = driven / payload.driving_seconds
        areas.append(
            TentativeStayArea(
                id=f"stay-area:{len(areas) + 1}",
                coordinates=_point(curve, fraction),
                label=f"Potential stay search area {len(areas) + 1}",
                route_fraction=fraction,
                driving_seconds_before=round(driven, 3),
                meal_allowance_seconds=allowance,
                day_index=math.floor(finish / 1440),
                pause_clock=f"{int(finish // 60) % 24:02d}:{int(finish) % 60:02d}",
                notice=AREA_NOTICE,
            )
        )
        if len(areas) == MAX_AREAS:
            return areas
        now = restart
    return areas


def preview_details(phase, geometry, stops, *, areas=None):
    """Public, bounded provisional scene; omit ratings, profiles and source blobs."""
    raw = geometry.get("coordinates", []) if isinstance(geometry, dict) else []
    raw = raw if isinstance(raw, (list, tuple)) else []
    points = [
        p
        for p in raw
        if isinstance(p, (list, tuple))
        and len(p) == 2
        and all(type(v) in (int, float) and math.isfinite(v) for v in p)
        and abs(p[0]) <= 180
        and abs(p[1]) <= 90
    ]
    if len(points) != len(raw) or len(points) < 2:
        geometry = None
    else:
        if len(points) > 10000:
            points = [points[round(i * (len(points) - 1) / 9999)] for i in range(10000)]
        geometry = {"type": "LineString", "coordinates": points}
    valid = []
    for stop in stops:
        if not isinstance(stop, dict) or not isinstance(stop.get("name"), str):
            continue
        point = stop.get("coordinates")
        if (
            not isinstance(point, (list, tuple))
            or len(point) != 2
            or any(type(value) not in (int, float) or not math.isfinite(value) for value in point)
            or abs(point[0]) > 90
            or abs(point[1]) > 180
        ):
            continue
        valid.append(
            {
                "name": stop["name"][:300],
                "coordinates": list(point),
                "type": "hotel" if stop.get("type") == "hotel" else "stop",
                **(
                    {"provider_id": stop["provider_id"]}
                    if isinstance(stop.get("provider_id"), str)
                    else {}
                ),
            }
        )
    if len(valid) > MAX_PLACES:
        valid = [valid[round(i * (len(valid) - 1) / (MAX_PLACES - 1))] for i in range(MAX_PLACES)]
    return {
        "phase": phase,
        "preview_only": True,
        "geometry": geometry,
        "stops": valid,
        **(
            {"possible_overnight_areas": [a.model_dump(mode="json") for a in areas]}
            if areas is not None
            else {}
        ),
    }


@in_run
async def prepare_route(payload: RoutePreparationRequest):
    areas = estimate_stay_areas(payload)
    emit(
        "preparation.areas",
        **preview_details(
            "preparing", {"type": "LineString", "coordinates": payload.geometry}, [], areas=areas
        ),
    )
    curve = _curve(payload.geometry)
    places, seen, failed = [], set(), 0
    for index in range(MAX_SECTIONS):
        point = _point(curve, (index + 0.5) / MAX_SECTIONS)
        try:
            records = await threaded(
                "catalog",
                alternatives.catalog_nearby,
                list(point),
                ["daytime"],
                radius_miles=5,
                limit=MAX_PLACES,
                require_visit_calendar=True,
            )
            accepted = 0
            for record in records:
                try:
                    if not isinstance(record, dict) or not calendar_eligible(record):
                        continue
                    place = alternatives._public_place(record)
                    if place.id in seen or alternatives._distance(point, place.coordinates) > 5:
                        continue
                except (ValidationError, ValueError, TypeError, AttributeError):
                    continue
                seen.add(place.id)
                place.route_fraction = (index + 0.5) / MAX_SECTIONS
                place.offset_miles = round(alternatives._distance(point, place.coordinates), 2)
                places.append(place)
                accepted += 1
                if accepted == 2 or len(places) == MAX_PLACES:
                    break
        except Exception:
            failed += 1
        emit(
            "preparation.catalog",
            sections_checked=index + 1,
            sections_total=MAX_SECTIONS,
            sections_failed=failed,
            places=[place.model_dump(mode="json") for place in places],
        )
    return RoutePreparationResponse(
        places=places,
        possible_overnight_areas=areas,
        sections_checked=MAX_SECTIONS,
        sections_failed=failed,
        catalog_status="unavailable"
        if failed == MAX_SECTIONS
        else "partial"
        if failed
        else "ready",
        notice=NOTICE,
    )


def candidate_stay_areas(route, start, policy):
    """Optional hints must never reject an otherwise valid planning request."""
    if start is None:
        return []
    try:
        scene = preview_details("preparing", route.geometry.model_dump(), [])
        if scene["geometry"] is None:
            return []
        return estimate_stay_areas(
            RoutePreparationRequest(
                geometry=scene["geometry"]["coordinates"],
                driving_seconds=route.duration,
                departure_clock=start.strftime("%H:%M"),
                scheduling_policy=policy,
            )
        )
    except (ValueError, TypeError, AttributeError):
        return []
