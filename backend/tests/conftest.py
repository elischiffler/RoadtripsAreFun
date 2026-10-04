"""Shared HTTP auth override for tests focused on route business logic."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.main import app
from app.utils.auth import _jwks_client, require_authenticated_user

POOL = "us-west-1_fixture"
CLIENT = "fixture-client"
ISSUER = f"https://cognito-idp.us-west-1.amazonaws.com/{POOL}"


@pytest.fixture
def allow_provider_auth():
    app.dependency_overrides[require_authenticated_user] = lambda: "fixture-user"
    yield
    app.dependency_overrides.pop(require_authenticated_user, None)


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
