# AI Usage Report — Snake Arena

A running log of how AI (Claude) was used on this project, and what was
human-reviewed at each stage. Updated after each stage completes, not
reconstructed afterward.

## Stage 1 — Product spec

**Asked for:** a product spec for a class exercise: a Snake game with a
frontend and backend split by a defined API contract, data persisted in
SQLite, following a controlled, stage-by-stage workflow.

**AI produced:** `product-spec.md` — goals/non-goals, user stories,
gameplay rules, data model, API surface summary, architecture diagram,
tech stack choice (Python/FastAPI backend, vanilla JS/canvas frontend,
pytest), and a definition-of-done checklist. Left three open questions
for human decision (arena size/tick speed, leaderboard size, whether to
add a personal-best indicator).

**Human review:** confirmed fixed defaults (20x20 grid, 120ms tick) and a
leaderboard capped at 10; declined the personal-best indicator (out of
scope for v1). Spec approved as `product-spec.md`.

## Stage 2 — Repo layout & API contract

**Asked for:** deliverables to be organized as `product-spec.md`,
`AGENTS.md`, `frontend/`, `backend/`, `openapi.yaml`, `tests/`, and
`docs/ai-usage-report.md`, per the class's required structure.

**AI produced:** reorganized the spec and moved the contract to
repository-root paths; wrote `openapi.yaml` (OpenAPI 3.0.3) matching the
approved spec exactly — three endpoints (`GET /api/health`,
`POST /api/scores`, `GET /api/scores`), `ScoreCreate`/`Score` schemas with
the same validation rules as the spec; wrote `AGENTS.md` documenting the
contract-first rule (contract changes before code changes), setup/run/test
commands, and conventions.

**Human review:** approved both `openapi.yaml` and `AGENTS.md` as
written, no changes requested.

## Stage 3 — Backend, database, and its own tests

**Asked for:** the backend, with the app running locally per the README,
data persisted in SQLite, and its own test suite passing.

**AI produced:**
- `backend/app/` — FastAPI app (`main.py`), SQLAlchemy models/session
  (`models.py`, `database.py`), Pydantic schemas mirroring `openapi.yaml`
  exactly (`schemas.py`), and query logic (`crud.py`), backed by a SQLite
  file at `backend/data/snake_arena.db`.
- `tests/` — 9 pytest tests covering the health check, score validation
  (blank/over-length name, negative score all rejected with 422),
  successful submission, and leaderboard ordering/limit behavior. Each
  test runs against its own isolated temp SQLite file via a FastAPI
  dependency override, not the real data file.
- `README.md` — setup/run/test instructions for the backend.

**Verification actually performed (not just claimed):**
- Ran `uv venv` + `uv pip install -r requirements.txt` + `uv run pytest
  ../tests -v` — all 9 tests passed.
- Separately started the real server with `uvicorn` and drove it with
  `curl`: health check, two score submissions, leaderboard retrieval (in
  correct descending order), and a negative-score submission confirmed
  rejected with HTTP 422.
- Confirmed persistence directly against the SQLite file on disk (queried
  `backend/data/snake_arena.db` with `sqlite3`/Python after stopping the
  server) — the submitted rows were actually there, not just returned by
  the API in-memory.
- Cleared that demo database afterward so the delivered repo starts with
  an empty leaderboard.

**Human review:** approved ("looks good").

## Stage 4 — Frontend

**Asked for:** the frontend, per the approved spec and contract.

**AI produced:** `frontend/` — vanilla HTML5 `<canvas>` game
(`game.js`: grid, movement, collision, food, fixed 120ms tick, no
framework), an API client matching `openapi.yaml` exactly (`api.js`), a
config file for the backend URL (`config.js`), DOM wiring for the
start/playing/game-over screens and the leaderboard (`app.js`), and
markup/styling (`index.html`, `style.css`).

**Verification actually performed:** rather than only reading the code
back, a full copy of the built backend + frontend was run in an isolated
sandbox and driven with a real (headless) Chromium browser via
Playwright:
- Loaded the page, confirmed the empty-leaderboard message shows on a
  clean database.
- Entered a name, started the game, confirmed the start screen hides and
  the canvas/game appear.
- Sent keyboard input (arrow keys) and confirmed the snake responds and
  the canvas renders the snake and food as expected (screenshotted).
- Drove the snake into a wall to end the game deterministically, and
  confirmed: the game-over screen appears with the correct final score,
  the score is submitted to the backend automatically, the UI shows
  "Score saved," and the leaderboard panel refreshes and shows the new
  entry — all matching what a person clicking through it would see.
- Checked the browser console/network log for errors during the whole
  run. One was found — a 404 for `/favicon.ico` (the browser's automatic
  icon request, not anything the app does) — and fixed by adding an
  empty icon link in `index.html`, rather than left in "known harmless
  noise" since a clean console is cheap to have.
- Not verified in this automated pass: an actual eating-food scoring
  event (the scripted movement pattern didn't happen to cross the food's
  random spawn point in the time budgeted for the test). The eating/
  growth/scoring logic itself is a short, deterministic block in
  `game.js` and is easy to eyeball-review; playing the game by hand
  confirms it directly.

**Human review:** two real bugs surfaced during review (see the two
follow-up entries below); once both were fixed and re-verified, the user
confirmed it working.

## Stage 4 follow-up — name input width bug

**Reported:** the name text box only appeared to allow ~4 characters.

