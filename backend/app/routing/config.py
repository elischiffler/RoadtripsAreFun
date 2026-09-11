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
# (e.g. MAPBOX_API, AMADEUS_ENABLED set on Render) take precedence over any .env file
# that happens to be present; dotenv only fills in values that aren't already set.
load_dotenv(Path(__file__).resolve().parents[3] / ".env")

# Explicit (connect, read) timeouts in seconds for all outbound sourcing calls.
# Without a timeout, a hung upstream would block the worker (and, for calls made
# from async routes, the event loop) indefinitely. Kept here so every source
# module shares one bounded value.
HTTP_TIMEOUT = (5, 20)

# API tokens
MAPBOX_API = os.getenv("MAPBOX_API")
TRIPADVISOR_API = os.getenv("TRIPADVISOR_API")
GOOGLE_PLACES_API = os.getenv("GOOGLE_PLACES_API")
OPENCAGE_KEY = os.getenv("OPENCAGE_KEY")

# The Amadeus hotel API is currently nonfunctional, so the fallback is disabled by
# default. Set AMADEUS_ENABLED=true in the environment to re-enable the fallback path
# in find_hotel once the upstream API is working again.
AMADEUS_ENABLED = os.getenv("AMADEUS_ENABLED", "false").lower() == "true"

# A single shared reverse-geocoder.
geolocator = OpenCage(api_key=OPENCAGE_KEY, user_agent="RP-Hotels", timeout=10)
