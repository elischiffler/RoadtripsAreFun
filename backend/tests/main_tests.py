from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_get():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "Hello world"

def test_get_route():
    response = client.get("/get-route?start_lat=33.710521&start_lon=-117.763716&end_lat=33.71847966763839&end_lon=-117.92881679273557")
    print(response.json())
    assert response.status_code == 200

