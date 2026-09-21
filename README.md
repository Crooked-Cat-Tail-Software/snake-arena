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
- [x] Backend (FastAPI + SQLite), with a passing test suite
- [x] Frontend (React + Vite, HTML5 canvas for the game), played
      end-to-end in a real headless browser as part of verification
- [x] Frontend/end-to-end test suite (Playwright), covering both bugs
      found during manual review as regression tests
- [x] Dockerfile — single container serves both the API and the frontend,
      building the frontend for real with Node/npm

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) for environment/dependency management
- Node.js 20+ and npm, for the frontend (React, built with Vite)

## Run the backend

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

Data persists to `backend/data/snake_arena.db` (SQLite), created
automatically on first run. Delete that file to reset the leaderboard.

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
hand.

Then, from `backend/`:

```bash
uv run pytest ../tests -v
```

All 15 tests should pass:
- **Backend/API tests** (`tests/test_health.py`, `tests/test_scores.py`)
  — exercise the API exactly as documented in `openapi.yaml`: the health
  check; score submission, including validation (blank name, name over
  20 chars, negative score all rejected with 422); and leaderboard
  ordering/limit behavior. Each runs against its own temporary, isolated
  SQLite file.
- **Frontend/end-to-end tests** (`tests/frontend/test_frontend.py`) —
  start a real, temporary copy of the backend (its own throwaway SQLite
  file) and frontend (on free ports, so this never collides with a copy
  you're running by hand) and drive them with a real headless browser:
  typing a name, starting a game, ending it, submitting a score, and
  seeing it appear on the leaderboard. Two of these are regression tests
  for real bugs found during manual review — see
  `docs/ai-usage-report.md` for the story on both.

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

## Run it in Docker (one container, no separate frontend server)

The `Dockerfile` builds the frontend for real (Node: `npm ci && npm run
build`) and the backend into one image; the backend serves the built
frontend itself, so there's only one thing to run and one port to visit.

```bash
docker build -t snake-arena .
docker run --rm -p 8000:8000 -v snake-arena-data:/app/data snake-arena
```

Then open `http://localhost:8000` — that's the game itself, not just the
API. The `-v snake-arena-data:/app/data` volume keeps your SQLite data
across container restarts/rebuilds; drop it if you want a clean
leaderboard every time instead.

Unlike the old vanilla frontend, no code edit is needed if you map to a
different host port (e.g. `-p 9000:8000`): the Dockerfile builds the
frontend with `VITE_API_BASE_URL=""`, so the built app calls the API on
its own origin (same host and port the page was loaded from) instead of
a hardcoded URL — it works at whatever port you map to it.

Note on verification: I confirmed the actual application behavior this
enables (the backend serving the built frontend at `/`, static files, the
API routes, and the absolute-path SQLite URL format) by reproducing those
exact steps directly — installing the same dependencies, running the same
`npm ci && npm run build` the image runs, copying `frontend/dist` into
`backend/static`, and running the same `uvicorn` command the image runs —
and drove it with a real browser end-to-end (play a game, submit a score,
see it on the leaderboard) with no console errors. I was not able to run
`docker build` itself in my sandbox (its network doesn't allow reaching
Docker Hub for the base images), so that exact command is worth running
once yourself before you rely on it — see `docs/ai-usage-report.md` for
the full story.
