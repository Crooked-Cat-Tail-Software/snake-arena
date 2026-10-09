from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import models, schemas


def create_score(db: Session, score_in: schemas.ScoreCreate) -> models.ScoreRecord:
    record = models.ScoreRecord(player_name=score_in.player_name, score=score_in.score)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_top_scores(db: Session, limit: int = 10) -> list[models.ScoreRecord]:
    stmt = (
        select(models.ScoreRecord)
        .order_by(
            models.ScoreRecord.score.desc(),
            models.ScoreRecord.created_at.asc(),
            models.ScoreRecord.id.asc(),
        )
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def get_high_score(db: Session) -> int | None:
    """The current #1 score, or None if no scores exist yet."""
    return db.scalar(select(func.max(models.ScoreRecord.score)))
