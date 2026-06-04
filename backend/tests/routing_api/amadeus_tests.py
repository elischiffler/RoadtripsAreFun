import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.routers.routing_api import _get_amadeus_token, _find_hotel


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _amadeus_token_response():
    return {
        "type": "amadeusOAuth2Token",
        "username": "test@example.com",
        "application_name": "TestApp",
        "client_id": "test_client_id",
        "token_type": "Bearer",
        "access_token": "test_access_token_abc123",
        "expires_in": 1799,
        "state": "approved",
        "scope": "",
    }


def _mock_location(address="South Holland, IL, United States", lat=41.583, lon=-87.604):
    loc = MagicMock()
    loc.address = address
    loc.latitude = lat
    loc.longitude = lon
    return loc


# ---------------------------------------------------------------------------
# _get_amadeus_token
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_amadeus_token():
    """Returns the access_token string from a mocked Amadeus auth response."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = _amadeus_token_response()

    with patch("app.routers.routing_api.requests.post", return_value=mock_resp):
        token = await _get_amadeus_token("fake_key", "fake_secret")

    assert isinstance(token, str)
    assert token == "test_access_token_abc123"


# ---------------------------------------------------------------------------
# _find_hotel  (via Google Hotels scraping path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_find_hotel_returns_dict():
    """_find_hotel returns a dict with expected keys when scraping succeeds."""
    mock_hotel = {
        "name": "Mock Hotel",
        "coordinates": [33.32, -117.48],
        "address": "123 Main St, San Diego, CA",
        "price": 150.0,
        "stars": 3,
        "review_count": 200,
        "type": "hotel",
    }

    with (
        patch("app.routers.routing_api.get_location", return_value=_mock_location()),
        patch("app.routers.routing_api.find_google_hotels", return_value=mock_hotel),
        patch("app.routers.routing_api._get_nearby_city", return_value="San Diego"),
    ):
        hotel_info = await _find_hotel(
            lat=33.319952,
            lon=-117.482767,
            price_range=((0, 200), "0-200"),
            check_in=datetime(2025, 6, 1, 0, 0, 0),
        )

    assert isinstance(hotel_info, dict)
    assert hotel_info["type"] == "hotel"
    assert "name" in hotel_info
    assert "coordinates" in hotel_info


@pytest.mark.asyncio
async def test_find_hotel_no_location_raises_404():
    """_find_hotel raises HTTPException 404 when geolocation returns None."""
    from fastapi import HTTPException

    with patch("app.routers.routing_api.get_location", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            await _find_hotel(
                lat=0.0,
                lon=0.0,
                price_range=((0, 200), "0-200"),
                check_in=datetime(2025, 6, 1),
            )
    assert exc_info.value.status_code == 404


if __name__ == "__main__":
    pytest.main()
