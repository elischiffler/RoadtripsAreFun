"""Real PostgreSQL CRUD probe for the disposable Compose test stack only.

The ``seed`` and ``verify`` phases run in separate Python processes so the
second phase also checks that no module-level cache or pool hides lost data.
"""

import os
import sys

import psycopg2
from pydantic import BaseModel

from app.agent.memory import ConversationMemory, MemoryFact
from app.agent.trip_profile import TripProfile
from app.crud import chat_crud, memory_crud
from app.models.scheduling_policy import SchedulingPolicy
from app.schemas.chat_schemas import ChatLogSchema
from app.utils.location_resolution import LocationCandidate, PendingLocation


class RouteComponent(BaseModel):
    route: dict


class InitialComponent(BaseModel):
    initial: dict


POLICY = SchedulingPolicy(late_driving=True, morning_restart="10:30").model_dump()
EVENING_OPTIONS = [
    {
        "name": "Provider cafe fixture",
        "optional": True,
        "status": "tentative",
        "notice": "Check opening hours",
        "visit_time": None,
        "return_by": "2035-11-22T00:00:00-08:00",
    }
]

PENDING_JSON = TripProfile(
    scheduling_policy=POLICY,
    evening_interests=["food"],
    pending_locations={
        "start_address": PendingLocation(
            query="SLO",
            candidates=[
                LocationCandidate(
                    id="fixture-pending-location",
                    address="Salem-Leckrone Airport, Illinois",
                    latitude=38.64,
                    longitude=-88.96,
                    timezone="America/Chicago",
                )
            ],
        )
    },
).to_json()

RUN_ID = os.environ["DB_TEST_RUN_ID"]
OWNER_A = f"dbtest-{RUN_ID}-a"
OWNER_B = f"dbtest-{RUN_ID}-b"
CHAT_ID = f"dbtest-{RUN_ID}-chat"
SEGMENT_CHAT = f"dbtest-{RUN_ID}-segment-conflict"
STEP_CHAT = f"dbtest-{RUN_ID}-step-conflict"
DELETE_CHAT = f"dbtest-{RUN_ID}-delete"
ROUTE_A = f"{OWNER_A}-{CHAT_ID}"
GOOD_COORDS = [[-122.4, 37.7], [-121.9, 37.3]]
GOOD_STEPS = [[-122.4, 37.7], [-122.2, 37.5]]


def _raw_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"], sslmode="disable")


