"""Actual API/schema/CRUD behavior with a transactional cursor test double.

No database is connected or queried. The double checks the single owner-scoped
conditional-upsert contract and models RETURNING/commit/rollback outcomes; it is
not a substitute for PostgreSQL engine-level concurrency acceptance.
"""

import copy
import json
from unittest.mock import MagicMock

import psycopg2
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.crud import chat_crud
from app.routers import chat_api
from app.schemas.chat_schemas import ChatDataSchema


class StorageDouble:
    def __init__(self):
        self.rows = {}
        self.pending = None
        self.cursor = MagicMock()
        self.cursor.__enter__.return_value = self.cursor
        self.cursor.execute.side_effect = self.execute
        self.connection = MagicMock()
        self.connection.cursor.return_value = self.cursor
        self.connection.commit.side_effect = self.commit
        self.connection.rollback.side_effect = self.rollback

    def commit(self):
        if self.pending is not None:
            self.rows = self.pending
        self.pending = None

    def rollback(self):
        self.pending = None

    def execute(self, sql, params):
        statement = " ".join(sql.split())
        self.cursor.fetchone.return_value = None
        self.cursor.fetchall.return_value = []
        if statement.startswith("INSERT INTO chats"):
            # A precheck would not protect a race. The actual production query
            # must contain this condition in its one atomic INSERT statement.
            assert "ON CONFLICT (user_id, chat_id) DO UPDATE" in statement
            assert (
                "WHERE chats.chat_data->>'agentChatId' IS NOT DISTINCT FROM EXCLUDED.chat_data->>'agentChatId'"
                in statement
            )
            assert "RETURNING *" in statement
            owner, identifier, data, log = params
            data, log = json.loads(data), json.loads(log)
            existing = self.rows.get((owner, identifier))
            if existing and existing["chat_data"].get("agentChatId") != data.get("agentChatId"):
                return  # PostgreSQL returns no row when the conflict WHERE fails.
            assert "CASE WHEN chats.chat_data->>'agentChatId' IS NULL" in statement
            self.pending = copy.deepcopy(self.rows)
            row = (
                copy.deepcopy(existing)
                if existing and existing["chat_data"].get("agentChatId") is not None
                else {"user_id": owner, "chat_id": identifier, "chat_data": data, "chat_log": log}
            )
            self.pending[owner, identifier] = row
            self.cursor.fetchone.return_value = copy.deepcopy(row)
        elif statement == "SELECT * FROM chats WHERE user_id = %s":
            self.cursor.fetchall.return_value = [
                copy.deepcopy(row) for (owner, _), row in self.rows.items() if owner == params[0]
            ]
        elif statement.startswith("SELECT chat_"):
            column = statement.split()[1]
            assert "WHERE user_id = %s AND chat_id = %s" in statement
            row = self.rows.get(tuple(params))
            self.cursor.fetchone.return_value = (
                {column: copy.deepcopy(row[column])} if row else None
            )
        elif statement.startswith("UPDATE chats SET chat_"):
            column = statement.split()[3]
            assert "WHERE user_id = %s AND chat_id = %s RETURNING *" in statement
            value, owner, identifier = params
            if (owner, identifier) not in self.rows:
                return
            self.pending = copy.deepcopy(self.rows)
            self.pending[owner, identifier][column] = json.loads(value)
            self.cursor.fetchall.return_value = [copy.deepcopy(self.pending[owner, identifier])]
        else:
            raise AssertionError(f"Unexpected statement in mocked storage: {statement}")


@pytest.fixture
def storage(monkeypatch):
    double = StorageDouble()
    monkeypatch.setattr(chat_crud, "_get_conn", lambda: double.connection)
    returned = MagicMock()
    monkeypatch.setattr(chat_crud, "_put_conn", returned)
    double.returned = returned
    return double


def _data(identifier=1, *, planning_id="a-planning-uuid", presentation=None):
    return {
        "chatId": identifier,
        "agentChatId": planning_id,
        "presentation": presentation,
        "locationType": "start",
        "stops": 1,
        "showInputBar": False,
        "showStopSlider": False,
        "showBudgetSlider": False,
        "showAddressInput": False,
        "workflowStarted": False,
        "loading": False,
        "carDetails": [],
    }


def _body(identifier=1, **changes):
    return {
        "PartitionKey": "fixture-token-alice",
        "ChatData": _data(identifier, **changes),
        "ChatLog": {"id": identifier, "title": "Saved trip", "messages": []},
    }


@pytest.fixture
def client(monkeypatch):
    app = FastAPI()
    app.include_router(chat_api.router)
    monkeypatch.setattr(chat_api, "get_user_id_from_token", lambda token: "verified-alice")
    return TestClient(app)


