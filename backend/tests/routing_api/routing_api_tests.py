import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_route_short_trip():
    response = client.get("/get-initial-route", params={"start_lat": 33.710521, "start_lon": -117.763716,
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
    response = client.get("/get-initial-route", params={"start_lat": 33.710521, "start_lon": -117.763716,
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
                                                "end_lat": 40.647306, "end_lon": -74.157289, "num_stops": 0})

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
    response = client.get("/get-initial-route", params={"start_lat": 33.710521, "start_lon": -117.763716,
                                                "end_lat": 33.71847966763839, "end_lon": -117.92881679273557,
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


def test_get_route_three_stops_Portland_WashDC():
    response = client.get("/get-initial-route", params={"start_lat": 45.5202471, "start_lon": -122.674194,
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
    response = client.get("/get-initial-route", params={"start_lat": 33.71855065, "start_lon": -117.92873300964388,
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
    response = client.get("/get-initial-route", params={"start_lat": 33.718567625, "start_lon": -117.92836750000001,
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


def test_get_route_OC_to_NY():
    response = client.get("/get-initial-route", params={"start_lat": 33.7038145, "start_lon": -117.9627349,
                                                "end_lat": 40.7127281, "end_lon": -74.0060152})
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


def test_get_route_SantaMaria_LasVegas():
    response = client.get("/get-initial-route", params={"start_lat": 36.1672559, "start_lon": -115.148516,
                                                "end_lat": 34.9531295, "end_lon": -120.435857,
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


def test_final_route_OC_StLouis():
    response = client.get("/get-initial-route", params={"start_lat": 33.71856688888889, "start_lon": -117.92856555555556,
                                                        "end_lat": 38.6280278, "end_lon": -90.1910154})
    response_data = response.json()
    payload= {
        'initial_route': response_data,
        'num_stops': 1,
        'budget': 400,
    }
    final_response = client.post("/generate-final-route", json=payload)
    final_route = final_response.json()
    assert final_response.status_code == 200
    assert isinstance(final_route["distance"], float) and final_route["duration"] > 0


def test_bodies_of_water_route_Annapolis_CrystalFalls():
    response = client.get("/get-initial-route",
                          params={"start_lat": 38.9786401, "start_lon": -76.492786,
                                  "end_lat": 46.098007, "end_lon": -88.334024})
    response_data = response.json()
    payload = {
        'initial_route': response_data,
        'num_stops': 8,
        'budget': 600,
    }
    final_response = client.post("/generate-final-route", json=payload)
    final_route = final_response.json()
    assert final_response.status_code == 200
    assert isinstance(final_route["distance"], float) and final_route["duration"] > 0

if __name__ == "__main__":
    pytest.main()
