"""Occupancy contract shared by trip collection and dated hotel searches.

Google's selector supports six guests per search and child ages 0–17 (0/1
share age band 1), observed 2026-10-03. Four rooms is our bounded-lookup
application limit, not a provider inventory guarantee.
"""

from typing import Annotated

from pydantic import BaseModel, Field, model_validator

MAX_ROOMS = 4
MAX_ROOM_GUESTS = 6
MAX_CHILD_AGE = 17
MAX_TRAVELERS = MAX_ROOMS * MAX_ROOM_GUESTS

TravelerCount = Annotated[int, Field(strict=True, ge=1, le=MAX_TRAVELERS)]
ChildAge = Annotated[int, Field(strict=True, ge=0, le=MAX_CHILD_AGE)]


class HotelRoom(BaseModel):
    adults: Annotated[int, Field(strict=True, ge=1, le=MAX_ROOM_GUESTS)]
    child_ages: list[ChildAge] = Field(max_length=MAX_ROOM_GUESTS - 1)

    @model_validator(mode="after")
    def guest_limit(self):
        if self.adults + len(self.child_ages) > MAX_ROOM_GUESTS:
            raise ValueError(
                "Google Hotels supports at most 6 guests per room search; split the party across rooms."
            )
        return self

    @property
    def provider_child_ages(self) -> list[int]:
        return sorted(max(age, 1) for age in self.child_ages)


HotelRooms = Annotated[list[HotelRoom], Field(min_length=1, max_length=MAX_ROOMS)]
COUNT_QUESTION = "How many people are going, including you?"
OCCUPANCY_QUESTION = "How many hotel rooms do you need? For each room, give the number of adults and each child's age (or confirm no children)."
UNSUPPORTED_OCCUPANCY = "Please give 1–4 rooms, with at least one adult and at most 6 guests in each, and child ages 0–17. Larger room searches are not supported yet."


def require_occupancy(count: int | None, rooms: list[HotelRoom] | None) -> list[HotelRoom]:
    if count is None:
        raise ValueError(COUNT_QUESTION)
    if not rooms:
        raise ValueError(OCCUPANCY_QUESTION)
    if sum(room.adults + len(room.child_ages) for room in rooms) != count:
        raise ValueError(
            "Room occupants must equal the total travelers including you. Please clarify the room allocation."
        )
    return rooms
