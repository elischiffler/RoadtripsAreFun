"""Deterministic direct OpenAI contract and provider-chain behavior."""

import json

import httpx
import pytest

from app.agent.providers import (
    FallbackChain,
    OpenAIProvider,
    ProviderError,
    ProviderNotConfigured,
    ProvidersExhausted,
    build_default_chain,
)
from app.agent.schemas import LLMMessage, LLMResponse

from .conftest import FakeProvider


@pytest.fixture(autouse=True)
def skip_retry_backoff(monkeypatch):
    monkeypatch.setattr("app.agent.provider_diagnostics.time.sleep", lambda _: None)


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


def test_build_default_chain_is_direct_openai_only():
    chain = build_default_chain()
    names = [p.name for p in chain._providers]
    assert names == ["openai"]


MESSAGES = [
    LLMMessage(role="system", content="Return JSON."),
    LLMMessage(role="user", content="A trip with two stops."),
]


def hook_transport(monkeypatch, handler):
    monkeypatch.setattr(
        "app.routing.runtime.sync_http_client",
        lambda: httpx.Client(transport=httpx.MockTransport(handler)),
    )


def response_data(*, content=None, status="completed"):
    return {
        "status": status,
        "model": "gpt-5.4-mini-2026-03-17",
        "usage": {"input_tokens": 123, "output_tokens": 27},
        "output": [
            {
                "type": "reasoning",
                "summary": [{"type": "summary_text", "text": "private analysis"}],
            },
            {
                "type": "message",
                "role": "assistant",
                "content": content
                or [
                    {"type": "output_text", "text": '{"details":{"num_stops":2}}'},
                ],
            },
        ],
    }


def test_openai_responses_request_preserves_roles_usage_and_model(monkeypatch):
    from app.routing.run_metrics import measuring

    def handle(request):
        assert request.method == "POST"
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert request.headers["Authorization"] == "Bearer synthetic-test-key"
        assert json.loads(request.content) == {
            "model": "gpt-5.4-mini-2026-03-17",
            "input": [{"role": message.role, "content": message.content} for message in MESSAGES],
            "max_output_tokens": 8192,
            "store": False,
            "text": {"format": {"type": "json_object"}},
        }
        return httpx.Response(200, json=response_data())

    monkeypatch.setattr(
        "app.core.config.settings.ROADTRIPS_OPENAI_MODEL", "gpt-5.4-mini-2026-03-17"
    )
    hook_transport(monkeypatch, handle)
    with measuring() as metrics:
        answer = OpenAIProvider(api_key="synthetic-test-key").complete_once(MESSAGES, [])
    assert json.loads(answer.content) == {"details": {"num_stops": 2}}
    assert answer.provider == "openai"
    assert answer.model == "gpt-5.4-mini-2026-03-17"
    assert answer.usage.promptTokens == 123
    assert answer.usage.completionTokens == 27
    assert metrics["calls"] == {"language_model": 1}
    assert metrics["language_models"] == {
        "openai:gpt-5.4-mini-2026-03-17": {"responses": 1, "input_tokens": 123, "output_tokens": 27}
    }


def test_missing_key_never_requests_a_provider(monkeypatch):
    hook_transport(monkeypatch, lambda request: pytest.fail("Unexpected HTTP request"))
    with pytest.raises(ProviderNotConfigured, match="ROADTRIPS_OPENAI_API_KEY"):
        OpenAIProvider(api_key="").complete_once(MESSAGES, [])


def test_openai_refusal_never_returns_reasoning_or_retries(monkeypatch):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200, json=response_data(content=[{"type": "refusal", "refusal": "Private input"}])
        )

    hook_transport(monkeypatch, handle)
    with pytest.raises(ProviderError, match="declined") as caught:
        OpenAIProvider(api_key="synthetic-test-key").complete(MESSAGES, [])
    assert len(requests) == 1
    assert "Private input" not in str(caught.value)


def test_openai_incomplete_response_never_returns_a_partial_result(monkeypatch):
    hook_transport(
        monkeypatch, lambda request: httpx.Response(200, json=response_data(status="incomplete"))
    )
    with pytest.raises(ProviderError, match="did not finish"):
        OpenAIProvider(api_key="synthetic-test-key").complete(MESSAGES, [])


def test_openai_does_not_redirect_or_expose_a_failed_request_body(monkeypatch):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            307,
            headers={"Location": "https://unexpected.example/"},
            json={"error": {"message": "fixture-sensitive-output"}},
        )

    hook_transport(monkeypatch, handle)
    with pytest.raises(ProviderError, match="HTTP 307") as caught:
        OpenAIProvider(api_key="synthetic-test-key").complete(MESSAGES, [])
    assert len(requests) == 1
    assert "fixture-sensitive-output" not in str(caught.value)


def test_openai_single_attempt_for_quota_exhaustion(monkeypatch):
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(429, json={"error": {"code": "insufficient_quota"}})

    hook_transport(monkeypatch, handle)
    with pytest.raises(ProviderError) as caught:
        OpenAIProvider(api_key="synthetic-test-key").complete(MESSAGES, [])
    assert caught.value.provider_code == "insufficient_quota"
    assert len(requests) == 1
