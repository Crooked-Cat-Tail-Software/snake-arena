# Snake Arena — Product Spec

Status: APPROVED (v1)
Author: Donna Brown (with Claude as pair)
Date: 2026-09-13

## 1. Purpose

A small, complete full-stack app for a class exercise: build a classic Snake
game with a real client/server split, a contract-first API, and persistent
storage — practicing a workflow where each stage (spec → contract → backend
→ frontend → tests) is produced, reviewed, and verified before moving to the
next.

This is a learning project, not a production system. Favor clarity and a
complete, working slice over feature breadth.

## 2. Goals

- One player plays Snake in the browser; gameplay feels responsive (client-
  side game loop, no network round-trip per frame).
- On game over, the run is submitted to a backend API and persisted.
- A leaderboard of top scores is fetched from the backend and displayed.
- The frontend and backend are decoupled and communicate only through a
  documented OpenAPI contract — either side could be rebuilt independently
  as long as it honors the contract.
- Everything runs locally on one machine: frontend static page + local
  backend + local SQLite file. No cloud deps, no auth, no accounts.

## 3. Non-goals (out of scope for v1)

- Multiplayer / multiple snakes in the same arena at once.
- User accounts, authentication, or anti-cheat on submitted scores.
- Mobile/touch controls (keyboard only).
- Deployment/hosting concerns — this runs on localhost only.
- Persisting in-progress game state server-side (only the final score is
  sent, once, at game over).

## 4. User stories

1. As a player, I open the page, type my name, and press a key to start.
2. As a player, I steer the snake with arrow keys to eat food and grow
   longer, and the game ends if I hit a wall or my own body.
3. As a player, when my run ends I see my score, it's submitted
   automatically, and I see where I rank on the leaderboard.
4. As a player, I can see the current top scores before I even play.
5. As the developer, I can read one OpenAPI file and know exactly what the
   frontend is allowed to send and expect back, with no guessing.

## 5. Functional requirements

### 5.1 Gameplay (client-side only, no backend involved mid-game)
- Grid-based arena, default 20x20 cells.
- Snake starts length 3, moving right, at the center of the grid.
- Arrow keys (or WASD) change direction; the snake cannot reverse directly
  into itself (pressing the opposite direction is ignored).
- Food spawns at a random empty cell after each one is eaten.
- Eating food: snake grows by one segment, score increments by 1.
- Game over when the snake's head hits a wall or its own body.
- Tick rate: fixed step (e.g. every 120ms), no ramping speed for v1
  (documented here so it's an explicit, reviewable decision, not a
  surprise in the code).

### 5.2 Score submission
- On game over, the frontend prompts for/uses the player name entered at
  start and calls the backend once to submit `{ player_name, score }`.
- The backend validates the payload, stores it with a server-generated
  timestamp, and returns the stored record (including its id).
- A failed submission (e.g. backend down) shows an inline error on the
  game-over screen but does not crash the game; the player can retry.

### 5.3 Leaderboard
- The frontend fetches the top N (default 10) scores, highest first, on
  page load and again right after a successful submission.
- Ties broken by earliest submission (lower id / earlier created_at first).

### 5.4 Health check
- A simple endpoint the frontend (or a human) can hit to confirm the
  backend and its database connection are up.

## 6. Data model

Single table, `scores`:

| Field        | Type      | Constraints                              |
|--------------|-----------|-------------------------------------------|
| id           | integer   | primary key, autoincrement                |
| player_name  | text      | required, 1–20 chars, trimmed             |
| score        | integer   | required, >= 0                            |
| created_at   | datetime  | required, set by server (UTC), not client |

No updates or deletes in v1 — scores are append-only.

## 7. API surface (summary — full contract lives in `openapi.yaml`)

- `GET /api/health` → `{ status: "ok" }`
- `POST /api/scores` → body `{ player_name, score }` → 201 + stored record
- `GET /api/scores?limit=10` → array of top scores, highest first

CORS is enabled on the backend for local development (frontend and backend
run on different localhost ports).

## 8. Architecture

```
+----------------+        HTTP/JSON, per OpenAPI contract        +----------------+        SQLite (file)
|   Frontend     |  <--------------------------------------->    |    Backend     |  <----------------->  scores.db
| HTML5 canvas   |   POST /api/scores                            |   FastAPI      |
| + vanilla JS   |   GET  /api/scores                             |   Python       |
| (game loop     |   GET  /api/health                            |                |
|  runs locally) |                                                |                |
+----------------+                                                +----------------+
```

The frontend never touches the database directly and never runs the
authoritative game loop on the server — the server only ever sees a final
score, never frame-by-frame state.

## 9. Tech stack

- Backend: Python, FastAPI (generates/validates against the OpenAPI
  contract), SQLite via SQLAlchemy, run with `uv`.
- Frontend: vanilla HTML/CSS/JS, `<canvas>` for rendering, no build step —
  open `index.html` or serve it with a trivial static server.
- Tests: `pytest` for backend unit + API contract tests; a short manual/
  scripted check for frontend behavior (see testing plan in a later step).

## 10. Acceptance criteria / definition of done for v1

- [ ] Spec reviewed and approved (this document).
- [ ] `openapi.yaml` reviewed and approved.
- [ ] Backend implements exactly the contract's endpoints, backed by
      SQLite, and passes its tests.
- [ ] Frontend plays a full game start-to-finish, submits a score, and
      renders the leaderboard, using only the contract's endpoints.
- [ ] Tests cover: score validation (rejects bad payloads), leaderboard
      ordering/limit, health check, and at least the core snake movement/
      collision logic.
- [ ] README explains how to run backend + frontend locally from scratch.

## 11. Decisions (resolved during spec review)

- Arena size / tick speed: fixed defaults confirmed (20x20 grid, 120ms
  tick). No configurability in v1.
- Leaderboard size: default 10 confirmed. No "view all" mode in v1.
- Personal-best indicator: not requested — out of scope for v1, left as a
  future idea.

---
**Status:** Approved. Next artifact: `openapi.yaml`, written to
match exactly what's specified above.