def seed():
    for owner in (OWNER_A, OWNER_B):
        chat_crud.create_chat(owner, CHAT_ID, {"owner": owner}, {"messages": []})
    assert chat_crud.get_chat(OWNER_A, CHAT_ID)["chat_data"]["owner"] == OWNER_A
    assert chat_crud.get_chat(OWNER_B, CHAT_ID)["chat_data"]["owner"] == OWNER_B
    assert len(chat_crud.get_all_chats(OWNER_A)) == 1

    chat_crud.update_chat_component(
        OWNER_A,
        CHAT_ID,
        RouteComponent(
            route={
                "geometry": {"coordinates": GOOD_COORDS},
                "scheduling_policy": POLICY,
                "stops": [
                    {"name": "Hotel", "type": "hotel", "evening_suggestions": EVENING_OPTIONS}
                ],
            }
        ),
        "ChatData",
    )
    chat_crud.update_chat_component(
        OWNER_A,
        CHAT_ID,
        InitialComponent(
            initial={
                "geometry": {"coordinates": GOOD_COORDS},
                "legs": [{"steps": [{"geometry": {"coordinates": c}} for c in GOOD_STEPS]}],
            }
        ),
        "ChatData",
    )
    chat_crud.update_chat_component(
        OWNER_A,
        CHAT_ID,
        ChatLogSchema(
            id=1,
            title="Fixture trip",
            messages=[
                {"sender": "user", "text": "fixture hello"},
                {
                    "sender": "bot",
                    "text": "Updated trip details: Hotel budget: $200 per night",
                    "presentation": {
                        "title": "Updated trip details",
                        "updated": ["Hotel budget: $200 per night"],
                        "needed": ["What date would you like to leave?"],
                        "introduction": "A few details remain.",
                        "questions": [
                            "Which evening interests would you like suggestions for (optional)?"
                        ],
                        "notes": [],
                    },
                },
            ],
        ),
        "ChatLog",
    )
    assert chat_crud.get_segments(OWNER_A, CHAT_ID, ROUTE_A) == GOOD_COORDS
    assert chat_crud.get_segments(OWNER_B, CHAT_ID, ROUTE_A) == []
    leg_ref = f"{ROUTE_A}-leg-0"
    legs = [{"steps": [{"geometry": {"coordinates": leg_ref}} for _ in GOOD_STEPS]}]
    restored = chat_crud.restore_legs(OWNER_A, CHAT_ID, legs)
    assert [step["geometry"]["coordinates"] for step in restored[0]["steps"]] == GOOD_STEPS
    other_legs = [{"steps": [{"geometry": {"coordinates": leg_ref}}]}]
    assert chat_crud.restore_legs(OWNER_B, CHAT_ID, other_legs) == other_legs

    memory_crud.upsert_facts(OWNER_A, [MemoryFact(key="home_city", value="San Luis Obispo")])
    memory_crud.upsert_facts(OWNER_B, [MemoryFact(key="home_city", value="Boston")])
    memory_crud.save_conversation(
        OWNER_A, CHAT_ID, ConversationMemory(chat_id=CHAT_ID, summary="Pacific coast")
    )
    memory_crud.save_trip_profile(OWNER_A, CHAT_ID, PENDING_JSON)
    memory_crud.save_planned_route(
        OWNER_A,
        CHAT_ID,
        {
            "route": {
                "stops": [
                    {"name": "Museum"},
                    {"name": "Hotel", "type": "hotel", "evening_suggestions": EVENING_OPTIONS},
                ],
                "scheduling_policy": POLICY,
            },
            "departure": "2030-01-01T09:00:00Z",
        },
    )
    assert memory_crud.load_facts(OWNER_A)[0].value == "San Luis Obispo"
    assert memory_crud.load_facts(OWNER_B)[0].value == "Boston"
    assert memory_crud.load_conversation(OWNER_A, CHAT_ID).summary == "Pacific coast"
    assert memory_crud.load_conversation(OWNER_B, CHAT_ID).summary == ""
    assert memory_crud.load_trip_profile(OWNER_A, CHAT_ID) == PENDING_JSON
    saved_route = memory_crud.load_planned_route(OWNER_A, CHAT_ID)["route"]
    assert saved_route["scheduling_policy"] == POLICY
    assert saved_route["stops"][1]["evening_suggestions"] == EVENING_OPTIONS
    saved_chat = chat_crud.get_chat(OWNER_A, CHAT_ID)["chat_data"]["route"]
    assert saved_chat["scheduling_policy"] == POLICY
    assert saved_chat["stops"][0]["evening_suggestions"] == EVENING_OPTIONS
    assert memory_crud.load_trip_profile(OWNER_B, CHAT_ID) is None
    assert memory_crud.load_planned_route(OWNER_A, CHAT_ID)["route"]["stops"][0]["name"] == "Museum"
    assert memory_crud.load_planned_route(OWNER_B, CHAT_ID) is None

    chat_crud.create_chat(OWNER_A, DELETE_CHAT, {"temporary": True}, {})
    chat_crud.create_chat(OWNER_B, DELETE_CHAT, {"keeper": True}, {})
    assert len(chat_crud.delete_chat(OWNER_A, DELETE_CHAT)) == 1
    assert chat_crud.get_chat(OWNER_A, DELETE_CHAT) is None
    assert chat_crud.get_chat(OWNER_B, DELETE_CHAT)["chat_data"] == {"keeper": True}

    for conflict_chat in (SEGMENT_CHAT, STEP_CHAT):
        chat_crud.create_chat(OWNER_A, conflict_chat, {}, {})
    with _raw_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO route_segments (user_id,chat_id,route_id,segment_id,coords) "
            "VALUES (%s,%s,%s,'0',%s)",
            (OWNER_B, CHAT_ID, f"{OWNER_A}-{SEGMENT_CHAT}", "[[9,9]]"),
        )
        cur.execute(
            "INSERT INTO steps (user_id,chat_id,leg_id,step_id,coordinates) VALUES (%s,%s,%s,0,%s)",
            (OWNER_B, CHAT_ID, f"{OWNER_A}-{STEP_CHAT}-leg-0", "[9,9]"),
        )
    try:
        chat_crud.update_chat_component(
            OWNER_A,
            SEGMENT_CHAT,
            RouteComponent(route={"geometry": {"coordinates": GOOD_COORDS}}),
            "ChatData",
        )
        raise AssertionError("foreign segment key was overwritten")
    except PermissionError:
        pass
    try:
        chat_crud.update_chat_component(
            OWNER_A,
            STEP_CHAT,
            InitialComponent(
                initial={
                    "geometry": {"coordinates": GOOD_COORDS},
                    "legs": [{"steps": [{"geometry": {"coordinates": GOOD_STEPS[0]}}]}],
                }
            ),
            "ChatData",
        )
        raise AssertionError("foreign step key was overwritten")
    except PermissionError:
        pass
    verify()
    print("seed: real CRUD, geometry, memory, two-owner isolation and conflicts PASS")


