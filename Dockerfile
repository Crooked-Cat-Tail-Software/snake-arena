# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1: frontend (Node) -- real Vite/React build
# ---------------------------------------------------------------------------
# package*.json copied first so `npm ci` is cached unless dependencies
# change. VITE_API_BASE_URL="" makes the production bundle call the API on
# its own origin (relative URLs) -- correct here because the backend stage
# below serves this same build, so frontend and API always share an origin
# regardless of which host port `docker run -p` maps to.
FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
ENV VITE_API_BASE_URL=""
RUN npm run build

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

# The built frontend (frontend/dist), staged through Node above. main.py
# mounts this directory (backend/static, i.e. /app/static here) at "/" if
# it exists -- see backend/app/main.py -- so the API serves the game
# itself, not just JSON.
COPY --from=frontend /frontend/dist ./static

# SQLite lives here. Mount a volume at /app/data to persist scores across
# container restarts/rebuilds (see README.md for the `docker run` command).
RUN mkdir -p /app/data
ENV DATABASE_URL=sqlite:////app/data/snake_arena.db
VOLUME ["/app/data"]

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
