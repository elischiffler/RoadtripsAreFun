import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.main import app

client = TestClient(app)


def test_root_get():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "Hello world"


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:5173"])
def test_dev_frontend_preflight(origin):
    response = client.options(
        "/chats",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_ready_uses_pooler_compatible_statement_timeout(monkeypatch):
    executed = []

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, statement):
            executed.append(statement)

        def fetchone(self):
            return ("chats", "route_segments", "steps", "chat_memory")

    class Connection:
        def cursor(self):
            return Cursor()

        def close(self):
            pass

    def connect(*args, **kwargs):
        assert "options" not in kwargs  # Neon pooled connections reject startup options.
        return Connection()

    monkeypatch.setattr(main.psycopg2, "connect", connect)
    response = client.get("/ready")
    assert response.status_code == 200
    assert executed[0] == "SET statement_timeout = 5000"


if __name__ == "__main__":
    pytest.main()
