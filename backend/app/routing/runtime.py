"""Run-local clients and loop-independent process limits for provider leaves."""

import asyncio
import threading
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from functools import wraps
from time import perf_counter

import httpx

from app.agent.progress import current_stage, emit
from app.routing.run_metrics import increment, provider_activity

LIMITS = {
    "nearby": (4, 8),
    "mapbox": (4, 8),
    "ai": (2, 4),
    "hotels": (2, 2),
    "geocoding": (2, 4),
    "solver": (2, 2),
}
_PROCESS = {key: threading.BoundedSemaphore(total) for key, (_, total) in LIMITS.items()}
_current = ContextVar("routing_runtime", default=None)


class RunRuntime:
    def __init__(self, limits=None):
        self.gates = {
            key: threading.BoundedSemaphore((limits or {}).get(key, count))
            for key, (count, _) in LIMITS.items()
        }
        self.client = httpx.AsyncClient(timeout=30)
        self.tasks = {}
        self.thread_tasks = set()
        self.resources = {}
        self.sync_client = httpx.Client(timeout=90)
        self.lock = threading.Lock()
        self.counts = {}
        self.cancelled = threading.Event()


@asynccontextmanager
async def run_context(limits=None):
    if _current.get() is not None:
        yield _current.get()
        return
    runtime = RunRuntime(limits)
    token = _current.set(runtime)
    try:
        yield runtime
    finally:
        runtime.cancelled.set()
        pending = [task for task in runtime.tasks.values() if not task.done()]
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        await asyncio.gather(*list(runtime.thread_tasks), return_exceptions=True)
        runtime.sync_client.close()
        await runtime.client.aclose()
        _current.reset(token)


def in_run(fn):
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        async with run_context():
            return await fn(*args, **kwargs)

    return wrapper


async def joined(calls):
    """Fail promptly and cancel siblings on failure/disconnect, preserving order."""
    tasks = [asyncio.create_task(call) for call in calls]
    try:
        return await asyncio.gather(*tasks)
    except BaseException:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise


async def singleflight(key, call):
    runtime = _current.get()
    if runtime is None:
        return await call()
    if key not in runtime.tasks:
        increment(str(key[0]), "requests")
        runtime.tasks[key] = asyncio.create_task(call())
    return await asyncio.shield(runtime.tasks[key])


def _activity(runtime, kind, delta, wait=0, elapsed=0):
    with runtime.lock:
        counts = runtime.counts.setdefault(kind, {"active": 0, "completed": 0, "peak": 0})
        counts["active"] += delta
        counts["peak"] = max(counts["peak"], counts["active"])
        if delta < 0:
            counts["completed"] += 1
        provider_activity(kind, delta, wait, elapsed)
        emit("providers.activity", provider=kind, operation=current_stage(), **counts)


async def _acquire(runtime, kind):
    started = perf_counter()
    run_gate, process_gate = runtime.gates[kind], _PROCESS[kind]
    # No blocking acquisition in a worker thread: cancelled waiters own no permits.
    while True:
        if runtime.cancelled.is_set():
            raise asyncio.CancelledError
        if run_gate.acquire(blocking=False):
            if process_gate.acquire(blocking=False):
                break
            run_gate.release()
        await asyncio.sleep(0.005)
    _activity(runtime, kind, 1, wait=(perf_counter() - started) * 1000)


def _release(runtime, kind, started):
    _activity(runtime, kind, -1, elapsed=(perf_counter() - started) * 1000)
    _PROCESS[kind].release()
    runtime.gates[kind].release()


async def limited(kind, call):
    async with run_context() as runtime:
        await _acquire(runtime, kind)
        started = perf_counter()
        try:
            return await call()
        finally:
            _release(runtime, kind, started)


async def threaded(kind, call, *args, **kwargs):
    async with run_context() as runtime:
        await _acquire(runtime, kind)
        started = perf_counter()

        def work():
            try:
                return call(*args, **kwargs)
            finally:
                # Real completion owns release even if its awaiting task disconnected.
                _release(runtime, kind, started)

        task = asyncio.create_task(asyncio.to_thread(work))
        runtime.thread_tasks.add(task)
        task.add_done_callback(runtime.thread_tasks.discard)
        task.add_done_callback(
            lambda completed: completed.exception() if not completed.cancelled() else None
        )
        return await asyncio.shield(task)


async def http_get(url, **kwargs):
    async with run_context() as runtime:
        return await runtime.client.get(url, **kwargs)


@asynccontextmanager
async def hotel_client(transport=None):
    if transport is not None:
        async with httpx.AsyncClient(transport=transport) as client:
            yield client
    else:
        async with run_context() as runtime:
            yield runtime.client


@contextmanager
def sync_http_client():
    runtime = _current.get()
    if runtime is not None:
        yield runtime.sync_client
    else:
        with httpx.Client(timeout=90) as client:
            yield client


def run_resource(key, factory):
    runtime = _current.get()
    if runtime is None:
        return factory()
    if key not in runtime.resources:
        runtime.resources[key] = factory()
    return runtime.resources[key]
