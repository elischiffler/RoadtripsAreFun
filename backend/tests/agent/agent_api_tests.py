"""TestClient tests for the thin agent router (design doc §3)."""

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
