from pathlib import Path

from fastapi import FastAPI, Depends, Query, Request, Response
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import crud, schemas
from opentelemetry import metrics

from .database import Base, engine, get_db
from .game_metrics import GameMetrics
from .telemetry import setup_telemetry

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Snake Arena API",
    version="1.0.0",
    description=(
        "Backend for the Snake Arena class project. "
        "See openapi.yaml at the repo root for the reviewed contract."
    ),
)

# Local-only class project: allow whatever localhost port serves the frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenTelemetry: a span per request and per DB query, plus game metrics,
# all tagged with service name, environment, and deployed version -- see
# telemetry.py and game_metrics.py. Kept on app.state so tests can swap in
# an in-memory recorder.
setup_telemetry(app, engine)
app.state.game_metrics = GameMetrics(metrics.get_meter("snake_arena"))


@app.exception_handler(RequestValidationError)
async def count_rejected_scores(request: Request, exc: RequestValidationError):
    """Counts rejected score submissions, then responds exactly as FastAPI
    would by default (the 422 body openapi.yaml documents)."""
    if request.method == "POST" and request.url.path == "/api/scores":
        # Reason = the field the first error is about ("player_name" or
        # "score"); anything else (bad JSON, missing body) is "malformed".
        loc = exc.errors()[0].get("loc", ()) if exc.errors() else ()
        reason = loc[1] if len(loc) > 1 and loc[0] == "body" else "malformed"
        request.app.state.game_metrics.record_rejection(str(reason))
    return await request_validation_exception_handler(request, exc)


@app.get("/api/health", response_model=schemas.HealthStatus, tags=["health"])
def get_health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return schemas.HealthStatus(status="ok")


@app.post("/api/scores", response_model=schemas.Score, status_code=201, tags=["scores"])
def submit_score(
    score_in: schemas.ScoreCreate, request: Request, db: Session = Depends(get_db)
):
    high_score = crud.get_high_score(db)
    record = crud.create_score(db, score_in)
    request.app.state.game_metrics.record_submission(
        record.score, is_new_top=high_score is None or record.score > high_score
    )
    return record


@app.get("/api/scores", response_model=list[schemas.Score], tags=["scores"])
def read_leaderboard(
    request: Request,
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    request.app.state.game_metrics.record_leaderboard_read()
    return crud.get_top_scores(db, limit=limit)


@app.post("/api/client-errors", status_code=204, tags=["client-errors"])
def report_client_error(report: schemas.ClientErrorReport, request: Request):
    """A failure in the player's browser (see openapi.yaml). Counted for
    alerting, never stored."""
    request.app.state.game_metrics.record_canvas_failure(report.reason)
    return Response(status_code=204)


# Serve the built frontend, if present. In local dev the frontend is
# served separately (see README.md) and this directory doesn't exist, so
# nothing here changes -- this only activates inside the Docker image,
# which copies the frontend's static files to backend/static (see
# Dockerfile). Mounted last, and at "/", so it never shadows the /api
# routes above: FastAPI matches routes in the order they were declared,
# and only falls through to this catch-all mount for anything else.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
