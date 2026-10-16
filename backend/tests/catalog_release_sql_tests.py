"""Guarded connector release SQL is exercised against real disposable PostgreSQL."""

import copy

import psycopg2
import pytest

from app.catalog import ingest
from tests.catalog_extraction_tests import load_script
from tests.catalog_ingest_tests import bundle, feature
from tests.catalog_postgres_tests import connection as connection

compiler = load_script("catalog_release_sql")


def digest(connection, generation):
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT md5(jsonb_agg(to_jsonb(p) ORDER BY source_id COLLATE "C")::text) '
            "FROM places_catalog p WHERE generation=%s",
            (generation,),
        )
        result = cursor.fetchone()[0]
    connection.rollback()
    return result


def execute(connection, statements):
    with connection, connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


def active(connection):
    with connection.cursor() as cursor:
        cursor.execute("SELECT generation FROM places_catalog_active")
        result = cursor.fetchone()[0]
    connection.rollback()
    return result


def inputs(tmp_path):
    (tmp_path / "prior").mkdir()
    (tmp_path / "next").mkdir()
    old_path, old_manifest = bundle(tmp_path / "prior", [feature()])
    path, manifest = bundle(
        tmp_path / "next", [feature(), feature(id="new-museum", names={"primary": "New Museum"})]
    )
    baseline, _ = ingest.prepare(old_path, old_manifest)
    rows, _ = ingest.prepare(path, manifest)
    return old_path, old_manifest, baseline, rows, manifest


@pytest.mark.parametrize(
    "violation", ["preserved_fields", "duplicate", "generation", "fingerprint"]
)
def test_compilation_refuses_unsafe_replacement(tmp_path, violation):
    _, _, baseline, rows, manifest = inputs(tmp_path)
    old, fingerprint = "a" * 64, "b" * 32
    if violation == "preserved_fields":
        rows[0] = {**rows[0], "name": "Changed preserved museum"}
    elif violation == "duplicate":
        rows.append(copy.deepcopy(rows[-1]))
    elif violation == "generation":
        old = "injected'; SELECT 1; --"
    else:
        fingerprint = "injected"
    with pytest.raises(ValueError):
        compiler.stage_statements(
            rows, manifest, old=old, old_count=1, old_fingerprint=fingerprint, baseline=baseline
        )


def test_atomic_staging_activation_rollback_and_negative_controls(
    connection, tmp_path, monkeypatch
):
    old_path, old_manifest, baseline, rows, manifest = inputs(tmp_path)
    original = ingest.stage(connection, old_path, old_manifest)["generation"]
    ingest.activate(connection, original)
    old_digest = digest(connection, original)
    generation, statements = compiler.stage_statements(
        rows,
        manifest,
        old=original,
        old_count=1,
        old_fingerprint=old_digest,
        baseline=baseline,
    )
    execute(connection, statements)
    assert active(connection) == original
    assert digest(connection, original) == old_digest
    new_digest = digest(connection, generation)
    execute(connection, statements)
    assert digest(connection, generation) == new_digest
    tampered = statements[:-1] + [statements[-1].replace("New Museum", "Changed Museum")]
    with pytest.raises(psycopg2.Error, match="Immutable catalog content"):
        execute(connection, tampered)
    assert digest(connection, generation) == new_digest
    monkeypatch.setattr(compiler, "MAX_DATABASE_BYTES", 1)
    _, oversized = compiler.stage_statements(
        rows,
        manifest,
        old=original,
        old_count=1,
        old_fingerprint=old_digest,
        baseline=baseline,
    )
    with pytest.raises(psycopg2.Error, match="storage ceiling"):
        execute(connection, oversized)
    assert active(connection) == original
    arguments = {
        "old": original,
        "new": generation,
        "old_count": 1,
        "new_count": 2,
        "old_fingerprint": old_digest,
        "new_fingerprint": new_digest,
    }
    with pytest.raises(psycopg2.Error, match="incomplete or changed"):
        execute(
            connection,
            compiler.cutover_statements(**{**arguments, "new_fingerprint": "0" * 32}),
        )
    assert active(connection) == original
    activation = compiler.cutover_statements(**arguments)
    execute(connection, activation)
    execute(connection, activation)
    assert active(connection) == generation
    with pytest.raises(psycopg2.Error, match="Unexpected active generation"):
        execute(connection, statements)
    rollback = compiler.cutover_statements(**arguments, rollback=True)
    execute(connection, rollback)
    execute(connection, rollback)
    assert active(connection) == original
    assert digest(connection, original) == old_digest
