import pytest
from fastapi.testclient import TestClient
from app.main import app

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

def test_get_route_one_stop():
    response = client.get("/get-route", params={"start_lat": 33.710521, "start_lon": -117.763716,
                                                "end_lat": 33.71847966763839, "end_lon": -117.92881679273557, "num_stops": 1})

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

def test_get_route_three_stops_Portland_WashDC():
    response = client.get("/get-route", params={"start_lat": 45.5202471, "start_lon": -122.674194,
                                                "end_lat": 38.8950368, "end_lon": -77.0365427,
                                                "num_stops": 3})

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

def test_get_route_three_stops_LA_Arlington():
    response = client.get("/get-route", params={"start_lat": 33.71855065, "start_lon": -117.92873300964388,
                                                "end_lat": 38.8769326, "end_lon": -77.0893094,
                                                "num_stops": 3})

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

def test_get_route_one_stop_day_trip():
    response = client.get("/get-route", params={"start_lat": 33.718567625, "start_lon": -117.92836750000001,
                                                "end_lat": 34.4221319, "end_lon": -119.702667,
                                                "num_stops": 1})
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