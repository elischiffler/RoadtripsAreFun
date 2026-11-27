"""Shared configuration for the routing layer.

Centralizes API tokens, the geolocator, and feature flags so the sourcing
modules don't each re-read the environment. Loaded once at import.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from geopy.geocoders import OpenCage

# app/routing/config.py -> parents[3] == the repo root, where .env lives (matches
# app/core/config.py and the routers). parents[2] would be backend/, which has no .env.
# Use the default non-overriding behavior so real deployment environment variables
# take precedence over any .env file; dotenv fills in missing values.
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

# Explicit (connect, read) timeouts in seconds for all outbound sourcing calls.
# Without a timeout, a hung upstream would block the worker (and, for calls made
# from async routes, the event loop) indefinitely. Kept here so every source
# module shares one bounded value.
HTTP_TIMEOUT = (5, 20)

# API tokens
APPLE_MAPS_TEAM_ID = os.getenv("APPLE_MAPS_TEAM_ID")
APPLE_MAPS_KEY_ID = os.getenv("APPLE_MAPS_KEY_ID")
APPLE_MAPS_PRIVATE_KEY = os.getenv("APPLE_MAPS_PRIVATE_KEY")
APPLE_MAPS_PRIVATE_KEY_FILE = os.getenv("APPLE_MAPS_PRIVATE_KEY_FILE")
GOOGLE_PLACES_API = os.getenv("GOOGLE_PLACES_API")
OPENCAGE_KEY = os.getenv("OPENCAGE_KEY")

# A single shared reverse-geocoder.
geolocator = OpenCage(api_key=OPENCAGE_KEY, user_agent="RP-Hotels", timeout=10)
