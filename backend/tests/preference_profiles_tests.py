"""Offline settings authorization, validation and SQL ownership contracts."""

from unittest.mock import MagicMock
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.agent.persona import default_weights
from app.crud import chat_crud
from app.crud import preference_profiles as store
from app.main import app
from app.schemas.preference_profiles import PreferenceProfile, PreferenceProfileInput
from app.utils.auth import require_authenticated_user


def payload():
    return {
        "name": "My car and timing",
        "choices": {"car_status": "skipped", "persona_weights": default_weights()},
    }


@pytest.fixture
def client(monkeypatch):
    # No lifespan or real connection: every store function is explicitly stubbed.
    return TestClient(app)


def test_auth_before_storage(client, monkeypatch):
    read = MagicMock()
    monkeypatch.setattr(store, "list_profiles", read)
    assert client.get("/preference-profiles").status_code == 401
    assert client.put(f"/preference-profiles/{uuid4()}", json=payload()).status_code == 401
    assert client.delete(f"/preference-profiles/{uuid4()}").status_code == 401
    read.assert_not_called()


def test_verified_owner_and_no_store_cache(client, allow_provider_auth, monkeypatch):
    profile_id = uuid4()
    data = PreferenceProfileInput.model_validate(payload())
    saved = PreferenceProfile(id=profile_id, **data.model_dump())
    read, write, delete = (
        MagicMock(return_value=[saved]),
        MagicMock(return_value=saved),
        MagicMock(),
    )
    monkeypatch.setattr(store, "list_profiles", read)
    monkeypatch.setattr(store, "save_profile", write)
    monkeypatch.setattr(store, "delete_profile", delete)
    response = client.get("/preference-profiles")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    read.assert_called_once_with("fixture-user")
    assert client.put(f"/preference-profiles/{profile_id}", json=payload()).status_code == 200
    assert write.call_args.args[0] == "fixture-user"
    assert client.delete(f"/preference-profiles/{profile_id}").status_code == 204
    delete.assert_called_once_with("fixture-user", profile_id)
    app.dependency_overrides[require_authenticated_user] = lambda: "second-user"
    client.get("/preference-profiles")
    read.assert_called_with("second-user")


@pytest.mark.parametrize(
    "change",
    [
        {"start_address": "private route"},
        {"user_id": "another-user"},
        {"num_stops": 4},
        {"car_status": "provided"},
        {"persona_weights": {"unknown": 1}},
        {"persona_weights": {**default_weights(), "nature": True}},
        {"scheduling_policy": {"morning_restart": "21:00", "preferred_hotel_arrival": "18:00"}},
    ],
)
def test_reject_invalid_and_trip_specific_choices(client, allow_provider_auth, monkeypatch, change):
    write = MagicMock()
    monkeypatch.setattr(store, "save_profile", write)
    value = payload()
    value["choices"].update(change)
    assert client.put(f"/preference-profiles/{uuid4()}", json=value).status_code == 422
    write.assert_not_called()


def test_unavailable_does_not_return_database_details(client, allow_provider_auth, monkeypatch):
    monkeypatch.setattr(
        store, "list_profiles", MagicMock(side_effect=psycopg2.OperationalError("secret"))
    )
    response = client.get("/preference-profiles")
    assert response.status_code == 503
    assert "secret" not in response.text


@pytest.fixture
def connection(monkeypatch):
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (0, 0)
    monkeypatch.setattr(chat_crud, "_get_conn", lambda: conn)
    monkeypatch.setattr(chat_crud, "_put_conn", MagicMock())
    return conn, cursor


def test_sql_scopes_every_operation_and_never_runs_ddl(connection):
    conn, cursor = connection
    profile_id = uuid4()
    cursor.fetchall.return_value = []
    assert store.list_profiles("account-a") == []
    store.save_profile("account-a", profile_id, PreferenceProfileInput.model_validate(payload()))
    store.delete_profile("account-b", profile_id)
    calls = cursor.execute.call_args_list
    for call in calls:
        sql, parameters = call.args
        assert "CREATE" not in sql
        if "pg_advisory" in sql:
            assert parameters == ("profiles:account-a",)
        else:
            assert "account-a" in parameters or "account-b" in parameters
        if "DELETE" in sql or "SELECT mem_key" in sql:
            assert "user_id = %s" in sql and "chat_id = ''" in sql and "mem_type = %s" in sql
    assert conn.commit.call_count == 2


def test_limit_per_account_allows_existing_updates_and_rolls_back(connection):
    conn, cursor = connection
    cursor.fetchone.return_value = (store.MAX_PROFILES, 0)
    with pytest.raises(store.ProfileLimitReached):
        store.save_profile("owner", uuid4(), PreferenceProfileInput.model_validate(payload()))
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    cursor.fetchone.return_value = (store.MAX_PROFILES, 1)
    store.save_profile("owner", uuid4(), PreferenceProfileInput.model_validate(payload()))
    conn.commit.assert_called_once()
