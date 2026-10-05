"""Request-local, credential-free progress for developer diagnostics."""

from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter
from uuid import uuid4

from app.routing.run_metrics import duration

_stage = ContextVar("provider_stage", default=None)


def current_stage():
    return _stage.get()


_reporter = ContextVar("agent_progress", default=None)


class ProgressReporter:
    def __init__(self, sink):
        self.sink = sink
        self.request_id = uuid4().hex[:12]
        self.started = perf_counter()
        self.sequence = 0

    def emit(self, stage, state, **details):
        self.sequence += 1
        self.sink(
            {
                "type": "progress",
                "requestId": self.request_id,
                "sequence": self.sequence,
                "stage": stage,
                "state": state,
                "elapsedMs": round((perf_counter() - self.started) * 1000),
                **details,
            }
        )


@contextmanager
def reporting(sink):
    token = _reporter.set(ProgressReporter(sink))
    try:
        yield
    finally:
        _reporter.reset(token)


def emit(stage, state="completed", **details):
    if "durationMs" in details:
        duration(stage, details["durationMs"])
    reporter = _reporter.get()
    if reporter:
        reporter.emit(stage, state, **details)


@contextmanager
def stage(name, **details):
    token = _stage.set(name)
    started = perf_counter()
    emit(name, "started", **details)
    try:
        yield
    except BaseException:
        emit(name, "failed", durationMs=round((perf_counter() - started) * 1000, 3), **details)
        raise
    else:
        emit(name, durationMs=round((perf_counter() - started) * 1000, 3), **details)
    finally:
        _stage.reset(token)
