"""Request-local, credential-free progress for developer diagnostics."""

from contextlib import contextmanager
from contextvars import ContextVar
from time import monotonic
from uuid import uuid4

_reporter = ContextVar("agent_progress", default=None)


class ProgressReporter:
    def __init__(self, sink):
        self.sink = sink
        self.request_id = uuid4().hex[:12]
        self.started = monotonic()
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
                "elapsedMs": round((monotonic() - self.started) * 1000),
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
    reporter = _reporter.get()
    if reporter:
        reporter.emit(stage, state, **details)


@contextmanager
def stage(name, **details):
    started = monotonic()
    emit(name, "started", **details)
    try:
        yield
    except BaseException:
        emit(name, "failed", durationMs=round((monotonic() - started) * 1000), **details)
        raise
    else:
        emit(name, durationMs=round((monotonic() - started) * 1000), **details)
