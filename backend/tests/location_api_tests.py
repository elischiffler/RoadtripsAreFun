import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_location_LosAngeles_address():
    response = client.get("/validate-location", params={"address": "Los Angeles"})

    print(response.text)
    assert response.status_code == 200
    assert response.text == '"Los Angeles, Los Angeles County, California, United States"'

def test_get_location_HollyWood_Sign_coordinates():
    response = client.get("/validate-location", params={ "coordinates": "34.133759465, -118.319665388"})

    assert response.status_code == 200
    assert response.text == '"Mount Lee Drive, Los Feliz Neighborhood Council District, Los Angeles, Los Angeles County, California, 90068, United States"'

def test_get_location_misspell():
    response = client.get("/validate-location", params={"address": "Los Angls"})

    assert response.status_code == 404

def test_get_location_specific_SLO_address():
    address= "692 Canyon Circle, San Luis Obispo, CA, 93405"
    response = client.get("/validate-location", params={"address":address})
    
    assert response.status_code == 200
    assert response.text == '"Canyon Circle, Poly Canyon Village (171), San Luis Obispo County, California, 93407, United States"'


if __name__ == "__main__":
    pytest.main()