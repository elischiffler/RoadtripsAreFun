import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

CHAT_DATA = {
    "chatId": 1,
    "action": None,
    "locationType": "",
    "startCoords": [],
    "startAddress": ["", "", "", ""],
    "endCoords": [],
    "endAddress": ["", "", "", ""],
    "stops": 1,
    "showInputBar": False,
    "showStopSlider": False,
    "showBudgetSlider": False,
    "showAddressInput": False,
    "workflowStarted": False,
    "startConfirmed": None,
    "endConfirmed": None,
    "initial": None,
    "route": None,
    "itinerary": None,
    "loading": False,
    "hotelBudget": None,
    "carDetails": [],
    "budget": 0,
}

CHAT_LOG = {
    "id": 1,
    "title": "Chat 1",
    "messages": [{"text": "Hello welcome to Journey Genie", "sender": "bot", "buttons": []}],
}


def _make_mock_pool(fetchone_val=None, fetchall_val=None):
    """Return a mock pool whose getconn/putconn work with a mock connection."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = fetchone_val
    mock_cursor.fetchall.return_value = fetchall_val or []
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    mock_pool = MagicMock()
    mock_pool.getconn.return_value = mock_conn
    mock_pool.putconn = MagicMock()  # no-op return to pool
    mock_pool.closed = False
    return mock_pool, mock_conn, mock_cursor


# ---------------------------------------------------------------------------
# POST /chats/create/{chat_id}
# ---------------------------------------------------------------------------

def test_create_chat():
    """Returns 200 when a valid chat payload is posted."""
    mock_pool, _, mock_cursor = _make_mock_pool(fetchone_val=("user123", "1", {}, {}))

    with patch("app.crud.chat_crud._get_pool", return_value=mock_pool), \
         patch("app.routers.chat_api.get_user_id_from_token", return_value="user123"):
        response = client.post(
            "/chats/create/1",
            json={"PartitionKey": "user123", "ChatData": CHAT_DATA, "ChatLog": CHAT_LOG},
        )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# DELETE /chats/delete/{chat_id}
# ---------------------------------------------------------------------------

def test_delete_chat():
    """Returns 200 and a success message when a chat is deleted."""
    mock_pool, _, _ = _make_mock_pool(fetchall_val=[("user123", "2", {}, {})])

    with patch("app.crud.chat_crud._get_pool", return_value=mock_pool), \
         patch("app.routers.chat_api.get_user_id_from_token", return_value="user123"):
        response = client.delete(
            "/chats/delete/2",
            params={"partition_key": "user123"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "success"


# ---------------------------------------------------------------------------
# PUT /chats/update/{chat_id}
# ---------------------------------------------------------------------------

def test_update_chat():
    """Returns 200 when a valid update payload is sent."""
    mock_cursor = MagicMock()
    mock_cursor.__enter__ = lambda s: s
    mock_cursor.__exit__ = MagicMock(return_value=False)
    mock_cursor.fetchone.return_value = {"chat_data": {}, "chat_log": {}}
    mock_cursor.fetchall.return_value = [("user123", "3", {}, {})]

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    mock_pool = MagicMock()
    mock_pool.getconn.return_value = mock_conn
    mock_pool.putconn = MagicMock()
    mock_pool.closed = False

    updated_chat_data = {**CHAT_DATA, "action": "Address"}
    updated_chat_log = {
        **CHAT_LOG,
        "messages": CHAT_LOG["messages"] + [{"text": "LA to NYC", "sender": "user", "buttons": []}],
    }

    with patch("app.crud.chat_crud._get_pool", return_value=mock_pool), \
         patch("app.routers.chat_api.get_user_id_from_token", return_value="user123"):
        response = client.put(
            "/chats/update/3?partition_key=user123",
            json={"PartitionKey": "user123", "ChatData": updated_chat_data, "ChatLog": updated_chat_log},
        )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /chats
# ---------------------------------------------------------------------------

def test_get_all_chats_empty():
    """Returns 200 and an empty list when the user has no chats."""
    mock_pool, _, _ = _make_mock_pool(fetchall_val=[])

    with patch("app.crud.chat_crud._get_pool", return_value=mock_pool), \
         patch("app.routers.chat_api.get_user_id_from_token", return_value="user123"):
        response = client.get("/chats", params={"partition_key": "user123"})
    assert response.status_code == 200
    assert response.json() == []


def test_get_all_chats_returns_list():
    """Returns 200 and a list of chats matching the stored rows."""
    rows = [
        {"user_id": "88", "chat_id": str(i), "chat_data": {"initial": None, "route": None}, "chat_log": {}}
        for i in range(1, 4)
    ]
    mock_pool, _, _ = _make_mock_pool(fetchall_val=rows)

    with patch("app.crud.chat_crud._get_pool", return_value=mock_pool), \
         patch("app.routers.chat_api.get_user_id_from_token", return_value="88"):
        response = client.get("/chats", params={"partition_key": "88"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


if __name__ == "__main__":
    pytest.main()