def test_trip_presentation_survives_create_update_and_reload_through_real_schema_and_crud(
    client, storage
):
    presentation = {
        "visitedStopIds": ["place:first"],
        "futurePresentation": {"collapsedDays": ["2027-06-01"], "version": 42},
    }
    body = _body(presentation=presentation)
    assert client.post("/chats/create/1", json=body).status_code == 200
    loaded = client.get("/chats", headers={"Authorization": "Bearer fixture-token"})
    assert loaded.status_code == 200
    assert loaded.json()[0][0]["presentation"] == presentation
    assert storage.rows["verified-alice", "1"]["chat_data"]["presentation"] == presentation

    # An empty visited list clears visits while retaining unknown future UI state.
    changed = presentation | {"visitedStopIds": []}
    body["ChatData"]["presentation"] = changed
    assert client.put("/chats/update/1", json=body).status_code == 200
    reloaded = client.get("/chats", headers={"Authorization": "Bearer fixture-token"}).json()
    assert reloaded[0][0]["presentation"] == changed
    assert storage.rows["verified-alice", "1"]["chat_data"]["presentation"] == changed


def test_old_trip_schema_keeps_optional_presentation_and_existing_unknown_message_metadata(
    client, storage
):
    body = _body(planning_id=None)
    body["ChatData"].pop("presentation")
    body["ChatData"].pop("agentChatId")
    body["ChatLog"]["messages"] = [
        {"text": "Historical", "sender": "bot", "presentation": {"oldUnknownField": [1, 2]}}
    ]
    assert client.post("/chats/create/1", json=body).status_code == 200
    data, log = client.get("/chats", headers={"Authorization": "Bearer fixture-token"}).json()[0]
    assert data["presentation"] is None
    assert log["messages"][0]["presentation"] == {"oldUnknownField": [1, 2]}
    assert ChatDataSchema.model_validate(body["ChatData"]).presentation is None


def test_legacy_put_without_presentation_preserves_visited_and_unknown_ui_fields(client, storage):
    presentation = {"visitedStopIds": ["place:first"], "futureUI": {"view": "itinerary"}}
    assert client.post("/chats/create/1", json=_body(presentation=presentation)).status_code == 200
    legacy = _body()
    legacy["ChatData"].pop("presentation")
    legacy["ChatData"]["action"] = "Address"
    assert client.put("/chats/update/1", json=legacy).status_code == 200
    saved = client.get("/chats", headers={"Authorization": "Bearer fixture-token"}).json()[0][0]
    assert saved["action"] == "Address"
    assert saved["presentation"] == presentation
    assert storage.rows["verified-alice", "1"]["chat_data"]["presentation"] == presentation


@pytest.mark.parametrize("cleared", [{}, {"visitedStopIds": []}, None])
def test_explicit_presentation_reset_is_not_ignored_by_legacy_empty_field_rules(
    client, storage, cleared
):
    assert (
        client.post(
            "/chats/create/1",
            json=_body(presentation={"visitedStopIds": ["place:first"], "futureUI": {}}),
        ).status_code
        == 200
    )
    assert client.put("/chats/update/1", json=_body(presentation=cleared)).status_code == 200
    saved = client.get("/chats", headers={"Authorization": "Bearer fixture-token"}).json()[0][0]
    assert saved["presentation"] == cleared


@pytest.mark.parametrize(
    "existing,incoming", [("first-uuid", "other-uuid"), ("first-uuid", None), (None, "new-uuid")]
)
def test_create_conflict_cannot_replace_another_planning_operation(
    client, storage, existing, incoming
):
    first = _body(planning_id=existing, presentation={"visitedStopIds": ["keep-me"]})
    assert client.post("/chats/create/1", json=first).status_code == 200
    before = copy.deepcopy(storage.rows)
    calls = storage.cursor.execute.call_count
    response = client.post("/chats/create/1", json=_body(planning_id=incoming))
    assert response.status_code == 409
    assert response.json() == {"detail": "Trip ID belongs to a different planning request"}
    assert storage.rows == before
    assert storage.cursor.execute.call_count == calls + 1
    assert storage.connection.commit.call_count == 1
    storage.connection.rollback.assert_called_once()
    assert storage.returned.call_count == 2


@pytest.mark.parametrize("planning_id", ["same-uuid", None])
def test_same_planning_identity_and_legacy_null_creates_remain_idempotent(
    client, storage, planning_id
):
    body = _body(planning_id=planning_id)
    assert client.post("/chats/create/1", json=body).status_code == 200
    assert client.post("/chats/create/1", json=body).status_code == 200
    body["ChatLog"]["title"] = "Retried trip"
    assert client.post("/chats/create/1", json=body).status_code == (
        200 if planning_id is None else 409
    )
    assert len(storage.rows) == 1
    assert storage.rows["verified-alice", "1"]["chat_log"]["title"] == (
        "Retried trip" if planning_id is None else "Saved trip"
    )
    assert storage.connection.commit.call_count == 3
    storage.connection.rollback.assert_not_called()


