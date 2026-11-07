"""Real request-schema/CRUD JSON boundaries; only authentication and SQL I/O are fake."""

import copy
import json
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.crud import chat_crud
from app.routers import chat_api
from tests.chat_persistence_tests import StorageDouble, _body


class RouteStorage(StorageDouble):
    def __init__(self):
        self.segments = {}
        super().__init__()

    def execute(self, sql, params):
        statement = " ".join(sql.split())
        if statement.startswith("INSERT INTO route_segments"):
            owner, chat, route, segment, coordinates = params
            self.segments[owner, chat, route, segment] = json.loads(coordinates)
            self.cursor.fetchone.return_value = {"user_id": owner}
            return
        if statement.startswith("DELETE FROM route_segments"):
            owner, chat, route, retained = params
            assert "user_id = %s AND chat_id = %s AND route_id = %s" in statement
            self.segments = {
                key: value
                for key, value in self.segments.items()
                if key[:3] != (owner, chat, route) or key[3] in retained
            }
            return
        if statement.startswith("SELECT * FROM route_segments"):
            owner, chat, route = params
            self.cursor.fetchall.return_value = [
                {"coords": copy.deepcopy(coords)}
                for (user, identifier, route_id, _), coords in sorted(self.segments.items())
                if (user, identifier, route_id) == (owner, chat, route)
            ]
            return
        return super().execute(sql, params)


@pytest.fixture
def boundary(monkeypatch):
    storage = RouteStorage()
    monkeypatch.setattr(chat_crud, "_get_conn", lambda: storage.connection)
    monkeypatch.setattr(chat_crud, "_put_conn", MagicMock())
    monkeypatch.setattr(chat_api, "get_user_id_from_token", lambda _: "verified-alice")
    app = FastAPI()
    app.include_router(chat_api.router)
    return TestClient(app, raise_server_exceptions=False), storage


def timed_body(departure="2027-06-01T09:00:00-07:00"):
    body = _body(presentation={"visitedStopIds": ["place:first"], "futureUI": {"version": 3}})
    body["ChatData"]["initial"] = None
    body["ChatData"]["route"] = {
        "coordinates": [[40, -105], [39.7, -104.9]],
        "distance": 50000,
        "duration": 3600,
        "steps": [],
        "stops": [{"name": "Destination", "type": "end", "duration": 3600}],
        "geometry": {"type": "LineString", "coordinates": [[-105, 40], [-104.9, 39.7]]},
        "cost": 0,
        "departure_time": departure,
        "start_timezone": "America/Los_Angeles",
    }
    body["ChatData"]["tripProfile"] = {"start_date": departure, "unknownFutureField": [1, 2]}
    return body


def loaded(client):
    response = client.get("/chats", headers={"Authorization": "Bearer fixture-token"})
    assert response.status_code == 200
    return response.json()[0]


@pytest.mark.parametrize("departure", ["2027-06-01T09:00:00-07:00", "2027-06-01T16:00:00Z"])
def test_create_real_typed_route_serializes_datetime_and_round_trips_json(boundary, departure):
    client, storage = boundary
    body = timed_body(departure)
    response = client.post("/chats/create/1", json=body)
    assert response.status_code == 200
    stored = storage.rows["verified-alice", "1"]["chat_data"]
    value = stored["route"]["departure_time"]
    assert isinstance(value, str)
    assert datetime.fromisoformat(value) == datetime.fromisoformat(departure)
    data, log = loaded(client)
    assert data["route"] == stored["route"]
    assert data["agentChatId"] == body["ChatData"]["agentChatId"]
    assert data["chatId"] == log["id"] == 1
    assert data["tripProfile"] == body["ChatData"]["tripProfile"]
    assert data["presentation"] == body["ChatData"]["presentation"]


def test_update_typed_route_retains_datetime_geometry_and_visit_undo(boundary):
    client, storage = boundary
    body = timed_body()
    # Seed the already JSON-safe request directly to isolate UPDATE from CREATE.
    chat_crud.create_chat("verified-alice", "1", body["ChatData"], body["ChatLog"])
    changed = copy.deepcopy(body)
    changed["ChatData"]["route"]["departure_time"] = "2027-06-02T10:15:00-07:00"
    changed["ChatData"]["presentation"]["visitedStopIds"] = []
    response = client.put("/chats/update/1", json=changed)
    assert response.status_code == 200
    data, log = loaded(client)
    assert data["route"]["departure_time"] == "2027-06-02T10:15:00-07:00"
    assert data["route"]["geometry"] == body["ChatData"]["route"]["geometry"]
    assert data["presentation"] == changed["ChatData"]["presentation"]
    assert data["agentChatId"] == body["ChatData"]["agentChatId"]
    assert data["chatId"] == log["id"] == 1
    assert storage.connection.rollback.call_count == 0


def test_legacy_route_without_departure_stays_compatible(boundary):
    client, _ = boundary
    body = timed_body()
    body["ChatData"]["route"].pop("departure_time")
    body["ChatData"].pop("agentChatId")
    body["ChatData"].pop("presentation")
    assert client.post("/chats/create/1", json=body).status_code == 200
    assert client.put("/chats/update/1", json=body).status_code == 200
    data, _ = loaded(client)
    assert data["route"]["departure_time"] is None
    assert data["agentChatId"] is None


def test_long_route_replacement_prunes_only_own_obsolete_segments_and_preserves_initial(boundary):
    client, storage = boundary
    body = timed_body()
    chat_crud.create_chat("verified-alice", "1", body["ChatData"], body["ChatLog"])
    raw = storage.rows["verified-alice", "1"]["chat_data"]
    raw["initial"] = {"geometry": "verified-alice-1", "legs": []}
    initial = [[-110, 40], [-109, 41]]
    storage.segments["verified-alice", "1", "verified-alice-1", "0"] = initial
    foreign = ("other-owner", "9", "other-route", "1")
    storage.segments[foreign] = [[1, 2]]
    geometry = [[-105 + i / 100000, 40] for i in range(10001)]
    body["ChatData"]["route"]["geometry"]["coordinates"] = geometry
    body["ExpectedRevision"] = chat_crud.chat_data_revision(raw)
    first = client.put("/chats/update/1", json=body)
    assert first.status_code == 200
    assert len([k for k in storage.segments if k[2] == "verified-alice-1-final"]) == 2
    shorter = [[-105, 40], [-104, 40]]
    body["ChatData"]["route"]["geometry"]["coordinates"] = shorter
    body["ExpectedRevision"] = first.json()["savedRevision"]
    second = client.put("/chats/update/1", json=body)
    assert second.status_code == 200
    data, _ = loaded(client)
    assert data["route"]["geometry"]["coordinates"] == shorter
    assert data["initial"]["geometry"]["coordinates"] == initial
    assert len([k for k in storage.segments if k[2] == "verified-alice-1-final"]) == 1
    assert storage.segments[foreign] == [[1, 2]]
    assert second.json()["savedRevision"] != first.json()["savedRevision"]
