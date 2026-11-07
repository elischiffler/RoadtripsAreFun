"""Real signed-auth/API/CRUD sharing acceptance on the selected disposable PG only.

Uses the existing settings fixture's fixed local target guard; no DATABASE_URL
fallback, hosted access, provider requests, schema initialization or startup DDL.
The standard offline suite skips this lane. The disposable runner supplies schema.
"""

import copy
import json
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.crud import chat_crud
from app.crud import trip_sharing as store
from app.routers import chat_api, trip_sharing
from app.schemas.chat_schemas import ChatDataSchema
from tests.chat_json_serialization_tests import timed_body
from tests.settings_postgres_tests import database as database
from tests.settings_postgres_tests import pytestmark as pytestmark


@pytest.fixture
def journey(database, signed_token):
    conn, prefix = database
    owner, member, stranger = prefix + "-owner", prefix + "-member", prefix + "-stranger"
    body = timed_body()
    hidden = "PRIVATE_PREF_LOG_VISIT_LOCATION_CAR"
    body["ChatData"]["startConfirmed"] = {"address": "Boulder"}
    body["ChatData"]["endConfirmed"] = {"address": "Denver"}
    body["ChatData"]["itinerary"] = [
        {
            "date": "2027-06-01",
            "stops": [
                {"name": "Museum", "time": "10:00", "price": hidden, "source_provenance": [hidden]}
            ],
        }
    ]
    body["ChatData"]["presentation"] = {"visitedStopIds": [hidden], "current_location": hidden}
    body["ChatData"]["tripProfile"] = {"private": hidden}
    body["ChatLog"]["messages"] = [{"text": hidden, "sender": "user"}]
    chat_crud.create_chat(owner, "1", body["ChatData"], body["ChatLog"])
    app = FastAPI()
    app.include_router(chat_api.router)
    app.include_router(trip_sharing.router)
    client = TestClient(app)

    def headers(user):
        return {"Authorization": "Bearer " + signed_token(sub=user)}

    def link():
        revision = chat_crud.chat_data_revision(chat_crud.get_chat(owner, "1")["chat_data"])
        response = client.post(
            "/chats/1/sharing/link", headers=headers(owner), json={"expected_revision": revision}
        )
        assert response.status_code == 200, response.text
        return response.json()

    yield conn, client, owner, member, stranger, headers, link, body, hidden
    with conn.cursor() as cur:
        cur.execute("DELETE FROM route_segments WHERE user_id LIKE %s", (prefix + "%",))
    conn.commit()


def test_actual_signed_auth_minimal_projection_member_read_only_and_owner_isolation(journey):
    conn, client, owner, member, stranger, headers, link, body, hidden = journey
    before = chat_crud.get_chat(owner, "1")
    grant = link()
    assert chat_crud.get_chat(owner, "1") == before  # sharing does not rotate owner edit revisions
    token, share_id = grant["token"], grant["share_id"]
    anonymous = client.post("/trip-sharing/view", json={"token": token})
    assert anonymous.status_code == 200
    assert anonymous.headers["cache-control"] == "no-store, private"
    assert hidden not in anonymous.text
    assert set(anonymous.json()) == {
        "share_id",
        "revision",
        "start",
        "destination",
        "title",
        "route",
        "itinerary",
    }
    assert client.get("/shared-trips/" + share_id, headers=headers(member)).status_code == 404
    connected = client.post(
        "/trip-sharing/connect",
        headers=headers(member),
        json={"token": token, "display_name": "Traveler"},
    )
    assert connected.status_code == 200
    assert (
        client.post(
            "/trip-sharing/connect",
            headers=headers(member),
            json={"token": token, "display_name": "Renamed"},
        ).status_code
        == 200
    )
    status = client.get("/chats/1/sharing", headers=headers(owner)).json()
    assert len(status["members"]) == 1 and status["members"][0]["display_name"] == "Renamed"
    assert "account_id" not in json.dumps(status) and member not in json.dumps(status)
    assert (
        client.get("/shared-trips/" + share_id, headers=headers(member)).json() == anonymous.json()
    )
    assert client.get("/shared-trips/" + share_id, headers=headers(stranger)).status_code == 404
    assert client.get("/shared-trips", headers=headers(member)).json()[0]["share_id"] == share_id
    for method, path in [
        ("get", "/chats/1/sharing"),
        ("delete", f"/chats/1/sharing?share_id={share_id}"),
    ]:
        assert getattr(client, method)(path, headers=headers(member)).status_code == 404
    # A valid member token cannot save through the existing owner-scoped API.
    forged = copy.deepcopy(body)
    forged["PartitionKey"] = headers(member)["Authorization"].split(" ", 1)[1]
    assert client.put("/chats/update/1", json=forged).status_code == 404
    assert chat_crud.get_chat(owner, "1") == before
    with conn.cursor() as cur:
        cur.execute("SELECT token_digest FROM trip_shares WHERE id=%s", (share_id,))
        digest = cur.fetchone()[0]
        assert digest == store.token_digest(token) and token not in digest
        cur.execute("SELECT count(*) FROM chats WHERE user_id=%s", (member,))
        assert cur.fetchone()[0] == 0
    conn.rollback()


