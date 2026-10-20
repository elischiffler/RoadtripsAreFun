"""Synthetic route acquisition tests never call OSRM or paid providers."""

import hashlib
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "catalog_test_routes",
    Path(__file__).resolve().parents[2] / "scripts/catalog_test_routes.py",
)
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class FakeClock:
    def __init__(self):
        self.value = 0.0
        self.delays = []

    def monotonic(self):
        return self.value

    def sleep(self, seconds):
        self.delays.append(seconds)
        self.value += seconds


class Response:
    def __init__(self, url, *, body=None, status=200, headers=None):
        self.url = url
        self.status_code = status
        self.headers = {"Content-Type": "application/json", **(headers or {})}
        self.body = (
            body
            if body is not None
            else json.dumps(
                {
                    "code": "Ok",
                    "routes": [
                        {
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [[-122.4, 37.7], [-122.3, 37.8]],
                            }
                        }
                    ],
                }
            ).encode()
        )
        self.closed = False

    def iter_content(self, chunk_size):
        assert chunk_size == 64 * 1024
        yield self.body

    def close(self):
        self.closed = True


def acquire(tmp_path, request, *, include_optional=True):
    clock = FakeClock()
    path = capture.acquire(
        tmp_path / "routes",
        request_get=request,
        include_optional=include_optional,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        now=lambda: datetime(2026, 10, 20, tzinfo=UTC),
    )
    return path, clock


def test_complete_capture_validates_receipts_and_never_exceeds_one_request_per_second(tmp_path):
    starts, responses, calls = [], [], []
    clock = FakeClock()

    def request(url, **kwargs):
        starts.append(clock.monotonic())
        calls.append(kwargs)
        response = Response(url)
        responses.append(response)
        return response

    output = tmp_path / "immutable"
    path = capture.acquire(
        output,
        request_get=request,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        now=lambda: datetime(2026, 10, 20, tzinfo=UTC),
    )
    index = json.loads(path.read_text())
    assert len(index["routes"]) == len(index["receipts"]) == 8
    assert starts == list(range(8))
    assert all(call["allow_redirects"] is False and call["stream"] is True for call in calls)
    assert all(call["timeout"] == (5, 30) for call in calls)
    assert all("Authorization" not in call["headers"] for call in calls)
    assert all(response.closed for response in responses)
    loaded, _ = capture.validate_routes(path, output.resolve())
    assert len(loaded) == 8
    for receipt in index["receipts"]:
        body = (output / receipt["path"]).read_bytes()
        assert receipt["sha256"] == hashlib.sha256(body).hexdigest()
        assert receipt["bytes"] == len(body)
        assert receipt["retrieved_at"] == "2026-10-20T00:00:00+00:00"
        assert receipt["url"].startswith(capture.SERVER + "/route/v1/driving/")
    assert "OpenStreetMap" in index["attribution"]


def test_current_studio_pairs_are_exact_and_optional_routes_can_be_excluded(tmp_path):
    path, _ = acquire(tmp_path, lambda url, **kwargs: Response(url), include_optional=False)
    index = json.loads(path.read_text())
    assert len(index["routes"]) == 6
    expected = {("sf", value[1]) for value in capture.PRESETS.values()} | {
        (value[1], value[2]) for value in capture.BENCHMARKS.values()
    }
    assert {(r["start_id"], r["destination_id"]) for r in index["routes"]} == expected
    sf = next(r for r in index["routes"] if r["id"] == "dense-corridor")
    assert sf["endpoint_coordinates_lat_lon"][0] == capture.ENDPOINTS["sf"]["coordinates"]


def test_changed_studio_pairs_fail_before_network_or_output(tmp_path, monkeypatch):
    monkeypatch.setattr(capture, "PRESETS", {"new": ("New", "unknown", 2, {})})
    with pytest.raises(ValueError, match="corridors changed"):
        acquire(tmp_path, lambda *args, **kwargs: pytest.fail("network forbidden"))
    assert not (tmp_path / "routes").exists()


def test_existing_output_is_never_overwritten_or_fetched_again(tmp_path):
    directory = tmp_path / "routes"
    directory.mkdir()
    (directory / "sentinel").write_text("preserve")
    with pytest.raises(ValueError, match="already exists"):
        acquire(tmp_path, lambda *args, **kwargs: pytest.fail("network forbidden"))
    assert (directory / "sentinel").read_text() == "preserve"


@pytest.mark.parametrize("status,changed_url", [(302, False), (200, True)])
def test_redirect_or_changed_destination_is_rejected_without_publishing(
    tmp_path, status, changed_url
):
    responses = []

    def request(url, **kwargs):
        assert kwargs["allow_redirects"] is False
        response = Response("https://other.example/" if changed_url else url, status=status)
        responses.append(response)
        return response

    with pytest.raises(ValueError, match="fixed requested URL"):
        acquire(tmp_path, request)
    assert all(response.closed for response in responses)
    assert not (tmp_path / "routes").exists()
    assert not list(tmp_path.glob(".routes.partial-*"))


@pytest.mark.parametrize("declared", [True, False])
def test_body_ceiling_is_checked_for_declared_and_chunked_responses(tmp_path, declared):
    def request(url, **kwargs):
        return Response(
            url,
            body=b"x" * (capture.MAX_RESPONSE_BYTES + 1),
            headers={"Content-Length": str(capture.MAX_RESPONSE_BYTES + 1)} if declared else None,
        )

    with pytest.raises(ValueError, match="two-MiB ceiling"):
        acquire(tmp_path, request)
    assert not (tmp_path / "routes").exists()


def test_malformed_successful_geojson_cannot_publish_a_capture(tmp_path):
    bad = json.dumps(
        {
            "code": "Ok",
            "routes": [
                {
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[-122, 37], [float("nan"), 38]],
                    }
                }
            ],
        }
    ).encode()
    with pytest.raises(ValueError, match="driving geometry"):
        acquire(tmp_path, lambda url, **kwargs: Response(url, body=bad))
    assert not (tmp_path / "routes").exists()


def test_real_session_disables_ambient_credentials_and_closes_on_failure(tmp_path, monkeypatch):
    class Session:
        trust_env = True
        auth = "ambient-secret-never-used"
        closed = False

        def get(self, url, **kwargs):
            assert self.trust_env is False and self.auth is None
            return Response(url, status=503)

        def close(self):
            self.closed = True

    session = Session()
    monkeypatch.setattr(capture.requests, "Session", lambda: session)
    with pytest.raises(ValueError, match="successful response"):
        capture.acquire(tmp_path / "routes")
    assert session.closed
    assert not (tmp_path / "routes").exists()
