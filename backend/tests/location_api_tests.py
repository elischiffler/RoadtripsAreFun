import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_post_location_LosAngeles_address():
    payload = {"is_coordinates": False,
                "location": {
                    "address": "Los Angeles",
                }
                }

    response = client.post("/validate-location", json=payload)

    print(response.text)
    assert response.status_code == 200
    assert response.text == '"Los Angeles, Los Angeles County, California, United States"'

def test_post_location_HollyWood_Sign_coordinates():
    payload = {"is_coordinates": True,
              "location":{
              "coordinates": [34.133759465, -118.319665388]
              }}
    response = client.post("/validate-location", json=payload)

    assert response.status_code == 200
    assert response.text == '"Mount Lee Drive, Los Feliz Neighborhood Council District, Los Angeles, Los Angeles County, California, 90068, United States"'

def test_post_location_misspell():
    payload= {"is_coordinates": False,
              "location":{
                  "address": "Los Angls"
              }}
    response = client.post("/validate-location", json=payload)

    assert response.status_code == 404

def test_post_location_specific_SLO_address():
    address= "692 Canyon Circle, San Luis Obispo, CA, 93405"
    payload = {"is_coordinates": False,
               "location":{
                   "address":address
               }}
    response = client.post("/validate-location", json=payload)
    
    assert response.status_code == 200
    assert response.text == '"Canyon Circle, Poly Canyon Village (171), San Luis Obispo County, California, 93407, United States"'

def test_post_location_with_invalid_payload():
    payload = {"is_coordinates": False,}
    response = client.post("/validate-location", json=payload)
    assert response.status_code == 400
    assert "Invalid payload" in response.json()["detail"]

def test_post_location_with_invalid_location():
    payload = {"is_coordinates": False, "location":{"coordinates":"Not coordinate tuple"}}
    response = client.post("/validate-location", json=payload)
    assert response.status_code == 400
    assert "Invalid payload" in response.json()["detail"]

if __name__ == "__main__":
    pytest.main()