**Investigated:** `maxlength` on `#player-name` was already `20`, matching
the approved contract's 1–20 character range — so nothing was actually
capping input at 4 characters. The real bug was CSS: `.panel` had no
width of its own (sized by shrink-to-fit) while the input inside it was
`width: 100%`, a combination some browsers (this looked like a Safari-
style rendering, not reproducible in the Chromium used for automated
testing) size far too narrow, visually cutting off most of what's typed.

**Fixed:** added `min-width: 320px` to `.panel` in `style.css` so the
input has a reliable amount of room regardless of the browser's shrink-
to-fit quirks — a real fix, not a workaround, and it does not touch the
already-approved 20-character limit.

**Verified:** re-tested at two viewport widths (1000px and 480px) in a
headless browser; the input renders ~400-440px wide in both, comfortably
fits a 15-character test string with no truncation or overflow, and nothing
else in the layout broke.

## Stage 4 follow-up #2 — WASD keys blocked in the name field (real bug)

**Reported:** typing "Donn" then "a" (to spell "Donna") wouldn't add the
"a" — the field appeared stuck at 4 characters. Not reproducible with an
initial automated re-test, which pointed at autofill; the user checked
(Chrome, no dropdown appears) and that ruled it out.

**Root cause found:** `app.js`'s keyboard handler was attached to the
whole document and intercepted W/A/S/D and the arrow keys unconditionally
— including while the user was typing in the name field, not just during
gameplay. "Donna" contains a lowercase "a", one of the movement keys, so
that keystroke was captured for "move left" and never reached the text
box. Any name containing w, a, s, or d would hit this the same way.

(Why my first re-test missed it: the way that test simulated typing
didn't dispatch the same per-key keyboard events a real keypress does, so
it never exercised the buggy code path. Re-tested properly with actual
key-by-key input, which reproduced it immediately.)

**Fixed:** the handler now checks `e.target` and skips handling
game-movement keys when focus is on an INPUT/TEXTAREA/contenteditable
element, so typing in any form field is never intercepted for gameplay.

**Verified on the user's own machine**, not just in an isolated sandbox:
used Claude's browser pane to load `http://localhost:5500` for real,
confirmed the bug's existence with genuine key-by-key input first
("d o n n a" produced "onn" — the leading "d" and trailing "a" were both
swallowed), then, after the fix (loaded via a cache-bypassed URL to
guarantee the updated file was actually running, not a stale cached
copy), the same key sequence produced "donna" correctly. Also confirmed
WASD still steers the snake normally once a game is in progress — the
fix only suppresses movement keys while a form field has focus.

**Aside:** during this test the leaderboard showed "failed to fetch" —
that's just the backend not running at that moment, not related to this
bug.

**Human review:** confirmed working ("That worked.") on her own machine
with both servers running.

## Stage 5 — Frontend/end-to-end test suite

**Asked for:** frontend tests, since the two bugs found during manual
review (the keyboard/WASD one especially) were exactly the kind that a
backend-only test suite would never catch.

**AI produced:** `tests/frontend/` — a Playwright-based end-to-end suite
(`conftest.py` starts a real, temporary backend + frontend on free ports
with their own throwaway SQLite file, isolated from anything you're
running by hand; `test_frontend.py` has 6 tests) plus `tests/requirements.txt`
for the extra test-only dependencies (`playwright`, `pytest-playwright`).
Two of the six are direct regression tests for the bugs found earlier:
- `test_name_field_accepts_movement_key_letters` — types "wasd" into the
  name field and asserts it all lands, guarding against the keyboard
  handler ever hijacking those keys from a text field again.
- `test_name_input_has_enough_room_to_type_in` — asserts the name input
  renders at least 250px wide, guarding against the shrink-to-fit CSS
  bug recurring.
The other four cover things not tested anywhere else: the empty-name
guard, the start-screen-to-game transition, a full game (start → wall
collision → score submitted → appears on the leaderboard), and "play
again" returning to the start screen.

**Verification actually performed:**
- Ran the full suite (all 15 tests: 9 backend + 6 frontend) in an
  isolated sandbox — all passed.
- To make sure the two regression tests actually test something (rather
  than passing vacuously), temporarily reverted the WASD fix in a scratch
  copy of `app.js` and re-ran `test_name_field_accepts_movement_key_letters`
  on its own: it failed exactly as expected (empty field instead of
  "wasd"), then re-ran the full suite again after restoring the fix — all
  15 passed again. This confirms the regression test would actually
  catch this bug if it were ever reintroduced.
- Note: installing the Playwright browser requires an internet download
  (`playwright install chromium`, one-time, documented in README.md and
  AGENTS.md) — this is a normal step on a real machine with normal
  internet access.

**Human review:** approved ("looks good").

## Stage 6 — Dockerfile (Node build stage + Python backend serving the frontend)

**Asked for:** a Dockerfile that builds the frontend with Node, then
builds a Python image containing the backend and the frontend's static
files, with the backend serving the frontend.

**Clarified first:** the frontend has no build tooling (no
`package.json`, no bundler) — nothing for a Node stage to actually
compile. Asked how to handle that rather than guessing; the choice made
was a no-op Node stage (just stages the files through, ready for a real
build step later without other changes).

**AI produced:**
- `Dockerfile` — a two-stage build. Stage 1 (`node:20-alpine`) stages
  `frontend/` unchanged (commented with what a real `npm run build` step
  would look like, for later). Stage 2 (`python:3.11-slim`) installs
  backend dependencies, copies the backend app code, copies the staged
  frontend from stage 1 into `backend/static`, creates a data directory,
  sets `DATABASE_URL` to an absolute-path SQLite URL, declares a volume
  at `/app/data` for persistence, and runs `uvicorn` on port 8000.
