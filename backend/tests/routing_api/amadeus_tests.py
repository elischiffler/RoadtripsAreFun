import os
from datetime import datetime, timedelta

from app.routers.routing_api import _get_amadeus_token, _find_hotel, _get_offers, _get_hotel_ratings
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
async def test_get_hotels_SanDiego():
    lat = 33.319952
    lon = -117.482767
    price_range = (0,200),'0-200'
    check_in = datetime(2024,11,20,0,0,0)
    hotel_info = await _find_hotel(lat, lon, price_range, check_in)
    assert isinstance(hotel_info, dict)

@pytest.mark.asyncio
async def test_get_offers(): # Change once API gets worked out
    hotelIds = ['MCLONGHM']
    key = os.getenv('AMADEUS_KEY')
    secret = os.getenv('AMADEUS_SECRET')
    amadeus_token = await _get_amadeus_token(key, secret)
    price_range = '100-200'
    check_in = datetime(2024, 12, 20, 0, 0, 0)
    check_out = check_in + timedelta(days=1)
    hotel_cost = await _get_offers(amadeus_token, hotelIds, check_in, check_out, price_range)
    assert isinstance(hotel_cost, dict)
    keys = hotel_cost.keys()
    for key in keys:
        assert isinstance(hotel_cost[key], dict)
        assert isinstance(hotel_cost[key]['price'], float)
        assert isinstance(hotel_cost[key]['name'], str)

@pytest.mark.asyncio
async def test_get_hotel_ratings():
    ratings = await _get_hotel_ratings(['MCLONGHM'])
    assert isinstance(ratings, tuple)
    assert isinstance(ratings[0], str)
    assert isinstance(ratings[1], int)

if __name__ == "__main__":
    pytest.main()


