import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_generate_itinerary():
    response = client.get("/get-route", params={"start_lat": 33.710521, "start_lon": -117.763716,
                                                "end_lat": 40.647306, "end_lon": -74.157289})
    assert response.status_code == 200
    payload = {'route': response.json()
            }
    itinerary = client.post('/generate-itinerary', json=payload)
    print(itinerary.json())
    assert itinerary.status_code == 200

if __name__ == "__main__":
    pytest.main()