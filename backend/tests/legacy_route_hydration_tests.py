"""Reload historical route representations without altering durable source JSON."""

from copy import deepcopy
from unittest.mock import MagicMock

import pytest

from app.crud import chat_crud
from tests.chat_json_serialization_tests import boundary as boundary
from tests.chat_json_serialization_tests import timed_body
from tests.routing.conftest import build_route


def legacy_body():
    body = timed_body()
    body["ChatData"]["initial"] = build_route(3600).model_dump(mode="json")
    body["ChatData"]["initial"]["legs"][0]["steps"] = []
    body["ChatData"].pop("agentChatId")
    return body


def reload(client):
    return client.get("/chats", headers={"Authorization": "Bearer fixture-token"})


def test_segmented_legacy_initial_with_empty_step_list_reloads_without_data_loss(boundary):
    client, storage = boundary
    body = legacy_body()
    initial = body["ChatData"]["initial"]
    coordinates = initial["geometry"]["coordinates"]
    initial["geometry"] = "verified-alice-1"
    initial["legacyMetadata"] = {"retain": ["original", "route"]}
    chat_crud.create_chat("verified-alice", "1", body["ChatData"], body["ChatLog"])
    storage.segments["verified-alice", "1", "verified-alice-1", "0"] = coordinates
    # Another owner's same route reference cannot contribute coordinates.
    storage.segments["other-owner", "1", "verified-alice-1", "1"] = [[1, 2]]
    before = deepcopy(storage.rows)
    response = reload(client)
    assert response.status_code == 200, response.text
    restored, log = response.json()[0]
    assert restored["initial"]["geometry"]["coordinates"] == coordinates
    assert restored["initial"]["legs"] == initial["legs"]
    assert restored["initial"]["legacyMetadata"] == initial["legacyMetadata"]
    assert restored["route"] == body["ChatData"]["route"]
    assert restored["presentation"] == body["ChatData"]["presentation"]
    assert restored["tripProfile"] == body["ChatData"]["tripProfile"]
    assert log == body["ChatLog"]
    assert restored["savedRevision"] == chat_crud.chat_data_revision(
        before["verified-alice", "1"]["chat_data"]
    )
    assert storage.rows == before


@pytest.mark.parametrize("empty_steps", [False, True])
@pytest.mark.parametrize("coordinates", [None, []])
def test_inline_initial_geometry_round_trips_real_create_schema_without_segment_lookup(
    boundary, empty_steps, coordinates
):
    client, storage = boundary
    body = legacy_body()
    if not empty_steps:
        body["ChatData"]["initial"] = build_route(3600).model_dump(mode="json")
    if coordinates is not None:
        body["ChatData"]["initial"]["geometry"]["coordinates"] = coordinates
    assert client.post("/chats/create/1", json=body).status_code == 200
    before = deepcopy(storage.rows)
    response = reload(client)
    assert response.status_code == 200, response.text
    assert response.json()[0][0]["initial"] == before["verified-alice", "1"]["chat_data"]["initial"]
    assert storage.rows == before


@pytest.mark.parametrize("which", ["initial", "route"])
def test_unavailable_referenced_geometry_is_not_replaced_with_invented_empty_route(boundary, which):
    client, storage = boundary
    body = legacy_body()
    if which == "initial":
        body["ChatData"][which]["geometry"] = "missing-owner-scoped-route"
    else:
        body["ChatData"]["initial"] = None
        body["ChatData"][which]["geometry"]["coordinates"] = "missing-owner-scoped-route"
    chat_crud.create_chat("verified-alice", "1", body["ChatData"], body["ChatLog"])
    before = deepcopy(storage.rows)
    response = reload(client)
    assert response.status_code == 503, response.text
    assert response.json() == {"detail": "Saved trip geometry is temporarily unavailable"}
    assert storage.rows == before


def test_malformed_stored_geometry_is_distinct_from_empty_or_unavailable_geometry(boundary):
    client, storage = boundary
    body = legacy_body()
    body["ChatData"]["initial"]["geometry"] = {"coordinates": None}
    chat_crud.create_chat("verified-alice", "1", body["ChatData"], body["ChatLog"])
    before = deepcopy(storage.rows)
    response = reload(client)
    assert response.status_code == 500
    assert response.json() == {"detail": "Saved trip geometry is invalid"}
    assert storage.rows == before


@pytest.mark.parametrize("geometry_present", [False, True])
@pytest.mark.parametrize("steps", [None, "missing"])
def test_absent_initial_geometry_and_maneuver_details_remain_absent(
    boundary, geometry_present, steps
):
    client, storage = boundary
    body = legacy_body()
    initial = body["ChatData"]["initial"]
    if geometry_present:
        initial["geometry"] = None
    else:
        initial.pop("geometry")
    if steps == "missing":
        initial["legs"][0].pop("steps")
    else:
        initial["legs"][0]["steps"] = steps
    chat_crud.create_chat("verified-alice", "1", body["ChatData"], body["ChatLog"])
    before = deepcopy(storage.rows)
    response = reload(client)
    assert response.status_code == 200, response.text
    assert response.json()[0][0]["initial"] == initial
    assert storage.rows == before


@pytest.mark.parametrize("coordinates", [[], [[-110, 40, 1200], [-109, 41, 1300]]])
def test_legacy_bare_coordinate_list_is_wrapped_without_changing_its_points(boundary, coordinates):
    client, storage = boundary
    body = legacy_body()
    body["ChatData"]["initial"]["geometry"] = coordinates
    chat_crud.create_chat("verified-alice", "1", body["ChatData"], body["ChatLog"])
    before = deepcopy(storage.rows)
    response = reload(client)
    assert response.status_code == 200, response.text
    assert response.json()[0][0]["initial"]["geometry"] == {"coordinates": coordinates}
    assert storage.rows == before


def step_connection(monkeypatch, rows):
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchall.return_value = rows
    connection = MagicMock()
    connection.cursor.return_value = cursor
    monkeypatch.setattr(chat_crud, "_get_conn", lambda: connection)
    monkeypatch.setattr(chat_crud, "_put_conn", MagicMock())
    return cursor


def test_mixed_stored_and_inline_steps_restore_only_owner_scoped_references(monkeypatch):
    cursor = step_connection(
        monkeypatch,
        [
            {"step_id": 0, "coordinates": [[-110, 40], [-109, 41]]},
            {"step_id": 1, "coordinates": [[1, 2], [3, 4]]},
            {"step_id": 9, "coordinates": [[5, 6]]},
        ],
    )
    inline = [[-109, 41], [-108, 42]]
    legs = [
        {
            "steps": [
                {"geometry": {"coordinates": "owner-leg-0"}},
                {"geometry": {"coordinates": inline}},
            ]
        }
    ]
    restored = chat_crud.restore_legs("alice", "chat-1", legs)
    assert restored[0]["steps"][0]["geometry"]["coordinates"] == [[-110, 40], [-109, 41]]
    assert restored[0]["steps"][1]["geometry"]["coordinates"] == inline
    sql, params = cursor.execute.call_args.args
    assert "user_id = %s AND chat_id = %s AND leg_id = %s" in sql
    assert params == ("alice", "chat-1", "owner-leg-0")


def test_missing_stored_step_coordinates_fail_without_relabeling_leg_as_empty(monkeypatch):
    step_connection(monkeypatch, [])
    legs = [{"steps": [{"geometry": {"coordinates": "owner-leg-0"}}]}]
    before = deepcopy(legs)
    with pytest.raises(chat_crud.ChatGeometryUnavailable):
        chat_crud.restore_legs("alice", "chat-1", legs)
    assert legs == before
