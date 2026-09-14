"""LLM provider interface + the Mentro gateway provider + fallback chain (§6).

The chat agent's single LLM provider is the **self-hosted Mentro gateway** — a
separate service the user owns that fronts several inference tiers
(Cerebras -> Groq -> Together) and streams an OpenAI-compatible completion over
Server-Sent Events. Our backend is the *agent brain* (memory + tools + the
loop); the gateway is just the leaf that produces text.

Two responsibilities live here:

- :class:`MentroGatewayProvider` — authenticates to the gateway with a Supabase
  JWT (minted server-side from a service account), POSTs the assembled messages
  to ``/api/chat/stream-full``, consumes the SSE stream, and returns the final
  aggregated ``end`` payload as a normalized :class:`LLMResponse`. Non-streaming
  from the agent loop's point of view: we consume the whole stream server-side
  and hand back one response, which keeps the tool loop simple.
- :class:`FallbackChain` — a thin :class:`LLMProvider` that tries providers in
  order, skips unconfigured ones, advances past a :class:`ProviderError`, and
  raises :class:`ProvidersExhausted` when nothing serves. Today the chain holds
  just the gateway, but it stays so a second provider can be added without
  touching the loop.

Auth seam: :class:`SupabaseServiceAuth` isolates *how* we obtain a token
(service-account password grant + refresh) from the provider, so the token
strategy can change without touching the HTTP call.
"""

from __future__ import annotations

import logging
import time
from typing import Protocol, runtime_checkable

import httpx

from app.agent.schemas import AgentUsage, LLMMessage, LLMResponse, ToolSpec
from app.core.config import settings

logger = logging.getLogger(__name__)

# (connect, read) timeouts. The gateway auto-stops when idle on Fly.io, so the
# first call after a cold start can take a few seconds — the read timeout is
# generous to absorb that.
_CONNECT_TIMEOUT = 10.0
_READ_TIMEOUT = 90.0


class ProviderError(Exception):
    """A recoverable provider failure (network, 5xx, 429, timeout, auth).

    Raising this signals :class:`FallbackChain` to move on to the next provider.
    """


class ProviderNotConfigured(ProviderError):
    """The provider is missing the config it needs to be attempted.

    Subclasses :class:`ProviderError` so the chain skips/advances past it rather
    than crashing — an unconfigured agent simply yields ``ProvidersExhausted``,
    which the router maps to a clean 503.
    """


class ProvidersExhausted(Exception):
    """Every provider was unconfigured or failed — no response could be served."""


@runtime_checkable
class LLMProvider(Protocol):
    """Provider interface: a name plus a normalized ``complete`` call."""

    name: str

    def complete(self, messages: list[LLMMessage], tools: list[ToolSpec]) -> LLMResponse:
        """Return an :class:`LLMResponse`, or raise :class:`ProviderError`."""
        ...


# --------------------------------------------------------------------------- #
# Auth seam — obtaining a Supabase access token for the gateway.
# --------------------------------------------------------------------------- #


