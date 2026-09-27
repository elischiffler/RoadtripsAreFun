import json
from datetime import datetime

from app.core.ops_events import format_http_event


def test_operational_event_excludes_request_data():
    event = json.loads(format_http_event("POST", 201, 12.6))
    timestamp = event.pop("timestamp")
    assert datetime.fromisoformat(timestamp).tzinfo is not None
    assert event == {
        "kind": "ops",
        "service": "roadtrips-api",
        "level": "info",
        "message": "HTTP POST completed with status 201 in 13 ms",
        "event": "http.response",
        "method": "POST",
        "status": 201,
        "duration_ms": 13,
    }
    invalid = json.loads(format_http_event("Bearer secret", 999, -1))
    assert invalid["level"] == "error"
    assert invalid["message"] == "HTTP OTHER completed with status 0 in 0 ms"
    assert "secret" not in json.dumps(invalid)
    assert json.loads(format_http_event("GET", 404, 1))["level"] == "warn"
