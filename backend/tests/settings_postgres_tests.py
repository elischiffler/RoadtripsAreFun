"""Real CRUD only on the explicitly configured, known disposable local stack.

The standard suite skips these tests. The disposable PostgreSQL runner supplies
SETTINGS_TEST_DATABASE_URL; this never falls back to DATABASE_URL or Neon.
"""

import os
from urllib.parse import urlsplit
from uuid import uuid4

import psycopg2
import pytest
from psycopg2.extras import Json

from app.agent.persona import default_weights
from app.crud import chat_crud, preference_profiles, trip_car
from app.schemas.preference_profiles import PreferenceProfileInput
from app.schemas.trip_car import TripCarUpdate

pytestmark = pytest.mark.skipif(
    not os.getenv("SETTINGS_TEST_DATABASE_URL"), reason="Disposable settings database not selected"
)


@pytest.fixture
def database(monkeypatch):
    url = os.environ["SETTINGS_TEST_DATABASE_URL"]
    target = urlsplit(url)
    assert target.hostname in {"postgres", "127.0.0.1", "localhost"}
    assert target.username == "postgres" and target.password == "disposable-local-only"
    assert target.path == "/roadtrips" and not target.query
    assert (
        os.environ.get("DB_TEST_RUN_ID", "").startswith("settings") or target.hostname == "postgres"
    )
    conn = psycopg2.connect(url, sslmode="disable", connect_timeout=5)
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.chat_memory'), to_regclass('public.chats')")
        assert cur.fetchone() == ("chat_memory", "chats")
    conn.rollback()
    prefix = "settings-test-" + str(uuid4())
    monkeypatch.setattr(
        chat_crud, "_get_conn", lambda: psycopg2.connect(url, sslmode="disable", connect_timeout=5)
    )
    monkeypatch.setattr(chat_crud, "_put_conn", lambda connection: connection.close())
    yield conn, prefix
    with conn.cursor() as cur:
        cur.execute("DELETE FROM chat_memory WHERE user_id LIKE %s", (prefix + "%",))
        cur.execute("DELETE FROM chats WHERE user_id LIKE %s", (prefix + "%",))
    conn.commit()
    conn.close()


def test_profile_discriminator_roundtrip_account_isolation_and_idempotence(database):
    conn, prefix = database
    owner, other, profile_id = prefix + "-a", prefix + "-b", uuid4()
    value = PreferenceProfileInput(
        name="First set", choices={"car_status": "skipped", "persona_weights": default_weights()}
    )
    preference_profiles.save_profile(owner, profile_id, value)
    assert preference_profiles.list_profiles(other) == []
    assert preference_profiles.list_profiles(owner)[0].name == "First set"
    updated = value.model_copy(update={"name": "Renamed set"})
    preference_profiles.save_profile(owner, profile_id, updated)
    assert len(preference_profiles.list_profiles(owner)) == 1
    preference_profiles.delete_profile(other, profile_id)
    assert preference_profiles.list_profiles(owner)[0].name == "Renamed set"
    preference_profiles.save_profile(other, profile_id, value)
    assert len(preference_profiles.list_profiles(other)) == 1
    with conn.cursor() as cur:
        cur.execute(
            "SELECT mem_type, updated_at IS NOT NULL FROM chat_memory WHERE user_id=%s", (owner,)
        )
        assert cur.fetchone() == ("preference_profile", True)
    preference_profiles.delete_profile(owner, profile_id)
    preference_profiles.delete_profile(owner, profile_id)
    assert preference_profiles.list_profiles(owner) == []
    assert len(preference_profiles.list_profiles(other)) == 1


