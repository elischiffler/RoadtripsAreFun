"""Cognito access-token verification with a locally signed, offline JWKS."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

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


def test_rejects_future_issued_at(signed_token):
    with pytest.raises(HTTPException) as error:
        get_user_id_from_token(signed_token(iat=datetime.now(UTC) + timedelta(days=1)))
    assert error.value.status_code == 401


def test_rejects_token_without_key_id(signed_token):
    token = signed_token()
    # The local token body is valid, but a keyless header must never select a key.
    header, body, signature = token.split(".")
    keyless_header = jwt.utils.base64url_encode(b'{"alg":"RS256","typ":"JWT"}').decode()
    with pytest.raises(HTTPException) as error:
        get_user_id_from_token(f"{keyless_header}.{body}.{signature}")
    assert error.value.status_code == 401


def test_rejects_when_jwks_unavailable(signed_token, monkeypatch):
    token = signed_token()
    _jwks_client.cache_clear()

    def unavailable(self):
        raise jwt.PyJWKClientConnectionError("offline fixture")

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", unavailable)
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
    with patch("app.routers.chat_api.get_all_chats") as db_read:
        assert (
            client.get("/chats", headers={"Authorization": "Bearer cognito-user-123"}).status_code
            == 401
        )
        db_read.assert_not_called()
    with patch("app.crud.memory_crud.MemoryCrudStore.load_facts") as memory_read:
        response = client.post(
            "/agent/chat",
            json={"partitionKey": "cognito-user-123", "chatId": "42", "message": "hi"},
        )
        assert response.status_code == 401
        memory_read.assert_not_called()


def test_query_tokens_cannot_authorize_chat_reads_or_deletes(signed_token):
    token = signed_token()
    client = TestClient(app)
    with (
        patch("app.routers.chat_api.get_all_chats") as db_read,
        patch("app.routers.chat_api.delete_chat") as db_delete,
    ):
        assert client.get("/chats", params={"partition_key": token}).status_code == 401
        assert client.delete("/chats/delete/1", params={"partition_key": token}).status_code == 401
        db_read.assert_not_called()
        db_delete.assert_not_called()


def test_two_signed_users_reach_only_their_scoped_chat_segments(signed_token):
    row = {
        "ChatId": "chat-1",
        "ChatData": {"initial": {"geometry": "shared-route", "legs": []}, "route": None},
        "ChatLog": {},
    }
    client = TestClient(app)
    with (
        patch(
            "app.routers.chat_api.get_all_chats", side_effect=lambda user: [deepcopy(row)]
        ) as chats,
        patch(
            "app.routers.chat_api.get_segments",
            side_effect=lambda user_id, chat_id, route_id: (
                [[1, 2]] if user_id == "alice" else [[9, 9]]
            ),
        ) as segments,
        patch("app.routers.chat_api.restore_legs", return_value=[]),
    ):
        alice = client.get(
            "/chats", headers={"Authorization": f"Bearer {signed_token(sub='alice')}"}
        )
        bob = client.get("/chats", headers={"Authorization": f"Bearer {signed_token(sub='bob')}"})

    assert alice.status_code == bob.status_code == 200
    assert alice.json()[0][0]["initial"]["geometry"]["coordinates"] == [[1, 2]]
    assert bob.json()[0][0]["initial"]["geometry"]["coordinates"] == [[9, 9]]
    assert [call.args[0] for call in chats.call_args_list] == ["alice", "bob"]
    assert [call.kwargs["user_id"] for call in segments.call_args_list] == ["alice", "bob"]
