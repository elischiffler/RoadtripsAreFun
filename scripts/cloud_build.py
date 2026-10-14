#!/usr/bin/env python3
"""Build locked dependencies offline when nested Docker cannot use workspace egress.

Prerequisite caches are populated on the workspace with normal certificate
verification. A temporary Dockerfile changes only dependency installation; the
committed runtime Dockerfiles, security settings and application code are retained.
"""

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def normalized_context(destination):
    """Copy Git-visible build inputs; never follow symlinks or copy ignored files."""
    entries = (
        subprocess.check_output(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
        )
        .decode()
        .split("\0")
    )
    executable = set()
    for entry in (
        subprocess.check_output(["git", "ls-files", "-s", "-z"], cwd=ROOT).decode().split("\0")
    ):
        if entry.startswith("100755 "):
            executable.add(entry.split("\t", 1)[1])
    for name in set(entries) - {""}:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Invalid Git build path")
        if any(part.startswith(".env") for part in relative.parts):
            continue
        source = ROOT / relative
        if any(
            (ROOT / Path(*relative.parts[:i])).is_symlink()
            for i in range(1, len(relative.parts) + 1)
        ):
            continue
        if not source.is_file():
            continue  # tracked files deleted in the worktree
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        target.chmod(0o755 if name in executable else 0o644)
    for directory in destination.rglob("*"):
        if directory.is_dir():
            directory.chmod(0o755)
    destination.chmod(0o755)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=("backend-test", "backend-runtime", "web"))
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--docker-config", type=Path, required=True)
    parser.add_argument("--revision", default="local-cloud-test")
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    args.docker_config.mkdir(parents=True, exist_ok=True)
    backend = args.target.startswith("backend")
    source = ROOT / ("backend/Dockerfile" if backend else "frontend/Dockerfile")
    text = source.read_text()
    if backend:
        original = "RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt"
        replacement = "RUN --mount=type=bind,from=clouddeps,target=/clouddeps python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir --no-index --find-links=/clouddeps -r requirements.txt"
        if not list(args.cache.glob("*.whl")):
            parser.error("backend cache must contain downloaded Python 3.12 Linux wheels")
    else:
        original = "RUN npm ci --no-audit --no-fund"
        replacement = "RUN --mount=type=bind,from=clouddeps,target=/clouddeps,rw npm ci --offline --cache /clouddeps --no-audit --no-fund"
        if not (args.cache / "_cacache").is_dir():
            parser.error("web cache must contain an npm _cacache directory")
    if text.count(original) != 1:
        parser.error("Dockerfile install command changed; review offline adaptation")
    artifacts = ROOT / ".artifacts"
    artifacts.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cloud-build-", dir=artifacts) as temporary:
        context = Path(temporary) / "context"
        context.mkdir()
        normalized_context(context)
        dockerfile = Path(temporary) / "Dockerfile"
        dockerfile.write_text(text.replace(original, replacement))
        command = [
            "docker",
            "build",
            "--network",
            "none",
            "--build-context",
            f"clouddeps={args.cache.resolve()}",
            "--build-arg",
            f"VCS_REF={args.revision}",
            "-f",
            str(dockerfile),
            "-t",
            args.tag,
        ]
        if backend:
            command.extend(["--target", "test" if args.target == "backend-test" else "runtime"])
        else:
            command.extend(["--build-arg", "VITE_BACKEND_SERVER=http://127.0.0.1:8002/"])
        command.append(str(context))
        subprocess.run(
            command,
            check=True,
            env={**os.environ, "DOCKER_CONFIG": str(args.docker_config.resolve())},
        )


if __name__ == "__main__":
    main()
