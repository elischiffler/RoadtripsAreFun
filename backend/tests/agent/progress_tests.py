import asyncio
import json
import threading

import pytest

from app.agent import progress_stream
from app.agent.progress import reporting, stage
from app.agent.schemas import AgentChatResponse


@pytest.mark.asyncio
async def test_progress_and_heartbeat_arrive_before_blocking_provider_finishes(monkeypatch):
    release = threading.Event()
    monkeypatch.setattr(progress_stream, "HEARTBEAT_SECONDS", 0.02)

    async def run():
        with stage("route.test"):
            release.wait(2)  # Deliberately blocking: transport must remain responsive.
        return AgentChatResponse(reply="Done")

    stream = progress_stream.stream_turn(run)
    try:
        events = [json.loads(await anext(stream)), json.loads(await anext(stream))]
        assert events[1]["stage"] == "route.test" and events[1]["state"] == "started"
        assert not release.is_set()
        heartbeat = json.loads(await asyncio.wait_for(anext(stream), 0.5))
        assert heartbeat["type"] == "heartbeat"
        release.set()
        events.extend([json.loads(line) async for line in stream])
        assert events[-1]["type"] == "result"
        assert events[-1]["response"]["reply"] == "Done"
        progress = [event for event in events if event["type"] == "progress"]
        assert len({event["requestId"] for event in progress}) == 1
        assert [event["sequence"] for event in progress] == sorted(
            event["sequence"] for event in progress
        )
    finally:
        release.set()
        await stream.aclose()


@pytest.mark.asyncio
async def test_concurrent_progress_is_request_scoped_and_errors_are_scrubbed():
    async def capture(name):
        async def run():
            with stage(name):
                await asyncio.sleep(0.01)
            return AgentChatResponse(reply=name)

        return [json.loads(line) async for line in progress_stream.stream_turn(run)]

    first, second = await asyncio.gather(capture("first"), capture("second"))
    assert first[0]["requestId"] != second[0]["requestId"]
    assert not any(event.get("stage") == "second" for event in first)

    async def failed():
        raise RuntimeError("secret-token must never appear")

    events = [json.loads(line) async for line in progress_stream.stream_turn(failed)]
    assert events[-1] == {"type": "error", "status": 503}
    assert "secret-token" not in json.dumps(events)


@pytest.mark.asyncio
async def test_disconnection_cancels_turn_and_resets_reporting_context():
    cancelled = threading.Event()
    entered = threading.Event()

    async def run():
        entered.set()
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()

    stream = progress_stream.stream_turn(run)
    await anext(stream)
    await asyncio.to_thread(entered.wait, 1)
    await stream.aclose()
    assert await asyncio.to_thread(cancelled.wait, 1)
    events = []
    with reporting(events.append), stage("fresh"):
        pass
    assert [event["sequence"] for event in events] == [1, 2]
