"""Shared structured-model contract and direct OpenAI Responses transport."""

from __future__ import annotations

import logging
import re
from typing import Protocol, runtime_checkable

import httpx

from app.agent.provider_diagnostics import MAX_ATTEMPTS, retry_sync, safe_message
from app.agent.schemas import AgentUsage, LLMMessage, LLMResponse, ToolSpec
from app.core.config import settings
from app.routing.run_metrics import increment, record_model_usage

logger = logging.getLogger(__name__)
RESPONSES_URL = "https://api.openai.com/v1/responses"
_TIMEOUT = httpx.Timeout(90.0, connect=10.0)
_MAX_OUTPUT_TOKENS = 8192
_SAFE_PROVIDER_CODES = {
    "insufficient_quota",
    "model_not_found",
    "rate_limit_exceeded",
    "server_error",
    "invalid_api_key",
}


class ProviderError(Exception):
    """A normalized provider failure with sanitized diagnostics."""

    def __init__(
        self, message, *, status_code=None, retryable=False, provider=None, provider_code=None
    ):
        self.public_message = safe_message(message)
        super().__init__(self.public_message)
        self.status_code = status_code
        self.retryable = retryable
        self.provider = provider
        self.provider_code = provider_code


class ProviderNotConfigured(ProviderError):
    """The provider is missing required server configuration."""


class ProvidersExhausted(Exception):
    """No provider successfully served the request."""


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def complete(self, messages: list[LLMMessage], tools: list[ToolSpec]) -> LLMResponse:
        """Return one normalized structured response or raise ProviderError."""
        ...


class OpenAIProvider:
    """Stateless OpenAI calls for ratings, trip details and duration estimates."""

    name = "openai"

    def __init__(self, api_key: str | None = None):
        self._key = (api_key if api_key is not None else settings.ROADTRIPS_OPENAI_API_KEY) or ""

    def configured(self) -> bool:
        return bool(self._key.strip())

    def complete(self, messages: list[LLMMessage], tools: list[ToolSpec]) -> LLMResponse:
        attempts = 0

        def request():
            nonlocal attempts
            attempts += 1
            try:
                return self.complete_once(messages, tools)
            except ProviderError as exc:
                if exc.provider_code == "EMPTY_COMPLETION":
                    increment(
                        "llm_empty_retries"
                        if attempts < MAX_ATTEMPTS
                        else "llm_empty_attempt_caps",
                        "events",
                    )
                raise

        return retry_sync(request)

    def complete_once(self, messages: list[LLMMessage], tools: list[ToolSpec]) -> LLMResponse:
        if not self.configured():
            raise ProviderNotConfigured("ROADTRIPS_OPENAI_API_KEY is not set.", provider=self.name)
        # Current callers ask for JSON. Keep trusted instructions and user content
        # separately typed and keep the app's own validators authoritative.
        payload = {
            "model": settings.ROADTRIPS_OPENAI_MODEL,
            "input": [
                {"role": m.role, "content": m.content}
                for m in messages
                if m.role in {"system", "user", "assistant"} and m.content.strip()
            ],
            "text": {"format": {"type": "json_object"}},
            "max_output_tokens": _MAX_OUTPUT_TOKENS,
            "store": False,
        }
        if not payload["input"] or tools:
            raise ProviderError("OpenAI requires a structured text request.", provider=self.name)
        from app.routing.runtime import sync_http_client

        try:
            with sync_http_client() as client:
                increment("language_model")
                response = client.post(
                    RESPONSES_URL,
                    headers={"Authorization": f"Bearer {self._key.strip()}"},
                    json=payload,
                    timeout=_TIMEOUT,
                    follow_redirects=False,
                )
        except httpx.HTTPError as exc:
            raise ProviderError("OpenAI network request failed.", provider=self.name) from exc
        if response.status_code != 200:
            raise self._failed_request(response)
        return self._decode(response)

    def _failed_request(self, response):
        code = None
        try:
            value = response.json()["error"]["code"]
            if isinstance(value, str) and value in _SAFE_PROVIDER_CODES:
                code = value
        except (ValueError, KeyError, TypeError):
            pass
        error = ProviderError(
            f"OpenAI returned HTTP {response.status_code}.",
            status_code=response.status_code,
            provider=self.name,
            provider_code=code,
        )
        retry_after = response.headers.get("Retry-After", "")
        if re.fullmatch(r"\d{1,3}(?:\.\d+)?", retry_after):
            error.retry_after = str(min(15.0, float(retry_after)))
        return error

    def _decode(self, response):
        try:
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError
            if body.get("status") != "completed":
                raise ProviderError("OpenAI did not finish the response.", provider=self.name)
            parts = [
                part
                for item in body["output"]
                if item.get("type") == "message" and item.get("role") == "assistant"
                for part in item["content"]
            ]
            if any(part.get("type") == "refusal" for part in parts):
                raise ProviderError("OpenAI declined the structured request.", provider=self.name)
            text = "".join(part["text"] for part in parts if part.get("type") == "output_text")
            usage = body.get("usage")
            model = body["model"]
            if not isinstance(model, str) or not re.fullmatch(
                r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}", model
            ):
                raise ValueError
            if usage is not None:
                usage = AgentUsage(
                    promptTokens=usage.get("input_tokens"),
                    completionTokens=usage.get("output_tokens"),
                )
        except (KeyError, AttributeError, TypeError, ValueError):
            raise ProviderError(
                "OpenAI returned an invalid response.", provider=self.name
            ) from None
        if not text.strip():
            raise ProviderError(
                "OpenAI returned an empty completion.",
                retryable=True,
                provider=self.name,
                provider_code="EMPTY_COMPLETION",
            )
        record_model_usage(self.name, model, usage)
        return LLMResponse(content=text.strip(), provider=self.name, model=model, usage=usage)


