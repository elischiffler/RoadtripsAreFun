import os
from datetime import datetime, timedelta

from app.routers.routing_api import _get_amadeus_token, _find_hotel, _get_offers
import pytest
from dotenv import load_dotenv

load_dotenv()

@pytest.mark.asyncio
async def test_get_amadeus_token():
    key = os.getenv('AMADEUS_KEY')
    secret = os.getenv('AMADEUS_SECRET')
    amadeus_token = await _get_amadeus_token(key, secret)
    print(amadeus_token)
    assert isinstance(amadeus_token, str)

@pytest.mark.asyncio
async def test_get_hotels():
    lat = 33.710521
    lon = -117.763716
    price_range = '100-200'
    check_in = datetime.now()
    hotel_info = await _find_hotel(lat, lon, price_range, check_in)
    assert isinstance(hotel_info, dict)

@pytest.mark.asyncio
async def test_get_offers():
    hotelIds = ['adafas']
    access_token = 'fake'
    price_range = '100-200'
    check_in = datetime.now()
    check_out = check_in + timedelta(days=1)
    hotel_cost = await _get_offers(access_token, hotelIds, check_in, check_out, price_range)
    assert isinstance(hotel_cost, dict)
    assert isinstance(hotel_cost['price'], float)
    assert isinstance(hotel_cost['name'], str)

if __name__ == "__main__":
    pytest.main()


