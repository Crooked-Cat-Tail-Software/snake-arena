# AGENTS.md — Snake Arena

This file orients any AI agent (or human) working in this repository. It
follows the community AGENTS.md convention: plain instructions an agent
should read before making changes.

## What this project is

A small full-stack Snake game built as a class exercise in a **contract-
first, verify-every-step** workflow. See `product-spec.md` for the full
product spec. The short version: the game runs client-side; the backend
only ever receives a final score to persist and serves a leaderboard.

## Repo layout

```
snake-arena/
├── product-spec.md         # Product spec — read this first
├── AGENTS.md                # This file
├── openapi.yaml             # THE contract — source of truth for the API
├── Dockerfile                # Node (builds frontend) + Python (backend, serves it)
├── docker-compose.yml        # Backend + a local Postgres, wired together
├── db-init/                  # Postgres init script (creates the test database)
├── .dockerignore
├── frontend/                 # React (Vite), built with npm — see frontend/package.json
├── backend/                  # Python/FastAPI, Postgres persistence (via SQLAlchemy)
│   └── app/main.py           # Mounts backend/static (built frontend) at "/" if present
├── tests/                    # pytest — backend/API tests + frontend/e2e tests
└── docs/
    └── ai-usage-report.md    # Log of how AI was used across this project
```

## The one hard rule: contract-first

`openapi.yaml` at the repo root is the source of truth for every request
and response shape the frontend and backend exchange. If a change requires
a different endpoint, field, status code, or validation rule:

1. Update `openapi.yaml` first.
2. Update `product-spec.md` if the change affects behavior described there.
3. Only then change backend/frontend code to match.

Never let backend or frontend code drift from `openapi.yaml` silently. The
backend's actual behavior (status codes, response bodies, validation
errors) must match what the contract promises — that's what the contract
tests in `tests/` check.

## Setup & run

Backend needs a Postgres database to talk to. Easiest way — from the repo
root, with Docker installed:
```
docker compose up -d db
```
This starts Postgres on `localhost:5432` with the database/credentials
`backend/app/database.py` already defaults to, and also creates the
separate `snake_arena_test` database the test suite uses (see `db-init/`).
No Postgres install needed. (If something else is already using 5432,
change the host-side port in `docker-compose.yml` and the matching
defaults in `backend/app/database.py` / `tests/conftest.py` /
`tests/frontend/conftest.py`. Don't have Docker? Any Postgres server
works — create a `snake_arena` database and user matching `DATABASE_URL`,
or set `DATABASE_URL` to point at what you already have.)

Then the backend itself (from `backend/`):
```
uv venv
uv pip install -r requirements.txt
uv run uvicorn app.main:app --reload --port 8000
```

Frontend (from `frontend/`) — Node/npm required:
```
npm install
npm run dev
```
Then open the URL Vite prints (`http://localhost:5500` by default — see
`frontend/vite.config.js`). The frontend expects the backend at
`http://localhost:8000` by default; override with `VITE_API_BASE_URL` (see
`frontend/.env.example` and `frontend/src/config.js`) if you're running the
backend somewhere else.

For a production build (what the Dockerfile also runs):
```
npm run build
```
This emits static files to `frontend/dist/`.

## Testing

One-time setup (in addition to `uv pip install -r requirements.txt`):
```
uv pip install -r ../tests/requirements.txt
uv run playwright install chromium
```
Node/npm must also be installed (see "Setup & run" above) — the frontend
e2e tests build the real React app as part of the test run. Postgres must
be running too (`docker compose up -d db` from the repo root, or your own
server) — the tests use its `snake_arena_test` database, reset before
every run, so they never touch the real `snake_arena` database's data.

Then, from `backend/`:
```
uv run pytest ../tests -v
```

