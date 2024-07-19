import pytest
from fastapi.testclient import TestClient
from app.routers.routing_api import app

client = TestClient(app)


def test_root_get():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "Hello world"

if __name__ == "__main__":
    pytest.main()