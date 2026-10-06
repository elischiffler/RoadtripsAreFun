"""Authoritative optional trip scheduling preferences and local calendar rules."""

from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, StrictBool, field_validator, model_validator

from app.agent.trip_dates import _localize, normalize_departure_time

EveningInterest = Literal["food", "culture", "nightlife"]


class SchedulingPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred_hotel_arrival: str = "18:00"
    latest_hotel_arrival: str = "20:00"
    latest_destination_arrival: str | None = None
    morning_restart: str = "09:00"
    late_driving: StrictBool = False
    late_cutoff: str = "24:00"

    @field_validator(
        "preferred_hotel_arrival",
        "latest_hotel_arrival",
        "morning_restart",
        "latest_destination_arrival",
        "late_cutoff",
        mode="before",
    )
    @classmethod
    def _clock(cls, value, info):
        if info.field_name == "latest_destination_arrival" and value is None:
            return None
        if (
            info.field_name == "late_cutoff"
            and isinstance(value, str)
            and value.lower() in {"24:00", "midnight", "00:00"}
        ):
            return "24:00"
        return normalize_departure_time(value)

    @model_validator(mode="after")
    def _ordered(self):
        if (
            not self.morning_restart
            < self.preferred_hotel_arrival
            <= self.latest_hotel_arrival
            <= self.late_cutoff
        ):
            raise ValueError(
                "Morning restart must precede preferred arrival; preferred <= latest <= late cutoff (at most 24:00)."
            )
        return self

    @property
    def cutoff(self) -> str:
        return self.late_cutoff if self.late_driving else self.latest_hotel_arrival

    def at(self, travel_day: date, clock: str, zone) -> datetime:
        hour, minute = map(int, clock.split(":"))
        if hour == 24:
            travel_day += timedelta(days=1)
            hour = 0
        naive = datetime.combine(travel_day, datetime.min.time()).replace(hour=hour, minute=minute)
        return _localize(naive, zone) if isinstance(zone, ZoneInfo) else naive.replace(tzinfo=zone)

    def arrival_cutoff(self, *, final: bool = False) -> str:
        if not final:
            return self.cutoff
        destination = self.latest_destination_arrival
        if self.late_driving:
            return min(destination or self.late_cutoff, self.late_cutoff)
        cutoff = min(destination or "21:00", "21:00", self.late_cutoff)
        # Earlier hotel windows conservatively constrain the whole travel day.
        return (
            min(cutoff, self.latest_hotel_arrival)
            if self.latest_hotel_arrival < "20:00"
            else cutoff
        )

    def deadline(self, travel_day: date, zone, *, final: bool = False) -> datetime:
        return self.at(travel_day, self.arrival_cutoff(final=final), zone)

    def restart(self, travel_day: date, zone) -> datetime:
        # travel_day identifies the preceding booking night, even at exact midnight.
        return self.at(travel_day + timedelta(days=1), self.morning_restart, zone)


def advance(value: datetime, seconds: float) -> datetime:
    """Durations are elapsed seconds, including across DST transitions."""
    if value.tzinfo is None:
        return value + timedelta(seconds=seconds)
    return (value.astimezone(UTC) + timedelta(seconds=seconds)).astimezone(value.tzinfo)


def seconds_until(value: datetime, deadline: datetime) -> float:
    if value.tzinfo is not None:
        return (deadline.astimezone(UTC) - value.astimezone(UTC)).total_seconds()
    return (deadline - value).total_seconds()


def local_time(value: datetime, zone) -> datetime:
    if value.tzinfo is None:
        return _localize(value, zone) if isinstance(zone, ZoneInfo) else value.replace(tzinfo=zone)
    return value.astimezone(zone)