class FallbackChain:
    """An :class:`LLMProvider` that tries each provider in order.

    Unconfigured providers are skipped. A :class:`ProviderError` from one
    provider advances to the next. If nothing is configured or every attempt
    fails, :class:`ProvidersExhausted` is raised. The served provider's name is
    echoed in :attr:`LLMResponse.provider`.

    Production supplies Direct OpenAI as the sole provider.
    """

    name = "fallback"

    def __init__(self, providers: list[LLMProvider]):
        self._providers = list(providers)

    def complete_once(self, messages: list[LLMMessage], tools: list[ToolSpec]) -> LLMResponse:
        return self._complete(messages, tools, once=True)

    def complete(self, messages: list[LLMMessage], tools: list[ToolSpec]) -> LLMResponse:
        return self._complete(messages, tools, once=False)

    def _complete(self, messages, tools, *, once):
        errors: list[str] = []
        last_error = None
        for provider in self._providers:
            # ``configured`` is optional on the Protocol; only skip when a
            # provider explicitly reports itself unconfigured.
            check = getattr(provider, "configured", None)
            if callable(check) and not check():
                last_error = ProviderNotConfigured(
                    f"{provider.name}: not configured", provider=provider.name
                )
                errors.append(f"{provider.name}: skipped (not configured)")
                continue
            try:
                response = (
                    getattr(provider, "complete_once", provider.complete)
                    if once
                    else provider.complete
                )(messages, tools)
            except ProviderError as exc:
                last_error = exc
                errors.append(f"{provider.name}: {exc.public_message}")
                continue
            except Exception as exc:  # noqa: BLE001
                # Defensive: a provider should raise only ProviderError, but any
                # unexpected fault (e.g. a JSON/parse error, an httpx quirk) must
                # NOT escape the chain as an uncaught 500. Log it and advance so a
                # provider hiccup degrades to a clean ProvidersExhausted -> 503.
                last_error = exc
                logger.error("provider %s raised %s", provider.name, type(exc).__name__)
                errors.append(f"{provider.name}: unexpected {type(exc).__name__}")
                continue
            # Record who actually served the request.
            if not response.provider:
                response.provider = provider.name
            return response
        raise ProvidersExhausted(
            "All LLM providers were unconfigured or failed: " + "; ".join(errors)
        ) from last_error


def build_default_chain() -> FallbackChain:
    """Use only the configured direct OpenAI project; failures remain explicit."""
    return FallbackChain([OpenAIProvider()])
