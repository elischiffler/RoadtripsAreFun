"""Cognito access-token verification with a locally signed, offline JWKS."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.utils.auth import _jwks_client, get_user_id_from_token

POOL = "us-west-1_fixture"
CLIENT = "fixture-client"
ISSUER = f"https://cognito-idp.us-west-1.amazonaws.com/{POOL}"


@pytest.fixture
def signed_token(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    public_jwk.update({"kid": "local-fixture", "use": "sig", "alg": "RS256"})
    monkeypatch.setenv("COGNITO_USER_POOL_ID", POOL)
    monkeypatch.setenv("COGNITO_APP_CLIENT_ID", CLIENT)
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda self: {"keys": [public_jwk]})
    _jwks_client.cache_clear()

    def sign(*, omit=(), **overrides):
        now = datetime.now(UTC)
        claims = {
            "iss": ISSUER,
            "sub": "cognito-user-123",
            "client_id": CLIENT,
            "token_use": "access",
            "iat": now,
            "exp": now + timedelta(minutes=10),
        }
        claims.update(overrides)
        for claim in omit:
            claims.pop(claim)
        return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "local-fixture"})

    yield sign
    _jwks_client.cache_clear()


def test_valid_locally_signed_access_token(signed_token):
    assert get_user_id_from_token(signed_token()) == "cognito-user-123"


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "https://evil.example/pool"},
        {"client_id": "another-client"},
        {"token_use": "id"},
        {"exp": datetime(2000, 1, 1, tzinfo=UTC)},
        {"sub": ""},
    ],
)
def test_rejects_invalid_claims(signed_token, claims):
    with pytest.raises(HTTPException) as error:
        get_user_id_from_token(signed_token(**claims))
    assert error.value.status_code == 401


@pytest.mark.parametrize("claim", ["exp", "iat", "iss", "sub", "client_id", "token_use"])
def test_rejects_missing_required_claim(signed_token, claim):
    with pytest.raises(HTTPException) as error:
        get_user_id_from_token(signed_token(omit=(claim,)))
    assert error.value.status_code == 401


def test_rejects_hs256_algorithm(signed_token):
    token = jwt.encode(
        {"sub": "cognito-user-123"},
        "untrusted-fixture-secret-32-bytes-long",
        algorithm="HS256",
        headers={"kid": "local-fixture"},
    )
    with pytest.raises(HTTPException) as error:
        get_user_id_from_token(token)
    assert error.value.status_code == 401


def test_rejects_tampered_signature_and_raw_user_id(signed_token):
    valid = signed_token()
    header, payload, signature = valid.split(".")
    tampered = f"{header}.{payload}.{('A' if signature[0] != 'A' else 'B') + signature[1:]}"
    for token in (tampered, "cognito-user-123"):
        with pytest.raises(HTTPException) as error:
            get_user_id_from_token(token)
        assert error.value.status_code == 401


def test_rejects_token_signed_by_unknown_key(signed_token):
    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = jwt.encode(
        {
            "iss": ISSUER,
            "sub": "cognito-user-123",
            "client_id": CLIENT,
            "token_use": "access",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=10),
        },
        other_key,
        algorithm="RS256",
        headers={"kid": "local-fixture"},
    )
    with pytest.raises(HTTPException) as error:
        get_user_id_from_token(token)
    assert error.value.status_code == 401


def test_rejects_without_configuration(signed_token, monkeypatch):
    monkeypatch.delenv("COGNITO_USER_POOL_ID")
    with pytest.raises(HTTPException) as error:
        get_user_id_from_token(signed_token())
    assert error.value.status_code == 503


def test_unverified_token_cannot_reach_chat_or_agent(signed_token):
    client = TestClient(app)
    assert client.get("/chats", params={"partition_key": "cognito-user-123"}).status_code == 401
    response = client.post(
        "/agent/chat", json={"partitionKey": "cognito-user-123", "chatId": "42", "message": "hi"}
    )
    assert response.status_code == 401
