"""TestClient tests for the thin agent router (design doc §3)."""

import pytest
from fastapi.testclient import TestClient

from app.agent.providers import FallbackChain
from app.agent.schemas import LLMResponse
from app.main import app
from app.routers.agent_api import (
    _EmptyTools,
    _NullMemory,
    get_agent_dependencies,
)

from .conftest import FakeProvider, FakeTools

client = TestClient(app)

_BODY = {"partitionKey": "user-123", "chatId": "42", "message": "hello"}


@pytest.fixture(autouse=True)
def _verified_test_user(monkeypatch):
    # Agent API behavior is covered here; token validation has dedicated tests.
    monkeypatch.setattr("app.agent.agent.get_user_id_from_token", lambda token: "user-123")


def _override(providers, memory=None, tools=None):
    def _dep():
        return providers, memory or _NullMemory(), tools or _EmptyTools()

    return _dep


def test_agent_chat_happy_path():
    provider = FakeProvider(responses=[LLMResponse(content="Hi! Where are we headed?")])
    chain = FallbackChain([provider])
    app.dependency_overrides[get_agent_dependencies] = _override(chain, tools=FakeTools())
    try:
        resp = client.post("/agent/chat", json=_BODY)
    finally:
        app.dependency_overrides.pop(get_agent_dependencies, None)

    assert resp.status_code == 200
    data = resp.json()
    assert data["reply"] == "Hi! Where are we headed?"
    assert data["provider"] == "fake"
    assert data["toolsUsed"] == []


def test_agent_chat_returns_503_on_providers_exhausted():
    # All providers fail -> ProvidersExhausted -> HTTP 503.
    failing = FakeProvider(name="groq", fail=True)
    chain = FallbackChain([failing])
    app.dependency_overrides[get_agent_dependencies] = _override(chain)
    try:
        resp = client.post("/agent/chat", json=_BODY)
    finally:
        app.dependency_overrides.pop(get_agent_dependencies, None)

    assert resp.status_code == 503


def test_agent_chat_rejects_malformed_body():
    resp = client.post("/agent/chat", json={"chatId": "42"})  # missing partitionKey + message
    assert resp.status_code == 422


def test_agent_chat_maps_unexpected_error_to_503_not_500():
    """An unexpected fault in the turn (outside the guarded tool loop) must map to
    a clean 503, never leak a raw 500."""

    class _BoomMemory(_NullMemory):
        def load_facts(self, user_id):
            raise RuntimeError("simulated DB outage")

    provider = FakeProvider(responses=[LLMResponse(content="hi")])
    chain = FallbackChain([provider])
    app.dependency_overrides[get_agent_dependencies] = _override(
        chain, memory=_BoomMemory(), tools=FakeTools()
    )
    try:
        resp = client.post("/agent/chat", json=_BODY)
    finally:
        app.dependency_overrides.pop(get_agent_dependencies, None)

    assert resp.status_code == 503


def test_stream_returns_progress_and_same_final_response():
    import json

    provider = FakeProvider(responses=[LLMResponse(content="Hi streamed")])
    app.dependency_overrides[get_agent_dependencies] = _override(
        FallbackChain([provider]), tools=FakeTools()
    )
    try:
        response = client.post("/agent/chat/stream", json=_BODY)
    finally:
        app.dependency_overrides.pop(get_agent_dependencies, None)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[0]["type"] == "progress"
    assert events[-1]["response"]["reply"] == "Hi streamed"
    assert any(event.get("stage") == "agent.extract_details" for event in events)
    assert not any(
        "user-123" in json.dumps(event) for event in events if event["type"] == "progress"
    )


def test_stream_rejects_invalid_token_before_emitting_events(monkeypatch):
    from fastapi import HTTPException

    def invalid(token):
        raise HTTPException(status_code=401, detail="invalid")

    monkeypatch.setattr("app.agent.agent.get_user_id_from_token", invalid)
    response = client.post("/agent/chat/stream", json=_BODY)
    assert response.status_code == 401
    assert "application/x-ndjson" not in response.headers["content-type"]
