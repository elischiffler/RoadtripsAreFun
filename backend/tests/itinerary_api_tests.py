import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_generate_itinerary_LA_NYC():
    response = client.get("/get-route", params={"start_lat": 33.710521, "start_lon": -117.763716,
                                                "end_lat": 40.647306, "end_lon": -74.157289})
    assert response.status_code == 200
    payload = {'route': response.json()
            }
    itinerary = client.post('/generate-itinerary', json=payload)
    assert itinerary.status_code == 200
    data = itinerary.json()
    print(data)
    assert len(data) > 0
    assert data[0]['stops'][0]['name'] == 'Depart from your starting location'
    assert data[-1]['stops'][-1]['name'] == 'Arrive at your destination'

if __name__ == "__main__":
    pytest.main()