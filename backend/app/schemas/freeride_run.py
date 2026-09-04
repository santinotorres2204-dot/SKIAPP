from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FreerideRunCreate(BaseModel):
    location_name: str = Field(min_length=1, max_length=255)
    vertical_m: float = Field(ge=0)
    distance_km: float = Field(ge=0)
    max_gradient: float = Field(ge=0)
    flow_score: int = Field(ge=0, le=100)
    control_score: int = Field(ge=0, le=100)
    line_choice_score: int = Field(ge=0, le=100)
    difficulty_score: int = Field(ge=0, le=100)


class FreerideRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    video_id: int
    user_id: int
    location_name: str
    vertical_m: float
    distance_km: float
    max_gradient: float
    flow_score: int
    control_score: int
    line_choice_score: int
    difficulty_score: int
    created_at: datetime
