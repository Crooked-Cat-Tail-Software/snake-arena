from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator, field_serializer, ConfigDict


class HealthStatus(BaseModel):
    status: str = "ok"


class ScoreCreate(BaseModel):
    player_name: str = Field(..., min_length=1, max_length=20)
    score: int = Field(..., ge=0)

    @field_validator("player_name")
    @classmethod
    def trim_name(cls, v: str) -> str:
        trimmed = v.strip()
        if not trimmed:
            raise ValueError("player_name must not be blank")
        if len(trimmed) > 20:
            raise ValueError("player_name must be at most 20 characters")
        return trimmed


class Score(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    player_name: str
    score: int
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime, _info):
        # Stored as naive UTC; present it as an explicit UTC ISO-8601 string
        # to match the "Z"-suffixed examples in openapi.yaml.
        return dt.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
