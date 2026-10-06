#!/usr/bin/env python3
"""Require successful main-push CI on the exact current main commit before deploying."""

import json
import os
import re
import time
import urllib.request


def choose_revision(event, main_sha):
    """Accept manual main dispatch or a same-repository main-push workflow completion."""
    if os.environ["GITHUB_EVENT_NAME"] == "workflow_run":
        run = event["workflow_run"]
        if (
            run["event"] != "push"
            or run["head_branch"] != "main"
            or run["head_repository"]["full_name"] != os.environ["GITHUB_REPOSITORY"]
        ):
            raise ValueError(
                "Only same-repository main-push checks can trigger deployment"
            )
        revision = run["head_sha"]
    else:
        if os.environ["GITHUB_REF"] != "refs/heads/main":
            raise ValueError("Manual deployments must run from main")
        revision = os.environ["GITHUB_SHA"]
    if not re.fullmatch(r"[0-9a-f]{40}", revision) or revision != main_sha:
        raise ValueError("Deployment must use the current main commit")
    return revision


def checks_ready(runs, required):
    """Inspect the latest main-push execution of each required workflow."""
    latest = {}
    for run in sorted(runs, key=lambda item: item["id"], reverse=True):
        if run["event"] == "push" and run["head_branch"] == "main":
            latest.setdefault(run["name"], run)
    for name in required:
        run = latest.get(name)
        if run is None or run["status"] != "completed":
            return False
        if run["conclusion"] != "success":
            raise ValueError(f"Required workflow did not pass: {name}")
    return True


def main():
    """Poll GitHub checks, then expose only the validated commit SHA to the deploy job."""
    repository = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GH_TOKEN"]

    def get(path):
        request = urllib.request.Request(
            f"https://api.github.com/repos/{repository}/{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    with open(os.environ["GITHUB_EVENT_PATH"]) as source:
        event = json.load(source)
    required = json.loads(os.environ["CI_WORKFLOWS"])
    revision = choose_revision(event, get("git/ref/heads/main")["object"]["sha"])
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        if get("git/ref/heads/main")["object"]["sha"] != revision:
            raise ValueError("Main advanced; discard this deployment")
        runs = get(
            f"actions/runs?head_sha={revision}&event=push&branch=main&per_page=100"
        )["workflow_runs"]
        runs = [run for run in runs if run["head_sha"] == revision]
        if checks_ready(runs, required):
            with open(os.environ["GITHUB_OUTPUT"], "a") as output:
                output.write(f"revision={revision}\n")
            return
        print("Waiting for required main checks", flush=True)
        time.sleep(20)
    raise TimeoutError("Main checks did not finish within 20 minutes")


if __name__ == "__main__":
    main()