- `.dockerignore` — keeps dev-only artifacts (`.venv`, `__pycache__`,
  `tests/`, `docs/`, the real `backend/data/`) out of the build context.
- `backend/app/main.py` — added a static-files mount: if `backend/static`
  exists, it's mounted at `"/"` (after the `/api/*` routes are declared,
  so they still take priority) so the backend serves the game itself, not
  only JSON. Guarded on the directory existing, so local dev (where that
  directory never exists) is completely unaffected — the separate
  frontend/backend dev servers documented in README.md still work exactly
  as before.
- `README.md` / `AGENTS.md` — added `docker build`/`docker run`
  instructions, and a note that changing the published host port requires
  updating `frontend/config.js` (it calls an absolute URL, not a relative
  one, so it must match wherever the container is actually reached).

**Verification actually performed, and its real limit:**
- Could not run `docker build` itself in this environment — its network
  doesn't allow reaching Docker Hub to pull the `node`/`python` base
  images (confirmed via the proxy explicitly rejecting the connection,
  not just a timeout).
- To verify the part that actually carries risk — the application code,
  not the Dockerfile's copy/install steps — reproduced the image's
  effective steps directly: installed `backend/requirements.txt` into a
  fresh venv, copied `frontend/` to `backend/static` (what
  `COPY --from=frontend` does), set `DATABASE_URL` to the same
  absolute-path SQLite URL format the image sets, and ran the same
  `uvicorn app.main:app --host 0.0.0.0 --port 8000` command the image
  runs.
- Confirmed via curl: `/` serves `index.html`, `/app.js` and `/style.css`
  serve with correct content types (not swallowed by the API routes),
  `/api/health`, `/api/scores` (POST and GET) all still work correctly
  from the same server.
- Confirmed via a real headless browser: loaded `http://localhost:8000/`
  (the single combined origin), played a full game, submitted a score,
  saw it appear on the leaderboard, and checked for console errors —
  none. This is the actual end-to-end behavior "backend serves frontend"
  promises, verified for real, just not through `docker build` itself.
- What's NOT verified: the Dockerfile's own build mechanics (does it
  build cleanly, are the base images/layer order sensible, does the
  final image run correctly as a container). This needs `docker build -t
  snake-arena .` run once on a machine with normal internet access —
  worth doing before considering this deliverable done.

**Human review:** approved ("looks good").

## Stage 7 — Convert the frontend to React

**Asked for:** convert the frontend to React, because the class assignment
requires Node.js (the request noted vanilla HTML/JS is cleaner, but the
assignment's requirement takes priority).

**AI produced:**
- `frontend/` rebuilt as a React app scaffolded with Vite:
  `package.json`/`package-lock.json`, `vite.config.js`, `index.html`,
  `.env.example`, `.gitignore` (`node_modules/`, `dist/`, `.env*`).
- `frontend/src/game.js` — the `SnakeGame` class carried over **unchanged**
  from the vanilla version. It was already a plain, framework-agnostic
  class operating on a canvas element via callbacks, so nothing about the
  actual game logic (movement, collision, scoring) needed to change.
- `frontend/src/api.js` — the API client, ported with no behavior changes.
- `frontend/src/config.js` — `API_BASE_URL` now reads
  `import.meta.env.VITE_API_BASE_URL` (Vite's build-time env var
  mechanism) with the same `http://localhost:8000` default as before, so
  local dev is unchanged; see `.env.example` for how to override it.
- `frontend/src/App.jsx` plus `components/StartScreen.jsx`,
  `GameOverScreen.jsx`, `Leaderboard.jsx` — React function components with
  hooks (`useState`/`useEffect`/`useRef`/`useCallback`) replacing the old
  imperative DOM-manipulation code in `app.js`. All existing element ids
  and classes (`#player-name`, `#start-button`, `#game-canvas`,
  `#leaderboard-list`, etc.) were kept exactly, so the existing
  `style.css` and the existing frontend test suite needed no changes.
  Both previously-fixed bugs were carried forward deliberately: the CSS
  width fix (unchanged `style.css`) and the WASD-in-textbox guard, now a
  check inside the `keydown` `useEffect` (`if target is INPUT/TEXTAREA/
  contentEditable, return before treating the key as a movement key`).
- `Dockerfile` — the Node stage is now a real build instead of a no-op:
  `npm ci` (using the checked-in lockfile), then `npm run build` with
  `VITE_API_BASE_URL=""` so the production bundle calls the API on its
  own origin (relative URLs) rather than a hardcoded host — this also
  removes the old caveat that changing the container's published port
  required editing a source file. The backend stage now copies
  `frontend/dist` (the build output) into `backend/static`, instead of
  the raw `frontend/` directory.
- `tests/frontend/conftest.py` — rewritten so the `app_urls` fixture runs
  the real `npm ci && npm run build` (pointed at that test session's
  throwaway backend port via `VITE_API_BASE_URL`) and serves the built
  `dist/` directory, instead of copying static files and text-patching a
  `config.js`. `tests/frontend/test_frontend.py` itself needed **no
  changes** — same ids, same behavior.
- `product-spec.md`, `AGENTS.md`, `README.md` — tech stack, repo layout,
  setup/run/test instructions, and the Docker port-change note all
  updated for React/Vite/Node (see those files' git history for exact
  diffs); Node.js added as a project requirement alongside Python/uv.

**Verification actually performed:**
- `npm install` (19 packages, 0 vulnerabilities) and `npm run build`
  completed cleanly, producing a small production bundle (~225KB JS,
  ~1.4KB CSS).
- Ran the pre-existing vanilla-frontend Playwright playtest script
  against the React build with **no changes to the script itself**: full
  game start-to-finish, score submission, leaderboard update, zero
  console errors, zero failed network requests. Same result running the
  full stack through the backend's static-file mount (the same
  same-origin, `VITE_API_BASE_URL=""` setup Docker uses) rather than a
  separate dev server.
