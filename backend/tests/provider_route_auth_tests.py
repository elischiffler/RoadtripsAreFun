"""Public API routes reject anonymous requests before any provider work."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_public_static_routes_remain_public():
    assert client.get("/health").status_code == 200
    assert client.get("/algorithms").status_code == 200


def test_provider_routes_reject_missing_token():
    requests = [
        ("get", "/get-initial-route"),
        ("post", "/generate-final-route"),
        ("post", "/validate-location"),
        ("post", "/generate-itinerary"),
        ("get", "/get-car-details"),
        ("get", "/get-gas-price"),
        ("get", "/benchmark"),
    ]
    for method, path in requests:
        response = getattr(client, method)(path)
        assert response.status_code == 401, (method, path, response.text)


def test_provider_routes_reject_invalid_token(monkeypatch):
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "us-west-1_fixture")
    monkeypatch.setenv("COGNITO_APP_CLIENT_ID", "fixture-client")
    response = client.get("/get-initial-route", headers={"Authorization": "Bearer invalid-token"})
    assert response.status_code == 401


def test_authenticated_request_reaches_business_validation(monkeypatch):
    monkeypatch.setattr("app.utils.auth.get_user_id_from_token", lambda token: "fixture-user")
    response = client.post(
        "/generate-itinerary", headers={"Authorization": "Bearer signed-fixture"}, json={}
    )
    assert response.status_code == 400