class SupabaseServiceAuth:
    """Mints and caches a Supabase access token for a service account.

    Uses Supabase's password grant (``/auth/v1/token?grant_type=password``) with
    a dedicated service-account email/password, then refreshes with the returned
    refresh token before expiry. Keeping this behind its own object means the
    provider doesn't care whether the token comes from a service account, a
    static long-lived token, or (later) a per-user session — only that
    :meth:`get_token` returns a bearer string.
    """

    # Refresh this many seconds before the token's stated expiry to avoid using
    # a token that lapses mid-flight.
    _EXPIRY_SKEW = 60.0

    def __init__(
        self,
        supabase_url: str | None = None,
        anon_key: str | None = None,
        email: str | None = None,
        password: str | None = None,
    ):
        self._url = (supabase_url if supabase_url is not None else settings.SUPABASE_URL) or ""
        self._anon_key = (anon_key if anon_key is not None else settings.SUPABASE_ANON_KEY) or ""
        self._email = (email if email is not None else settings.MENTRO_SERVICE_EMAIL) or ""
        self._password = (
            password if password is not None else settings.MENTRO_SERVICE_PASSWORD
        ) or ""
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0.0

    def configured(self) -> bool:
        """True when all Supabase service-account credentials are present."""
        return bool(self._url and self._anon_key and self._email and self._password)

    def get_token(self) -> str:
        """Return a valid access token, refreshing/logging in as needed.

        Raises:
            ProviderNotConfigured: If Supabase creds are missing.
            ProviderError: If the auth request to Supabase fails.
        """
        if not self.configured():
            raise ProviderNotConfigured(
                "Mentro gateway auth is not configured: set SUPABASE_URL, "
                "SUPABASE_ANON_KEY, MENTRO_SERVICE_EMAIL, MENTRO_SERVICE_PASSWORD."
            )
        now = time.monotonic()
        if self._access_token and now < self._expires_at - self._EXPIRY_SKEW:
            return self._access_token
        # Prefer a refresh when we have a refresh token; otherwise password login.
        if self._refresh_token:
            try:
                return self._grant("refresh_token", {"refresh_token": self._refresh_token})
            except ProviderError:
                # Refresh token may be stale — fall back to a fresh password login.
                logger.info("Supabase refresh failed; re-authenticating with password grant.")
        return self._grant(
            "password", {"email": self._email, "password": self._password}
        )

    def _grant(self, grant_type: str, body: dict) -> str:
        token_url = f"{self._url.rstrip('/')}/auth/v1/token"
        try:
            resp = httpx.post(
                token_url,
                params={"grant_type": grant_type},
                headers={"apikey": self._anon_key, "Content-Type": "application/json"},
                json=body,
                timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT),
            )
        except httpx.HTTPError as exc:
            raise ProviderError(f"Supabase auth request failed: {exc}") from exc
        if resp.status_code != httpx.codes.OK:
            raise ProviderError(
                f"Supabase auth returned {resp.status_code}: {resp.text[:200]}"
            )
        try:
            data = resp.json()
        except ValueError as exc:
            # A 200 with a non-JSON body (proxy/HTML error page, empty body). Treat
            # as a recoverable provider failure, not an uncaught 500.
            raise ProviderError(
                f"Supabase auth returned a non-JSON body: {resp.text[:200]}"
            ) from exc
        access = data.get("access_token")
        if not access:
            raise ProviderError("Supabase auth response had no access_token.")
        self._access_token = access
        self._refresh_token = data.get("refresh_token") or self._refresh_token
        # expires_in is seconds from now; default to a conservative 1h if absent.
        expires_in = float(data.get("expires_in") or 3600)
        self._expires_at = time.monotonic() + expires_in
        return access


# --------------------------------------------------------------------------- #
# The Mentro gateway provider.
# --------------------------------------------------------------------------- #


def _messages_to_gateway_payload(messages: list[LLMMessage]) -> list[dict]:
    """Flatten our LLMMessages into the gateway's {role, content} contract.

    The gateway only accepts roles ``user`` / ``assistant`` / ``system`` and a
    non-empty string ``content``. Our loop can produce ``tool`` messages and
    assistant turns carrying ``tool_calls``; since the gateway itself has no
    native tool-calling, we render those into plain text so the model still sees
    them as context. Empty-content messages are dropped (the gateway rejects
    them).
    """
    out: list[dict] = []
    for m in messages:
        role = m.role
        content = m.content or ""
        if role == "tool":
            # Represent a tool result as an assistant-visible system note.
            role = "system"
            content = f"[tool result] {content}" if content else ""
        elif role == "assistant" and m.tool_calls and not content:
            # An assistant turn that only requested tools — summarize it as text.
            names = ", ".join(tc.name for tc in m.tool_calls)
            content = f"[requested tools: {names}]"
        if role not in ("user", "assistant", "system"):
            role = "user"
        if content.strip():
            out.append({"role": role, "content": content})
    return out


