"""Offline ASGI transparency, cancellation and bounds; no app/DB/provider startup."""

import asyncio
import json
import unittest

from preparation_observer import PreparationObserver

SCOPE = {"type": "http", "method": "POST", "path": "/route-preparation/stream"}
REQUEST = json.dumps(
    {
        "scheduling_policy": {
            "daily_schedule": {
                "slots": ["drive"] * 12 + ["sleep"] * 12,
                "timezone": "route_local",
            }
        },
        "departure_clock": "20:00",
        "unrelated_secret": "NEVER_EXPORT",
    }
).encode()
PROGRESS = {"type": "progress", "stage": "preparation.catalog", "sections_checked": 6}
RESULT = {
    "type": "result",
    "response": {"catalog_status": "ready", "notice": "synthetic café"},
}


class ObserverTests(unittest.IsolatedAsyncioTestCase):
    async def invoke(
        self,
        *,
        observer_options=None,
        body=REQUEST,
        chunks=None,
        fail_send=None,
        records=None,
    ):
        records = [] if records is None else records
        chunks = chunks or [
            (
                json.dumps(PROGRESS)
                + "\n"
                + json.dumps(RESULT, ensure_ascii=False)
                + "\n"
            ).encode()
        ]
        incoming = [
            {"type": "http.request", "body": body[:5], "more_body": True},
            {"type": "http.request", "body": body[5:]},
        ]
        received, emitted, forwarded = [], [], []

        async def receive():
            return incoming.pop(0)

        async def send(message):
            if fail_send and fail_send(message):
                raise asyncio.CancelledError("synthetic client cancellation")
            forwarded.append(message)

        async def application(scope, receive_next, send_next):
            while True:
                message = await receive_next()
                received.append(message)
                if not message.get("more_body", False):
                    break
            messages = [
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/x-ndjson")],
                }
            ]
            messages += [
                {
                    "type": "http.response.body",
                    "body": chunk,
                    "more_body": index < len(chunks) - 1,
                }
                for index, chunk in enumerate(chunks)
            ]
            for message in messages:
                emitted.append(message)
                await send_next(message)

        observer = PreparationObserver(application, records, **(observer_options or {}))
        try:
            await observer(SCOPE, receive, send)
        except asyncio.CancelledError:
            return records, received, emitted, forwarded, True
        return records, received, emitted, forwarded, False

    async def test_byte_exact_forwarding_fragmented_unicode_and_sanitized_request(self):
        raw = (
            json.dumps(PROGRESS) + "\n" + json.dumps(RESULT, ensure_ascii=False) + "\n"
        ).encode()
        split = raw.index("é".encode()) + 1
        records, received, emitted, forwarded, cancelled = await self.invoke(
            chunks=[raw[:split], raw[split:]]
        )
        self.assertFalse(cancelled)
        self.assertEqual(b"".join(message["body"] for message in received), REQUEST)
        self.assertEqual(emitted, forwarded)
        self.assertTrue(all(a is b for a, b in zip(emitted, forwarded)))
        self.assertEqual(records[0]["events"], [PROGRESS, RESULT])
        self.assertEqual(records[0]["status"], 200)
        self.assertEqual(records[0]["request"]["departure_clock"], "20:00")
        self.assertNotIn("NEVER_EXPORT", json.dumps(records))

    async def test_cancelled_result_send_is_not_a_receipt(self):
        first = (json.dumps(PROGRESS) + "\n").encode()
        result = (json.dumps(RESULT) + "\n").encode()
        records, _, emitted, forwarded, cancelled = await self.invoke(
            chunks=[first, result],
            fail_send=lambda message: message.get("body") == result,
        )
        self.assertTrue(cancelled)
        self.assertEqual(records[0]["events"], [PROGRESS])
        self.assertEqual(forwarded, emitted[:-1])

    async def test_byte_bound_never_changes_large_output(self):
        records, _, emitted, forwarded, _ = await self.invoke(
            chunks=[b"x" * 1000], observer_options={"max_bytes": 512}
        )
        self.assertEqual(emitted, forwarded)
        self.assertTrue(records[0]["truncated"])
        self.assertEqual(records[0]["events"], [])

    async def test_event_bound_preserves_all_transport_messages(self):
        records, _, emitted, forwarded, _ = await self.invoke(
            chunks=[(json.dumps(PROGRESS) + "\n").encode()] * 4,
            observer_options={"max_events": 2},
        )
        self.assertEqual(emitted, forwarded)
        self.assertEqual(len(records[0]["events"]), 2)
        self.assertTrue(records[0]["truncated"])

    async def test_request_bound_preserves_application_input(self):
        records, received, _, _, _ = await self.invoke(
            body=b"x" * 1000, observer_options={"max_bytes": 512}
        )
        self.assertEqual(b"".join(message["body"] for message in received), b"x" * 1000)
        self.assertTrue(records[0]["truncated"])
        self.assertEqual(records[0]["request"], {})

    async def test_malformed_event_is_observed_without_suppressing_output(self):
        records, _, emitted, forwarded, _ = await self.invoke(chunks=[b"not-json\n"])
        self.assertEqual(emitted, forwarded)
        self.assertTrue(records[0]["invalid_event"])

    async def test_unrelated_routes_are_exactly_bypassed(self):
        records = []

        async def receive():
            raise AssertionError("must not consume unrelated request")

        async def send(message):
            raise AssertionError("must not invent output")

        async def application(scope, actual_receive, actual_send):
            self.assertIs(actual_receive, receive)
            self.assertIs(actual_send, send)

        observer = PreparationObserver(application, records)
        await observer({**SCOPE, "path": "/chats"}, receive, send)
        self.assertEqual(records, [])


if __name__ == "__main__":
    unittest.main()
