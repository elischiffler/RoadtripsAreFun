"""Serialize Terra starts and share throttling cooldown across worker event loops."""

import asyncio
import threading
import time

import httpx

from app.agent.provider_diagnostics import retry_delay
from app.routing import config


class TerraPacer:
    def __init__(self, interval, *, clock=time.monotonic, sleep=asyncio.sleep):
        self.minimum_interval = interval
        self.interval = interval
        self.next_start = 0.0
        self.throttles = 0
        self.clock = clock
        self.sleep = sleep
        # A process lock, never an asyncio primitive shared across private loops.
        self.gate = threading.Lock()

    async def call(self, request):
        # Cancellation while queued must neither send a request nor retain a lock.
        while not self.gate.acquire(blocking=False):
            await self.sleep(0.01)
        try:
            while (delay := self.next_start - self.clock()) > 0:
                await self.sleep(delay)
            self.next_start = self.clock() + self.interval
            response = await request()
            if response.status_code == 429:
                self.throttles += 1
                self.interval = min(self.interval * 2, self.minimum_interval * 16)
                backoff = min(60, 5 * 2 ** min(self.throttles - 1, 4))
                error = httpx.HTTPStatusError(
                    "Terra throttled", request=response.request, response=response
                )
                # Retry-After (seconds or HTTP date) also pauses unrelated queries.
                delay = max(backoff, retry_delay(error, backoff), self.interval)
                self.next_start = max(self.next_start, self.clock() + delay)
            elif response.is_success:
                self.throttles = 0
                self.interval = max(self.minimum_interval, self.interval * 0.9)
            return response
        finally:
            self.gate.release()


terra_requests = TerraPacer(config.TRIPADVISOR_REQUEST_INTERVAL_SECONDS)
