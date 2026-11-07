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


@pytest.mark.parametrize("name", ["ROUTING_REMOTE_URL", "MAPBOX_API", "OPENCAGE_KEY"])
def test_local_preview_rejects_live_provider_configuration(name):
    env = local_env()
    env[name] = "not-a-real-secret"
    with pytest.raises(ValueError, match=name):
        validate_local_environment(env)


def test_local_preview_accepts_explicit_local_services():
    validate_local_environment(local_env())
    restored = local_env()
    restored["DATABASE_URL"] = "postgresql://test:test@restore/test"
    validate_local_environment(restored)


def test_incomplete_preview_blocks_provider_routes_before_dispatch(monkeypatch):
    monkeypatch.setattr(settings, "LOCAL_PREVIEW", True)
    client = TestClient(app)
    for path in ["/get-gas-price", "/get-initial-route", "/chats", "/validate-location"]:
        response = client.get(path)
        assert response.status_code == 503
        assert "fixtures" in response.json()["detail"]


def test_cors_allows_preview_but_not_unapproved_origin():
    client = TestClient(app)
    for origin, allowed in [
        ("http://127.0.0.1:8082", True),
        ("https://roadtrips.elischiffler.dev", True),
        ("https://unapproved.example", False),
    ]:
        response = client.options(
            "/health", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
        )
        assert (response.headers.get("access-control-allow-origin") == origin) == allowed


def test_neon_private_stage_rejects_write_routes(monkeypatch):
    monkeypatch.setattr(settings, "NEON_READ_ONLY", True)
    client = TestClient(app)
    response = client.post("/chats/create/1", json={})
    assert response.status_code == 503
    assert "disabled" in response.json()["detail"]
    assert client.get("/health").status_code == 200
    preflight = client.options(
        "/chats/create/1",
        headers={
            "Origin": "https://roadtrips.elischiffler.dev",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert preflight.status_code == 200


def test_readiness_tracks_database_failure_and_recovery(monkeypatch):
    client = TestClient(app)
    conn = MagicMock()
    connect = MagicMock(side_effect=RuntimeError("offline"))
    monkeypatch.setattr(main.psycopg2, "connect", connect)
    assert client.get("/health").status_code == 200
    assert client.get("/ready").status_code == 503
    connect.side_effect = None
    connect.return_value = conn
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [
        ("table",) * 8,
        (True,),
        ("trip_shares", "trip_share_members"),
        (True,) * 8,
    ]
    cursor.fetchall.return_value = [
        (table, column, kind) for (table, column), kind in main._SHARING_COLUMN_TYPES.items()
    ]
    assert client.get("/ready").status_code == 200
    conn.close.assert_called_once()
    cursor.fetchone.side_effect = [("table",) * 5 + (None,) * 3]
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json()["dependency"] == "database_schema"


def test_readiness_requires_nonempty_active_catalog(monkeypatch):
    conn = MagicMock()
    monkeypatch.setattr(main.psycopg2, "connect", MagicMock(return_value=conn))
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [("table",) * 8, (False,)]
    response = TestClient(app).get("/ready")
    assert response.status_code == 503
    assert response.json()["dependency"] == "places_catalog"
    assert "SELECT EXISTS" in cursor.execute.call_args.args[0]
    conn.close.assert_called_once()


@pytest.fixture
def ready_database(monkeypatch):
    conn = MagicMock()
    monkeypatch.setattr(main.psycopg2, "connect", MagicMock(return_value=conn))
    cur = conn.cursor.return_value.__enter__.return_value
    cur.fetchone.side_effect = [
        ("table",) * 8,
        (True,),
        ("trip_shares", "trip_share_members"),
        (True,) * 8,
    ]
    cur.fetchall.return_value = [
        (table, column, kind) for (table, column), kind in main._SHARING_COLUMN_TYPES.items()
    ]
    return conn, cur


@pytest.mark.parametrize("missing", [0, 1])
def test_readiness_requires_each_sharing_table(ready_database, missing):
    conn, cur = ready_database
    tables = ["trip_shares", "trip_share_members"]
    tables[missing] = None
    cur.fetchone.side_effect = [("table",) * 8, (True,), tuple(tables)]
    response = TestClient(app).get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "dependency": "sharing_schema"}
    assert TestClient(app).get("/health").status_code == 200
    conn.close.assert_called_once()


@pytest.mark.parametrize("malformation", ["missing_column", "wrong_type"])
def test_readiness_requires_sharing_columns_and_types(ready_database, malformation):
    conn, cur = ready_database
    columns = list(cur.fetchall.return_value)
    if malformation == "missing_column":
        columns = [row for row in columns if row[:2] != ("trip_share_members", "share_id")]
    else:
        columns = [
            (*row[:2], "integer") if row[:2] == ("trip_shares", "id") else row for row in columns
        ]
    cur.fetchall.return_value = columns
    response = TestClient(app).get("/ready")
    assert response.status_code == 503
    assert response.json()["dependency"] == "sharing_schema"
    conn.close.assert_called_once()


@pytest.mark.parametrize("missing", range(8))
def test_readiness_requires_every_individual_sharing_privilege(ready_database, missing):
    conn, cur = ready_database
    privileges = [True] * 8
    privileges[missing] = False
    cur.fetchone.side_effect = [
        ("table",) * 8,
        (True,),
        ("trip_shares", "trip_share_members"),
        tuple(privileges),
    ]
    response = TestClient(app).get("/ready")
    assert response.status_code == 503
    assert response.json()["dependency"] == "sharing_permissions"
    query = cur.execute.call_args.args[0]
    assert query.count("has_table_privilege(current_user,") == 8
    for table in ("trip_shares", "trip_share_members"):
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            assert f"'public.{table}', '{privilege}')" in query
    conn.close.assert_called_once()


def test_readiness_select_only_sharing_role_is_insufficient(ready_database):
    _, cur = ready_database
    cur.fetchone.side_effect = [
        ("table",) * 8,
        (True,),
        ("trip_shares", "trip_share_members"),
        (True, False, False, False) * 2,
    ]
    response = TestClient(app).get("/ready")
    assert response.status_code == 503
    assert response.json()["dependency"] == "sharing_permissions"


def test_readiness_checks_sharing_without_writes_or_sensitive_failure(ready_database):
    conn, cur = ready_database
    response = TestClient(app).get("/ready")
    assert response.status_code == 200
    statements = [call.args[0] for call in cur.execute.call_args_list]
    assert all(sql.startswith(("SELECT ", "SET statement_timeout")) for sql in statements)
    assert sum("LIMIT 0" in sql for sql in statements) == 2
    conn.commit.assert_not_called()
    conn.close.assert_called_once()

    cur.reset_mock()
    cur.fetchone.side_effect = [("table",) * 8, (True,)]
    cur.execute.side_effect = lambda sql: (
        (_ for _ in ()).throw(RuntimeError("private DSN credentials"))
        if "trip_shares" in sql
        else None
    )
    response = TestClient(app).get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "dependency": "sharing_schema"}
    assert "private" not in response.text
