from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.routing.sources.hotels import find_hotel as _find_hotel


def _mock_location(address="South Holland, IL, United States", lat=41.583, lon=-87.604):
    loc = MagicMock()
    loc.address = address
    loc.latitude = lat
    loc.longitude = lon
    return loc


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
        patch("app.routing.sources.hotels.get_location", return_value=_mock_location()),
        patch("app.routing.sources.hotels.find_google_hotels", return_value=mock_hotel),
        patch("app.routing.sources.hotels.get_nearby_city", return_value="San Diego"),
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

    with patch("app.routing.sources.hotels.get_location", return_value=None):
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


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [404, 502])
async def test_google_scraper_failure_propagates_without_another_provider(status):
    from fastapi import HTTPException

    with (
        patch("app.routing.sources.hotels.get_location", return_value=_mock_location()),
        patch("app.routing.sources.hotels.get_nearby_city", return_value="San Diego"),
        patch(
            "app.routing.sources.hotels.find_google_hotels",
            side_effect=HTTPException(status_code=status, detail="Google lookup failed"),
        ) as scrape,
    ):
        with pytest.raises(HTTPException) as failure:
            await _find_hotel(33.32, -117.48, ((0, 200), "0-200"), datetime(2026, 11, 20))
    assert failure.value.status_code == status
    assert failure.value.detail == "Google lookup failed"
    scrape.assert_called_once()
