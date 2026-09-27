"""Fixed-schema operational events; excludes request paths, headers and bodies."""

import json
from datetime import UTC, datetime

_METHODS = {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}


def format_http_event(method: str, status: int, duration_ms: float) -> str:
    safe_method = method if method in _METHODS else "OTHER"
    safe_status = status if isinstance(status, int) and 100 <= status <= 599 else 0
    safe_duration = max(0, round(duration_ms))
    return json.dumps(
        {
            "kind": "ops",
            "service": "roadtrips-api",
            "timestamp": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": "error"
            if safe_status >= 500 or safe_status == 0
            else "warn"
            if safe_status >= 400
            else "info",
            "message": f"HTTP {safe_method} completed with status {safe_status} in {safe_duration} ms",
            "event": "http.response",
            "method": safe_method,
            "status": safe_status,
            "duration_ms": safe_duration,
        },
        separators=(",", ":"),
    )