def test_conflict_rolls_back_before_pool_reuse_and_another_owner_keeps_same_number(storage):
    chat_crud.create_chat("alice", "1", _data(planning_id="alice-uuid"), {})
    chat_crud.create_chat("bob", "1", _data(planning_id="bob-uuid"), {})
    before = copy.deepcopy(storage.rows)
    with pytest.raises(chat_crud.ChatIdentityConflict):
        chat_crud.create_chat("alice", "1", _data(planning_id="another-alice-uuid"), {})
    assert storage.rows == before
    assert storage.pending is None
    storage.returned.assert_called_with(storage.connection)
    assert storage.connection.commit.call_count == 2
    storage.connection.rollback.assert_called_once()
    # The same pooled connection remains usable after the rejected transaction.
    chat_crud.create_chat("alice", "2", _data(2, planning_id="another-alice-uuid"), {})
    assert storage.rows["alice", "1"]["chat_data"]["agentChatId"] == "alice-uuid"
    assert storage.rows["bob", "1"]["chat_data"]["agentChatId"] == "bob-uuid"
    assert storage.rows["alice", "2"]["chat_data"]["agentChatId"] == "another-alice-uuid"
    assert storage.connection.commit.call_count == 3
    assert storage.returned.call_count == 4


def test_storage_failure_rolls_back_and_returns_pooled_connection(storage):
    storage.cursor.execute.side_effect = psycopg2.OperationalError("fixture failure")
    with pytest.raises(psycopg2.OperationalError):
        chat_crud.create_chat("alice", "1", _data(), {})
    storage.connection.rollback.assert_called_once()
    storage.connection.commit.assert_not_called()
    storage.returned.assert_called_once_with(storage.connection)


@pytest.mark.parametrize("method,path", [("post", "/chats/create/1"), ("put", "/chats/update/1")])
@pytest.mark.parametrize("field", ["ChatData", "ChatLog"])
def test_mismatched_path_data_or_log_ids_are_rejected_before_storage(
    client, storage, method, path, field
):
    body = _body()
    body[field]["chatId" if field == "ChatData" else "id"] = 2
    response = getattr(client, method)(path, json=body)
    assert response.status_code == 422
    assert response.json() == {"detail": "Trip IDs must match the request path"}
    storage.cursor.execute.assert_not_called()
    assert storage.rows == {}


def test_get_revision_hashes_raw_snapshot_before_geometry_hydration(client, storage, monkeypatch):
    body = _body()
    client.post("/chats/create/1", json=body)
    raw = storage.rows["verified-alice", "1"]["chat_data"]
    raw["route"] = {"geometry": {"coordinates": "owner-route-reference"}}
    revision = chat_crud.chat_data_revision(raw)
    monkeypatch.setattr(chat_api, "get_segments", lambda **kwargs: [[1, 2], [3, 4]])
    loaded = client.get("/chats", headers={"Authorization": "Bearer fixture"}).json()[0][0]
    assert loaded["savedRevision"] == revision
    assert loaded["route"]["geometry"]["coordinates"] == [[1, 2], [3, 4]]
    assert "savedRevision" not in raw


def test_atomic_route_save_rejects_concurrent_car_change_after_preflight(client, storage):
    body = _body()
    client.post("/chats/create/1", json=body)
    before = storage.rows["verified-alice", "1"]["chat_data"]
    body["ExpectedRevision"] = chat_crud.chat_data_revision(before)
    before["carDetails"] = ["2024", "Honda", "Civic"]
    before["tripProfile"] = {"car_status": "provided", "car": {"year": 2024}}
    retained = copy.deepcopy(storage.rows)
    body["ChatData"]["itinerary"] = [{"changed": True}]
    response = client.put("/chats/update/1", json=body)
    assert response.status_code == 409
    assert storage.rows == retained
    assert "FOR UPDATE" in storage.cursor.execute.call_args.args[0]
    storage.connection.rollback.assert_called_once()


