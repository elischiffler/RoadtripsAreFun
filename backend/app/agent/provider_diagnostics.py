"""Bounded retries and safe, request-local provider failure records."""

import asyncio
import re
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx
import requests
from geopy.exc import GeocoderRateLimited, GeocoderTimedOut, GeocoderUnavailable

from app.agent.progress import current_stage, current_stage_details, emit
from app.routing.run_metrics import increment

_records = ContextVar("provider_attempts", default=None)
MAX_ATTEMPTS = 3


def safe_message(value):
    from app.core.config import settings
    from app.routing import config

    text = str(value)
    for key in ("MAPBOX_API", "TRIPADVISOR_API", "GOOGLE_PLACES_API", "OPENCAGE_KEY"):
        secret = getattr(config, key, None)
        if secret:
            text = text.replace(str(secret), "[redacted]")
    for key in ("SUPABASE_ANON_KEY", "MENTRO_SERVICE_PASSWORD", "MENTRO_SERVICE_EMAIL"):
        secret = getattr(settings, key, None)
        if secret:
            text = text.replace(str(secret), "[redacted]")
    text = re.sub(r"https?://\S+", "[provider URL]", text)
    text = re.sub(r"(?i)bearer\s+\S+", "Bearer [redacted]", text)
    text = re.sub(r"eyJ[\w-]+\.[\w-]+\.[\w-]+", "[redacted token]", text)
    text = re.sub(
        r'(?i)((?:api[_-]?key|token|password|authorization)[\s"\x27]*[:=][\s"\x27]*)[^\s,}\x27"]+',
        r"\1[redacted]",
        text,
    )
    return text[:500]


def diagnostic(exc):
    causes = []
    seen = set()
    while exc is not None and id(exc) not in seen and len(causes) < 8:
        seen.add(id(exc))
        item = {"type": type(exc).__name__}
        if hasattr(exc, "public_message"):
            item["message"] = safe_message(exc.public_message)
        status = getattr(exc, "status_code", None) if hasattr(exc, "public_message") else None
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            status = exc.response.status_code
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
        if isinstance(status, int):
            item["http_status"] = status
        if getattr(exc, "provider", None):
            item["provider"] = safe_message(exc.provider)
        if getattr(exc, "provider_code", None):
            item["provider_code"] = safe_message(exc.provider_code)
        causes.append(item)
        exc = exc.__cause__
    status = next((c["http_status"] for c in reversed(causes) if "http_status" in c), None)
    return {"causes": causes, **({"http_status": status} if status else {})}


def retryable(exc):
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        status = getattr(exc, "status_code", None)
        if isinstance(exc, requests.HTTPError) and exc.response is not None:
            status = exc.response.status_code
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
        if isinstance(status, int):
            return status in (408, 429) or 500 <= status <= 599
        if isinstance(
            exc,
            (
                GeocoderTimedOut,
                GeocoderUnavailable,
                GeocoderRateLimited,
                TimeoutError,
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.RemoteProtocolError,
                requests.Timeout,
                requests.ConnectionError,
            ),
        ):
            return True
        if getattr(exc, "retryable", None) is not None:
            if exc.retryable or exc.__cause__ is None:
                return exc.retryable
        exc = exc.__cause__
    return False


@contextmanager
def collecting_attempts():
    records = []
    token = _records.set(records)
    try:
        yield records
    finally:
        _records.reset(token)


def record_failure(exc, attempt, operation):
    again = attempt < MAX_ATTEMPTS and retryable(exc)
    cause = exc
    seen = set()
    while cause is not None and id(cause) not in seen:
        seen.add(id(cause))
        if (
            operation == "ai.ratings"
            and getattr(cause, "provider_code", None) == "EMPTY_COMPLETION"
        ):
            increment("llm_empty_retries" if again else "llm_empty_attempt_caps", "events")
            break
        cause = cause.__cause__
    entry = {
        **current_stage_details(),
        "operation": operation,
        "attempt": attempt,
        "max_attempts": MAX_ATTEMPTS,
        "retryable": retryable(exc),
        "outcome": "retrying" if again else "failed",
        **diagnostic(exc),
    }
    if (records := _records.get()) is not None:
        records.append(entry)
    emit(operation, "retrying" if again else "failed", retry=entry)
    return again


def recovered(attempt, operation):
    if attempt > 1:
        entry = {
            **current_stage_details(),
            "operation": operation,
            "attempt": attempt,
            "max_attempts": MAX_ATTEMPTS,
            "outcome": "recovered",
        }
        if (records := _records.get()) is not None:
            records.append(entry)
        emit(operation, "started", retry=entry)


def retry_delay(exc, attempt):
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        response = getattr(exc, "response", None)
        value = (
            response.headers.get("Retry-After")
            if response is not None
            else getattr(exc, "retry_after", None)
        )
        if value:
            try:
                return max(0, float(value))
            except (ValueError, TypeError):
                try:
                    return max(
                        0, (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
                    )
                except (ValueError, TypeError, OverflowError):
                    pass
        exc = exc.__cause__
    return attempt


def retry_sync(call):
    operation = current_stage() or "ai.provider"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = call()
        except Exception as exc:
            if not record_failure(exc, attempt, operation):
                raise
            time.sleep(retry_delay(exc, attempt))
        else:
            recovered(attempt, operation)
            return result


async def retry_async(call, operation=None):
    operation = operation or current_stage() or "provider.request"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            result = await call()
        except Exception as exc:
            if not record_failure(exc, attempt, operation):
                raise
            await asyncio.sleep(retry_delay(exc, attempt))
        else:
            recovered(attempt, operation)
            return result
