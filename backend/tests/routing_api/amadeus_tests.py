import os
from app.routers.routing_api import _get_amadeus_token, _find_hotel
import pytest
from dotenv import load_dotenv

load_dotenv()

@pytest.mark.asyncio
async def test_get_amadeus_token():
    key = os.getenv('AMADEUS_KEY')
    secret = os.getenv('AMADEUS_SECRET')
    amadeus_token = await _get_amadeus_token(key, secret)
    assert isinstance(amadeus_token, str)

@pytest.mark.asyncio
async def test_get_hotels():
    lat = 33.710521
    lon = -117.763716
    hotel_coords = await _find_hotel(lat, lon)
    assert isinstance(hotel_coords, list)

if __name__ == "__main__":
    pytest.main()


