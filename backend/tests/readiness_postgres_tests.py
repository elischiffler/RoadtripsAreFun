"""Actual /ready SQL on the guarded disposable PostgreSQL stack only.

Imports the fixed local settings target guard; no hosted/DATABASE_URL fallback.
Only this test fixture performs bounded DDL/role grants, restored in finally.
Every readiness connection is a real read-only transaction. The endpoint's
schema, privilege and catalog queries are neither replaced nor simulated.
"""

import os
from contextlib import contextmanager
from uuid import uuid4

import psycopg2
import pytest
from fastapi.testclient import TestClient
from psycopg2 import sql

from app import main
from app.crud import chat_crud
from tests.settings_postgres_tests import database as database
from tests.settings_postgres_tests import pytestmark as pytestmark

TABLES = ("trip_shares", "trip_share_members")
PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE")


@pytest.fixture
def readiness(database, monkeypatch):
    conn, _ = database
    url = os.environ["SETTINGS_TEST_DATABASE_URL"]
    connect = psycopg2.connect
    monkeypatch.setattr(main.settings, "DATABASE_URL", url)
    monkeypatch.setattr(main.settings, "DATABASE_SSLMODE", "disable")
    client = TestClient(main.app)

    def probe(role=None):
        opened = []

        def readonly_connection(dsn, **kwargs):
            assert dsn == url
            assert kwargs == {"sslmode": "disable", "connect_timeout": 5}
            candidate = connect(dsn, **kwargs)
            if role:
                # Keep privileged session_user, change effective current_user.
                candidate.autocommit = True
                with candidate.cursor() as cur:
                    cur.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
                candidate.autocommit = False
            candidate.set_session(readonly=True)
            with candidate.cursor() as cur:
                cur.execute(
                    "SELECT current_user, session_user, current_setting('transaction_read_only')"
                )
                current, session, readonly = cur.fetchone()
                assert current == (role or "postgres")
                assert session == "postgres"
                assert readonly == "on"
            opened.append(candidate)
            return candidate

        with monkeypatch.context() as patch:
            patch.setattr(main.psycopg2, "connect", readonly_connection)
            response = client.get("/ready")
        assert len(opened) == 1 and opened[0].closed
        return response

    yield conn, probe
    client.close()


@contextmanager
def app_role(conn):
    role = "readiness_test_" + uuid4().hex
    with conn.cursor() as cur:
        cur.execute(
            sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOINHERIT").format(sql.Identifier(role))
        )
        cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        cur.execute(
            sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(
                sql.Identifier(role)
            )
        )
        for table in TABLES:
            cur.execute(
                sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON {} TO {}").format(
                    sql.Identifier(table), sql.Identifier(role)
                )
            )
    conn.commit()
    try:
        yield role
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role)))
            cur.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)))
        conn.commit()


def assert_unready(response, dependency):
    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "dependency": dependency}


def test_full_schema_effective_application_role_is_ready_without_writes(readiness):
    conn, probe = readiness
    with app_role(conn) as role:
        response = probe(role)
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}


def test_select_only_effective_role_is_not_ready_despite_privileged_session(readiness):
    conn, probe = readiness
    with app_role(conn) as role:
        with conn.cursor() as cur:
            for table in TABLES:
                cur.execute(
                    sql.SQL("REVOKE INSERT, UPDATE, DELETE ON {} FROM {}").format(
                        sql.Identifier(table), sql.Identifier(role)
                    )
                )
        conn.commit()
        assert_unready(probe(role), "sharing_permissions")


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("privilege", PRIVILEGES)
def test_each_sharing_privilege_is_individually_required(readiness, table, privilege):
    conn, probe = readiness
    with app_role(conn) as role:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("REVOKE {} ON {} FROM {}").format(
                    sql.SQL(privilege), sql.Identifier(table), sql.Identifier(role)
                )
            )
        conn.commit()
        assert_unready(probe(role), "sharing_permissions")


@contextmanager
def changed_schema(conn, table, defect):
    column = "created_at" if table == "trip_shares" else "connected_at"
    if defect == "absent":
        change = sql.SQL("ALTER TABLE {} RENAME TO {}").format(
            sql.Identifier(table), sql.Identifier(table + "_readiness_hidden")
        )
        restore = sql.SQL("ALTER TABLE {} RENAME TO {}").format(
            sql.Identifier(table + "_readiness_hidden"), sql.Identifier(table)
        )
    elif defect == "missing_column":
        change = sql.SQL("ALTER TABLE {} RENAME COLUMN {} TO readiness_hidden_column").format(
            sql.Identifier(table), sql.Identifier(column)
        )
        restore = sql.SQL("ALTER TABLE {} RENAME COLUMN readiness_hidden_column TO {}").format(
            sql.Identifier(table), sql.Identifier(column)
        )
    else:
        assert defect == "wrong_type"
        change = sql.SQL(
            "ALTER TABLE {} ALTER COLUMN {} DROP DEFAULT, ALTER COLUMN {} TYPE text USING {}::text"
        ).format(
            sql.Identifier(table),
            sql.Identifier(column),
            sql.Identifier(column),
            sql.Identifier(column),
        )
        restore = sql.SQL(
            "ALTER TABLE {} ALTER COLUMN {} TYPE timestamptz USING {}::timestamptz, ALTER COLUMN {} SET DEFAULT now()"
        ).format(
            sql.Identifier(table),
            sql.Identifier(column),
            sql.Identifier(column),
            sql.Identifier(column),
        )
    with conn.cursor() as cur:
        cur.execute(change)
    conn.commit()
    try:
        yield
    finally:
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(restore)
        conn.commit()


@pytest.mark.parametrize("table", TABLES)
@pytest.mark.parametrize("defect", ("absent", "missing_column", "wrong_type"))
def test_missing_or_malformed_sharing_schema_fails_closed(readiness, table, defect):
    conn, probe = readiness
    with changed_schema(conn, table, defect):
        assert_unready(probe(), "sharing_schema")
    assert probe().status_code == 200


def test_owned_trip_crud_remains_independent_of_absent_sharing(readiness, database):
    conn, probe = readiness
    _, prefix = database
    owner = prefix + "-readiness-owner"
    with (
        changed_schema(conn, "trip_shares", "absent"),
        changed_schema(conn, "trip_share_members", "absent"),
    ):
        assert_unready(probe(), "sharing_schema")
        data = {"chatId": 1, "agentChatId": None, "title": "Original"}
        chat_crud.create_chat(owner, "1", data, {"messages": []})
        assert chat_crud.get_chat(owner, "1")["chat_data"] == data
        assert chat_crud.get_chat(owner + "-other", "1") is None
        data = {**data, "title": "Updated"}
        chat_crud.create_chat(owner, "1", data, {"messages": []})
        assert chat_crud.get_chat(owner, "1")["chat_data"] == data
        assert chat_crud.delete_chat(owner, "1")
        assert chat_crud.get_chat(owner, "1") is None
    assert probe().status_code == 200
