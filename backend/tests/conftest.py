"""Shared HTTP auth override for tests focused on route business logic."""

import pytest

from app.main import app
from app.utils.auth import require_authenticated_user


@pytest.fixture
def allow_provider_auth():
    app.dependency_overrides[require_authenticated_user] = lambda: "fixture-user"
    yield
    app.dependency_overrides.pop(require_authenticated_user, None)
