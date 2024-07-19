import pytest
from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_root_get():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == "Hello world"

def test_get_route():
    response = client.get("/get-route", params={"start_lat": 33.710521, "start_lon": -117.763716,
                                                "end_lat": 33.71847966763839, "end_lon": -117.92881679273557})

    assert response.status_code == 200
    response_data = response.json()
    assert "coordinates" in response_data
    assert isinstance(response_data["coordinates"], list)
    assert "distance" in response_data
    assert isinstance(response_data["distance"], float)
    assert "duration" in response_data
    assert isinstance(response_data["duration"], float)
    assert "route" in response_data
    assert isinstance(response_data["route"], list)
    assert len(response_data["route"]) > 0


# A cross country trip

def test_get_route2():
    response = client.get("/get-route", params={"start_lat": 33.710521, "start_lon": -117.763716,
                                                "end_lat": 40.647306, "end_lon": -74.157289})

    assert response.status_code == 200
    response_data = response.json()
    assert "coordinates" in response_data
    assert isinstance(response_data["coordinates"], list)
    assert "distance" in response_data
    assert isinstance(response_data["distance"], float)
    assert "duration" in response_data
    assert isinstance(response_data["duration"], float)
    assert "route" in response_data
    assert isinstance(response_data["route"], list)
    assert len(response_data["route"]) > 0


if __name__ == "__main__":
    pytest.main()