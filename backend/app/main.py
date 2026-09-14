from fastapi import FastAPI, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import crud, schemas
from .database import Base, engine, get_db

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


@app.get("/api/health", response_model=schemas.HealthStatus, tags=["health"])
def get_health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return schemas.HealthStatus(status="ok")


@app.post("/api/scores", response_model=schemas.Score, status_code=201, tags=["scores"])
def submit_score(score_in: schemas.ScoreCreate, db: Session = Depends(get_db)):
    return crud.create_score(db, score_in)


@app.get("/api/scores", response_model=list[schemas.Score], tags=["scores"])
def read_leaderboard(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return crud.get_top_scores(db, limit=limit)
