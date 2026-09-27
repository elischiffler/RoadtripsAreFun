"""Owner predicates and conflict guards for chat route/step records."""

from unittest.mock import MagicMock, patch

import pytest

from app.crud import chat_crud


def _connection(*, fetchone=None, fetchall=None):
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.fetchone.return_value = fetchone
    cursor.fetchall.return_value = fetchall or []
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


def test_segment_and_step_reads_are_scoped_to_verified_user_and_chat():
    conn, cursor = _connection(fetchall=[{"coords": [[1, 2]], "step_id": 0, "coordinates": [3, 4]}])
    with (
        patch("app.crud.chat_crud._get_conn", return_value=conn),
        patch("app.crud.chat_crud._put_conn"),
    ):
        assert chat_crud.get_segments("alice", "chat-1", "route-1") == [[1, 2]]
        segment_sql, segment_params = cursor.execute.call_args.args
        assert "user_id = %s AND chat_id = %s AND route_id = %s" in segment_sql
        assert segment_params == ("alice", "chat-1", "route-1")

        legs = [{"steps": [{"geometry": {"coordinates": "route-1-leg-0"}}]}]
        assert chat_crud.restore_legs("bob", "chat-2", legs)[0]["steps"][0]["geometry"][
            "coordinates"
        ] == [3, 4]
        step_sql, step_params = cursor.execute.call_args.args
        assert "user_id = %s AND chat_id = %s AND leg_id = %s" in step_sql
        assert step_params == ("bob", "chat-2", "route-1-leg-0")


def test_foreign_step_identifier_conflict_rejects_write():
    conn, cursor = _connection(fetchone=None)
    legs = [{"steps": [{"geometry": {"coordinates": [1, 2]}}]}]
    with pytest.raises(PermissionError, match="different chat"):
        chat_crud._store_legs(conn, "bob", "chat-2", "shared-route", legs)
    sql, params = cursor.execute.call_args.args
    assert "steps.user_id = EXCLUDED.user_id" in sql
    assert "steps.chat_id = EXCLUDED.chat_id" in sql
    assert params[:2] == ("bob", "chat-2")


def test_foreign_segment_identifier_conflict_rolls_back_chat_update():
    conn, cursor = _connection()
    cursor.fetchone.side_effect = [{"chat_data": {}}, None]
    schema = MagicMock()
    schema.model_dump.return_value = {"route": {"geometry": {"coordinates": [[1, 2]]}}}
    with (
        patch("app.crud.chat_crud._get_conn", return_value=conn),
        patch("app.crud.chat_crud._put_conn"),
        patch("app.crud.chat_crud.segment_route", return_value=[[[1, 2]]]),
        pytest.raises(PermissionError, match="different chat"),
    ):
        chat_crud.update_chat_component("bob", "chat-2", schema, "ChatData")
    insert_sql, insert_params = cursor.execute.call_args.args
    assert "route_segments.user_id = EXCLUDED.user_id" in insert_sql
    assert "route_segments.chat_id = EXCLUDED.chat_id" in insert_sql
    assert insert_params[:2] == ("bob", "chat-2")
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