class MentroGatewayProvider:
    """Calls the self-hosted Mentro SSE gateway and returns its final reply.

    Consumes the whole SSE stream server-side and returns the aggregated ``end``
    payload (assembled ``content`` + ``usage`` + which upstream tier served it)
    as an :class:`LLMResponse`. Failures — missing config, Supabase auth errors,
    non-2xx from the gateway, an SSE ``error`` event, or a network fault — are
    raised as :class:`ProviderError` so :class:`FallbackChain` can advance.

    Tool specs are accepted for interface compatibility but not forwarded: the
    gateway has no native function-calling. Tool *use* is driven by our own loop
    via the system prompt + the assembled message history.
    """

    name = "mentro"

    # The gateway's upstream tiers intermittently return an empty completion
    # (empty content, no usage). Retry a bounded number of times before giving
    # up, since a retry frequently lands on a tier that produces real text.
    _MAX_ATTEMPTS = 3

    def __init__(self, gateway_url: str | None = None, auth: SupabaseServiceAuth | None = None):
        self._url = (
            gateway_url if gateway_url is not None else settings.MENTRO_GATEWAY_URL
        ) or ""
        self._auth = auth if auth is not None else SupabaseServiceAuth()

    def configured(self) -> bool:
        """True when we have a gateway URL and the auth seam is configured."""
        return bool(self._url) and self._auth.configured()

    def complete(self, messages: list[LLMMessage], tools: list[ToolSpec]) -> LLMResponse:
        if not self._url:
            raise ProviderNotConfigured("MENTRO_GATEWAY_URL is not set.")
        payload = {"messages": _messages_to_gateway_payload(messages)}
        endpoint = f"{self._url.rstrip('/')}/api/chat/stream-full"

        last_error: ProviderError | None = None
        for attempt in range(1, self._MAX_ATTEMPTS + 1):
            token = self._auth.get_token()  # may raise ProviderNotConfigured / ProviderError
            try:
                response = self._stream(endpoint, token, payload)
            except httpx.HTTPError as exc:
                raise ProviderError(f"Mentro gateway request failed: {exc}") from exc
            # Treat an empty completion as a transient failure worth retrying —
            # the gateway occasionally returns blank content with no usage.
            if response.content.strip():
                return response
            last_error = ProviderError(
                f"Mentro gateway returned an empty completion (attempt {attempt})."
            )
            logger.info(
                "Mentro gateway empty completion on attempt %s/%s; retrying.",
                attempt,
                self._MAX_ATTEMPTS,
            )
        # Exhausted retries with only empty responses.
        raise last_error or ProviderError("Mentro gateway returned only empty completions.")

    def _stream(self, endpoint: str, token: str, payload: dict) -> LLMResponse:
        """POST to the gateway and reduce the SSE stream to the final response."""
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        with httpx.Client(timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT)) as client:
            with client.stream("POST", endpoint, headers=headers, json=payload) as resp:
                # Pre-stream failures (validation/auth/rate-limit) come back as a
                # plain-JSON body with a non-2xx status, NOT as SSE.
                if resp.status_code != httpx.codes.OK:
                    body = resp.read().decode(errors="replace")
                    raise ProviderError(
                        f"Mentro gateway returned {resp.status_code}: {body[:200]}"
                    )
                return self._reduce_sse(resp.iter_lines())

    def _reduce_sse(self, lines) -> LLMResponse:
        """Parse an SSE line iterator into the final :class:`LLMResponse`.

        We only need the ``end`` event's aggregated payload; ``chunk`` events are
        ignored (no live streaming to the caller in v1). An ``error`` event —
        which can arrive *after* a 200 OK once streaming has begun — is turned
        into a :class:`ProviderError`.
        """
        import json

        event_name = "message"
        data_parts: list[str] = []

        def flush() -> LLMResponse | None:
            nonlocal event_name, data_parts
            if not data_parts:
                event_name = "message"
                return None
            raw = "".join(data_parts)
            event, data_parts = event_name, []
            event_name = "message"
            if not raw.strip():
                return None
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                return None
            if event == "end":
                return self._response_from_end(payload)
            if event == "error":
                code = payload.get("code", "STREAM_FAILURE")
                message = payload.get("message", "unknown gateway error")
                raise ProviderError(f"Mentro gateway error [{code}]: {message}")
            return None  # a "chunk" or unknown event — ignored

        for raw_line in lines:
            line = raw_line.rstrip("\n").rstrip("\r")
            if line == "":
                result = flush()
                if result is not None:
                    return result
                continue
            if line.startswith("event:"):
                event_name = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_parts.append(line[len("data:") :].strip())
        # Stream closed — flush any trailing buffered event.
        result = flush()
        if result is not None:
            return result
        raise ProviderError("Mentro gateway stream closed without an 'end' event.")

    def _response_from_end(self, payload: dict) -> LLMResponse:
        """Map the gateway's aggregated ``end`` payload into an LLMResponse.

        The gateway already falls back to reasoning-channel text when the model's
        ``content`` channel is empty (reasoning models like ``gpt-oss`` stream
        their output on the analysis channel). We still prefer ``content`` and
        fall back to the separate ``reasoning`` field defensively, so a valid
        reply is never dropped even if the gateway's own fallback changes.
        """
        usage_raw = payload.get("usage") or None
        usage = None
        if isinstance(usage_raw, dict):
            usage = AgentUsage(
                promptTokens=usage_raw.get("prompt_tokens"),
                completionTokens=usage_raw.get("completion_tokens"),
            )
        # Record the upstream tier the gateway actually used (e.g. "Cerebras"),
        # namespaced so it's clear it came via our gateway.
        upstream = payload.get("provider")
        provider = f"mentro:{upstream}" if upstream else self.name
        content = (payload.get("content") or "").strip()
        if not content:
            # Defensive fallback: use the analysis-channel text if content is blank.
            content = (payload.get("reasoning") or "").strip()
        return LLMResponse(
            content=content,
            tool_calls=[],  # gateway has no native tool-calling
            provider=provider,
            usage=usage,
        )


