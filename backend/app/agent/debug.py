"""Live console debugging for the agent's evolving data structures.

Prints a readable, per-turn trace to the console (via ``logging``, so it shows
up in the uvicorn output) of how the structured data changes as the user chats:
which tools fired, how the per-chat ``TripProfile`` mutated, and what trip state
(``route`` / ``itinerary``) the turn produced.

Gated by the ``AGENT_DEBUG`` env var (default on in local dev) so it can be
silenced in production. Purely observational — it never alters behavior, and it
truncates large blobs (route geometry) so the console stays legible and no
secrets are dumped.
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger("app.agent.debug")

# OFF by default — this trace prints user messages, coordinates, and tool
# args/results, so it must be opt-in. Set AGENT_DEBUG=true for local debugging.
_ENABLED = os.getenv("AGENT_DEBUG", "false").strip().lower() in ("true", "1", "yes")

# Fields whose values are huge / noisy and get summarized instead of dumped.
_BULKY_KEYS = {"route", "coordinates", "geometry", "legs", "steps", "itinerary"}


def enabled() -> bool:
    return _ENABLED


def _summarize(value):
    """Shrink bulky values so the console trace stays readable."""
    if isinstance(value, list):
        return f"[{len(value)} items]"
    if isinstance(value, dict):
        return f"{{{len(value)} keys}}"
    return value


def _compact(data: dict) -> dict:
    """Copy a dict, summarizing bulky keys."""
    out = {}
    for k, v in (data or {}).items():
        out[k] = _summarize(v) if k in _BULKY_KEYS else v
    return out


def turn_start(user_id: str, chat_id: str, message: str) -> None:
    if not _ENABLED:
        return
    logger.info(
        "\n╭─ AGENT TURN  user=%s chat=%s\n│  user said: %r",
        user_id[:12],
        chat_id,
        message[:200],
    )


def trip_snapshot(label: str, trip) -> None:
    """Log the per-chat trip-profile state (before/after). ``trip`` is a TripProfile."""
    if not _ENABLED:
        return
    try:
        data = trip.model_dump(exclude_none=True)
    except Exception:
        data = {}
    logger.info("│  trip %-6s %s", label, json.dumps(data) if data else "(empty)")


def tool_fired(
    name: str, arguments: dict, ok: bool, result: dict | None, error: str | None
) -> None:
    if not _ENABLED:
        return
    status = "ok" if ok else "FAIL"
    detail = _compact(result) if ok else {"error": error}
    logger.info(
        "│  tool → %-20s args=%s  [%s] %s",
        name,
        json.dumps(_compact(arguments)),
        status,
        json.dumps(detail),
    )


def turn_end(reply: str, tools_used: list[str], actions) -> None:
    if not _ENABLED:
        return
    action_types = [getattr(a, "type", a) for a in (actions or [])]
    logger.info(
        "│  reply: %r\n│  tools used: %s\n│  actions: %s\n╰─ end turn",
        reply[:200],
        tools_used or "[]",
        action_types or "[]",
    )
