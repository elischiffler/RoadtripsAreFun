"""Real offline Cognito verification on every Studio and research HTTP boundary."""

from copy import deepcopy
from uuid import uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.routers import algorithm_lab as lab
from app.routers import studio, studio_research
from app.routing.selection import OWNER_EMAIL
from tests.conftest import CLIENT


def _app():
    app = FastAPI()
    app.include_router(studio.router)
    app.include_router(studio_research.router)
    assert not app.dependency_overrides
    return app


def _headers(signed_token, **identity_changes):
    return {
        "Authorization": f"Bearer {signed_token()}",
        "X-Cognito-Id-Token": signed_token(
            **{
                "token_use": "id",
                "aud": CLIENT,
                "email": OWNER_EMAIL,
                "email_verified": True,
                **identity_changes,
            }
        ),
    }


def _requests(app):
    identifier = str(uuid4())
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/studio"):
            continue
        path = route.path
        for parameter in route.param_convertors:
            path = path.replace("{" + parameter + "}", identifier)
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            yield method, path


def test_every_studio_route_declares_verified_owner_guard():
    app = _app()
    routes = [route for route in app.routes if isinstance(route, APIRoute)]
    assert len(routes) >= 20
    for route in routes:
        assert any(
            dependency.call is lab.require_lab_owner for dependency in route.dependant.dependencies
        ), route.path


def test_missing_access_token_rejected_on_all_studio_and_capability_routes(monkeypatch):
    app = _app()
    monkeypatch.setattr(
        studio_research, "reap_workers", lambda: pytest.fail("unauthorized capability work")
    )
    client = TestClient(app)
    for method, path in _requests(app):
        response = client.request(
            method,
            path,
            json={},
            headers={
                "X-Studio-Session": "old-visitor-session",
                "X-Studio-Batch-Key": "saved-capability",
            },
        )
        assert response.status_code == 401, (method, path, response.text)


@pytest.mark.parametrize(
    "kind",
    [
        "non-owner",
        "unverified-email",
        "mismatched-subject",
        "missing-identity",
        "forged-email",
        "wrong-identity-use",
    ],
)
def test_nonowner_or_unverified_identity_cannot_reach_any_studio_resource(
    signed_token, monkeypatch, kind
):
    app = _app()
    headers = _headers(signed_token)
    if kind == "non-owner":
        headers = _headers(signed_token, email="another-person@example.test")
    elif kind == "unverified-email":
        headers = _headers(signed_token, email_verified=False)
    elif kind == "mismatched-subject":
        headers = _headers(signed_token, sub="a-different-subject")
    elif kind == "missing-identity":
        headers.pop("X-Cognito-Id-Token")
    elif kind == "forged-email":
        # Alter the signed non-owner payload without re-signing it. A decoded
        # email or a local frontend capability must never grant API access.
        token = _headers(signed_token, email="another-person@example.test")["X-Cognito-Id-Token"]
        header, payload, signature = token.split(".")
        claims = jwt.api_jwt.decode_complete(token, options={"verify_signature": False})["payload"]
        claims["email"] = OWNER_EMAIL
        import json

        payload = jwt.utils.base64url_encode(json.dumps(claims).encode()).decode()
        headers["X-Cognito-Id-Token"] = f"{header}.{payload}.{signature}"
    elif kind == "wrong-identity-use":
        headers["X-Cognito-Id-Token"] = signed_token()
    headers.update(
        {"X-Studio-Session": "old-visitor-session", "X-Studio-Batch-Key": "saved-capability"}
    )
    monkeypatch.setattr(
        studio_research, "reap_workers", lambda: pytest.fail("unauthorized capability work")
    )
    client = TestClient(app)
    for method, path in _requests(app):
        response = client.request(method, path, json={}, headers=headers)
        assert response.status_code == 403, (kind, method, path, response.text)


def test_owner_identity_requires_a_valid_access_token(signed_token):
    headers = _headers(signed_token)
    headers["Authorization"] = "Bearer malformed"
    response = TestClient(_app()).get("/studio/research/catalog", headers=headers)
    assert response.status_code == 401


def test_verified_owner_can_access_catalog_and_issue_separate_scoped_sessions(
    signed_token, monkeypatch
):
    app = _app()
    client = TestClient(app)
    headers = _headers(signed_token)
    catalog = client.get("/studio/research/catalog", headers=headers)
    assert catalog.status_code == 200
    assert catalog.headers["cache-control"] == "no-store"
    first = client.post("/studio/access", json={"password": "cp-sat"}, headers=headers)
    second = client.post("/studio/access", json={"password": "cp-sat"}, headers=headers)
    assert first.status_code == second.status_code == 200
    first_token = first.json()["token"]
    second_token = second.json()["token"]
    assert studio.require_studio_session(first_token) != studio.require_studio_session(second_token)
    assert client.get("/studio/presets", headers=headers).status_code == 401
    assert (
        client.get(
            "/studio/presets", headers=headers | {"X-Studio-Session": first_token}
        ).status_code
        == 200
    )
    seen = []
    monkeypatch.setattr(lab.lab_runs, "history", lambda owner, *args: seen.append(owner) or [])
    assert (
        client.get("/studio/runs", headers=headers | {"X-Studio-Session": first_token}).status_code
        == 200
    )
    assert seen == [studio.require_studio_session(first_token)]


def test_verified_owner_still_needs_per_study_capability(signed_token, monkeypatch):
    app = _app()
    client = TestClient(app)
    identifier = str(uuid4())
    headers = _headers(signed_token)
    study = {
        "id": identifier,
        "state": "paused",
        "created_at": "fixture-time",
        "identity": {},
        "plan": {"counts": {}, "design": {}, "variants": [], "dataset_hash": "fixture"},
    }
    monkeypatch.setattr(studio_research, "reap_workers", lambda: None)
    seen = []

    def authorized(study_id, key):
        seen.append((study_id, key))
        if key != "retained-key":
            from fastapi import HTTPException

            raise HTTPException(404, "Study not found")
        return deepcopy(study)

    monkeypatch.setattr(studio_research.store, "study", authorized)
    monkeypatch.setattr(studio_research.store, "changes", lambda *args: ([], {}, 0))
    path = f"/studio/research/batches/{identifier}"
    assert client.get(path, headers=headers).status_code == 404
    assert (
        client.get(path, headers=headers | {"X-Studio-Batch-Key": "retained-key"}).status_code
        == 200
    )
    assert seen == [(identifier, None), (identifier, "retained-key")]
