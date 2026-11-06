"""The retired conversational API must never dispatch providers or memory."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.mark.parametrize("path", ["/agent/chat", "/agent/chat/stream"])
def test_retired_api_is_absent_without_side_effects(path):
    with (
        patch("app.agent.providers.build_default_chain") as provider,
        patch("app.crud.memory_crud.MemoryCrudStore.load_facts") as memory,
    ):
        response = TestClient(app).post(path, json={"message": "plan a trip"})
    assert response.status_code == 404
    assert path not in app.openapi()["paths"]
    provider.assert_not_called()
    memory.assert_not_called()
