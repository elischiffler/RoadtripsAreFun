"""Exercise the CI/container runner without importing the application or networking."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parents[2] / "scripts" / "run_offline_tests.py"

FAKE_PYTEST = """import json
import os
import socket
from pathlib import Path
import dotenv

def main(args):
    blocked = []
    for action in (
        lambda: socket.getaddrinfo("example.invalid", 443),
        lambda: socket.socket().connect(("203.0.113.1", 443)),
    ):
        try:
            action()
        except OSError:
            blocked.append(True)
        else:
            blocked.append(False)
    dotenv_result = dotenv.load_dotenv(Path.cwd() / ".env")
    print(json.dumps({
        "cwd": str(Path.cwd()),
        "args": args,
        "blocked": blocked,
        "ambient_removed": all(name not in os.environ for name in (
            "MENTRO_SERVICE_PASSWORD", "OPENAI_API_KEY", "DATABASE_URL", "PGPASSWORD"
        )),
        "dotenv_disabled": os.environ.get("PYTHON_DOTENV_DISABLED"),
        "dotenv_result": dotenv_result,
        "dotenv_marker": os.environ.get("OFFLINE_RUNNER_MARKER"),
        "catalog_database": os.environ.get("CATALOG_TEST_DATABASE_URL"),
    }))
    return 7
"""


def fixture_layout(tmp_path):
    root = tmp_path / "checkout with spaces"
    script = root / "scripts" / "run_offline_tests.py"
    script.parent.mkdir(parents=True)
    shutil.copyfile(RUNNER, script)
    backend = root / "backend"
    backend.mkdir()
    (backend / "pytest.py").write_text(FAKE_PYTEST)
    (backend / ".env").write_text("OFFLINE_RUNNER_MARKER=must-not-load\n")
    return script, backend


def invoke(script, cwd, *arguments, catalog_database="postgresql://fixture@localhost/catalog_test"):
    env = {
        **os.environ,
        "MENTRO_SERVICE_PASSWORD": "fixture-not-a-secret",
        "OPENAI_API_KEY": "fixture-not-a-secret",
        "DATABASE_URL": "postgresql://fixture@external.invalid/production",
        "PGPASSWORD": "fixture-not-a-secret",
        "CATALOG_TEST_DATABASE_URL": catalog_database,
    }
    env.pop("OFFLINE_RUNNER_MARKER", None)
    return subprocess.run(
        [sys.executable, str(script), *arguments],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def test_default_backend_and_pytest_exit_status_are_preserved(tmp_path):
    script, backend = fixture_layout(tmp_path)
    result = invoke(script, tmp_path, "--cov=app", "--cov-fail-under=63", "-q")
    assert result.returncode == 7, result.stderr
    payload = json.loads(result.stdout)
    assert payload["cwd"] == str(backend)
    assert payload["args"] == ["--cov=app", "--cov-fail-under=63", "-q"]
    assert payload["blocked"] == [True, True]
    assert payload["ambient_removed"]
    assert payload["dotenv_disabled"] == "1"
    assert payload["dotenv_result"] is False
    assert payload["dotenv_marker"] is None
    assert payload["catalog_database"] is None


def test_explicit_backend_directory_supports_container_layout(tmp_path):
    script, _ = fixture_layout(tmp_path)
    backend = tmp_path / "app with spaces"
    backend.mkdir()
    (backend / "pytest.py").write_text(FAKE_PYTEST)
    result = invoke(script, tmp_path, "--backend-dir", str(backend), "-x", "tests/example.py")
    assert result.returncode == 7, result.stderr
    payload = json.loads(result.stdout)
    assert payload["cwd"] == str(backend)
    assert payload["args"] == ["-x", "tests/example.py"]
    assert payload["blocked"] == [True, True]
    assert payload["ambient_removed"]


def test_loopback_opt_in_retains_only_disposable_catalog_target(tmp_path):
    script, _ = fixture_layout(tmp_path)
    target = "postgresql://fixture@127.0.0.1/catalog_test"
    result = invoke(script, tmp_path, "--allow-loopback", catalog_database=target)
    assert result.returncode == 7, result.stderr
    payload = json.loads(result.stdout)
    assert payload["catalog_database"] == target
    assert payload["blocked"] == [True, True]
    assert payload["ambient_removed"]


@pytest.mark.parametrize(
    "target",
    [
        "postgresql://fixture@external.invalid/catalog_test",
        "postgresql://fixture@127.0.0.1/production",
    ],
)
def test_loopback_opt_in_rejects_external_or_non_disposable_targets(tmp_path, target):
    script, _ = fixture_layout(tmp_path)
    result = invoke(script, tmp_path, "--allow-loopback", catalog_database=target)
    assert result.returncode == 1
    assert result.stdout == ""
    assert "only the disposable loopback catalog_test database is allowed" in result.stderr
