from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Discipline


class SkiRatingUpsert(BaseModel):
    score: int = Field(ge=0, le=100)
    confidence_score: int = Field(ge=0, le=100)
    coach_verified: bool = False


class SkiRatingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    discipline: Discipline
    score: int
    confidence_score: int
    coach_verified: bool
    updated_at: datetime