Tests should be run — and pass — before any change is considered done.
`tests/` has two kinds:
- `tests/test_*.py` — backend/API tests against an in-process TestClient
  (fast, no browser), run against the real `snake_arena_test` Postgres
  database (reset before each test — see `tests/conftest.py`). Validation
  rules, leaderboard ordering, contract conformance with `openapi.yaml`.
- `tests/frontend/test_frontend.py` — end-to-end tests. `tests/frontend/
  conftest.py` runs a real `npm ci && npm run build` (pointed at a
  throwaway backend port via `VITE_API_BASE_URL` and the same Postgres
  test database, reset before the run), serves the built `dist/`, and
  drives it with a real headless browser (Playwright). These catch things
  the API tests can't: DOM behavior, keyboard handling, screen
  transitions. When you fix a frontend bug found by manual testing, add a
  regression test here (see the existing ones for the pattern) — that's
  what happened for both bugs logged in `docs/ai-usage-report.md`.

## Conventions

- Python: type hints on public functions, formatted with `black`, linted
  with `ruff`. No unnecessary abstraction — this is a small teaching
  project, prefer clarity over cleverness.
- JavaScript: React function components + hooks, built with Vite. The
  game loop (`frontend/src/game.js`, the `SnakeGame` class) and the API
  client (`frontend/src/api.js`) stay plain, framework-agnostic JS in
  their own files, unchanged in shape from the original vanilla
  implementation — React only owns the UI around them (screens, HUD,
  leaderboard list).
- Commits/changes: small, one concern at a time, matching the project's
  stage-by-stage workflow (spec → contract → backend → frontend → tests).
- Every AI-assisted step taken on this project should be reflected in
  `docs/ai-usage-report.md` (what was asked, what was generated, what was
  reviewed/changed by the human).

## Status

- [x] `product-spec.md` — approved
- [x] `openapi.yaml` — approved
- [x] `backend/` — implemented (FastAPI + SQLAlchemy + Postgres), run
      locally end-to-end and verified: health check, score submission +
      validation, leaderboard ordering/limit, and real persistence to
      Postgres. Originally SQLite; switched to Postgres, with
      `docker-compose.yml` added so a local Postgres needs no manual
      install — see `docs/ai-usage-report.md`.
- [x] `frontend/` — React (Vite), HTML5 canvas for the game itself. Built
      with `npm run build` and played start-to-finish in a real headless
      browser (Playwright + Chromium) during verification: game renders,
      keyboard controls work, game ends correctly on collision, score
      submits, leaderboard refreshes. Originally vanilla HTML/CSS/JS,
      converted to React/Vite per the class assignment's Node.js
      requirement — see `docs/ai-usage-report.md`.
- [x] `tests/` — 9 backend tests against `openapi.yaml` + 6 frontend/e2e
      tests (Playwright), 15 total, all passing against the React build
      and a real Postgres database via the real project test
      infrastructure (`pytest tests -v`). Two of the frontend tests are
      regressions for the WASD-in-textbox and name-input-width bugs found
      during manual review of the original vanilla frontend; both
      verified still fixed in the React port.
- [x] `docs/ai-usage-report.md` — living log, updated after each stage
- [x] `README.md` — run/test instructions for the backend and frontend
- [x] `Dockerfile` — builds the frontend for real (Node: `npm ci && npm
      run build`, with `VITE_API_BASE_URL=""` so the production bundle
      calls the API on its own origin) + backend (Python) into one image;
      the backend serves the built frontend itself. Application behavior
      verified by reproducing the image's steps directly; `docker build`
      itself not run in this environment (no Docker Hub access) — run it
      once yourself to confirm.
- [x] `docker-compose.yml` — runs the backend and a Postgres database
      together (`docker compose up --build`); `db-init/` creates the
      separate test database on first startup. Verified by reproducing
      the same environment/credentials with a real local Postgres server
      (health check, score submission, leaderboard, and the full
      `pytest tests -v` suite all passing against it); `docker compose
      up` itself not run in this environment for the same Docker Hub
      reason as the Dockerfile above.
