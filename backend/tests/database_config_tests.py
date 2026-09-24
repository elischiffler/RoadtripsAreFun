from unittest.mock import MagicMock

import psycopg2
import pytest

from app.core.config import _database_sslmode, settings
from app.crud import chat_crud


def test_hosted_database_still_requires_tls_by_default(monkeypatch):
    monkeypatch.delenv("DATABASE_SSLMODE", raising=False)
    assert _database_sslmode() == "require"


@pytest.mark.parametrize("mode", ["", "prefer", "allow", "typo"])
def test_invalid_or_opportunistic_tls_modes_fail_explicitly(monkeypatch, mode):
    monkeypatch.setenv("DATABASE_SSLMODE", mode)
    with pytest.raises(ValueError, match="DATABASE_SSLMODE"):
        _database_sslmode()


@pytest.mark.parametrize("mode", ["require", "verify-ca", "verify-full", "disable"])
def test_connection_and_reconnect_use_the_explicit_mode(monkeypatch, mode):
    monkeypatch.setenv("DATABASE_SSLMODE", mode)
    monkeypatch.setattr(settings, "DATABASE_SSLMODE", _database_sslmode())
    monkeypatch.setattr(settings, "DATABASE_URL", " postgres://test:example@postgres/roadtrips ")
    monkeypatch.setattr(chat_crud, "_pool", None)
    pool_factory = MagicMock()
    pool = pool_factory.return_value
    pool.closed = False
    stale = pool.getconn.return_value
    stale.cursor.side_effect = psycopg2.OperationalError("connection lost")
    connect = MagicMock()
    monkeypatch.setattr(chat_crud.psycopg2.pool, "SimpleConnectionPool", pool_factory)
    monkeypatch.setattr(chat_crud.psycopg2, "connect", connect)

    assert chat_crud._get_conn() is connect.return_value
    pool_factory.assert_called_once_with(
        1, 5, "postgres://test:example@postgres/roadtrips", sslmode=mode
    )
    connect.assert_called_once_with("postgres://test:example@postgres/roadtrips", sslmode=mode)
    stale.close.assert_called_once()
