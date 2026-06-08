import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# A minimal Route payload that satisfies Itinerary_Payload / Route models.
# No external API calls — the itinerary endpoint is pure data transformation.
# ---------------------------------------------------------------------------

MOCK_ROUTE = {
    "coordinates": [
        [33.7186, -117.9286],
        [36.1672, -115.1485],
        [38.6280, -90.1910],
    ],
    "distance": 3200000.0,
    "duration": 120000.0,
    "steps": [],
    "cost": 350.0,
    "geometry": {
        "coordinates": [
            [-117.9286, 33.7186],
            [-115.1485, 36.1672],
            [-90.1910, 38.6280],
        ],
        "type": "LineString",
    },
    "stops": [
        {
            "name": "The Strip, Las Vegas",
            "coordinates": [36.1672, -115.1485],
            "duration": 57600.0,  # 16 hours drive
            "type": "hotel",
            "address": "Las Vegas, NV",
            "price": 120.0,
            "url": None,
        },
        {
            "name": "Arrive at your destination",
            "coordinates": [38.6280, -90.1910],
            "duration": 62400.0,
            "type": "end",
            "address": "St. Louis, MO",
            "price": None,
            "url": None,
        },
    ],
}


def test_generate_itinerary_returns_days():
    """Itinerary endpoint returns a list of days."""
    response = client.post("/generate-itinerary", json={"route": MOCK_ROUTE})
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_generate_itinerary_first_stop_is_depart():
    """First stop of the first day is the departure message."""
    response = client.post("/generate-itinerary", json={"route": MOCK_ROUTE})
    assert response.status_code == 200
    data = response.json()
    assert data[0]["stops"][0]["name"] == "Depart from your starting location"


def test_generate_itinerary_last_stop_is_arrive():
    """Last stop of the last day is the arrival message."""
    response = client.post("/generate-itinerary", json={"route": MOCK_ROUTE})
    assert response.status_code == 200
    data = response.json()
    last_day_stops = data[-1]["stops"]
    last_stop_name = last_day_stops[-1]["name"]
    assert last_stop_name == "Arrive at your destination"


def test_generate_itinerary_each_day_has_date():
    """Every day object contains a non-empty date string."""
    response = client.post("/generate-itinerary", json={"route": MOCK_ROUTE})
    assert response.status_code == 200
    for day in response.json():
        assert isinstance(day["date"], str)
        assert len(day["date"]) > 0


def test_generate_itinerary_invalid_payload():
    """Returns 400 when the route payload is missing required fields."""
    response = client.post("/generate-itinerary", json={"route": {}})
    assert response.status_code == 400


if __name__ == "__main__":
    pytest.main()
