"""One bounded attraction-count contract for chat, tools and HTTP inputs."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[3] / ".env")
MIN_STOPS = 1
HARD_MAX_STOPS = 30
MAPBOX_MAX_COORDINATES = 25


def attraction_limit(value: str) -> int:
    if not value.isdecimal() or not MIN_STOPS <= int(value) <= HARD_MAX_STOPS:
        raise ValueError("MAX_TRIP_ATTRACTIONS must be an integer between 1 and 30")
    return int(value)


MAX_STOPS = attraction_limit(os.getenv("MAX_TRIP_ATTRACTIONS", "20"))
