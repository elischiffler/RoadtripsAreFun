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
from app.routing.selection import OWNER_EMAIL, owner_routing_claims
from app.utils.auth import _jwks_client, get_user_id_from_token
from tests.conftest import CLIENT, ISSUER


def test_valid_locally_signed_access_token(signed_token):
    assert get_user_id_from_token(signed_token()) == "cognito-user-123"


def test_verified_owner_capability(signed_token, monkeypatch):
    monkeypatch.setenv("ROUTING_ALGORITHM", "unregistered-environment-choice")
    response = TestClient(app).get(
        "/routing-settings",
        headers={
            "Authorization": f"Bearer {signed_token()}",
            "X-Cognito-Id-Token": signed_token(
                token_use="id", aud=CLIENT, email=OWNER_EMAIL, email_verified=True
            ),
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "can_select_algorithm": True,
        "algorithms": ["cp_sat"],
        "default": "cp_sat",
        "expires_at": response.json()["expires_at"],
    }
    assert isinstance(response.json()["expires_at"], int)
    assert response.headers["cache-control"] == "no-store"
    assert OWNER_EMAIL not in response.text


@pytest.mark.parametrize(
    "overrides",
    [
        {"email_verified": False},
        {"email_verified": "true"},
        {"email": "someone@example.test"},
        {"sub": "another-user"},
        {"aud": "another-client"},
        {"iss": "https://evil.example/pool"},
        {"token_use": "access"},
        {"exp": datetime(2000, 1, 1, tzinfo=UTC)},
        {"iat": datetime.now(UTC) + timedelta(days=1)},
    ],
)
def test_identity_evidence_fails_closed_without_breaking_access(signed_token, overrides):
    claims = {"token_use": "id", "aud": CLIENT, "email": OWNER_EMAIL, "email_verified": True}
    claims.update(overrides)
    response = TestClient(app).get(
        "/routing-settings",
        headers={
            "Authorization": f"Bearer {signed_token()}",
            "X-Cognito-Id-Token": signed_token(**claims),
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "can_select_algorithm": False,
        "algorithms": [],
        "default": "cp_sat",
        "expires_at": None,
    }


@pytest.mark.parametrize(
    "omit", ["exp", "iat", "iss", "sub", "aud", "token_use", "email", "email_verified"]
)
def test_incomplete_identity_cannot_grant_selection(signed_token, omit):
    token = signed_token(
        omit=(omit,), token_use="id", aud=CLIENT, email=OWNER_EMAIL, email_verified=True
    )
    assert owner_routing_claims("cognito-user-123", token) is None


def test_missing_forged_and_unavailable_identity(signed_token, monkeypatch):
    token = signed_token(token_use="id", aud=CLIENT, email=OWNER_EMAIL, email_verified=True)
    header, payload, signature = token.split(".")
    tampered = f"{header}.{payload}.{('A' if signature[0] != 'A' else 'B') + signature[1:]}"
    forged = jwt.encode(
        {"email": OWNER_EMAIL, "email_verified": True},
        "untrusted-fixture-secret-32-bytes-long",
        algorithm="HS256",
        headers={"kid": "local-fixture"},
    )
    for evidence in (None, "malformed", tampered, forged):
        assert owner_routing_claims("cognito-user-123", evidence) is None
    _jwks_client.cache_clear()

    def unavailable(self):
        raise jwt.PyJWKClientConnectionError("offline fixture")

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", unavailable)
    assert owner_routing_claims("cognito-user-123", token) is None


def test_capability_requires_valid_access_even_with_owner_identity(signed_token):
    identity = signed_token(token_use="id", aud=CLIENT, email=OWNER_EMAIL, email_verified=True)
    for access in (None, "malformed", signed_token(exp=datetime(2000, 1, 1, tzinfo=UTC))):
        headers = {"X-Cognito-Id-Token": identity}
        if access:
            headers["Authorization"] = f"Bearer {access}"
        assert TestClient(app).get("/routing-settings", headers=headers).status_code == 401


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
