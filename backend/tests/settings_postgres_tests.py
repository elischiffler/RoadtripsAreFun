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
