from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app import main
from app.core.config import settings, validate_local_environment
from app.main import app


def local_env():
    return {
        "LOCAL_PREVIEW": "true",
        "DATABASE_URL": "postgresql://test:test@postgres/test",
        "MENTRO_GATEWAY_URL": "http://mentro-server:3001",
        "SUPABASE_URL": "http://fixture:3004",
    }


@pytest.mark.parametrize("name", ["DATABASE_URL", "MENTRO_GATEWAY_URL", "SUPABASE_URL"])
@pytest.mark.parametrize("value", ["", "https://hosted.example"])
def test_local_preview_rejects_missing_or_hosted_destinations(name, value):
    env = local_env()
    env[name] = value
    with pytest.raises(ValueError, match=name):
        validate_local_environment(env)


@pytest.mark.parametrize(
    "name", ["ROUTING_REMOTE_URL", "MAPBOX_API", "TRIPADVISOR_API", "AMADEUS_KEY"]
)
def test_local_preview_rejects_live_provider_configuration(name):
    env = local_env()
    env[name] = "not-a-real-secret"
    with pytest.raises(ValueError, match=name):
        validate_local_environment(env)


def test_local_preview_accepts_explicit_local_services():
    validate_local_environment(local_env())


def test_incomplete_preview_blocks_provider_routes_before_dispatch(monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_PREVIEW", True)
    client = TestClient(app)
    for path in ["/get-gas-price", "/get-initial-route", "/chats", "/validate-location"]:
        response = client.get(path)
        assert response.status_code == 503
        assert "fixtures" in response.json()["detail"]


def test_cors_allows_preview_but_not_unapproved_origin():
    client = TestClient(app)
    for origin, allowed in [("http://127.0.0.1:8082", True), ("https://unapproved.example", False)]:
        response = client.options(
            "/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
        )
        assert (response.headers.get("access-control-allow-origin") == origin) == allowed


def test_readiness_tracks_database_failure_and_recovery(monkeypatch):
    client = TestClient(app)
    conn = MagicMock()
    connect = MagicMock(side_effect=RuntimeError("offline"))
    monkeypatch.setattr(main.psycopg2, "connect", connect)
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 503
    connect.side_effect = None
    connect.return_value = conn
    conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (
        "chats",
        "route_segments",
        "steps",
        "chat_memory",
    )
    assert client.get("/ready").status_code == 200
    conn.close.assert_called_once()
    conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (
        "chats",
        None,
        None,
        None,
    )
    assert client.get("/ready").status_code == 503
