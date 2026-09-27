"""Tests for the provider layer (design doc §6).

Covers:
- :class:`FallbackChain` skip/advance/exhaust behavior (via ``FakeProvider``).
- :class:`MentroGatewayProvider` SSE reduction — the ``end`` event, an ``error``
  event mid-stream, and a stream that closes without ``end``.
- :class:`SupabaseServiceAuth` configuration + token caching (httpx mocked).

No network: the gateway/auth HTTP calls are monkeypatched.
"""

import httpx
import pytest

from app.agent.providers import (
    FallbackChain,
    MentroGatewayProvider,
    ProviderError,
    ProviderNotConfigured,
    ProvidersExhausted,
    SupabaseServiceAuth,
    build_default_chain,
)
from app.agent.schemas import LLMMessage, LLMResponse

from .conftest import FakeProvider

# --- FallbackChain ----------------------------------------------------------


def test_chain_serves_first_configured_provider():
    p1 = FakeProvider(name="a", responses=[LLMResponse(content="from a")])
    p2 = FakeProvider(name="b")
    chain = FallbackChain([p1, p2])

    response = chain.complete(messages=[], tools=[])

    assert response.content == "from a"
    assert response.provider == "a"
    assert p1.calls == 1
    assert p2.calls == 0


def test_chain_skips_unconfigured_providers():
    unconfigured = FakeProvider(name="a", configured=False)
    served = FakeProvider(name="b", responses=[LLMResponse(content="hello")])
    chain = FallbackChain([unconfigured, served])

    response = chain.complete(messages=[], tools=[])

    assert unconfigured.calls == 0  # never attempted
    assert served.calls == 1
    assert response.provider == "b"


def test_chain_advances_past_provider_error():
    failing = FakeProvider(name="a", fail=True)
    served = FakeProvider(name="b", responses=[LLMResponse(content="recovered")])
    chain = FallbackChain([failing, served])

    response = chain.complete(messages=[], tools=[])

    assert failing.calls == 1
    assert served.calls == 1
    assert response.content == "recovered"
    assert response.provider == "b"


def test_chain_raises_when_all_fail():
    p1 = FakeProvider(name="a", fail=True)
    p2 = FakeProvider(name="b", fail=True, error=ProviderError("429 rate limit"))
    chain = FallbackChain([p1, p2])

    with pytest.raises(ProvidersExhausted):
        chain.complete(messages=[], tools=[])


def test_chain_raises_when_none_configured():
    p1 = FakeProvider(name="a", configured=False)
    p2 = FakeProvider(name="b", configured=False)
    chain = FallbackChain([p1, p2])

    with pytest.raises(ProvidersExhausted):
        chain.complete(messages=[], tools=[])


class _RaisingProvider:
    """A provider that raises a NON-ProviderError (e.g. a JSON/parse fault)."""

    def __init__(self, name, exc):
        self.name = name
        self._exc = exc
        self.calls = 0

    def configured(self):
        return True

    def complete(self, messages, tools):
        self.calls += 1
        raise self._exc


def test_chain_advances_past_unexpected_exception():
    # A non-ProviderError must NOT escape the chain (that would be a raw 500);
    # the chain logs it and advances to the next provider.
    boom = _RaisingProvider("a", ValueError("non-JSON body"))
    served = FakeProvider(name="b", responses=[LLMResponse(content="recovered")])
    chain = FallbackChain([boom, served])

    response = chain.complete(messages=[], tools=[])

    assert boom.calls == 1
    assert response.content == "recovered"
    assert response.provider == "b"


def test_chain_exhausts_on_unexpected_exception_when_alone():
    boom = _RaisingProvider("a", KeyError("access_token"))
    chain = FallbackChain([boom])
    with pytest.raises(ProvidersExhausted):
        chain.complete(messages=[], tools=[])


def test_build_default_chain_is_gateway_only():
    chain = build_default_chain()
    names = [p.name for p in chain._providers]
    assert names == ["mentro"]


# --- SupabaseServiceAuth ----------------------------------------------------


def _auth(**overrides):
    base = dict(
        supabase_url="https://proj.supabase.co",
        anon_key="anon",
        email="svc@example.com",
        password="secret",
    )
    base.update(overrides)
    return SupabaseServiceAuth(**base)


def test_auth_reports_unconfigured_when_missing_creds():
    auth = SupabaseServiceAuth(supabase_url="", anon_key="", email="", password="")
    assert auth.configured() is False
    with pytest.raises(ProviderNotConfigured):
        auth.get_token()


def test_auth_password_grant_and_caches(monkeypatch):
    calls = {"n": 0}

    def fake_post(url, params=None, headers=None, json=None, timeout=None):
        calls["n"] += 1
        assert params == {"grant_type": "password"}
        return httpx.Response(
            200,
            json={"access_token": "tok-123", "refresh_token": "ref-1", "expires_in": 3600},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    auth = _auth()

    assert auth.get_token() == "tok-123"
    # Second call within expiry window is served from cache — no new HTTP call.
    assert auth.get_token() == "tok-123"
    assert calls["n"] == 1


def test_auth_raises_provider_error_on_non_200(monkeypatch):
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: httpx.Response(400, json={"error": "bad grant"})
    )
    with pytest.raises(ProviderError):
        _auth().get_token()


def test_auth_non_json_200_body_becomes_provider_error(monkeypatch):
    # A 200 with a non-JSON body (proxy/HTML page) must degrade to ProviderError,
    # not an uncaught JSONDecodeError that escapes as a 500.
    monkeypatch.setattr(
        httpx, "post", lambda *a, **k: httpx.Response(200, text="<html>gateway error</html>")
    )
    with pytest.raises(ProviderError) as exc:
        _auth().get_token()
    assert "non-JSON" in str(exc.value)


