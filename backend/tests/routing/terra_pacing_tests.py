"""Terra pacing, global cooldown and cross-loop cancellation regression checks."""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest

from app.routing.terra_pacing import TerraPacer


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    async def sleep(self, delay):
        self.now += delay


def response(status=200, headers=None):
    return httpx.Response(
        status, headers=headers, request=httpx.Request("GET", "https://terra.test")
    )


async def test_spacing_and_shared_cooldown_apply_to_next_query():
    clock = Clock()
    pacer = TerraPacer(1, clock=clock, sleep=clock.sleep)
    starts = []
    responses = iter([response(), response(429, {"Retry-After": "12"}), response()])

    async def request():
        starts.append(clock())
        return next(responses)

    for _ in range(3):
        await pacer.call(request)
    assert starts == [0, 1, 13]
    assert pacer.interval == pytest.approx(1.8)


@pytest.mark.parametrize("header", [None, "invalid", "0"])
async def test_repeated_throttles_back_off_even_without_valid_retry_after(header):
    clock = Clock()
    pacer = TerraPacer(1, clock=clock, sleep=clock.sleep)
    starts = []

    async def request():
        starts.append(clock())
        return response(429, {"Retry-After": header} if header else None)

    for _ in range(6):
        await pacer.call(request)
    assert starts == [0, 5, 15, 35, 75, 135]
    assert pacer.interval == 16


async def test_http_date_cooldown():
    clock = Clock()
    pacer = TerraPacer(1, clock=clock, sleep=clock.sleep)
    date = format_datetime(datetime.now(UTC) + timedelta(seconds=30), usegmt=True)

    async def request():
        return response(429, {"Retry-After": date})

    await pacer.call(request)
    assert 28 < pacer.next_start <= 30


async def test_cancelled_waiters_and_failed_transport_release_lock():
    pacer = TerraPacer(0.001)
    started, finish = asyncio.Event(), asyncio.Event()
    sent = []

    async def held():
        started.set()
        await finish.wait()
        return response()

    async def request():
        sent.append(True)
        return response()

    first = asyncio.create_task(pacer.call(held))
    await started.wait()
    queued = asyncio.create_task(pacer.call(request))
    await asyncio.sleep(0)
    queued.cancel()
    with pytest.raises(asyncio.CancelledError):
        await queued
    assert not sent
    finish.set()
    await first

    async def fail():
        raise httpx.ConnectError("offline")

    with pytest.raises(httpx.ConnectError):
        await pacer.call(fail)
    await pacer.call(request)
    assert sent == [True]
    # Also cancel after lock acquisition, while waiting for the next start.
    pacer.next_start = time.monotonic() + 60
    waiting = asyncio.create_task(pacer.call(request))
    await asyncio.sleep(0)
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting
    assert not pacer.gate.locked()


async def test_multiple_worker_loops_share_spacing_and_one_inflight_request():
    pacer = TerraPacer(0.02)
    starts, active, peak = [], 0, 0
    barrier = threading.Barrier(3)

    async def request():
        nonlocal active, peak
        starts.append(time.monotonic())
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.03)
        active -= 1
        return response()

    def worker():
        barrier.wait()
        asyncio.run(pacer.call(request))

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(worker) for _ in range(3)]
        await asyncio.gather(*(asyncio.wrap_future(future) for future in futures))
    assert peak == 1
    assert len(starts) == 3
    assert all(b - a >= 0.02 for a, b in zip(starts, starts[1:]))
