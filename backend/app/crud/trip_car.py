"""Atomically change car fields without overwriting routes, logs or itinerary."""

import json

from app.crud import chat_crud
from app.schemas.trip_car import TripCarUpdate


def update_trip_car(user_id: str, chat_id: int, value: TripCarUpdate) -> str | None:
    car = value.car
    details = [str(car.year), car.make, car.model] if car else ["", "", ""]
    profile_patch = {"car_status": value.car_status, "car": car.model_dump() if car else None}
    conn = chat_crud._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE chats SET chat_data =
                jsonb_set(
                  jsonb_set(COALESCE(chat_data, '{}'::jsonb), '{carDetails}', %s::jsonb, true),
                  '{tripProfile}',
                  (CASE WHEN jsonb_typeof(chat_data->'tripProfile') = 'object'
                    THEN chat_data->'tripProfile' ELSE '{}'::jsonb END) || %s::jsonb, true
                ) || '{"carBudget":null}'::jsonb
                WHERE user_id = %s AND chat_id = %s
                  AND NULLIF(chat_data->>'agentChatId', '') IS NOT DISTINCT FROM %s
                RETURNING chat_data""",
                (
                    json.dumps(details),
                    json.dumps(profile_patch),
                    user_id,
                    str(chat_id),
                    value.expected_agent_chat_id,
                ),
            )
            row = cur.fetchone()
            revision = chat_crud.chat_data_revision(row[0]) if row else None
        conn.commit()
        return revision
    except Exception:
        conn.rollback()
        raise
    finally:
        chat_crud._put_conn(conn)
