import pytest
from fastapi.testclient import TestClient
from app.routers.routing_api import app

client = TestClient(app)


def test_get_route_short_trip():
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
    assert "steps" in response_data
    assert isinstance(response_data["steps"], list)
    assert len(response_data["steps"]) > 0


def test_get_route_LA_to_NY():
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
    assert "steps" in response_data
    assert isinstance(response_data["steps"], list)
    assert len(response_data["steps"]) > 0

def test_get_route_no_stops():
    response = client.get('/get-route', params={"start_lat": 33.710521, "start_lon": -117.763716,
                                                "end_lat": 40.647306, "end_lon": -74.157289,"num_stops": 0 })
    
    assert response.status_code == 200
    response_data = response.json()
    assert "coordinates" in response_data
    assert isinstance(response_data["coordinates"], list)
    assert "distance" in response_data
    assert isinstance(response_data["distance"], float)
    assert "duration" in response_data
    assert isinstance(response_data["duration"], float)
    assert "steps" in response_data
    assert isinstance(response_data["steps"], list)
    assert len(response_data["steps"]) > 0


if __name__ == "__main__":
    pytest.main()