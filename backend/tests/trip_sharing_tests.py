"""Sharing boundaries without a database/provider connection."""

import json
from unittest.mock import MagicMock
from uuid import uuid4

import psycopg2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.crud import chat_crud
from app.crud import trip_sharing as store
from app.routers import trip_sharing
from app.schemas.trip_sharing import ConnectTripInput

TOKEN = "x" * 43
SHARE = str(uuid4())


@pytest.fixture
def client():
    application = FastAPI()
    application.include_router(trip_sharing.router)
    return TestClient(application)


def test_private_routes_verify_signature_and_never_trust_claimed_account(
    client, signed_token, monkeypatch
):
    create = MagicMock(return_value={"share_id": SHARE})
    connect = MagicMock(return_value={"share_id": SHARE})
    monkeypatch.setattr(store, "create_link", create)
    monkeypatch.setattr(store, "connect", connect)
    body = {"expected_revision": "a" * 64}
    assert client.post("/chats/7/sharing/link", json=body).status_code == 401
    assert client.get("/shared-trips").status_code == 401
    assert client.get(f"/shared-trips/{SHARE}").status_code == 401
    assert (
        client.post("/trip-sharing/connect", json={"token": TOKEN, "display_name": "A"}).status_code
        == 401
    )
    create.assert_not_called()
    connect.assert_not_called()
    headers = {"Authorization": "Bearer " + signed_token(sub="verified-owner")}
    response = client.post("/chats/7/sharing/link", json=body, headers=headers)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store, private"
    create.assert_called_once_with("verified-owner", 7, "a" * 64)
    headers = {"Authorization": "Bearer " + signed_token(sub="verified-member")}
    assert (
        client.post(
            "/trip-sharing/connect",
            json={"token": TOKEN, "display_name": "Traveler"},
            headers=headers,
        ).status_code
        == 200
    )
    connect.assert_called_once_with("verified-member", TOKEN, "Traveler")
    assert (
        client.post(
            "/trip-sharing/connect",
            json={"token": TOKEN, "display_name": "Traveler", "account_id": "forged"},
            headers=headers,
        ).status_code
        == 422
    )
    assert connect.call_count == 1


@pytest.mark.parametrize(
    "failure,status",
    [
        (store.ShareUnavailable(), 404),
        (store.ShareConflict("Saved trip changed"), 409),
        (psycopg2.errors.UndefinedTable("private DSN"), 503),
    ],
)
def test_safe_errors_and_no_cache(client, signed_token, monkeypatch, failure, status):
    monkeypatch.setattr(store, "view", MagicMock(side_effect=failure))
    response = client.post("/trip-sharing/view", json={"token": TOKEN})
    assert response.status_code == status
    assert "private DSN" not in response.text and TOKEN not in response.text
    assert response.headers["cache-control"] == "no-store, private"


def test_token_is_never_in_sql_parameters_plaintext_and_shape_is_bounded():
    assert len(store.token_digest(TOKEN)) == 64
    assert TOKEN not in store.token_digest(TOKEN)
    for invalid in ("", TOKEN + "x", "bad?query=token", "x" * 42, "é" * 43):
        with pytest.raises(store.ShareUnavailable):
            store.token_digest(invalid)
    assert TOKEN not in repr(ConnectTripInput(token=TOKEN, display_name="Traveler"))


def test_projection_drops_private_nested_fields_and_owner_scopes_geometry():
    cur = MagicMock()
    cur.fetchall.return_value = [{"coords": [[-105, 40], [-104, 41]]}]
    hidden = "PRIVATE_PERSONA_LOG_VISIT_LOCATION_CAR_PRICE"
    row = {
        "id": SHARE,
        "owner_id": "owner",
        "chat_id": "7",
        "chat_data": {
            "route": {
                "geometry": {"coordinates": "owner-7-final"},
                "distance": 100,
                "duration": 60,
                "persona_weights": hidden,
                "stops": [{"car": hidden}],
            },
            "startConfirmed": {"address": "Boulder", "current_location": hidden},
            "endConfirmed": {"address": "Denver"},
            "presentation": {"visitedStopIds": [hidden]},
            "itinerary": [
                {
                    "date": "2030-01-01",
                    "private": hidden,
                    "stops": [
                        {
                            "name": "Visit",
                            "time": "10:00",
                            "status": hidden,
                            "price": hidden,
                            "source_provenance": [hidden],
                            "current_location": hidden,
                            "hotel_rooms": [hidden],
                        }
                    ],
                }
            ],
            "tripProfile": {"persona_weights": hidden},
            "carDetails": [hidden],
            "chat_log": hidden,
        },
    }
    projected = store._project(cur, row)
    assert hidden not in json.dumps(projected)
    assert set(projected) == {
        "share_id",
        "trip_mode",
        "revision",
        "start",
        "destination",
        "title",
        "route",
        "itinerary",
    }
    assert projected["route"]["coordinates"] == [[-105, 40], [-104, 41]]
    sql, params = cur.execute.call_args.args
    assert "user_id=%s AND chat_id=%s AND route_id=%s" in sql
    assert params == ("owner", "7", "owner-7-final")
    row["chat_data"]["carDetails"] = ["different private data"]
    assert store._project(cur, row)["revision"] == projected["revision"]