def test_rotation_expiration_link_stop_member_remove_and_stop_all(journey):
    conn, client, owner, member, _, headers, link, _, _ = journey
    first = link()
    sid = first["share_id"]
    client.post(
        "/trip-sharing/connect",
        headers=headers(member),
        json={"token": first["token"], "display_name": "Sam"},
    )
    second = link()
    assert second["share_id"] == sid and first["token"] != second["token"]
    assert client.post("/trip-sharing/view", json={"token": first["token"]}).status_code == 404
    assert (
        client.post(
            "/trip-sharing/connect",
            headers=headers(member),
            json={"token": first["token"], "display_name": "Sam"},
        ).status_code
        == 404
    )
    assert client.get("/shared-trips/" + sid, headers=headers(member)).status_code == 200
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE trip_shares SET link_expires_at=now()-interval '1 second' WHERE id=%s", (sid,)
        )
    conn.commit()
    assert client.post("/trip-sharing/view", json={"token": second["token"]}).status_code == 404
    assert client.get("/shared-trips/" + sid, headers=headers(member)).status_code == 200
    third = link()
    assert (
        client.delete("/chats/1/sharing/link?share_id=" + sid, headers=headers(owner)).status_code
        == 200
    )
    assert client.post("/trip-sharing/view", json={"token": third["token"]}).status_code == 404
    assert client.get("/shared-trips/" + sid, headers=headers(member)).status_code == 200
    member_id = client.get("/chats/1/sharing", headers=headers(owner)).json()["members"][0]["id"]
    assert (
        client.delete(
            f"/chats/1/sharing/members/{member_id}?share_id={sid}", headers=headers(owner)
        ).status_code
        == 200
    )
    assert client.get("/shared-trips/" + sid, headers=headers(member)).status_code == 404
    assert client.get("/shared-trips", headers=headers(member)).json() == []
    fourth = link()
    client.post(
        "/trip-sharing/connect",
        headers=headers(member),
        json={"token": fourth["token"], "display_name": "Sam"},
    )
    assert (
        client.delete("/chats/1/sharing?share_id=" + sid, headers=headers(owner)).status_code == 200
    )
    assert client.get("/shared-trips/" + sid, headers=headers(member)).status_code == 404
    assert client.post("/trip-sharing/view", json={"token": fourth["token"]}).status_code == 404
    fresh = link()
    assert fresh["share_id"] != sid
    # Stale owner UI must not revoke a recreated sharing identity.
    assert (
        client.delete("/chats/1/sharing?share_id=" + sid, headers=headers(owner)).status_code == 409
    )
    assert client.post("/trip-sharing/view", json={"token": fresh["token"]}).status_code == 200


