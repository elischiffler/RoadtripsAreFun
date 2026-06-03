import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _mock_location(address: str, lat: float = 34.05, lon: float = -118.24) -> MagicMock:
    loc = MagicMock()
    loc.address = address
    loc.latitude = lat
    loc.longitude = lon
    return loc


# ---------------------------------------------------------------------------
# Happy-path: address lookup
# ---------------------------------------------------------------------------

def test_post_location_by_address():
    """Returns 200 and the geocoded address when given a valid place name."""
    mock_loc = _mock_location(
        "Los Angeles, Los Angeles County, California, United States",
        34.0522, -118.2437,
    )
    with patch("app.routers.location_api.get_location", return_value=mock_loc):
        response = client.post(
            "/validate-location",
            json={"is_coordinates": False, "location": {"address": "Los Angeles"}},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["address"] == "Los Angeles, Los Angeles County, California, United States"
    assert isinstance(data["latitude"], float)
    assert isinstance(data["longitude"], float)


# ---------------------------------------------------------------------------
# Happy-path: coordinate reverse-geocode
# ---------------------------------------------------------------------------

def test_post_location_by_coordinates():
    """Returns 200 and an address when given valid lat/lon coordinates."""
    mock_loc = _mock_location(
        "Mount Lee Drive, Los Angeles, CA 90068, United States",
        34.1338, -118.3217,
    )
    with patch("app.routers.location_api.get_location", return_value=mock_loc):
        response = client.post(
            "/validate-location",
            json={
                "is_coordinates": True,
                "location": {"coordinates": [34.133759465, -118.319665388]},
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert "Mount Lee" in data["address"]
    assert isinstance(data["latitude"], float)


# ---------------------------------------------------------------------------
# 404: geocoder returns None (unrecognised address)
# ---------------------------------------------------------------------------

def test_post_location_not_found():
    """Returns 404 when the geocoder cannot resolve the address."""
    with patch("app.routers.location_api.get_location", return_value=None):
        response = client.post(
            "/validate-location",
            json={"is_coordinates": False, "location": {"address": "Los Angls"}},
        )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 400: malformed payloads (no external call needed)
# ---------------------------------------------------------------------------

def test_post_location_missing_location_key():
    """Returns 400 when the required 'location' key is absent."""
    response = client.post(
        "/validate-location",
        json={"is_coordinates": False},
    )
    assert response.status_code == 400
    assert "Invalid payload" in response.json()["detail"]


def test_post_location_invalid_coordinates_type():
    """Returns 400 when 'coordinates' is given a non-list value."""
    response = client.post(
        "/validate-location",
        json={"is_coordinates": False, "location": {"coordinates": "not a list"}},
    )
    assert response.status_code == 400
    assert "Invalid payload" in response.json()["detail"]


if __name__ == "__main__":
    pytest.main()