def test_read_snapshot_ends_transaction_and_rolls_back_failed_reads(monkeypatch):
    conn = MagicMock()
    monkeypatch.setattr(chat_crud, "_get_conn", lambda: conn)
    put = MagicMock()
    monkeypatch.setattr(chat_crud, "_put_conn", put)
    with store.transaction(readonly=True):
        pass
    conn.cursor.return_value.__enter__.return_value.execute.assert_called_once_with(
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    )
    conn.commit.assert_called_once()
    with pytest.raises(store.ShareUnavailable), store.transaction(readonly=True):
        raise store.ShareUnavailable
    conn.rollback.assert_called_once()
    assert put.call_count == 2


def test_public_route_is_explicitly_read_only_and_fixed_owner_revoke_identity(
    client, signed_token, monkeypatch
):
    read = MagicMock(return_value={"title": "Shared trip"})
    revoke = MagicMock(return_value={"share_id": None})
    monkeypatch.setattr(store, "view", read)
    monkeypatch.setattr(store, "revoke", revoke)
    assert client.post("/trip-sharing/view", json={"token": TOKEN}).status_code == 200
    read.assert_called_once_with(token=TOKEN)
    for method in (client.put, client.delete):
        assert method(f"/shared-trips/{SHARE}").status_code == 405
    headers = {"Authorization": "Bearer " + signed_token(sub="owner")}
    assert client.delete("/chats/7/sharing", headers=headers).status_code == 422
    assert client.delete(f"/chats/7/sharing?share_id={SHARE}", headers=headers).status_code == 200
    assert str(revoke.call_args.kwargs["share_id"]) == SHARE
    assert revoke.call_args.args == ("owner", 7)


def test_public_outline_bounds_large_geometry_without_changing_endpoints():
    points = [[-105 + i / 100000, 40] for i in range(10001)]
    row = {
        "id": SHARE,
        "owner_id": "owner",
        "chat_id": "7",
        "chat_data": {"route": {"geometry": {"coordinates": points}}, "itinerary": []},
    }
    outline = store._project(MagicMock(), row)["route"]["coordinates"]
    assert len(outline) <= 4096 and outline[0] == points[0] and outline[-1] == points[-1]


@pytest.mark.parametrize(
    "mode,expected",
    [
        ("one_day", "one_day"),
        ("overnight", "overnight"),
        ("unknown", None),
        ({"garbage": "DO_NOT_SHARE"}, None),
        (None, None),
    ],
)
def test_shared_mode_is_only_a_plan_label_and_scheduled_rest_sleep_rows_remain(mode, expected):
    row = {
        "id": SHARE,
        "owner_id": "owner",
        "chat_id": "7",
        "chat_data": {
            "route": {
                "trip_mode": mode,
                "one_day_proof": {
                    "status": "validated",
                    "elapsed_seconds": 1,
                    "private": "DO_NOT_SHARE",
                },
                "scheduling_policy": {"daily_schedule": {"slots": ["DO_NOT_SHARE"] * 24}},
            },
            "itinerary": [
                {
                    "date": "2027-01-01",
                    "stops": [
                        {
                            "name": "Rest time",
                            "kind": "rest",
                            "status": "planned",
                            "time": "20:00",
                            "arrival_time": "2027-01-01T20:00:00-07:00",
                            "departure_time": "2027-01-01T22:00:00-07:00",
                            "timezone": "America/Denver",
                        },
                        {
                            "name": "Sleep time",
                            "kind": "sleep",
                            "status": "planned",
                            "time": "22:00",
                            "arrival_time": "2027-01-01T22:00:00-07:00",
                            "departure_time": "2027-01-02T07:00:00-07:00",
                            "timezone": "America/Denver",
                        },
                    ],
                }
            ],
        },
    }
    result = store._project(MagicMock(), row)
    assert result["trip_mode"] == expected
    assert [s["kind"] for s in result["itinerary"][0]["stops"]] == ["rest", "sleep"]
    assert result["itinerary"][0]["stops"][1]["departure_time"] == "2027-01-02T07:00:00-07:00"
    assert "DO_NOT_SHARE" not in json.dumps(result)
    assert "one_day_proof" not in result and "scheduling_policy" not in result
