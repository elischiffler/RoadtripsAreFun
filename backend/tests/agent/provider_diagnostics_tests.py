import httpx
import pytest

from app.agent import provider_diagnostics as diagnostics
from app.agent.progress import reporting, stage
from app.agent.providers import FallbackChain, MentroGatewayProvider, ProviderError
from app.agent.schemas import LLMResponse


@pytest.fixture(autouse=True)
def no_backoff(monkeypatch):
    monkeypatch.setattr(diagnostics.time, "sleep", lambda _: None)

    async def noop(_):
        pass

    monkeypatch.setattr(diagnostics.asyncio, "sleep", noop)


@pytest.mark.parametrize("status,expected", [(429, 3), (503, 3), (401, 1), (403, 1), (400, 1)])
def test_gateway_bounded_attempts_and_preserved_chain_cause(status, expected):
    class Auth:
        def configured(self):
            return True

        def get_token(self):
            return "not-a-real-token"

    provider = MentroGatewayProvider("https://example.test", Auth())
    calls = []

    def fail(*args):
        calls.append(1)
        raise ProviderError("Upstream failed", status_code=status, provider="mentro")

    provider._stream = fail
    events = []
    with (
        diagnostics.collecting_attempts() as attempts,
        reporting(events.append),
        stage("attractions.ratings"),
    ):
        with pytest.raises(Exception) as caught:
            FallbackChain([provider]).complete([], [])
    assert len(calls) == expected
    assert len(attempts) == expected
    assert attempts[-1]["outcome"] == "failed"
    assert attempts[-1]["operation"] == "attractions.ratings"
    assert diagnostics.diagnostic(caught.value)["http_status"] == status
    assert sum(event["state"] == "retrying" for event in events) == expected - 1


def test_recovery_keeps_failed_attempts_and_records_success():
    calls = []

    def request():
        calls.append(1)
        if len(calls) < 3:
            raise httpx.ReadTimeout("URL containing private data")
        return LLMResponse(content="real reply")

    with diagnostics.collecting_attempts() as attempts:
        response = diagnostics.retry_sync(request)
    assert response.content == "real reply"
    assert [item["outcome"] for item in attempts] == ["retrying", "retrying", "recovered"]
    assert "private data" not in str(attempts)


@pytest.mark.asyncio
async def test_async_wrapped_transport_failure_retries_only_failed_operation():
    completed = []
    calls = []

    async def request():
        calls.append(1)
        if len(calls) == 1:
            try:
                raise httpx.ConnectError("private URL")
            except httpx.ConnectError as exc:
                raise RuntimeError("Provider wrapper") from exc
        return "records"

    completed.append("base route")
    with diagnostics.collecting_attempts() as attempts:
        assert await diagnostics.retry_async(request, "attractions.provider") == "records"
    assert completed == ["base route"]
    assert len(calls) == 2
    assert attempts[-1]["outcome"] == "recovered"


@pytest.mark.asyncio
async def test_cancellation_does_not_retry():
    async def cancel():
        raise diagnostics.asyncio.CancelledError()

    with diagnostics.collecting_attempts() as attempts:
        with pytest.raises(diagnostics.asyncio.CancelledError):
            await diagnostics.retry_async(cancel)
    assert attempts == []


def test_diagnostic_redacts_credentials_and_keeps_provider_code(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MENTRO_SERVICE_PASSWORD", "private-pass")
    error = ProviderError(
        'Gateway token="abc" password=private-pass Bearer xyz https://example.test?secret=abc',
        provider="mentro",
        provider_code="CONTENT_FILTERED",
    )
    saved = diagnostics.diagnostic(error)
    assert "CONTENT_FILTERED" in str(saved)
    assert "private-pass" not in str(saved)
    assert "xyz" not in str(saved)
    assert "secret=abc" not in str(saved)
    assert 'token="abc' not in str(saved)
    assert not diagnostics.retryable(error)


def test_local_planning_status_is_not_mislabeled_as_provider_http():
    from app.routing.base import PlanningError

    saved = diagnostics.diagnostic(PlanningError("Infeasible", 422))
    assert "http_status" not in saved
    assert not diagnostics.retryable(PlanningError("Infeasible", 422))


@pytest.mark.asyncio
async def test_mapbox_retries_http_faults_and_keeps_real_status(monkeypatch):
    import httpx

    from app.routing.run_metrics import measuring
    from app.routing.sources import mapbox

    calls = []

    async def fail(*args, **kwargs):
        calls.append(1)
        return httpx.Response(
            503, request=httpx.Request("GET", "https://example.test?access_token=private-token")
        )

    monkeypatch.setattr(mapbox, "http_get", fail)
    with diagnostics.collecting_attempts() as attempts, measuring() as measurements:
        with pytest.raises(httpx.HTTPStatusError):
            await mapbox.call_route(37, -122, 36, -121)
    assert len(calls) == 3
    assert measurements["calls"]["mapbox"] == 3
    assert attempts[-1]["http_status"] == 503
    assert "private-token" not in str(attempts)