def test_route_save_is_scoped_and_stale_visit_cannot_restore_old_route_or_car(client, storage):
    body = _body(presentation={"future": "keep", "visitedStopIds": ["old"]})
    created = client.post("/chats/create/1", json=body)
    revision = created.headers["X-Trip-Revision"]
    assert revision == chat_crud.chat_data_revision(
        storage.rows["verified-alice", "1"]["chat_data"]
    )
    stale_visit = copy.deepcopy(body) | {
        "ExpectedRevision": revision,
        "UpdateScope": "presentation",
    }
    body["ExpectedRevision"] = revision
    body["ChatData"]["itinerary"] = [{"new": "route itinerary"}]
    body["ChatData"]["carDetails"] = ["injected", "must", "not replace"]
    body["ChatLog"]["title"] = "must not replace log"
    saved = client.put("/chats/update/1", json=body)
    assert saved.status_code == 200
    row = storage.rows["verified-alice", "1"]
    assert row["chat_data"]["itinerary"] == [{"new": "route itinerary"}]
    assert row["chat_data"]["carDetails"] == []
    assert row["chat_log"]["title"] == "Saved trip"
    assert row["chat_data"]["presentation"] == {"future": "keep", "visitedStopIds": []}
    assert saved.json()["savedRevision"] != revision
    before = copy.deepcopy(storage.rows)
    assert client.put("/chats/update/1", json=stale_visit).status_code == 409
    assert storage.rows == before


def test_presentation_save_changes_only_presentation_and_refreshes_revision(client, storage):
    body = _body(presentation={"future": "keep"})
    client.post("/chats/create/1", json=body)
    raw = storage.rows["verified-alice", "1"]["chat_data"]
    raw["carDetails"] = ["2025", "Toyota", "Corolla"]
    raw["itinerary"] = [{"unchanged": True}]
    body["ExpectedRevision"] = chat_crud.chat_data_revision(raw)
    body["UpdateScope"] = "presentation"
    body["ChatData"]["presentation"] = {"future": "keep", "visitedStopIds": ["visit"]}
    assert client.put("/chats/update/1", json=body).status_code == 200
    saved = storage.rows["verified-alice", "1"]["chat_data"]
    assert saved["carDetails"] == ["2025", "Toyota", "Corolla"]
    assert saved["itinerary"] == [{"unchanged": True}]
    assert saved["presentation"]["visitedStopIds"] == ["visit"]
    assert "savedRevision" not in saved


@pytest.mark.parametrize("scope", ["route", "presentation", "full"])
def test_explicit_modern_scope_requires_revision_before_storage(client, storage, scope):
    body = _body() | {"UpdateScope": scope}
    assert client.put("/chats/update/1", json=body).status_code == 422
    storage.cursor.execute.assert_not_called()


def test_targeted_presentation_requires_explicit_field_without_clearing_existing_state(
    client, storage
):
    body = _body(presentation={"future": "keep"})
    response = client.post("/chats/create/1", json=body)
    body["ExpectedRevision"] = response.headers["X-Trip-Revision"]
    body["UpdateScope"] = "presentation"
    body["ChatData"].pop("presentation")
    before = copy.deepcopy(storage.rows)
    assert client.put("/chats/update/1", json=body).status_code == 422
    assert storage.rows == before


def test_stale_visit_after_car_change_rejects_and_fresh_visit_uses_new_revision(client, storage):
    body = _body(presentation={"visitedStopIds": []})
    created = client.post("/chats/create/1", json=body)
    body["UpdateScope"] = "presentation"
    body["ExpectedRevision"] = created.headers["X-Trip-Revision"]
    raw = storage.rows["verified-alice", "1"]["chat_data"]
    raw["carDetails"] = ["2024", "Honda", "Civic"]
    body["ChatData"]["presentation"] = {"visitedStopIds": ["visit"]}
    assert client.put("/chats/update/1", json=body).status_code == 409
    body["ExpectedRevision"] = chat_crud.chat_data_revision(raw)
    saved = client.put("/chats/update/1", json=body)
    assert saved.status_code == 200
    assert storage.rows["verified-alice", "1"]["chat_data"]["carDetails"] == [
        "2024",
        "Honda",
        "Civic",
    ]
    body["ExpectedRevision"] = saved.json()["savedRevision"]
    body["ChatData"]["presentation"] = {"visitedStopIds": []}
    assert client.put("/chats/update/1", json=body).status_code == 200


def test_late_same_planning_create_cannot_replace_newer_route_car_or_visits(client, storage):
    body = _body(presentation={"visitedStopIds": []})
    assert client.post("/chats/create/1", json=body).status_code == 200
    raw = storage.rows["verified-alice", "1"]["chat_data"]
    raw["carDetails"] = ["2025", "Honda", "Civic"]
    raw["itinerary"] = [{"newer": "route"}]
    raw["presentation"] = {"visitedStopIds": ["newer-visit"]}
    retained = copy.deepcopy(storage.rows)
    response = client.post("/chats/create/1", json=body)
    assert response.status_code == 409
    assert response.json()["detail"] == "Trip already saved; reload before continuing"
    assert storage.rows == retained
