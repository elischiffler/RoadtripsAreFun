import pytest
from geopy import Location
from dotenv import load_dotenv
import os
from app.utils.geolocation_helpers import get_location
from geopy.geocoders import OpenCage

load_dotenv()

open_cage_key = os.getenv('OPENCAGE_KEY')

print(open_cage_key)
geocoder= OpenCage(open_cage_key, user_agent='rp-testing')


def test_get_location():
    address = '300 Hogan Blvd, Mill Hall, PA 17751'
    location = get_location(geocoder=geocoder, address=address)
    assert isinstance(location, Location)
    assert isinstance(location.latitude, float) and isinstance(location.longitude, float)
    print(location.address)



if __name__ == "__main__":
    pytest.main()