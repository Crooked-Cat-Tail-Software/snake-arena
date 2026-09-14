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
- [x] Frontend (vanilla HTML5 canvas + JS), played end-to-end in a real
      headless browser as part of verification
- [x] Frontend/end-to-end test suite (Playwright), covering both bugs
      found during manual review as regression tests

## Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) for environment/dependency management

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

No build step — just serve the static files (opening `index.html`
directly with `file://` won't work because it uses ES modules, which
browsers block over `file://`):

```bash
cd frontend
python3 -m http.server 5500
```

Then open `http://localhost:5500` in a browser, with the backend already
running (see above) at `http://localhost:8000`. Enter a name, press
"Start game", and use the arrow keys or WASD to play. On game over your
score is submitted automatically and the leaderboard refreshes.

If you serve the frontend from a different port, no changes are needed —
the backend allows any localhost origin. If you move the backend to a
different port, update `API_BASE_URL` in `frontend/config.js`.
