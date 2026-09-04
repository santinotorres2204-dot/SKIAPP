from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TrickCardCreate(BaseModel):
    trick_name: str = Field(min_length=1, max_length=255)
    difficulty: int = Field(ge=1, le=10)
    execution_score: int = Field(ge=0, le=100)
    landing_score: int = Field(ge=0, le=100)
    style_score: int = Field(ge=0, le=100)
    consistency_score: int = Field(ge=0, le=100)


class TrickCardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    user_id: int
    trick_name: str
    difficulty: int
    execution_score: int
    landing_score: int
    style_score: int
    consistency_score: int
    created_at: datetime
