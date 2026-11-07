"""Validated recurring local availability, separate from booked accommodation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Activity = Literal["drive", "rest", "sleep"]


class DailyRhythmClockError(ValueError):
    """A requested local boundary has no unique instant on this travel date."""


class DailySchedule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slots: list[Activity] = Field(min_length=24, max_length=24)
    timezone: Literal["route_local"] = "route_local"

    @model_validator(mode="after")
    def continuous_windows(self):
        for kind in ("drive", "sleep"):
            starts = [
                i
                for i, value in enumerate(self.slots)
                if value == kind and self.slots[(i - 1) % 24] != kind
            ]
            if len(starts) != 1:
                raise ValueError(
                    "Choose one continuous driving block and one continuous sleep block around the 24-hour clock"
                )
        return self

    def bounds(self, kind: Activity) -> tuple[int, int]:
        start = next(
            i
            for i, value in enumerate(self.slots)
            if value == kind and self.slots[(i - 1) % 24] != kind
        )
        length = 1
        while self.slots[(start + length) % 24] == kind:
            length += 1
        return start, start + length

    @property
    def drive_start(self) -> str:
        return f"{self.bounds('drive')[0]:02d}:00"

    @property
    def drive_end(self) -> str:
        end = self.bounds("drive")[1]
        return f"{end if end <= 24 else end - 24:02d}:00"

    def available(self, instant: datetime) -> bool:
        return self.slots[instant.hour] == "drive"

    @property
    def supports_overnight_quotes(self) -> bool:
        # Shape validation is independent of hotel time-of-day. Exact dated
        # room coverage and unconfirmed access hours are checked downstream.
        return True