# --------------------------------------------------------------------------- #
# Fallback chain.
# --------------------------------------------------------------------------- #


class FallbackChain:
    """An :class:`LLMProvider` that tries each provider in order.

    Unconfigured providers are skipped. A :class:`ProviderError` from one
    provider advances to the next. If nothing is configured or every attempt
    fails, :class:`ProvidersExhausted` is raised. The served provider's name is
    echoed in :attr:`LLMResponse.provider`.

    The chain currently holds a single provider (the gateway), but it stays as a
    seam so a second provider can be slotted in without touching the loop.
    """

    name = "fallback"

    def __init__(self, providers: list[LLMProvider]):
        self._providers = list(providers)

    def complete(self, messages: list[LLMMessage], tools: list[ToolSpec]) -> LLMResponse:
        errors: list[str] = []
        for provider in self._providers:
            # ``configured`` is optional on the Protocol; only skip when a
            # provider explicitly reports itself unconfigured.
            check = getattr(provider, "configured", None)
            if callable(check) and not check():
                errors.append(f"{provider.name}: skipped (not configured)")
                continue
            try:
                response = provider.complete(messages, tools)
            except ProviderError as exc:
                errors.append(f"{provider.name}: {exc}")
                continue
            except Exception as exc:  # noqa: BLE001
                # Defensive: a provider should raise only ProviderError, but any
                # unexpected fault (e.g. a JSON/parse error, an httpx quirk) must
                # NOT escape the chain as an uncaught 500. Log it and advance so a
                # provider hiccup degrades to a clean ProvidersExhausted -> 503.
                logger.exception("provider %s raised an unexpected error", provider.name)
                errors.append(f"{provider.name}: unexpected {type(exc).__name__}: {exc}")
                continue
            # Record who actually served the request.
            if not response.provider:
                response.provider = provider.name
            return response
        raise ProvidersExhausted(
            "All LLM providers were unconfigured or failed: " + "; ".join(errors)
        )


def build_default_chain() -> FallbackChain:
    """Factory: the default provider chain — just the Mentro gateway for now."""
    return FallbackChain([MentroGatewayProvider()])
