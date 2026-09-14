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