def test_delete_cascades_and_same_chat_recreation_cannot_revive_old_access(journey):
    conn, client, owner, member, _, headers, link, body, _ = journey
    grant = link()
    sid = grant["share_id"]
    client.post(
        "/trip-sharing/connect",
        headers=headers(member),
        json={"token": grant["token"], "display_name": "Sam"},
    )
    assert client.delete("/chats/delete/1", headers=headers(owner)).status_code == 200
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM trip_shares WHERE id=%s", (sid,))
        assert cur.fetchone()[0] == 0
        cur.execute("SELECT count(*) FROM trip_share_members WHERE share_id=%s", (sid,))
        assert cur.fetchone()[0] == 0
    conn.rollback()
    recreated = copy.deepcopy(body["ChatData"])
    recreated["agentChatId"] = str(uuid4())
    chat_crud.create_chat(owner, "1", recreated, body["ChatLog"])
    assert client.get("/shared-trips/" + sid, headers=headers(member)).status_code == 404
    assert client.post("/trip-sharing/view", json={"token": grant["token"]}).status_code == 404
    fresh = link()
    assert fresh["share_id"] != sid
    assert (
        client.get("/shared-trips/" + fresh["share_id"], headers=headers(member)).status_code == 404
    )


def test_coherent_snapshot_during_actual_segmented_route_update_and_revocation(
    journey, monkeypatch
):
    _, client, owner, member, _, headers, link, body, _ = journey
    first_geometry = [[-105, 40], [-104, 41]]
    changed = ChatDataSchema.model_validate(body["ChatData"])
    changed.route.geometry.coordinates = first_geometry
    raw = chat_crud.get_chat(owner, "1")["chat_data"]
    chat_crud.update_chat_component(
        owner, "1", changed, "ChatData", expected_revision=chat_crud.chat_data_revision(raw)
    )
    grant = link()
    sid = grant["share_id"]
    client.post(
        "/trip-sharing/connect",
        headers=headers(member),
        json={"token": grant["token"], "display_name": "Sam"},
    )
    old = store.view(token=grant["token"])
    project = store._project

    def concurrently_edit(cur, row):
        newer = changed.model_copy(deep=True)
        newer.route.geometry.coordinates = [[-103, 42], [-102, 43]]
        newer.itinerary = [
            {"date": "2027-06-01", "stops": [{"name": "Updated museum", "time": "11:00"}]}
        ]
        raw = chat_crud.get_chat(owner, "1")["chat_data"]
        chat_crud.update_chat_component(
            owner, "1", newer, "ChatData", expected_revision=chat_crud.chat_data_revision(raw)
        )
        return project(cur, row)

    monkeypatch.setattr(store, "_project", concurrently_edit)
    coherent = store.view(token=grant["token"])
    assert coherent == old  # old authorized JSON and old segments from same MVCC snapshot
    monkeypatch.setattr(store, "_project", project)
    latest = store.view(user_id=member, share_id=UUID(sid))
    assert latest["route"]["coordinates"] == [[-103, 42], [-102, 43]]
    assert latest["itinerary"][0]["stops"][0]["name"] == "Updated museum"
    assert latest["revision"] != old["revision"]

    def concurrently_revoke(cur, row):
        store.revoke(owner, 1, share_id=UUID(sid))
        return project(cur, row)

    monkeypatch.setattr(store, "_project", concurrently_revoke)
    assert (
        store.view(token=grant["token"]) == latest
    )  # already authorized in-flight response may finish
    monkeypatch.setattr(store, "_project", project)
    assert client.post("/trip-sharing/view", json={"token": grant["token"]}).status_code == 404
    assert client.get("/shared-trips/" + sid, headers=headers(member)).status_code == 404


def test_stale_owner_create_and_member_leave_preserve_trip_and_other_members(journey):
    _, client, owner, member, other, headers, link, _, _ = journey
    before = chat_crud.get_chat(owner, "1")
    assert (
        client.post(
            "/chats/1/sharing/link", headers=headers(owner), json={"expected_revision": "b" * 64}
        ).status_code
        == 409
    )
    grant = link()
    sid = grant["share_id"]
    for account in (member, other):
        assert (
            client.post(
                "/trip-sharing/connect",
                headers=headers(account),
                json={"token": grant["token"], "display_name": "Traveler"},
            ).status_code
            == 200
        )
    assert (
        client.delete("/shared-trips/" + sid + "/membership", headers=headers(member)).status_code
        == 204
    )
    assert client.get("/shared-trips/" + sid, headers=headers(member)).status_code == 404
    assert client.get("/shared-trips/" + sid, headers=headers(other)).status_code == 200
    assert chat_crud.get_chat(owner, "1") == before