@pytest.mark.parametrize("legacy", [False, True])
def test_trip_car_patch_preserves_saved_trip_and_checks_owner_and_identity(database, legacy):
    conn, prefix = database
    owner = prefix + "-a"
    trip = {
        "chatId": 9,
        "agentChatId": None if legacy else "original-trip",
        "carDetails": ["2018", "Toyota", "Corolla"],
        "carBudget": 42,
        "route": {"geometry": "preserved-reference"},
        "itinerary": [{"date": "future", "stops": ["preserved"]}],
        "presentation": {"visitedStopIds": ["one"]},
        "tripProfile": None
        if legacy
        else {"num_stops": 3, "start_address": "Boulder", "persona_weights": default_weights()},
    }
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO chats (user_id,chat_id,chat_data,chat_log) VALUES (%s,'9',%s,%s)",
            (owner, Json(trip), Json({"messages": ["keep"]})),
        )
    conn.commit()
    choices = TripCarUpdate(
        car_status="provided",
        car={"year": 2021, "make": "Honda", "model": "Civic"},
        expected_agent_chat_id=trip["agentChatId"],
    )
    assert not trip_car.update_trip_car(prefix + "-b", 9, choices)
    assert not trip_car.update_trip_car(
        owner, 9, choices.model_copy(update={"expected_agent_chat_id": "stale-trip"})
    )
    assert trip_car.update_trip_car(owner, 9, choices)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT chat_data,chat_log FROM chats WHERE user_id=%s AND chat_id='9'", (owner,)
        )
        saved, log = cur.fetchone()
    for key in ("route", "itinerary", "presentation", "agentChatId"):
        assert saved[key] == trip[key]
    assert log == {"messages": ["keep"]}
    assert saved["carDetails"] == ["2021", "Honda", "Civic"]
    assert saved["carBudget"] is None
    assert saved["tripProfile"]["car"] == {"year": 2021, "make": "Honda", "model": "Civic"}
    if not legacy:
        assert saved["tripProfile"]["start_address"] == "Boulder"
    assert trip_car.update_trip_car(
        owner, 9, TripCarUpdate(car_status="skipped", expected_agent_chat_id=trip["agentChatId"])
    )
    with conn.cursor() as cur:
        cur.execute(
            "SELECT chat_data->'tripProfile'->'car',chat_data->'carDetails' FROM chats WHERE user_id=%s AND chat_id='9'",
            (owner,),
        )
        assert cur.fetchone() == (None, ["", "", ""])


def test_long_route_shortening_keeps_exact_geometry_initial_and_scoped_rollback(
    database, monkeypatch
):
    """Exercise the real segment-table transaction, not a cursor simulation."""
    import copy

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import chat_api
    from app.schemas.chat_schemas import ChatDataSchema
    from tests.chat_json_serialization_tests import timed_body

    conn, prefix = database
    owner, other = prefix + "-route-owner", prefix + "-other-owner"
    body = timed_body()
    chat_crud.create_chat(owner, "1", body["ChatData"], body["ChatLog"])
    initial_id = owner + "-1"
    initial = [[-110, 40], [-109, 41]]
    foreign_id = other + "-route"
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE chats SET chat_data=jsonb_set(chat_data,'{initial}',%s::jsonb) WHERE user_id=%s AND chat_id='1'",
            (Json({"geometry": initial_id, "legs": []}), owner),
        )
        cur.execute(
            "INSERT INTO route_segments (user_id,chat_id,route_id,segment_id,coords) VALUES (%s,%s,%s,%s,%s),(%s,%s,%s,%s,%s)",
            (
                owner,
                "1",
                initial_id,
                "0",
                Json(initial),
                other,
                "9",
                foreign_id,
                "1",
                Json([[1, 2]]),
            ),
        )
    conn.commit()
    app = FastAPI()
    app.include_router(chat_api.router)
    monkeypatch.setattr(chat_api, "get_user_id_from_token", lambda _: owner)
    client = TestClient(app)
    try:
        long_geometry = [[-105 + i / 100000, 40] for i in range(10001)]
        body["ChatData"]["route"]["geometry"]["coordinates"] = long_geometry
        body["ExpectedRevision"] = client.get(
            "/chats", headers={"Authorization": "Bearer fixture"}
        ).json()[0][0]["savedRevision"]
        first = client.put("/chats/update/1", json=body)
        assert first.status_code == 200
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM route_segments WHERE user_id=%s AND chat_id=%s AND route_id=%s",
                (owner, "1", owner + "-1-final"),
            )
            assert cur.fetchone()[0] == 2
        conn.rollback()
        shortened = [[-105, 40], [-104, 40]]
        body["ChatData"]["route"]["geometry"]["coordinates"] = shortened
        body["ExpectedRevision"] = first.json()["savedRevision"]
        second = client.put("/chats/update/1", json=body)
        assert second.status_code == 200
        restored = client.get("/chats", headers={"Authorization": "Bearer fixture"}).json()[0][0]
        assert restored["route"]["geometry"]["coordinates"] == shortened
        assert restored["initial"]["geometry"]["coordinates"] == initial
        assert restored["savedRevision"] != first.json()["savedRevision"]
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) FROM route_segments WHERE user_id=%s AND chat_id=%s AND route_id=%s",
                (owner, "1", owner + "-1-final"),
            )
            assert cur.fetchone()[0] == 1
            cur.execute(
                "SELECT coords FROM route_segments WHERE user_id=%s AND route_id=%s",
                (other, foreign_id),
            )
            assert cur.fetchone()[0] == [[1, 2]]
        conn.rollback()

        # A foreign identifier conflict after an earlier insert rolls back both
        # route JSON and already-written segment rows on the same connection.
        failed = copy.deepcopy(body["ChatData"])
        failed["chatId"] = 2
        failed["route"]["geometry"]["coordinates"] = long_geometry
        chat_crud.create_chat(owner, "2", failed, {"id": 2, "title": "Keep", "messages": []})
        before = chat_crud.get_chat(owner, "2")["chat_data"]
        poisoned = owner + "-2-final"
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO route_segments (user_id,chat_id,route_id,segment_id,coords) VALUES (%s,%s,%s,%s,%s)",
                (other, "9", poisoned, "1", Json([[3, 4]])),
            )
        conn.commit()
        with pytest.raises(PermissionError, match="different chat"):
            chat_crud.update_chat_component(
                owner,
                "2",
                ChatDataSchema.model_validate(failed),
                "ChatData",
                expected_revision=chat_crud.chat_data_revision(before),
            )
        assert chat_crud.get_chat(owner, "2")["chat_data"] == before
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id,segment_id,coords FROM route_segments WHERE route_id=%s",
                (poisoned,),
            )
            assert cur.fetchall() == [(other, "1", [[3, 4]])]
        conn.rollback()
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM route_segments WHERE user_id IN (%s,%s)", (owner, other))
        conn.commit()


