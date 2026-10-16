"""Develop CI cannot authorize a main production deployment."""

import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "deployment_gate", Path(__file__).resolve().parents[2] / "scripts/check_deployment.py"
)
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)
SHA = "a" * 40


def test_develop_workflow_completion_cannot_select_production_revision(monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_run")
    monkeypatch.setenv("GITHUB_REPOSITORY", "elischiffler/RoadtripsAreFun")
    event = {
        "workflow_run": {
            "event": "push",
            "head_branch": "develop",
            "head_sha": SHA,
            "head_repository": {"full_name": "elischiffler/RoadtripsAreFun"},
        }
    }
    with pytest.raises(ValueError, match="main-push"):
        gate.choose_revision(event, SHA)


def test_manual_develop_dispatch_cannot_select_production_revision(monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/develop")
    monkeypatch.setenv("GITHUB_SHA", SHA)
    with pytest.raises(ValueError, match="must run from main"):
        gate.choose_revision({}, SHA)


def test_develop_successes_do_not_satisfy_main_release_checks():
    runs = [
        {
            "id": 1,
            "name": "Backend CI",
            "event": "push",
            "head_branch": "develop",
            "status": "completed",
            "conclusion": "success",
        }
    ]
    assert not gate.checks_ready(runs, ["Backend CI"])
    runs.append({**runs[0], "id": 2, "head_branch": "main"})
    assert gate.checks_ready(runs, ["Backend CI"])


def test_exact_current_main_remains_releasable(monkeypatch):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_REF", "refs/heads/main")
    monkeypatch.setenv("GITHUB_SHA", SHA)
    assert gate.choose_revision({}, SHA) == SHA
    with pytest.raises(ValueError, match="current main"):
        gate.choose_revision({}, "b" * 40)
