import pytest
from unittest.mock import MagicMock
from geopy import Location
from app.utils.geolocation_helpers import get_location


def _mock_location(address: str, lat: float, lon: float) -> MagicMock:
    loc = MagicMock(spec=Location)
    loc.address = address
    loc.latitude = lat
    loc.longitude = lon
    return loc


def test_get_location_by_address():
    """get_location returns a Location when the geocoder resolves an address."""
    geocoder = MagicMock()
    geocoder.geocode.return_value = _mock_location(
        "300 Hogan Blvd, Mill Hall, PA 17751", 41.1234, -77.4567
    )
    location = get_location(geocoder=geocoder, address="300 Hogan Blvd, Mill Hall, PA 17751")
    assert isinstance(location.latitude, float)
    assert isinstance(location.longitude, float)
    geocoder.geocode.assert_called_once()


def test_get_location_by_address_long():
    """get_location works with a verbose address string."""
    geocoder = MagicMock()
    geocoder.geocode.return_value = _mock_location(
        "Thornwood High School, South Holland, IL, United States", 41.5832, -87.6048
    )
    location = get_location(
        geocoder=geocoder,
        address="Thornwood High School, 17101 South Park Avenue, South Holland, IL 60473",
    )
    assert isinstance(location.latitude, float)
    assert isinstance(location.longitude, float)


def test_get_location_by_coordinates():
    """get_location calls reverse() when coords are provided."""
    geocoder = MagicMock()
    geocoder.reverse.return_value = _mock_location(
        "Hollywood Sign, Los Angeles, CA", 34.1341, -118.3217
    )
    location = get_location(geocoder=geocoder, coords=[34.1341, -118.3217])
    assert isinstance(location.latitude, float)
    geocoder.reverse.assert_called_once()


def test_get_location_returns_none():
    """get_location returns None when the geocoder finds nothing."""
    geocoder = MagicMock()
    geocoder.geocode.return_value = None
    location = get_location(geocoder=geocoder, address="xyzzy not a real place")
    assert location is None


if __name__ == "__main__":
    pytest.main()
