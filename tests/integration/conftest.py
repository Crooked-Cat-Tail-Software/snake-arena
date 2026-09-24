"""Integration tests against the real docker-compose stack.

Unlike tests/ (in-process FastAPI TestClient) and tests/frontend/ (a real
uvicorn + `npm run build`, but no Docker), these tests run
`docker compose build` and `docker compose up` for real and talk to the
resulting containers over the network -- the only place in this project
that actually exercises the Dockerfile's build and docker-compose.yml's
orchestration, rather than reproducing their steps by hand.

Requires Docker Desktop (or another Docker Engine + Compose v2 plugin)
running locally, and needs host ports 8000 and 5432 free (see
docker-compose.yml and README.md if 5432 is already taken by something
else).

WARNING: this suite runs `docker compose down -v` before and after the
session, which deletes the Postgres volume entirely -- don't run it while
you're using the app for real, or you'll lose your leaderboard data. It's
meant to be run on its own:

    uv run pytest ../tests/integration -v

not as part of the regular `pytest ../tests -v` run (see README.md /
AGENTS.md for how the two are kept separate).
"""
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BASE_URL = "http://localhost:8000"

# The first `docker compose build` pulls base images and runs `npm ci` +
# `pip install` from scratch, so it gets a generous timeout; later builds
# are cached and much faster.
BUILD_TIMEOUT = 600
STARTUP_TIMEOUT = 60


def _compose(*args, timeout):
    """Runs `docker compose <args>` from the repo root, capturing output."""
    return subprocess.run(
        ["docker", "compose", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _wait_until_healthy(url: str, timeout: float) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except (urllib.error.URLError, ConnectionError, OSError) as exc:
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"{url} did not become reachable in time: {last_error}")


@pytest.fixture(scope="session")
def docker_build():
    """Runs `docker compose build` once for the whole session.

    Doesn't raise on failure -- test_build_succeeds asserts on the result
    directly, so a broken build shows up as one clear failing test instead
    of an opaque error from every other test in this file.
    """
    return _compose("build", timeout=BUILD_TIMEOUT)


@pytest.fixture(scope="session")
def compose_up(docker_build):
    """Brings up the real stack, only if the build succeeded."""
    if docker_build.returncode != 0:
        pytest.fail(
            "docker compose build failed, can't bring up the stack:\n"
            f"--- stdout ---\n{docker_build.stdout}\n"
            f"--- stderr ---\n{docker_build.stderr}"
        )

    # Defensive: clear out anything left over from a previous run (a
    # crashed test session, a manual `docker compose up` you forgot about)
    # so this always starts from a genuinely empty volume.
    _compose("down", "-v", timeout=60)

    up_result = _compose("up", "-d", timeout=120)
    if up_result.returncode != 0:
        pytest.fail(
            "docker compose up failed:\n"
            f"--- stdout ---\n{up_result.stdout}\n"
            f"--- stderr ---\n{up_result.stderr}"
        )

    try:
        _wait_until_healthy(f"{BASE_URL}/api/health", timeout=STARTUP_TIMEOUT)
    except RuntimeError as exc:
        logs = _compose("logs", timeout=30)
        pytest.fail(f"{exc}\n\n--- docker compose logs ---\n{logs.stdout}\n{logs.stderr}")

    try:
        yield BASE_URL
    finally:
        _compose("down", "-v", timeout=60)
