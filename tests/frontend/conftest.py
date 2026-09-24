"""Spins up a real backend + frontend for the frontend/e2e tests.

This is deliberately NOT the same `client` fixture used by the backend
API tests (tests/conftest.py), which drives the app in-process via
FastAPI's TestClient. Playwright needs an actual running server to point
a real browser at, so this starts real `uvicorn` and
`python -m http.server` processes as subprocesses.

The frontend is a Vite/React app (frontend/), not static files we can
copy and text-patch, so this fixture runs the real `npm ci && npm run
build` -- with VITE_API_BASE_URL pointed at this session's backend port
-- and serves the resulting dist/ folder. That means this suite exercises
the same build a real `npm run build` or `docker build` produces, not a
stand-in for it. Requires Node/npm to be installed (see README.md).

Isolated from anything you might be running yourself by using its own
free ports (chosen dynamically, not 8000/5500). The backend it starts
points at the same Postgres test database tests/conftest.py uses
(snake_arena_test by default -- see TEST_DATABASE_URL there and in this
file), reset to empty right before this backend starts, so this suite
never touches your real snake_arena database or its leaderboard.
"""
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from sqlalchemy import create_engine

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"

sys.path.insert(0, str(BACKEND_DIR))
from app.database import Base  # noqa: E402

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://snake_arena:snake_arena@localhost:5432/snake_arena_test",
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_up(url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except (urllib.error.URLError, ConnectionError, OSError) as exc:
            last_error = exc
            time.sleep(0.2)
    raise RuntimeError(f"{url} did not become reachable in time: {last_error}")


def _npm_install_command() -> list[str]:
    # `npm ci` needs an existing lockfile and is the reproducible choice;
    # fall back to `npm install` if someone runs this before one exists.
    if (FRONTEND_DIR / "package-lock.json").exists():
        return ["npm", "ci"]
    return ["npm", "install"]


@pytest.fixture(scope="session")
def app_urls():
    backend_port = _free_port()
    frontend_port = _free_port()

    # Start this suite from an empty database, the same way a fresh
    # SQLite temp file used to -- see module docstring.
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    engine.dispose()

    # --- real backend, pointed at the Postgres test database above ---
    env = os.environ.copy()
    env["DATABASE_URL"] = TEST_DATABASE_URL
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(backend_port)],
        cwd=BACKEND_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # --- a real production build of the frontend, pointed at that
    # backend's port via a build-time env var (see frontend/src/config.js
    # and frontend/.env.example) ---
    build_env = os.environ.copy()
    build_env["VITE_API_BASE_URL"] = f"http://localhost:{backend_port}"
    dist_dir = FRONTEND_DIR / "dist"
    try:
        subprocess.run(
            _npm_install_command(),
            cwd=FRONTEND_DIR,
            env=build_env,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["npm", "run", "build"],
            cwd=FRONTEND_DIR,
            env=build_env,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        backend_proc.terminate()
        raise RuntimeError(
            f"frontend build failed ({' '.join(exc.cmd)}):\n{exc.stdout}\n{exc.stderr}"
        ) from exc

    if not dist_dir.is_dir():
        backend_proc.terminate()
        raise RuntimeError(f"expected build output at {dist_dir}, but it doesn't exist")

    frontend_proc = subprocess.Popen(
        [sys.executable, "-m", "http.server", str(frontend_port)],
        cwd=dist_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    try:
        _wait_until_up(f"http://localhost:{backend_port}/api/health")
        _wait_until_up(f"http://localhost:{frontend_port}/index.html")
        yield {
            "frontend": f"http://localhost:{frontend_port}",
            "backend": f"http://localhost:{backend_port}",
        }
    finally:
        backend_proc.terminate()
        frontend_proc.terminate()
        try:
            backend_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend_proc.kill()
        try:
            frontend_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            frontend_proc.kill()
        # dist/ is a build artifact (frontend/.gitignore excludes it) --
        # clean it up so repeated test runs always rebuild fresh.
        shutil.rmtree(dist_dir, ignore_errors=True)


@pytest.fixture()
def game_page(page, app_urls):
    """A fresh page loaded against the isolated test instance."""
    page.goto(f"{app_urls['frontend']}/index.html")
    page.wait_for_selector("#player-name")
    return page