- Specifically re-checked both previously-fixed bugs against the React
  port with real, key-by-key Playwright input (not the less realistic
  batch `type()` action): the name input measured 439px wide (well over
  the 250px regression threshold), and typing "donna" character-by-
  character produced the correct value with no character loss.
- Ran the actual project test suite unmodified — `pytest tests -v` — and
  got **15/15 passing**: the 9 backend tests untouched by this change,
  plus all 6 frontend/e2e tests now running against the real React build
  via the rewritten `conftest.py`.
- Same limitation as Stage 6: `docker build` itself was not run in this
  environment (no Docker Hub access), so the Dockerfile's own build
  mechanics are unverified here — worth running once on a machine with
  normal internet access. Everything the Dockerfile's Node stage actually
  does (`npm ci && npm run build` with that exact env var, then serving
  the result from the backend) was verified by reproducing those steps
  directly, as in Stage 6.

**Human review:** approved implicitly — no changes requested to the React
conversion itself; the next request (Postgres, Stage 8 below) builds
directly on top of it.

## Stage 8 — Add Postgres support to the backend

**Asked for:** add Postgres support to the backend. Clarified scope
before touching code (three questions, since each changes what gets
built): (1) replace SQLite entirely or support both — answer: **replace
entirely**; (2) add a docker-compose.yml to run Postgres automatically —
answer: **yes**; (3) should the automated test suite also run against
Postgres, or stay on SQLite for speed — answer: **also run tests against
Postgres**.

**AI produced:**
- `backend/app/database.py` — rewritten. Default `DATABASE_URL` is now a
  Postgres URL (`postgresql://snake_arena:snake_arena@localhost:5432/
  snake_arena`, matching what `docker-compose.yml` sets up) instead of a
  SQLite file path; removed the SQLite-only `connect_args`. No other
  backend file needed changes — `models.py`, `schemas.py`, `crud.py`, and
  the health check in `main.py` were already plain SQLAlchemy/Pydantic
  with nothing SQLite-specific in them.
- `backend/requirements.txt` — added `psycopg2-binary` (the Postgres
  driver SQLAlchemy needs).
- `backend/.gitignore` — removed the now-meaningless `data/*.db` line.
- `docker-compose.yml` (new, repo root) — a `db` service (`postgres:16-
  alpine`, named volume for persistence, a healthcheck so the backend
  waits for it to actually be ready) and a `backend` service (built from
  the existing `Dockerfile`, `depends_on: db: condition: service_healthy`,
  `DATABASE_URL` pointed at the `db` service). `docker compose up --build`
  is the one-command way to run the whole app; `docker compose up -d db`
  starts just the database, for running the backend or the tests directly
  against a real Postgres without installing it yourself.
- `db-init/001-create-test-db.sql` (new) — runs automatically the first
  time the `db` service's volume is created, creating a second
  `snake_arena_test` database alongside the main `snake_arena` one, so
  the automated test suite has its own database and never touches real
  app data.
- `Dockerfile` — removed the SQLite-only `ENV DATABASE_URL=sqlite:///...`,
  `RUN mkdir -p /app/data`, and `VOLUME ["/app/data"]` lines (Postgres
  persistence now lives in the separate `db` service/volume, not this
  image); added a `DATABASE_URL` default matching the compose network's
  `db` hostname, so `docker compose up` needs no extra configuration.
- `.dockerignore` — removed the now-nonexistent `backend/data/` line.
- `tests/conftest.py` — rewritten. Instead of a fresh SQLite file created
  per test, the `client` fixture now connects to a real Postgres database
  (`snake_arena_test` by default, overridable with `TEST_DATABASE_URL`)
  and drops + recreates every table before each test runs — a real
  server can't be spun up fresh per test for free the way a SQLite file
  could, so this is the isolation mechanism instead. Test files
  themselves (`test_health.py`, `test_scores.py`) needed **no changes**.
- `tests/frontend/conftest.py` — the session-scoped `app_urls` fixture
  now resets that same Postgres test database to empty once, up front,
  then points the real backend subprocess it starts at it via
  `DATABASE_URL`, instead of a throwaway SQLite temp file.
  `test_frontend.py` itself needed **no changes**.
- `product-spec.md`, `AGENTS.md`, `README.md` — data model/tech
  stack/architecture diagram, repo layout, and all setup/run/test
  instructions updated for Postgres + docker-compose; every "backed by
  SQLite" phrasing replaced, with a note where the change happened for
  anyone reading the history.

**Verification actually performed:**
- Installed a real Postgres 16 server (not a stand-in) and created the
  exact `snake_arena` user/database/password `docker-compose.yml` and
  `backend/app/database.py`'s default both use, plus the separate
  `snake_arena_test` database `db-init/001-create-test-db.sql` creates —
  so what was tested is exactly what `docker compose up -d db` produces,
  not an approximation of it.
- Ran the backend against it directly: health check, submitting a score,
  and reading the leaderboard back all worked correctly over a real
  Postgres connection (verified via `curl`, not just by reading the code).
- Ran the same same-origin Docker-simulation playtest used in Stage 6
  (backend serving the built React frontend from `/`, `VITE_API_BASE_URL
  =""`) against this Postgres-backed backend: full game, score submitted,
  leaderboard updated, zero console errors.
