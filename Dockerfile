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

# Data now lives in Postgres, not this image -- see docker-compose.yml,
# which runs a separate `db` service and passes it to this container via
# DATABASE_URL. This default matches that service's hostname/credentials,
# so `docker compose up` needs no extra configuration; running this image
# standalone (docker run, no compose) requires passing a real DATABASE_URL,
# since there's no Postgres reachable at "db" without it.
ENV DATABASE_URL=postgresql://snake_arena:snake_arena@db:5432/snake_arena

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