def verify():
    assert chat_crud.get_chat(OWNER_A, CHAT_ID)["chat_data"]["owner"] == OWNER_A
    assert chat_crud.get_chat(OWNER_B, CHAT_ID)["chat_data"]["owner"] == OWNER_B
    assert (
        chat_crud.get_chat(OWNER_A, CHAT_ID)["chat_log"]["messages"][0]["text"] == "fixture hello"
    )
    restored_log = ChatLogSchema.model_validate(chat_crud.get_chat(OWNER_A, CHAT_ID)["chat_log"])
    assert restored_log.messages[0].presentation is None
    assert restored_log.messages[1].presentation.updated == ["Hotel budget: $200 per night"]
    assert restored_log.messages[1].presentation.needed == ["What date would you like to leave?"]
    assert restored_log.messages[1].presentation.introduction == "A few details remain."
    assert restored_log.messages[1].presentation.questions == [
        "Which evening interests would you like suggestions for (optional)?"
    ]
    assert chat_crud.get_segments(OWNER_A, CHAT_ID, ROUTE_A) == GOOD_COORDS
    assert chat_crud.get_segments(OWNER_B, CHAT_ID, ROUTE_A) == []
    assert memory_crud.load_facts(OWNER_A)[0].value == "San Luis Obispo"
    assert memory_crud.load_facts(OWNER_B)[0].value == "Boston"
    assert memory_crud.load_conversation(OWNER_A, CHAT_ID).summary == "Pacific coast"
    assert memory_crud.load_trip_profile(OWNER_A, CHAT_ID) == PENDING_JSON
    saved_route = memory_crud.load_planned_route(OWNER_A, CHAT_ID)["route"]
    assert saved_route["scheduling_policy"] == POLICY
    assert saved_route["stops"][1]["evening_suggestions"] == EVENING_OPTIONS
    saved_chat = chat_crud.get_chat(OWNER_A, CHAT_ID)["chat_data"]["route"]
    assert saved_chat["scheduling_policy"] == POLICY
    assert saved_chat["stops"][0]["evening_suggestions"] == EVENING_OPTIONS
    assert memory_crud.load_planned_route(OWNER_A, CHAT_ID)["departure"] == "2030-01-01T09:00:00Z"
    assert memory_crud.load_planned_route(OWNER_B, CHAT_ID) is None
    assert chat_crud.get_chat(OWNER_A, DELETE_CHAT) is None
    assert chat_crud.get_chat(OWNER_B, DELETE_CHAT)["chat_data"] == {"keeper": True}
    with _raw_connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT user_id,coords FROM route_segments WHERE route_id=%s AND segment_id='0'",
            (f"{OWNER_A}-{SEGMENT_CHAT}",),
        )
        owner, coords = cur.fetchone()
        assert owner == OWNER_B and coords == [[9, 9]]
        cur.execute(
            "SELECT user_id,coordinates FROM steps WHERE leg_id=%s AND step_id=0",
            (f"{OWNER_A}-{STEP_CHAT}-leg-0",),
        )
        owner, coords = cur.fetchone()
        assert owner == OWNER_B and coords == [9, 9]
        cur.execute(
            "SELECT chat_data FROM chats WHERE user_id=%s AND chat_id=%s", (OWNER_A, SEGMENT_CHAT)
        )
        assert cur.fetchone()[0] == {}
        cur.execute(
            "SELECT chat_data FROM chats WHERE user_id=%s AND chat_id=%s", (OWNER_A, STEP_CHAT)
        )
        assert cur.fetchone()[0] == {}
    print("verify: persisted CRUD and ownership state PASS")


if __name__ == "__main__":
    if sys.argv[1:] == ["seed"]:
        seed()
    elif sys.argv[1:] == ["verify"]:
        verify()
    else:
        raise SystemExit("Usage: db_integration_probe.py seed|verify")
