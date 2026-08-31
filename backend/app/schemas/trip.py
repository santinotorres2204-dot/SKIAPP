from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TripStatus


class TripCreate(BaseModel):
    destination: str = Field(min_length=1, max_length=255)
    start_date: date


class TripUpdate(BaseModel):
    destination: str | None = Field(default=None, min_length=1, max_length=255)
    start_date: date | None = None
    status: TripStatus | None = None


class TripRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    destination: str
    start_date: date
    status: TripStatus
    created_at: datetime
