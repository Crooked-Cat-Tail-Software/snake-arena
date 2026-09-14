from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime

from .database import Base


class ScoreRecord(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    player_name = Column(String(20), nullable=False)
    score = Column(Integer, nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