- Ran the actual project test suite, unmodified except for the
  Postgres-aware `conftest.py` files described above — `pytest tests -v`
  — and got **15/15 passing**: 9 backend tests and 6 frontend/e2e tests,
  all now running against a real Postgres database instead of SQLite.
- Same limitation as Stages 6 and 7: `docker build`/`docker compose up`
  themselves were not run in this environment (no Docker Hub access), so
  the Dockerfile's and docker-compose.yml's own build/orchestration
  mechanics (image layer order, the healthcheck actually gating startup
  as intended, the init script actually firing on a fresh volume) are
  unverified here. Everything these files' steps actually *do* once
  running was verified by reproducing them directly against a real
  Postgres server, as described above — worth running `docker compose up
  --build` once yourself before relying on it.

**Human review:** pending — this stage's files are ready for review.

## Stage 8 follow-up — port 5432 already in use

**Reported:** running `docker compose up` failed with `Bind for
0.0.0.0:5432 failed: port is already allocated` — something else on the
machine (commonly a local Postgres install, Postgres.app, or another
container) was already listening on Postgres's usual port.

**Fix:** changed the `db` service's *host-side* port mapping in
`docker-compose.yml` from `5432:5432` to `5433:5432`. The container still
listens on the standard 5432 internally — `backend`'s `DATABASE_URL`
(`postgresql://...@db:5432/...`) is untouched, since container-to-
container traffic goes over Docker's internal network, not the published
host port. Only things connecting from *outside* Docker to this database
are affected, so their defaults were updated to match:
`backend/app/database.py`'s `DEFAULT_DATABASE_URL`, and the
`TEST_DATABASE_URL` default in both `tests/conftest.py` and
`tests/frontend/conftest.py`. `README.md` and `AGENTS.md` updated to say
`localhost:5433` instead of `5432` wherever they describe connecting to
the compose-managed database directly. `DATABASE_URL`/`TEST_DATABASE_URL`
remain fully overridable for anyone who'd rather free up the real 5432 or
use a different port entirely.

**Verification actually performed:** proxied a real, already-passing
Postgres connection onto port 5433 (so it matched the new default port
exactly, without needing Docker to test the fix) and reran the full
`pytest tests -v` suite against it with **no environment overrides** —
15/15 passing, confirming the new default port is actually what the code
now uses, not just what the comments say.

**Human review:** pending.

## Stage 8 follow-up #2 — reverted to port 5432

**Asked for:** change the host-side port back to 5432 (`lsof -i :5432`
showed the conflicting process was Docker itself, `com.docker...` — most
likely a leftover or still-running container from an earlier attempt,
not a separate Postgres install — so freeing it up was straightforward).

**Fix:** reverted every place the 5433 follow-up touched, back to 5432:
`docker-compose.yml`'s host-side port mapping, the `DEFAULT_DATABASE_URL`
in `backend/app/database.py`, the `TEST_DATABASE_URL` default in both
`tests/conftest.py` and `tests/frontend/conftest.py`, and the port
mentioned in `README.md`/`AGENTS.md`. Comments in those files now note
that the port is easy to change again in the same handful of places if
this ever recurs.

**Verification actually performed:** ran the full `pytest tests -v` suite
again with no environment overrides, against a real local Postgres server
on the standard port 5432 — 15/15 passing.

**Human review:** pending.

## Stage 9 — Integration tests against docker-compose

**Asked for:** integration tests that run against `docker-compose.yaml`.
Proposed a tiered set of scenarios and asked which to build — answer:
**core only** (build succeeds; health check comes up; a score round-trips
through the real Postgres container; the built frontend is served and
playable end-to-end via a real browser) — deferring the "recommended"
tier (data survives a restart, test-db isolation, teardown/volume
removal) and "lower priority" tier (input validation through the real
stack, crash recovery) unless asked for later.

**AI produced:**
- `tests/integration/conftest.py` (new) — `docker_build` (session-scoped,
  runs `docker compose build` once, doesn't raise on failure so a broken
  build shows up as one clear failing test) and `compose_up` (session-
  scoped, depends on `docker_build`; runs `docker compose down -v` first
  to guarantee a clean volume, then `docker compose up -d`, then polls
  `/api/health` until it responds or times out — dumping `docker compose
  logs` into the failure message if it never comes up — and always runs
  `docker compose down -v` again in a `finally`, whether the tests passed,
  failed, or errored).
- `tests/integration/test_docker_compose.py` (new) — the four core
  scenarios: `test_build_succeeds`, `test_health_check_becomes_available`,
  `test_score_round_trips_through_postgres` (submits a score through the
  real container and reads it back off the leaderboard, proving the
  backend actually reaches Postgres over the compose network — DNS for
  the `db` hostname, `DATABASE_URL`, psycopg2 in the built image — not a
  database this project already knows works), and
  `test_frontend_is_served_and_playable` (plays a full game through a
  real browser against the container-served frontend, the same shape as
  the `tests/frontend/` suite but against the actual built image instead
  of a dev build).
- `pytest.ini` (new, repo root) — registers an `integration` marker
  (documentation/tooling only) and marks the new test file with
  `pytestmark = pytest.mark.integration`. Deliberately **not** using
  `addopts = -m "not integration"` to exclude it from the default run:
  that would make the integration tests impossible to select from the
  command line at all, since an `addopts`-injected marker filter combines
  with rather than being overridden by an explicit `-m integration` on
  the command line. Used `--ignore=tests/integration` in the documented
  fast-suite command instead, which cleanly excludes the directory while
  leaving `pytest tests/integration -v` free to run it directly.
