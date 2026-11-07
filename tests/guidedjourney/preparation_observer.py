"""Test-only passive ASGI receipt; never changes requests, output or cancellation."""

import json


class PreparationObserver:
    def __init__(
        self, app, records, *, max_records=32, max_bytes=2 * 1024 * 1024, max_events=32
    ):
        self.app = app
        self.records = records
        self.max_records = max_records
        self.max_bytes = max_bytes
        self.max_events = max_events
        self.sequence = 0

    async def __call__(self, scope, receive, send):
        if (
            scope.get("type") != "http"
            or scope.get("method") != "POST"
            or scope.get("path") != "/route-preparation/stream"
        ):
            return await self.app(scope, receive, send)
        self.sequence += 1
        record = {
            "sequence": self.sequence,
            "request": {},
            "events": [],
            "truncated": False,
        }
        self.records.append(record)
        del self.records[: -self.max_records]
        request_body = bytearray()
        pending = bytearray()
        received_bytes = 0

        async def receive_tee():
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                if len(request_body) + len(body) <= self.max_bytes:
                    request_body.extend(body)
                else:
                    record["truncated"] = True
                if not message.get("more_body", False) and not record["truncated"]:
                    try:
                        payload = json.loads(request_body)
                        daily = payload.get("scheduling_policy", {}).get(
                            "daily_schedule"
                        )
                        if (
                            isinstance(daily, dict)
                            and isinstance(daily.get("slots"), list)
                            and len(daily["slots"]) == 24
                            and all(
                                slot in {"drive", "rest", "sleep"}
                                for slot in daily["slots"]
                            )
                        ):
                            record["request"] = {
                                "daily_schedule": {
                                    "slots": daily["slots"],
                                    "timezone": daily.get("timezone"),
                                },
                                "departure_clock": payload.get("departure_clock"),
                            }
                    except (ValueError, TypeError, AttributeError):
                        record["invalid_request"] = True
            return message

        def observe(line):
            if not line.strip():
                return
            if len(record["events"]) >= self.max_events:
                record["truncated"] = True
                return
            try:
                event = json.loads(line)
                allowed = (
                    "type",
                    "stage",
                    "phase",
                    "preview_only",
                    "geometry",
                    "possible_overnight_areas",
                    "sections_checked",
                    "response",
                    "status",
                    "code",
                )
                record["events"].append(
                    {key: event[key] for key in allowed if key in event}
                )
            except (ValueError, TypeError):
                record["invalid_event"] = True

        async def send_tee(message):
            nonlocal received_bytes
            # Forward the exact original message once, with no sleeps or buffering
            # ahead of the client. Cancelled/failed sends are never receipts.
            await send(message)
            if message["type"] == "http.response.start":
                record["status"] = message["status"]
            elif message["type"] == "http.response.body":
                body = message.get("body", b"")
                received_bytes += len(body)
                if received_bytes > self.max_bytes:
                    record["truncated"] = True
                    pending.clear()
                    return
                pending.extend(body)
                while b"\n" in pending:
                    line, _, rest = pending.partition(b"\n")
                    pending[:] = rest
                    observe(line)
                if not message.get("more_body", False) and pending:
                    observe(pending)
                    pending.clear()

        return await self.app(scope, receive_tee, send_tee)
