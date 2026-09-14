"""Tests for the reply leak monitor (``app/agent/agent._scan_reply_for_leaks``).

The monitor is the backstop for "keep private things private": it detects when
INTERNAL context we send to the model — the client UI hint, trip-profile
internals, raw coordinates, the rolling summary, or the tool protocol — is
recited back in the user-facing reply. It logs (never rewrites) so a leak is
observable instead of silent.
"""

from __future__ import annotations

import logging

import pytest

from app.agent.agent import _scan_reply_for_leaks
from app.agent.trip_profile import TripProfile


def test_clean_reply_has_no_leaks():
    trip = TripProfile(start_address="San Luis Obispo, CA", start_coords=[35.28, -120.66])
    reply = "Great — starting from San Luis Obispo. How many stops would you like?"
    assert _scan_reply_for_leaks(reply, trip) == []


def test_empty_reply_has_no_leaks():
    assert _scan_reply_for_leaks("", TripProfile()) == []


@pytest.mark.parametrize(
    "reply",
    [
        "The client UI hint had 1 stop and a $0 budget.",
        "Your trip profile shows you want 3 stops.",
        "I'll pass route_handle to the next tool.",
        "Setting start_coords now.",
        "```tool\n{\"tool\": \"validate_location\"}\n```",
        "Here's the Summary of earlier conversation you asked about.",
    ],
)
def test_internal_markers_are_flagged(reply):
    hits = _scan_reply_for_leaks(reply, TripProfile())
    assert hits, f"expected a leak marker for reply: {reply!r}"


def test_raw_coordinates_from_trip_are_flagged():
    # Echoing the raw lat/lon the trip profile holds is a concrete privacy leak.
    trip = TripProfile(start_address="SLO", start_coords=[35.28, -120.66])
    hits = _scan_reply_for_leaks("You're starting at 35.28, -120.66.", trip)
    assert any(h.startswith("raw_coords") for h in hits)


def test_address_paraphrase_is_not_flagged():
    # The human-readable address is fine to say back — only raw coords aren't.
    trip = TripProfile(start_address="482 Luneta Dr", start_coords=[35.28, -120.66])
    hits = _scan_reply_for_leaks("Got it — starting from 482 Luneta Dr.", trip)
    assert hits == []


def test_leak_is_logged_as_warning(caplog):
    trip = TripProfile(start_coords=[35.28, -120.66])
    with caplog.at_level(logging.WARNING, logger="app.agent.agent"):
        _scan_reply_for_leaks("The client UI hint had 1 stop.", trip)
    assert any("leak internal context" in r.message.lower() for r in caplog.records)