- `README.md`, `AGENTS.md` — new "Run the Docker integration tests"
  section/subsection (requirements, the port-availability and data-wipe
  warnings, what each test checks), the documented fast-suite command
  updated to `--ignore=tests/integration`, and status sections updated.

**Verification actually performed:** this is the first stage of the
project where I had no substitute available for the real thing, in any
environment — every earlier Docker-adjacent stage (the Dockerfile, then
docker-compose itself) could at least be verified by reproducing the
image's/compose file's steps by hand against a real, separately-installed
Postgres server. Here the object under test **is** `docker compose
build`/`up` themselves, and I have no Docker access anywhere (cloud
sandbox blocks Docker Hub; the device bridge to this machine has no
`docker` installed at all). So what I actually verified was narrower:
- The new files are syntactically valid (`py_compile`) and collect
  correctly: `pytest tests --collect-only -q` finds 19 tests without the
  `--ignore`, 15 with it — confirming both that the integration tests are
  discovered and that `--ignore=tests/integration` actually excludes them.
- The **logic** inside `conftest.py` — not the real Docker calls, which I
  can't make — is correct: called the `compose_up` fixture's raw function
  directly (bypassing pytest's fixture injection) with `docker compose`
  itself mocked out via `unittest.mock.patch`, under four scenarios (build
  fails, `up` fails, health check times out, everything succeeds), and
  confirmed in each case it behaves as intended — stopping before `up` on
  a build failure, surfacing Docker's own stderr on an `up` failure,
  dumping `docker compose logs` on a health-check timeout, and — on
  success — running `down -v` both before yielding and afterward via
  `finally`. Also verified the health-check polling helper against a real
  local `http.server` (detects it near-instantly; correctly times out
  against nothing listening) and confirmed the `docker compose <args>`
  subprocess command is constructed with the right arguments
  (`cwd`/`timeout`/`capture_output`/`text`).
- Re-ran the existing fast suite end-to-end against real Postgres after
  all these changes — still **15/15 passing**, confirming nothing about
  the new `pytest.ini`/marker registration broke the existing tests.
- What this does **not** prove: that `docker compose build` and `docker
  compose up` will actually succeed against the real `Dockerfile` and
  `docker-compose.yml` on your machine, that the healthcheck actually
  gates backend startup the way it's supposed to, or that the four tests
  themselves pass against real containers. None of that can be checked
  without Docker. **Please run `uv run pytest ../tests/integration -v`
  yourself, with Docker Desktop running and ports 8000/5432 free, for the
  first real signal on these tests** — see `README.md`'s "Run the Docker
  integration tests" section, including its data-wipe warning, before you
  do.

**Human review:** pending — in particular, whether the four tests
actually pass against real Docker on your machine is still unknown to me.

## Stage 10 — Deploy to AWS with CloudFormation

**Asked for:** deploy the application to AWS, using CloudFormation.
Clarified scope before building, since this had several independent
decisions (three questions, given how differently each answer could
send the work): (1) whether I should actually run the deployment or
just author the templates for you to run — answer: **actually deploy
it**, though this ran into a hard constraint described below; (2) how
Postgres should run in AWS — answer: **managed RDS**; (3) how the app
container should run — answer: **ECS Fargate**.

Before writing anything, I checked whether I could actually run a
deployment from any environment available to me: no `aws` CLI in the
cloud sandbox, no AWS credentials anywhere, and network access to AWS's
API is blocked by egress policy from both the cloud sandbox and the
bridge to your computer (confirmed via a direct connection test to
`sts.amazonaws.com`, which failed with a proxy-level `403`/`connect_rejected`
in the sandbox and the equivalent in the device bridge). This is the
same category of restriction that's blocked Docker Hub access all
session — I'm not able to run `aws cloudformation deploy` (or the
`docker build`/`push` steps a deployment needs) myself, regardless of
which architecture we picked. I surfaced this and confirmed you still
wanted the templates + a runbook for you to execute yourself, which is
the recommended default in the question I originally asked before
proceeding.

**AI produced:**
- `backend/app/database.py` — small, backward-compatible addition: a
  new `_database_url_from_env()` helper that builds the connection
  string from split `DB_HOST`/`DB_PORT`/`DB_USER`/`DB_PASSWORD`/`DB_NAME`
  environment variables (URL-encoding user/password) whenever `DB_HOST`
  is set, taking priority over `DATABASE_URL`. `DATABASE_URL` remains
  the default path and is completely unchanged for local dev and
  `docker-compose.yml` — only the ECS task definition sets `DB_HOST`,
  since the RDS endpoint doesn't exist until deploy time and the
  password comes from AWS Secrets Manager rather than a plain env var.
- `infra/aws/01-ecr.yaml` (new) — a CloudFormation stack for the ECR
  repository the app image gets pushed to (image scanning on push, a
  lifecycle policy keeping only the 10 most recent images). Deployed
  first, since the app stack's ECS task definition needs to reference an
  image that already exists.
- `infra/aws/02-app.yaml` (new) — the main stack: a VPC with two public
  subnets across two AZs (no NAT gateway, to avoid its ~$30+/month fixed
  cost — security groups do the actual access control instead of subnet
  placement), security groups scoped so only the ALB can reach the ECS
  tasks and only the ECS tasks can reach RDS, an RDS Postgres instance
  (`db.t4g.micro`, single-AZ, `ManageMasterUserPassword` so the master
  password is generated and owned by Secrets Manager rather than
  appearing anywhere in the template), an ECS cluster/task
  definition/service on Fargate (the task's execution role is granted
  read access to that specific Secrets Manager secret, nothing broader),
  and an internet-facing ALB with a health check against `/api/health`.
  Outputs the app URL, DB endpoint, and cluster/service names.