# --- MentroGatewayProvider: SSE reduction -----------------------------------


class _FakeStreamResponse:
    """Minimal stand-in for httpx's streaming response context manager."""

    def __init__(self, status_code=200, lines=None, body=b""):
        self.status_code = status_code
        self._lines = lines or []
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_lines(self):
        yield from self._lines

    def read(self):
        return self._body


class _FakeClient:
    def __init__(self, response):
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def stream(self, method, url, headers=None, json=None):
        return self._response


def _gateway(monkeypatch, response):
    """A configured provider whose httpx.Client yields ``response`` and whose
    auth returns a static token without network."""
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: _FakeClient(response))
    auth = _auth()
    monkeypatch.setattr(auth, "get_token", lambda: "tok")
    return MentroGatewayProvider(gateway_url="https://gw.example", auth=auth)


def test_gateway_reduces_end_event(monkeypatch):
    lines = [
        "event: chunk",
        'data: {"choices":[{"delta":{"content":"Hel"}}]}',
        "",
        "event: end",
        'data: {"content":"Hello!","provider":"Cerebras","usage":'
        '{"prompt_tokens":20,"completion_tokens":9,"total_tokens":29}}',
        "",
    ]
    provider = _gateway(monkeypatch, _FakeStreamResponse(lines=lines))

    resp = provider.complete([LLMMessage(role="user", content="hi")], tools=[])

    assert resp.content == "Hello!"
    assert resp.provider == "mentro:Cerebras"
    assert resp.usage.promptTokens == 20
    assert resp.usage.completionTokens == 9


def test_gateway_falls_back_to_reasoning_when_content_empty(monkeypatch):
    lines = [
        "event: end",
        'data: {"content":"","reasoning":"The analysis-channel answer.",'
        '"provider":"Groq","usage":null}',
        "",
    ]
    provider = _gateway(monkeypatch, _FakeStreamResponse(lines=lines))
    resp = provider.complete([LLMMessage(role="user", content="hi")], tools=[])
    assert resp.content == "The analysis-channel answer."
    assert resp.provider == "mentro:Groq"


def test_gateway_prefers_content_over_reasoning(monkeypatch):
    lines = [
        "event: end",
        'data: {"content":"Real reply.","reasoning":"internal thoughts","provider":"Groq"}',
        "",
    ]
    provider = _gateway(monkeypatch, _FakeStreamResponse(lines=lines))
    resp = provider.complete([LLMMessage(role="user", content="hi")], tools=[])
    assert resp.content == "Real reply."


def test_gateway_error_event_becomes_provider_error(monkeypatch):
    lines = [
        "event: error",
        'data: {"code":"UPSTREAM_ERROR","message":"all tiers failed"}',
        "",
    ]
    provider = _gateway(monkeypatch, _FakeStreamResponse(lines=lines))

    with pytest.raises(ProviderError) as exc:
        provider.complete([LLMMessage(role="user", content="hi")], tools=[])
    assert "UPSTREAM_ERROR" in str(exc.value)


def test_gateway_stream_without_end_raises(monkeypatch):
    lines = ["event: chunk", 'data: {"choices":[{"delta":{"content":"x"}}]}', ""]
    provider = _gateway(monkeypatch, _FakeStreamResponse(lines=lines))

    with pytest.raises(ProviderError):
        provider.complete([LLMMessage(role="user", content="hi")], tools=[])


def test_gateway_non_200_raises(monkeypatch):
    provider = _gateway(
        monkeypatch, _FakeStreamResponse(status_code=429, body=b'{"error":"rate limited"}')
    )
    with pytest.raises(ProviderError) as exc:
        provider.complete([LLMMessage(role="user", content="hi")], tools=[])
    assert "429" in str(exc.value)


def test_gateway_unconfigured_when_auth_missing():
    provider = MentroGatewayProvider(
        gateway_url="https://gw.example",
        auth=SupabaseServiceAuth(supabase_url="", anon_key="", email="", password=""),
    )
    assert provider.configured() is False


# --- MentroGatewayProvider: empty-completion retry --------------------------


class _SequenceClient:
    """httpx.Client stand-in that yields a different response per stream() call."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def stream(self, method, url, headers=None, json=None):
        resp = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return resp


def _end(content, provider="Groq"):
    import json as _json

    payload = {"content": content, "provider": provider}
    return _FakeStreamResponse(lines=["event: end", f"data: {_json.dumps(payload)}", ""])


def _gateway_seq(monkeypatch, responses):
    client = _SequenceClient(responses)
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: client)
    auth = _auth()
    monkeypatch.setattr(auth, "get_token", lambda: "tok")
    provider = MentroGatewayProvider(gateway_url="https://gw.example", auth=auth)
    return provider, client


def test_gateway_retries_empty_then_succeeds(monkeypatch):
    # First two attempts return empty content; the third has real text.
    provider, client = _gateway_seq(monkeypatch, [_end(""), _end(""), _end("Real answer.")])
    resp = provider.complete([LLMMessage(role="user", content="hi")], tools=[])
    assert resp.content == "Real answer."
    assert client.calls == 3


def test_gateway_all_empty_raises_provider_error(monkeypatch):
    provider, client = _gateway_seq(monkeypatch, [_end(""), _end(""), _end("")])
    with pytest.raises(ProviderError) as exc:
        provider.complete([LLMMessage(role="user", content="hi")], tools=[])
    assert "empty" in str(exc.value).lower()
    # Bounded by _MAX_ATTEMPTS.
    assert client.calls == MentroGatewayProvider._MAX_ATTEMPTS
