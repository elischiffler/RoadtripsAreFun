"""Fixed public transport contract for the upcoming-departure guard only."""

from fastapi import HTTPException

DEPARTURE_NOT_UPCOMING_CODE = "departure_not_upcoming"
DEPARTURE_NOT_UPCOMING_MESSAGE = "Choose a departure date and time in the future."


class DepartureNotUpcomingHTTPError(HTTPException):
    """A typed allowlist entry; never copy provider exception text into this error."""

    def __init__(self):
        super().__init__(status_code=422, detail=DEPARTURE_NOT_UPCOMING_MESSAGE)
