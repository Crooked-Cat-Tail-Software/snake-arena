# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: frontend (Node)
# ---------------------------------------------------------------------------
# The frontend is plain HTML/CSS/JS today -- no package.json, no bundler,
# nothing for Node to actually compile. This stage still exists (as asked)
# so the project already has the shape of a real build pipeline: the day a
# package.json shows up, this becomes a real build with no other changes to
# this file. Until then it just stages the static files through Node's
# image untouched.
#
# What this would look like with real build tooling (kept here for when
# that day comes):
#   COPY frontend/package*.json ./
#   RUN npm ci
#   COPY frontend/ .
#   RUN npm run build          # emits ./dist
#   # ...then in the backend stage below: COPY --from=frontend /frontend/dist ./static
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/ .

# ---------------------------------------------------------------------------
# Stage 2: backend (Python) -- serves the API and the built frontend
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS backend
WORKDIR /app

# Dependencies first so this layer is cached unless requirements.txt changes.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend application code.
COPY backend/app ./app

# The frontend, staged through Node above. main.py mounts this directory
# (backend/static, i.e. /app/static here) at "/" if it exists -- see
# backend/app/main.py -- so the API serves the game itself, not just JSON.
COPY --from=frontend /frontend ./static

# SQLite lives here. Mount a volume at /app/data to persist scores across
# container restarts/rebuilds (see README.md for the `docker run` command).
RUN mkdir -p /app/data
ENV DATABASE_URL=sqlite:////app/data/snake_arena.db
VOLUME ["/app/data"]

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
