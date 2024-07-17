from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_root_get():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "Hello world"

# A short trip test
def test_get_route1():
    response = client.get("/get-route?start_lat=33.710521&start_lon=-117.763716&end_lat=33.71847966763839&end_lon=-117.92881679273557")
    print("\n", response.json())
    print("\nThe number of steps for the trip:", len(response.json()['route']))
    assert response.status_code == 200

# A cross country trip
def test_get_route2():
    response = client.get("/get-route?start_lat=33.710521&start_lon=-117.763716&end_lat=40.647306&end_lon=-74.157289")
    print("\nThe number of steps for the trip:", len(response.json()['route']))
    assert response.status_code == 200