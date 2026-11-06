"""Trip car HTTP validation, identity protection and isolated SQL update tests."""

from unittest.mock import MagicMock

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.crud import chat_crud, trip_car
from app.main import app
from app.routers import trip_car as api
from app.schemas.trip_car import TripCarUpdate


def payload(**changes):
    return {
        "car_status": "provided",
        "car": {"year": 2020, "make": "Honda", "model": "Civic"},
        "expected_agent_chat_id": "original-trip",
        **changes,
    }


def test_auth_required(monkeypatch):
    write = MagicMock()
    monkeypatch.setattr(api, "update_trip_car", write)
    assert TestClient(app).put("/chats/3/car", json=payload()).status_code == 401
    write.assert_not_called()


def test_verified_owner_and_validated_response(allow_provider_auth, monkeypatch):
    write = MagicMock(return_value=True)
    monkeypatch.setattr(api, "update_trip_car", write)
    response = TestClient(app).put("/chats/3/car", json=payload())
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {"car_status": "provided", "car": payload()["car"]}
    owner, chat_id, value = write.call_args.args
    assert owner == "fixture-user" and chat_id == 3
    assert value.expected_agent_chat_id == "original-trip"


@pytest.mark.parametrize(
    "patch",
    [
        {"car_status": "unanswered"},
        {"car_status": "skipped"},
        {"car": None},
        {"car": {"year": 1900, "make": "Honda", "model": "Civic"}},
        {"car": {"year": 2020, "make": " ", "model": "Civic"}},
        {"user_id": "other"},
    ],
)
def test_invalid_car_has_no_write(allow_provider_auth, monkeypatch, patch):
    write = MagicMock()
    monkeypatch.setattr(api, "update_trip_car", write)
    assert TestClient(app).put("/chats/3/car", json=payload(**patch)).status_code == 422
    write.assert_not_called()


def test_deleted_or_reused_trip_and_storage_error(allow_provider_auth, monkeypatch):
    monkeypatch.setattr(api, "update_trip_car", lambda *args: False)
    assert TestClient(app).put("/chats/3/car", json=payload()).status_code == 404
    monkeypatch.setattr(
        api, "update_trip_car", MagicMock(side_effect=psycopg2.OperationalError("secret"))
    )
    response = TestClient(app).put("/chats/3/car", json=payload())
    assert response.status_code == 503 and "secret" not in response.text


def test_atomic_car_update_is_scoped_and_rolls_back(monkeypatch):
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = ("3",)
    monkeypatch.setattr(chat_crud, "_get_conn", lambda: conn)
    release = MagicMock()
    monkeypatch.setattr(chat_crud, "_put_conn", release)
    value = TripCarUpdate.model_validate(payload())
    assert trip_car.update_trip_car("owner-a", 3, value)
    sql, parameters = cursor.execute.call_args.args
    assert "user_id = %s AND chat_id = %s" in sql
    assert "IS NOT DISTINCT FROM %s" in sql
    assert parameters[-3:] == ("owner-a", "3", "original-trip")
    assert "route" not in sql and "itinerary" not in sql
    conn.commit.assert_called_once()
    cursor.execute.side_effect = psycopg2.OperationalError("offline")
    with pytest.raises(psycopg2.OperationalError):
        trip_car.update_trip_car("owner-a", 3, value)
    conn.rollback.assert_called_once()
    assert release.call_count == 2