def test_missing_migration_fails_sharing_only_without_database_detail(journey):
    conn, client, owner, _, _, headers, _, _, _ = journey
    # Exclusive synthetic lane only; temporarily rename this new table and restore.
    with conn.cursor() as cur:
        cur.execute("ALTER TABLE trip_shares RENAME TO fixture_trip_shares_unavailable")
    conn.commit()
    try:
        response = client.get("/chats/1/sharing", headers=headers(owner))
        assert response.status_code == 503
        assert response.json() == {"detail": "Trip sharing is temporarily unavailable"}
        assert client.get("/chats", headers=headers(owner)).status_code == 200
    finally:
        with conn.cursor() as cur:
            cur.execute("ALTER TABLE fixture_trip_shares_unavailable RENAME TO trip_shares")
        conn.commit()


@pytest.mark.parametrize("action", ["stop", "rotate"])
def test_revocation_wins_racing_token_join_under_actual_row_lock(journey, monkeypatch, action):
    """Pause the actual winning writer before commit; prove old-token join waits/rejects."""
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor

    conn, _, owner, member, _, _, link, _, _ = journey
    grant = link()
    status = store._status
    get_conn = chat_crud._get_conn
    main_thread = threading.current_thread()
    entered = threading.Event()
    pid = []
    pending = []

    def observe_join_connection():
        connection = get_conn()
        if threading.current_thread() is not main_thread:
            pid.append(connection.get_backend_pid())
            entered.set()
        return connection

    monkeypatch.setattr(chat_crud, "_get_conn", observe_join_connection)
    with ThreadPoolExecutor(max_workers=1) as executor:

        def paused_status(cur, owner_id, chat_id):
            pending.append(executor.submit(store.connect, member, grant["token"], "Racing join"))
            assert entered.wait(3), "Join did not obtain its own connection"
            deadline = time.monotonic() + 3
            blocked = False
            while time.monotonic() < deadline:
                with conn.cursor() as control:
                    control.execute("SELECT pg_stat_clear_snapshot()")
                    control.execute(
                        "SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s", (pid[0],)
                    )
                    row = control.fetchone()
                    blocked = row is not None and row[0] == "Lock"
                conn.rollback()
                if blocked:
                    break
                time.sleep(0.01)
            assert blocked, "Token join must wait on the actual owner sharing-row writer"
            return status(cur, owner_id, chat_id)

        monkeypatch.setattr(store, "_status", paused_status)
        if action == "stop":
            store.revoke(owner, 1, share_id=UUID(grant["share_id"]), link_only=True)
        else:
            revision = chat_crud.chat_data_revision(chat_crud.get_chat(owner, "1")["chat_data"])
            store.create_link(owner, 1, revision)
        with pytest.raises(store.ShareUnavailable):
            pending[0].result(timeout=3)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM trip_share_members WHERE share_id=%s", (grant["share_id"],)
        )
        assert cur.fetchone()[0] == 0
    conn.rollback()


