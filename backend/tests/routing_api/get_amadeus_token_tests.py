import os

from app.routers.routing_api import _get_amadeus_token
import pytest
from unittest.mock import patch, Mock
from dotenv import load_dotenv

load_dotenv()

@pytest.mark.asyncio
async def test_get_amadeus_token():
    key = os.getenv('AMADEUS_KEY')
    secret = os.getenv('AMADEUS_SECRET')
    amadeus_token = await _get_amadeus_token(key, secret)
    assert isinstance(amadeus_token, str)

if __name__ == "__main__":
    pytest.main()


