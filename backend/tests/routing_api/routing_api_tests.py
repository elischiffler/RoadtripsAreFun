import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Minimal valid Mapbox Directions API response shape
# (must satisfy the MapBox pydantic model)
# ---------------------------------------------------------------------------

def _mapbox_response(start_lon=-117.93, start_lat=33.72, end_lon=-74.16, end_lat=40.65):
    return {
        "code": "Ok",
        "uuid": "test-uuid",
        "waypoints": [
            {"name": "Start", "location": [start_lon, start_lat], "distance": 0},
            {"name": "End",   "location": [end_lon,   end_lat],   "distance": 0},
        ],
        "routes": [
            {
                "weight_name": "auto",
                "weight": 50000.0,
                "duration": 50000.0,
                "distance": 4500000.0,
                "geometry": {
                    "coordinates": [
                        [start_lon, start_lat],
                        [(start_lon + end_lon) / 2, (start_lat + end_lat) / 2],
                        [end_lon, end_lat],
                    ],
                    "type": "LineString",
                },
                "legs": [
                    {
                        "weight": 50000.0,
                        "duration": 50000.0,
                        "distance": 4500000.0,
                        "summary": "",
                        "steps": [
                            {
                                "distance": 4500000.0,
                                "duration": 50000.0,
                                "weight": 50000.0,
                                "mode": "driving",
                                "driving_side": "right",
                                "name": "",
                                "intersections": [],
                                "maneuver": {
                                    "type": "depart",
                                    "instruction": "Drive east",
                                    "bearing_after": 90,
                                    "bearing_before": 0,
                                    "location": [start_lon, start_lat],
                                },
                                "geometry": {
                                    "coordinates": [
                                        [start_lon, start_lat],
                                        [end_lon, end_lat],
                                    ],
                                    "type": "LineString",
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }


def _mock_requests_get(url, **kwargs):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = _mapbox_response()
    return resp


# ---------------------------------------------------------------------------
# GET /get-initial-route
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("params", [
    {"start_lat": 33.710521, "start_lon": -117.763716, "end_lat": 33.71848,  "end_lon": -117.92882},
    {"start_lat": 33.710521, "start_lon": -117.763716, "end_lat": 40.647306, "end_lon": -74.157289},
    {"start_lat": 45.520247, "start_lon": -122.674194, "end_lat": 38.895037, "end_lon": -77.036543},
    {"start_lat": 33.718551, "start_lon": -117.928733, "end_lat": 38.876933, "end_lon": -77.089309},
    {"start_lat": 33.718568, "start_lon": -117.928368, "end_lat": 34.422132, "end_lon": -119.702667},
    {"start_lat": 33.703815, "start_lon": -117.962735, "end_lat": 40.712728, "end_lon": -74.006015},
    {"start_lat": 36.167256, "start_lon": -115.148516, "end_lat": 34.953130, "end_lon": -120.435857},
])
def test_get_initial_route(params):
    """Returns 200 with a valid route shape for any origin/destination pair."""
    with patch("app.routers.routing_api.requests.get", side_effect=_mock_requests_get):
        response = client.get("/get-initial-route", params=params)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["distance"], float)
    assert isinstance(data["duration"], float)
    assert isinstance(data["geometry"]["coordinates"], list)
    assert len(data["geometry"]["coordinates"]) > 0


def test_get_initial_route_returns_steps():
    """Returned route contains at least one step."""
    params = {"start_lat": 33.710521, "start_lon": -117.763716,
              "end_lat": 40.647306, "end_lon": -74.157289}
    with patch("app.routers.routing_api.requests.get", side_effect=_mock_requests_get):
        response = client.get("/get-initial-route", params=params)
    assert response.status_code == 200
    assert len(response.json()["legs"][0]["steps"]) > 0


# ---------------------------------------------------------------------------
# POST /generate-final-route  (0 stops — skips hotel/attraction search)
# ---------------------------------------------------------------------------

def test_generate_final_route_zero_stops():
    """Zero stops, short trip: only Mapbox is called, returns a valid Route."""
    # A short trip (duration < 4hrs) won't trigger hotel search
    short_trip_mapbox = _mapbox_response()
    short_trip_mapbox["routes"][0]["duration"] = 7200.0   # 2 hours
    short_trip_mapbox["routes"][0]["distance"] = 150000.0
    short_trip_mapbox["routes"][0]["legs"][0]["duration"] = 7200.0
    short_trip_mapbox["routes"][0]["legs"][0]["distance"] = 150000.0

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = short_trip_mapbox

    mock_location = MagicMock()
    mock_location.address = "Somewhere, USA"

    with patch("app.routers.routing_api.requests.get", return_value=mock_resp), \
         patch("app.routers.routing_api.get_location", return_value=mock_location):

        init_resp = client.get(
            "/get-initial-route",
            params={"start_lat": 33.7186, "start_lon": -117.9286,
                    "end_lat": 34.0522, "end_lon": -118.2437},
        )
        assert init_resp.status_code == 200

        payload = {
            "initial_route": init_resp.json(),
            "num_stops": 0,
            "budget": 400,
        }
        response = client.post("/generate-final-route", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["distance"], float)
    assert data["duration"] > 0


def test_generate_final_route_invalid_payload():
    """Returns 502 when the payload cannot be validated."""
    response = client.post("/generate-final-route", json={"initial_route": {}, "num_stops": 1, "budget": 200})
    assert response.status_code == 502


if __name__ == "__main__":
    pytest.main()