def test_removing_member_stops_known_link_and_preserves_other_connections(journey):
    _, client, owner, member, other, headers, link, _, _ = journey
    grant = link()
    sid = grant["share_id"]
    for account in (member, other):
        client.post(
            "/trip-sharing/connect",
            headers=headers(account),
            json={"token": grant["token"], "display_name": "Traveler"},
        )
    access = client.get("/chats/1/sharing", headers=headers(owner)).json()
    member_id = access["members"][0]["id"]
    removed_account = member
    # Ordering is deterministic insertion time; identify the test membership independently.
    # Never expose account IDs in the actual owner response.
    with journey[0].cursor() as cur:
        cur.execute("SELECT account_id FROM trip_share_members WHERE id=%s", (member_id,))
        removed_account = cur.fetchone()[0]
    journey[0].rollback()
    retained_account = other if removed_account == member else member
    response = client.delete(
        f"/chats/1/sharing/members/{member_id}?share_id={sid}", headers=headers(owner)
    )
    assert response.status_code == 200 and not response.json()["link_enabled"]
    assert client.get("/shared-trips/" + sid, headers=headers(removed_account)).status_code == 404
    assert client.get("/shared-trips/" + sid, headers=headers(retained_account)).status_code == 200
    assert client.post("/trip-sharing/view", json={"token": grant["token"]}).status_code == 404
    assert (
        client.post(
            "/trip-sharing/connect",
            headers=headers(removed_account),
            json={"token": grant["token"], "display_name": "Retry"},
        ).status_code
        == 404
    )


def test_bounded_connections_still_allow_existing_member_to_update_label(journey, monkeypatch):
    _, client, _, member, other, headers, link, _, _ = journey
    monkeypatch.setattr(store, "MAX_MEMBERS", 1)
    grant = link()
    for label in ("First", "Renamed"):
        assert (
            client.post(
                "/trip-sharing/connect",
                headers=headers(member),
                json={"token": grant["token"], "display_name": label},
            ).status_code
            == 200
        )
    assert (
        client.post(
            "/trip-sharing/connect",
            headers=headers(other),
            json={"token": grant["token"], "display_name": "Other"},
        ).status_code
        == 409
    )


def test_shared_geometry_hydration_cannot_read_foreign_segments(journey):
    conn, client, owner, _, other, _, link, _, _ = journey
    route_id = owner + "-private-reference"
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE chats SET chat_data=jsonb_set(chat_data,'{route,geometry,coordinates}',to_jsonb(%s::text)) WHERE user_id=%s AND chat_id='1'",
            (route_id, owner),
        )
        cur.execute(
            "INSERT INTO route_segments (user_id,chat_id,route_id,segment_id,coords) VALUES (%s,'1',%s,'0','[[-105,40],[-104,41]]'),(%s,'1',%s,'1','[[99,88]]')",
            (owner, route_id, other, route_id),
        )
    conn.commit()
    grant = link()
    response = client.post("/trip-sharing/view", json={"token": grant["token"]})
    assert response.status_code == 200
    assert response.json()["route"]["coordinates"] == [[-105, 40], [-104, 41]]


def test_stale_member_remove_after_leave_reconnect_requires_reload_not_false_success(journey):
    _, client, owner, member, _, headers, link, _, _ = journey
    grant = link()
    sid = grant["share_id"]
    body = {"token": grant["token"], "display_name": "Sam"}
    client.post("/trip-sharing/connect", headers=headers(member), json=body)
    old_id = client.get("/chats/1/sharing", headers=headers(owner)).json()["members"][0]["id"]
    assert (
        client.delete("/shared-trips/" + sid + "/membership", headers=headers(member)).status_code
        == 204
    )
    assert (
        client.post("/trip-sharing/connect", headers=headers(member), json=body).status_code == 200
    )
    current = client.get("/chats/1/sharing", headers=headers(owner)).json()
    assert current["members"][0]["id"] != old_id
    stale = client.delete(
        f"/chats/1/sharing/members/{old_id}?share_id={sid}", headers=headers(owner)
    )
    assert stale.status_code == 409
    assert stale.json()["detail"] == "Connection changed; reload before removing access"
    assert client.get("/chats/1/sharing", headers=headers(owner)).json() == current
    new_id = current["members"][0]["id"]
    removed = client.delete(
        f"/chats/1/sharing/members/{new_id}?share_id={sid}", headers=headers(owner)
    )
    assert removed.status_code == 200 and not removed.json()["link_enabled"]
    assert client.get("/shared-trips/" + sid, headers=headers(member)).status_code == 404
    assert client.post("/trip-sharing/view", json={"token": grant["token"]}).status_code == 404