- `infra/aws/deploy.sh` (new) — deploys the ECR stack, builds the image
  from the existing `Dockerfile`, pushes it to ECR under a
  timestamp tag, then deploys the app stack with that image's URI and
  prints the resulting app URL. Meant to be run by you, not by me.
- `infra/aws/teardown.sh` (new) — deletes the app stack (RDS included —
  this destroys the leaderboard data, no separate backup is kept),
  empties and deletes the ECR repository stack. Asks for a typed
  confirmation of the project name before doing anything, since this is
  irreversible.
- `infra/aws/README.md` (new) — architecture diagram, prerequisites,
  deploy/teardown instructions, a cost estimate (researched current
  `us-east-1` pricing rather than relying on possibly-stale training
  data — see Verification below), and a troubleshooting section for the
  failure modes I could anticipate but not test (Secrets Manager access,
  RDS engine version deprecation over time).
- `README.md`, `AGENTS.md` — new "Deploy to AWS" section/status entry
  pointing at `infra/aws/README.md`, repo layout tree updated.

**Verification actually performed:** this stage has the same fundamental
limitation as the Docker integration tests in Stage 9 — no substitute
was available anywhere for the real thing, since the object under test
*is* `aws cloudformation deploy` and the AWS resources it creates, and I
have no AWS access in any environment available to me (confirmed by
testing, not assumed — see above). What I verified instead:
- Both CloudFormation templates pass `cfn-lint` (installed via pip, pure
  local schema/semantic validation, no AWS calls needed) with **zero
  errors or warnings** on the final version — the first pass flagged
  `EngineVersion: "16"` as invalid for new RDS instances, which I fixed
  by pinning to a specific supported minor version (`16.15`) rather than
  a bare major version, after confirming via web search what's currently
  supported (training data alone isn't reliable here, since RDS's
  supported-version list changes over time).
- Both shell scripts pass `shellcheck` cleanly (one real finding, fixed:
  an unused variable in `teardown.sh` left over from an earlier draft)
  and pass `bash -n` syntax checks.
- Both templates are well-formed YAML (parsed successfully with a
  CloudFormation-tag-tolerant YAML loader).
- The new `database.py` logic was tested directly against four cases:
  nothing set (falls back to the existing default), `DATABASE_URL` set
  with no `DB_HOST` (unchanged, uses `DATABASE_URL` — confirming
  backward compatibility), `DB_HOST` set alongside a password containing
  `@`, `/`, and `:` (confirming URL-encoding), and round-tripping that
  constructed URL through SQLAlchemy's own `make_url()` parser to
  confirm the password survives exactly, not just that string
  construction *looked* right.
- Re-ran the existing backend test suite (`pytest tests
  --ignore=tests/integration`) against real Postgres after the
  `database.py` change — still **9/9 passing**, confirming the change
  didn't affect local/Docker Compose behavior. Also re-confirmed the
  `tests/integration` collection counts (19 total, 15 with `--ignore`)
  are unchanged from Stage 9.
- The cost estimate in `infra/aws/README.md` is based on current
  `us-east-1` pricing found via web search at the time of writing (RDS
  `db.t4g.micro`, ALB base rate, Fargate per-vCPU/GB rates), not recalled
  from training data, specifically because AWS pricing and free-tier
  terms change and I didn't want to hand you a stale number with false
  confidence.
- What none of this proves: that `aws cloudformation deploy` will
  actually succeed against a real AWS account, that the ECS task will
  actually start and pass its health check, that the IAM permissions
  I've scoped are exactly sufficient (not too narrow) in practice, or
  that the RDS/ECS/ALB pieces actually talk to each other correctly once
  real. **Please run `infra/aws/deploy.sh` yourself, with the AWS CLI
  configured and Docker running, for the first real signal** — see
  `infra/aws/README.md`'s cost estimate before you do, since this
  creates real, billable resources.

**Human review:** pending — in particular, whether the deployment
actually succeeds against a real AWS account is entirely unknown to me;
this is the first stage where even syntax-level tooling (`cfn-lint`,
`shellcheck`) was the full extent of what I could check, with no way to
exercise the actual AWS control plane at all.

## Stage 11 — CI/CD pipeline (GitHub Actions)

**Asked for:** a CI/CD pipeline that runs backend and frontend tests in
parallel, builds the Docker Compose stack and runs integration/e2e tests
against it, deploys to AWS using a GitHub OIDC role, and validates the
deploy via the health endpoint.

