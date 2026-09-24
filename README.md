# Snake Arena

A small full-stack Snake game built as a class exercise practicing a
contract-first, verify-every-step AI-assisted workflow: spec → contract →
backend → frontend → tests, with a human review checkpoint after each.

- Product spec: [product-spec.md](product-spec.md)
- API contract: [openapi.yaml](openapi.yaml)
- Agent/dev instructions: [AGENTS.md](AGENTS.md)
- How AI was used at each step: [docs/ai-usage-report.md](docs/ai-usage-report.md)

## Status

- [x] Product spec
- [x] API contract (`openapi.yaml`)
- [x] Backend (FastAPI + Postgres), with a passing test suite
- [x] Frontend (React + Vite, HTML5 canvas for the game), played
      end-to-end in a real headless browser as part of verification
- [x] Frontend/end-to-end test suite (Playwright), covering both bugs
      found during manual review as regression tests
- [x] Dockerfile — single container serves both the API and the frontend,
      building the frontend for real with Node/npm
- [x] docker-compose.yml — runs that container together with a local
      Postgres database, no separate install needed

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) for environment/dependency management
- Node.js 20+ and npm, for the frontend (React, built with Vite)
- A Postgres database — easiest via Docker (see below), or any Postgres
  server you already have

## Run the backend

The backend needs a Postgres database to talk to. If you have Docker, the
easiest way is to start just the database from `docker-compose.yml` (from
the repo root):

```bash
docker compose up -d db
```

This starts Postgres on `localhost:5432` with the database and
credentials `backend/app/database.py` already defaults to — no further
setup needed. (If something else on your machine is already using 5432,
change the host-side port in `docker-compose.yml` and the matching
defaults in `backend/app/database.py` / `tests/conftest.py` /
`tests/frontend/conftest.py` to a free port instead. No Docker? Point the
`DATABASE_URL` environment variable at any Postgres server instead, e.g.
`postgresql://user:password@host:5432/dbname`.)

Then the backend itself:

```bash
cd backend
uv venv
uv pip install -r requirements.txt
uv run uvicorn app.main:app --reload --port 8000
```

The API is now at `http://localhost:8000`. Interactive docs (auto-generated
by FastAPI from the same routes) are at `http://localhost:8000/docs`.

Quick check:

```bash
curl http://localhost:8000/api/health
# {"status":"ok"}
```

Data persists in Postgres. If you're running it via `docker compose`, the
data survives container restarts (it's in a named volume) — use
`docker compose down -v` if you want a clean leaderboard instead.

## Run the tests

There are two kinds of tests in `tests/`: backend/API tests (fast, no
browser needed) and frontend/end-to-end tests (drive a real browser
against a real, temporarily-running copy of the app). Both run with one
`pytest` command.

One-time setup, in addition to the backend install above:

```bash
cd backend
uv pip install -r ../tests/requirements.txt
uv run playwright install chromium
```

(`playwright install chromium` downloads a browser for the tests to
drive — a few hundred MB, one-time, only needed for the frontend tests.)
Node/npm (see Requirements above) must also be installed — the frontend
tests build the real app as part of the test run (`npm ci && npm run
build`), the same build the Dockerfile and `npm run build` produce by
hand. Postgres must also be reachable — `docker compose up -d db` (see
"Run the backend" above) also creates the separate `snake_arena_test`
database the tests use, so they never touch your real `snake_arena`
leaderboard.

Then, from `backend/`:

```bash
uv run pytest ../tests -v
```

All 15 tests should pass:
- **Backend/API tests** (`tests/test_health.py`, `tests/test_scores.py`)
  — exercise the API exactly as documented in `openapi.yaml`: the health
  check; score submission, including validation (blank name, name over
  20 chars, negative score all rejected with 422); and leaderboard
  ordering/limit behavior. Each test resets the `snake_arena_test`
  Postgres database to empty first, so tests never see each other's data.
- **Frontend/end-to-end tests** (`tests/frontend/test_frontend.py`) —
  start a real, temporary copy of the backend (pointed at that same,
  freshly-reset Postgres test database) and frontend (on free ports, so
  this never collides with a copy you're running by hand) and drive them
  with a real headless browser: typing a name, starting a game, ending
  it, submitting a score, and seeing it appear on the leaderboard. Two of
  these are regression tests for real bugs found during manual review —
  see `docs/ai-usage-report.md` for the story on both.

## Run the frontend

Install dependencies once, then start Vite's dev server:

```bash
cd frontend
npm install
npm run dev
```

Then open the URL Vite prints (`http://localhost:5500` by default), with
the backend already running (see above) at `http://localhost:8000`. Enter
a name, press "Start game", and use the arrow keys or WASD to play. On
game over your score is submitted automatically and the leaderboard
refreshes.

If you serve the frontend from a different port, no changes are needed —
the backend allows any localhost origin. If you move the backend to a
different port, set `VITE_API_BASE_URL` (see `frontend/.env.example`) to
match before starting `npm run dev`, instead of editing code.

For a production build (static files, no dev server) — this is what the
Dockerfile also runs:

```bash
npm run build
```

This writes to `frontend/dist/`, which you can serve with any static file
server.

## Run it in Docker (backend + Postgres, one command)

The `Dockerfile` builds the frontend for real (Node: `npm ci && npm run
build`) and the backend into one image; the backend serves the built
frontend itself. `docker-compose.yml` runs that image together with a
Postgres database, so there's one command for the whole app:

```bash
docker compose up --build
```

Then open `http://localhost:8000` — that's the game itself, not just the
API. Postgres data persists in a named volume across restarts; run
`docker compose down -v` if you want a clean leaderboard instead.

If you only want the database (e.g. to run the backend or the tests
directly on your machine against a real Postgres, as in the sections
above), start just that service:

```bash
docker compose up -d db
```

No code edit is needed if you map the backend to a different host port
in `docker-compose.yml` (e.g. `"9000:8000"`): it's built with
`VITE_API_BASE_URL=""`, so the app calls the API on its own origin
(whatever host/port the page was loaded from) instead of a hardcoded URL.

You can still build and run the backend image on its own without Compose
(`docker build -t snake-arena .`), but you'd need to pass your own
`DATABASE_URL` pointing at a reachable Postgres — the image has no
database of its own anymore, unlike the old SQLite version.

Note on verification: I confirmed the actual application behavior this
enables (the backend serving the built frontend at `/`, static files, the
API routes, and the Postgres connection) by reproducing those exact steps
directly — installing the same dependencies, running the same `npm ci &&
npm run build` the image runs, copying `frontend/dist` into
`backend/static`, running the same `uvicorn` command the image runs, and
pointing it at a real local Postgres server using the exact credentials
and database name `docker-compose.yml` sets up — then drove it with a
real browser end-to-end (play a game, submit a score, see it on the
leaderboard) with no console errors, and ran the full `pytest tests -v`
suite (15/15) against that same Postgres server. I was not able to run
`docker build` or `docker compose up` themselves in my sandbox (its
network doesn't allow reaching Docker Hub for the base images), so those
exact commands are worth running once yourself before you rely on them —
see `docs/ai-usage-report.md` for the full story.
