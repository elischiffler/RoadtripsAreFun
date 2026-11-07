"""Bounded owner/input-bound candidates and idempotent assessment requests.

The cache stores data and request outcomes, never provider clients. Misses,
expiry and cancellation require an explicit new check; no code here replans.
"""

import asyncio
import hashlib
import json
import secrets
from concurrent.futures import Future
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock

from app.core.candidate_errors import CandidateHTTPError
from app.models.planning_candidates import CandidateResponse, OneDayAssessment

TTL_SECONDS = 15 * 60
MAX_CANDIDATES = 32


def input_key(payload):
    inputs = payload.model_dump(
        mode="json", exclude={"request_id", "budget", "hotel_rooms", "trip_mode"}
    )
    return hashlib.sha256(
        json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass
class CandidateEntry:
    owner: str
    payload: object
    context: dict
    response: CandidateResponse
    busy: bool = False
    confirmed_key: str | None = None
    confirmed_route: object = None
    loop: object = None
    task: object = None


@dataclass
class AssessmentRequest:
    fingerprint: str | None
    expires_at: datetime
    future: Future
    cancelled: bool = False
    loop: object = None
    task: object = None


class CandidateStore:
    def __init__(self, *, maximum=MAX_CANDIDATES, ttl=TTL_SECONDS, now=None):
        self.maximum, self.ttl = maximum, ttl
        self.now = now or (lambda: datetime.now(UTC))
        self.entries, self.requests = {}, {}
        self.lock = RLock()

    def _prune(self):
        now = self.now()
        for key in list(self.entries):
            if self.entries[key].response.expires_at <= now:
                self._stop(self.entries[key])
                del self.entries[key]
        for key in list(self.requests):
            if self.requests[key].expires_at <= now:
                record = self.requests.pop(key)
                self._stop(record)

    @staticmethod
    def _stop(record):
        if record.loop and record.task and not record.loop.is_closed():
            try:
                record.loop.call_soon_threadsafe(record.task.cancel)
            except RuntimeError:
                pass
        if isinstance(record, AssessmentRequest) and not record.future.done():
            record.future.set_exception(CandidateHTTPError("candidate_cancelled"))

    def register(self, owner, request_id):
        key = (owner, str(request_id))
        with self.lock:
            self._prune()
            record = self.requests.get(key)
            if record is not None:
                if record.cancelled:
                    raise CandidateHTTPError("candidate_cancelled")
                return record.expires_at
            if len(self.requests) >= self.maximum:
                raise CandidateHTTPError("candidate_unavailable")
            record = AssessmentRequest(None, self.now() + timedelta(seconds=self.ttl), Future())
            self.requests[key] = record
            return record.expires_at

    def start_request(self, owner, payload):
        key = (owner, str(payload.request_id))
        fingerprint = input_key(payload)
        with self.lock:
            self._prune()
            record = self.requests.get(key)
            if record is None:
                raise CandidateHTTPError("candidate_expired")
            if record.cancelled:
                raise CandidateHTTPError("candidate_cancelled")
            if record.fingerprint is not None:
                if record.fingerprint != fingerprint:
                    raise CandidateHTTPError("candidate_inputs_changed")
                return record, False
            record.fingerprint = fingerprint
            record.loop, record.task = asyncio.get_running_loop(), asyncio.current_task()
            return record, True

    def end_request(self, record, *, response=None, error=None):
        with self.lock:
            if record.cancelled:
                raise CandidateHTTPError("candidate_cancelled")
            if not record.future.done():
                if error:
                    record.future.set_exception(error)
                else:
                    record.future.set_result(response.model_copy(deep=True))
            record.loop = record.task = None

    def cancel_request(self, owner, request_id):
        key = (owner, str(request_id))
        with self.lock:
            self._prune()
            record = self.requests.get(key)
            if record is None:
                if len(self.requests) >= self.maximum:
                    raise CandidateHTTPError("candidate_unavailable")
                record = AssessmentRequest(None, self.now() + timedelta(seconds=self.ttl), Future())
                self.requests[key] = record
            record.cancelled = True
            for token, entry in list(self.entries.items()):
                if entry.owner == owner and str(entry.payload.request_id) == str(request_id):
                    self._stop(entry)
                    del self.entries[token]
            if record.future.done() and record.future.exception() is None:
                response = record.future.result()
                self.entries.pop(response.candidate_id, None)
            self._stop(record)

    def add(self, owner, payload, context, assessment: OneDayAssessment, route):
        with self.lock:
            self._prune()
            request = self.requests.get((owner, str(payload.request_id)))
            if request and request.cancelled:
                raise CandidateHTTPError("candidate_cancelled")
            if len(self.entries) >= self.maximum:
                raise CandidateHTTPError("candidate_unavailable")
            token = secrets.token_urlsafe(32)
            response = CandidateResponse(
                candidate_id=token,
                input_key=input_key(payload),
                expires_at=self.now() + timedelta(seconds=self.ttl),
                one_day=assessment,
                candidate_route=route,
            )
            stored_payload = deepcopy(payload)
            if context.get("resolved_start") is not None:
                stored_payload.start = context["resolved_start"]
            self.entries[token] = CandidateEntry(owner, stored_payload, deepcopy(context), response)
            return response.model_copy(deep=True)

    def _get(self, owner, token):
        self._prune()
        entry = self.entries.get(token)
        if entry is None or entry.owner != owner:
            raise CandidateHTTPError("candidate_expired")
        return entry

    def cancel(self, owner, token):
        with self.lock:
            entry = self._get(owner, token)
            self._stop(entry)
            self.cancel_request(owner, entry.payload.request_id)
            self.entries.pop(token, None)

    def begin(self, owner, token, confirmation):
        key = confirmation.model_dump_json()
        with self.lock:
            entry = self._get(owner, token)
            if confirmation.input_key != entry.response.input_key:
                raise CandidateHTTPError("candidate_inputs_changed")
            if entry.confirmed_key is not None:
                if entry.confirmed_key != key:
                    raise CandidateHTTPError("candidate_already_confirmed")
                return entry, entry.confirmed_route.model_copy(deep=True)
            if entry.busy:
                raise CandidateHTTPError("candidate_busy")
            entry.busy = True
            entry.loop, entry.task = asyncio.get_running_loop(), asyncio.current_task()
            return entry, None

    def finish(self, owner, token, confirmation, route):
        with self.lock:
            entry = self._get(owner, token)
            entry.confirmed_key = confirmation.model_dump_json()
            entry.confirmed_route = route.model_copy(deep=True)
            entry.busy = False
            entry.loop = entry.task = None
            return route

    def release(self, owner, token):
        with self.lock:
            entry = self.entries.get(token)
            if entry and entry.owner == owner:
                entry.busy = False
                entry.loop = entry.task = None


store = CandidateStore()