Before writing anything, I needed two things only you could supply: the
GitHub org/repo (`Crooked-Cat-Tail-Software/snake-arena`, for scoping the
OIDC trust policy to this repo specifically — a role that trusted any
GitHub repo would let anyone's workflow assume it), and whether the AWS
deploy step should run automatically on every push to `main` or only on
manual trigger. You chose manual-only, which matches this project's cost
profile (see `infra/aws/README.md`'s cost estimate) — an automatic
deploy on every merge would start accruing AWS costs the moment this
pipeline merged, not just when you actually meant to deploy.

**AI produced:**
- `.github/workflows/ci-cd.yaml` (new) — four jobs. `backend-tests` and
  `frontend-tests` run in parallel (no `needs:` between them) against a
  Postgres service container, running the same two suites `README.md`
  documents (`tests/` minus `frontend/`/`integration/`, and
  `tests/frontend/`). `docker-compose-integration-tests` runs
  `tests/integration/` — a real `docker compose build`/`up` plus the
  integration and browser-driven end-to-end tests already in that suite
  — gated behind the first two passing, since it's by far the most
  expensive job (a full Docker image build) and there's no reason to pay
  for it if something cheaper already failed. `deploy` only exists on a
  manual "Run workflow" click (`if: github.event_name ==
  'workflow_dispatch'`) — a plain push or PR runs the first three jobs
  and stops there. It authenticates via `aws-actions/configure-aws-credentials`
  using OIDC (`permissions: id-token: write`, no stored AWS keys
  anywhere in the repo or its secrets), runs the existing `deploy.sh`
  unchanged, then polls `/api/health` on the resulting app URL for up to
  5 minutes before failing the job if it never comes up healthy.
- `infra/aws/00-github-oidc.yaml` (new) — a CloudFormation stack, deployed
  once by you (not by the pipeline — nothing can authenticate to deploy
  this stack until it exists), that creates the GitHub OIDC identity
  provider (or reuses an existing one via an `ExistingOIDCProviderArn`
  parameter, since AWS allows only one per account per provider URL) and
  an IAM role GitHub Actions can assume. The trust policy's `sub`
  condition restricts it to `repo:<org>/<repo>:ref:refs/heads/main`
  specifically — a workflow run on any other branch, or a pull request
  from a fork, is refused by AWS itself before the workflow file even
  runs. The permissions policy is scoped to exactly what `deploy.sh`
  needs: push to this project's ECR repo, create/update the two existing
  CloudFormation stacks, and manage the one IAM role
  (`snake-arena-ecs-execution-role`) those stacks create — nothing
  broader. The VPC/RDS/ECS/ALB create actions use `Resource: "*"`
  because AWS doesn't support resource-level ARN restrictions for most
  of those services' create actions (the resource doesn't exist yet to
  have an ARN); this is the same shape of access a person running
  `deploy.sh` by hand already needs, not wider.
- `backend/app/database.py` — unchanged this stage.
- `infra/aws/deploy.sh`, `infra/aws/teardown.sh` — fixed the default
  Region from `us-east-1` to `us-east-2`. This wasn't part of what was
  asked for, but the AWS Agent Toolkit setup earlier in this project
  revealed `us-east-2` is this account's actual assigned Region under
  the "new AWS experience" account type, and the "new AWS experience"
  rules are explicit that regional resources can't be created outside
  that assigned Region — so the original `us-east-1` default would have
  failed on this account. Flagged and fixed rather than left silently
  wrong now that it's known to matter.
- `infra/aws/README.md` — new "CI/CD (GitHub Actions)" section: the
  one-time setup (deploy `00-github-oidc.yaml`, copy its output ARN into
  a GitHub Actions repository variable), what the deploy role can and
  can't do, and how to trigger a deploy. Also updated the Region
  defaults and cost-estimate caveat to match the `deploy.sh` fix above.
- `README.md`, `AGENTS.md` — new CI/CD status entries and repo-layout
  line for `.github/workflows/`.

**Verification actually performed:** the same fundamental limitation as
Stages 9 and 10 — no way to execute a GitHub Actions run, exchange an
OIDC token, or otherwise touch the real AWS control plane from this
session. What I verified instead:
- `00-github-oidc.yaml` passes `cfn-lint` with **zero errors or
  warnings**.
- `ci-cd.yaml` passes `actionlint` (installed fresh from its GitHub
  releases for this check) with **zero findings** — this validates the
  workflow's YAML and expression syntax, every `uses:` action reference,
  and shellchecks every embedded `run:` script.
- The GitHub/AWS-documented OIDC thumbprint was looked up via live web
  search against GitHub's own changelog and AWS's security blog, not
  recalled from training data — present-day infrastructure values like
  this are exactly what's prone to silently going stale. My first
  recollection was actually wrong (missing a trailing character, 39 hex
  digits instead of the required 40) and `cfn-lint`'s own schema check
  on the `ThumbprintList` property caught it immediately; I then
  verified the corrected value against two independent official sources
  before using it, rather than just patching the length.
- `deploy.sh`/`teardown.sh` still pass `shellcheck` cleanly and `bash
  -n` after the Region-default edit; re-ran `cfn-lint` on `01-ecr.yaml`/
  `02-app.yaml` as a regression check (unaffected, unsurprisingly, since
  neither file changed) — zero errors, same as before.
- The IAM role's resource names (the ECS execution role name, the ECR
  repository name, the two stack names) were taken directly from reading
  the actual `01-ecr.yaml`/`02-app.yaml` files rather than recalled from
  memory of writing them in Stage 10, so the new template's scoping
  matches what those templates actually create.

None of that proves the pipeline will actually go green on GitHub:
whether the Postgres service container comes up in time for the tests,
whether `playwright install --with-deps chromium` behaves the same on a
GitHub-hosted runner as it does locally, whether the OIDC token exchange
actually succeeds against a real AWS account, and whether the deploy
job's health-check polling behaves correctly against a real ALB are all
untested by anything available to me.

**Human review:** pending — push this to GitHub, do the one-time OIDC
role deploy from `infra/aws/README.md`'s CI/CD section yourself (it
needs your own AWS credentials, same reasoning as every AWS-touching
step in this project), add the `AWS_DEPLOY_ROLE_ARN` repository
variable, and treat the first automatic push-triggered test run and the
first manual "Run workflow" deploy click as the real tests. I'd also
specifically want your eyes on the IAM policy in `00-github-oidc.yaml`
before trusting it with real AWS access — I'm confident in its scoping
logic, but least-privilege IAM policies are exactly the kind of thing
where a second pair of eyes matters most and mine have never seen it
actually enforced against a live account.
