"""Request-local, opt-in diagnostics; ordinary routing responses stay unchanged."""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

_capture: ContextVar[dict[str, Any] | None] = ContextVar("routing_explanation", default=None)


@contextmanager
def capture_explanation():
    result: dict[str, Any] = {"weights": {}, "candidates": [], "solver": None, "stages": []}
    token = _capture.set(result)
    try:
        yield result
    finally:
        _capture.reset(token)


def record_explanation(**values):
    if (capture := _capture.get()) is not None:
        capture.update(values)


def record_stage(name: str, status: str, detail: str):
    if (capture := _capture.get()) is not None:
        capture["stages"].append({"name": name, "status": status, "detail": detail})
