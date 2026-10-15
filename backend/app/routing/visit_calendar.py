"""Source calendars and hard CP-SAT visit windows; no inferred opening hours.

Calendars describe published access, not ticket inventory or reservations. The
two-hour dwell is the planner's existing policy, never a claim by the source.
Weekly windows and normalized seasonal ranges are alternatives; importers must
intersect conflicting source restrictions before emitting this contract.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from ortools.sat.python import cp_model
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.agent.trip_dates import _localize
from app.models.scheduling_policy import advance, seconds_until
from app.routing.base import PlanningError

SCHEMA = "roadtrips-source-visit-calendar/1"
VISIT_SECONDS = 7200
_TICKS = 1_000_000  # Datetime precision; fractional road legs must not move fixed starts.


class VisitCalendarConflict(PlanningError):
    """A candidate cannot satisfy a hard calendar constraint in this plan."""

    def __init__(self, provider_id: str, reason: str):
        super().__init__(f"No verified open visit window for {provider_id}: {reason}", 422)
        self.provider_id = provider_id
        self.reason = reason


class Window(BaseModel):
    model_config = ConfigDict(extra="forbid")
    opens: str
    closes: str
    end_day_offset: Literal[0, 1] = 0

    @field_validator("opens", "closes")
    @classmethod
    def clock(cls, value):
        parsed = datetime.strptime(value, "%H:%M")
        if parsed.strftime("%H:%M") != value:
            raise ValueError("Calendar clocks require HH:MM")
        return value


class WeeklyWindow(Window):
    weekdays: list[int] = Field(min_length=1, max_length=7)

    @field_validator("weekdays")
    @classmethod
    def days(cls, values):
        if any(type(day) is not int or not 0 <= day <= 6 for day in values):
            raise ValueError("Weekdays require Monday=0 through Sunday=6")
        return values


class Season(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["annual", "dated"]
    start: str
    end: str

    def includes(self, day: date) -> bool:
        if self.kind == "dated":
            return date.fromisoformat(self.start) <= day <= date.fromisoformat(self.end)
        start = date.fromisoformat(f"2000-{self.start}")
        end = date.fromisoformat(f"2000-{self.end}")
        point = day.replace(year=2000)
        return start <= point <= end if start <= end else point >= start or point <= end


class DateOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")
    date: date
    windows: list[Window] = Field(max_length=24)


class Calendar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["roadtrips-source-visit-calendar/1"]
    weekly_windows: list[WeeklyWindow] = Field(default_factory=list, max_length=168)
    seasons: list[Season] = Field(default_factory=list, max_length=100)
    date_overrides: list[DateOverride] = Field(default_factory=list, max_length=3660)
    annual_closures: list[str] = Field(default_factory=list, max_length=366)
    fixed_starts: list[datetime] = Field(default_factory=list, max_length=3660)
    source_receipts: list[dict] = Field(min_length=1, max_length=100)
    unknown_reasons: list[str] = Field(default_factory=list, max_length=100)

    @field_validator("fixed_starts")
    @classmethod
    def aware(cls, values):
        if any(value.tzinfo is None for value in values):
            raise ValueError("Fixed starts require verified aware instants")
        return values

    @field_validator("annual_closures")
    @classmethod
    def annual_dates(cls, values):
        for value in values:
            date.fromisoformat(f"2000-{value}")
        return values


def source_calendar(record: dict) -> Calendar | None:
    """Parse the single attributed calendar; malformed or conflicting data fails closed."""
    values = [
        item["source_visit_calendar"]
        for item in record.get("source_provenance", [])
        if isinstance(item, dict) and "source_visit_calendar" in item
    ]
    if len(values) != 1:
        return None
    try:
        calendar = Calendar.model_validate(values[0])
        # Validate all seasonal bounds, including ranges not reached on this trip.
        for season in calendar.seasons:
            season.includes(date(2000, 1, 1))
            if season.kind == "dated" and season.start > season.end:
                return None
        if len({item.date for item in calendar.date_overrides}) != len(calendar.date_overrides):
            return None
        if any(
            (item.end_day_offset == 0 and item.closes <= item.opens)
            for item in [
                *calendar.weekly_windows,
                *(w for d in calendar.date_overrides for w in d.windows),
            ]
        ):
            return None
        return calendar
    except (ValidationError, ValueError, TypeError):
        return None


def requires_calendar(record: dict) -> bool:
    """Identify timed venues; ordinary outdoor legacy records keep explicit unknown hours."""
    return (
        str(record.get("provider_id", "")).startswith(("usda-market:", "wikidata-park:"))
        or bool(set(record.get("categories", [])) & {"food", "culture", "nightlife"})
        or (record.get("availability") or {}).get("status") == "within_published_window"
        or any(
            isinstance(item, dict) and "source_visit_calendar" in item
            for item in record.get("source_provenance", [])
        )
    )


def calendar_eligible(record: dict) -> bool:
    if not requires_calendar(record):
        return True
    calendar = source_calendar(record)
    return bool(
        calendar
        and not calendar.unknown_reasons
        and (calendar.weekly_windows or calendar.date_overrides)
    )


def _allowed_day(calendar: Calendar, day: date) -> bool:
    return (
        day.strftime("%m-%d") not in calendar.annual_closures
        and (not calendar.seasons or any(season.includes(day) for season in calendar.seasons))
        and not any(item.date == day and not item.windows for item in calendar.date_overrides)
    )


def _at(day: date, clock: str, zone: ZoneInfo) -> datetime:
    return _localize(datetime.combine(day, datetime.strptime(clock, "%H:%M").time()), zone)


def open_intervals(calendar: Calendar, earliest: datetime, deadline: datetime, zone: ZoneInfo):
    """Enumerate bounded dated windows in the provider-resolved IANA zone.

    A previous-day window may cross midnight. Explicit closures and seasons also
    constrain that following portion. Ambiguous/nonexistent DST clocks withhold
    the affected window rather than inventing an offset.
    """
    if earliest.tzinfo is None or deadline.tzinfo is None or not isinstance(zone, ZoneInfo):
        return []
    first = earliest.astimezone(zone).date() - timedelta(days=1)
    last = deadline.astimezone(zone).date()
    if not 0 <= (last - first).days <= 3:
        return []
    result = []
    day = first
    overrides = {item.date: item.windows for item in calendar.date_overrides}
    while day <= last:
        if _allowed_day(calendar, day):
            windows = overrides.get(
                day, [item for item in calendar.weekly_windows if day.weekday() in item.weekdays]
            )
            for window in windows:
                try:
                    opens = _at(day, window.opens, zone)
                    closes = _at(day + timedelta(days=window.end_day_offset), window.closes, zone)
                    following = day + timedelta(days=1)
                    if window.end_day_offset and (
                        not _allowed_day(calendar, following) or following in overrides
                    ):
                        # A next-day override replaces that day's clocks, even
                        # the portion of yesterday's overnight weekly session.
                        closes = _at(following, "00:00", zone)
                    if seconds_until(opens, closes) > 0:
                        result.append((opens, closes))
                except ValueError:
                    continue
        day += timedelta(days=1)
    return result


def solve_visit(record: dict, earliest: datetime, deadline: datetime, *, dwell=VISIT_SECONDS):
    """Choose the earliest feasible start with hard CP-SAT window/dwell constraints.

    No objective penalty permits a closed visit. The bounded temporal subproblem
    feeds conflicts back into attraction reselection, and runs again after final
    road routing. Ticket/booking availability always remains unknown.
    """
    if not requires_calendar(record):
        return earliest, {"status": "unknown", "ticket_availability": "unknown"}
    provider_id = record.get("provider_id", "unknown")
    calendar = source_calendar(record)
    zone = earliest.tzinfo
    if (
        calendar is None
        or calendar.unknown_reasons
        or not isinstance(zone, ZoneInfo)
        or deadline.tzinfo is None
    ):
        raise VisitCalendarConflict(provider_id, "schedule or local timezone is unknown")
    dwell_ticks = round(dwell * _TICKS)
    horizon = math.floor(seconds_until(earliest, deadline) * _TICKS) - dwell_ticks
    if horizon < 0 or (deadline.astimezone(zone).date() - earliest.date()).days > 2:
        raise VisitCalendarConflict(provider_id, "full visit exceeds the daily cutoff")
    windows = open_intervals(calendar, earliest, deadline, zone)
    # A verified event start does not establish its end or all-day access.
    # Fixed starts must also fit a published window for the entire policy dwell.
    model = cp_model.CpModel()
    start = model.NewIntVar(0, horizon, "visit_start_elapsed_microseconds")
    choices = []
    for index, (opens, closes) in enumerate(windows):
        choice = model.NewBoolVar(f"source_window_{index}")
        model.Add(
            start >= max(0, math.ceil(seconds_until(earliest, opens) * _TICKS))
        ).OnlyEnforceIf(choice)
        model.Add(
            start + dwell_ticks <= math.floor(seconds_until(earliest, closes) * _TICKS)
        ).OnlyEnforceIf(choice)
        choices.append(choice)
    model.AddExactlyOne(choices)
    if calendar.fixed_starts:
        starts = [
            [round(seconds_until(earliest, value) * _TICKS)]
            for value in calendar.fixed_starts
            if _allowed_day(calendar, value.astimezone(zone).date())
            and 0 <= seconds_until(earliest, value) * _TICKS <= horizon
        ]
        model.AddAllowedAssignments([start], starts)
    model.Minimize(start)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 1
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise VisitCalendarConflict(provider_id, "no published window contains the full visit")
    wait_seconds = solver.Value(start) / _TICKS
    visit_start = advance(earliest, wait_seconds)
    chosen = next(index for index, choice in enumerate(choices) if solver.Value(choice))
    opens, closes = windows[chosen]
    return visit_start, {
        "status": "within_published_window",
        "schema_version": SCHEMA,
        "timezone": zone.key,
        "opens": opens.isoformat(),
        "closes": closes.isoformat(),
        "visit_start": visit_start.isoformat(),
        "visit_end": advance(visit_start, dwell).isoformat(),
        "wait_seconds": wait_seconds,
        "dwell_seconds": dwell,
        "dwell_source": "planner_policy",
        "ticket_availability": "unknown",
        "source_receipts": calendar.source_receipts,
    }