@pytest.mark.parametrize("representation", ["inline", "segmented", "unavailable", "absent"])
def test_legacy_initial_empty_steps_real_save_reload_preserves_json_revision_and_owner(
    database, monkeypatch, representation
):
    """Read hydration uses only actual owner-scoped segments, never rewrites JSON."""
    from copy import deepcopy

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.routers import chat_api
    from tests.legacy_route_hydration_tests import legacy_body

    conn, prefix = database
    owner, other = prefix + "-legacy", prefix + "-other"
    app = FastAPI()
    app.include_router(chat_api.router)
    monkeypatch.setattr(chat_api, "get_user_id_from_token", lambda _: owner)
    client = TestClient(app, raise_server_exceptions=False)
    body = legacy_body()
    coordinates = deepcopy(body["ChatData"]["initial"]["geometry"]["coordinates"])
    assert client.post("/chats/create/1", json=body).status_code == 200
    if representation == "segmented":
        # The actual legacy update path stores route references, even when a
        # valid Mapbox leg contains no maneuver steps.
        assert client.put("/chats/update/1", json=body).status_code == 200
    if representation in {"unavailable", "absent"}:
        geometry = "missing-" + owner if representation == "unavailable" else None
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE chats SET chat_data=jsonb_set(chat_data,'{initial,geometry}',%s::jsonb) WHERE user_id=%s AND chat_id='1'",
                (Json(geometry), owner),
            )
        conn.commit()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT chat_data,chat_log FROM chats WHERE user_id=%s AND chat_id='1'", (owner,)
        )
        raw, log = cur.fetchone()
        reference = "missing-" + owner if representation == "unavailable" else owner + "-1"
        cur.execute(
            "INSERT INTO route_segments(user_id,chat_id,route_id,segment_id,coords) VALUES(%s,'1',%s,'999',%s)",
            (other, reference, Json([[1, 2], [3, 4]])),
        )
    conn.commit()
    revision = chat_crud.chat_data_revision(raw)
    response = client.get("/chats", headers={"Authorization": "Bearer synthetic-local-token"})
    if representation == "unavailable":
        assert response.status_code == 503, response.text
        assert response.json() == {"detail": "Saved trip geometry is temporarily unavailable"}
    else:
        assert response.status_code == 200, response.text
        hydrated, returned_log = response.json()[0]
        assert hydrated["savedRevision"] == revision
        assert hydrated["initial"]["legs"] == raw["initial"]["legs"]
        if representation == "absent":
            assert hydrated["initial"]["geometry"] is None
        else:
            assert hydrated["initial"]["geometry"]["coordinates"] == coordinates
        assert hydrated["tripProfile"] == raw["tripProfile"]
        assert hydrated["presentation"] == raw["presentation"]
        assert returned_log == log
    with conn.cursor() as cur:
        cur.execute(
            "SELECT chat_data,chat_log FROM chats WHERE user_id=%s AND chat_id='1'", (owner,)
        )
        assert cur.fetchone() == (raw, log)
        cur.execute(
            "SELECT coords FROM route_segments WHERE user_id=%s AND route_id=%s", (other, reference)
        )
        assert cur.fetchone()[0] == [[1, 2], [3, 4]]
    conn.rollback()
