from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class DayLogCreate(BaseModel):
    date: date
    distance_km: float = Field(ge=0)
    elevation_gain_m: int = Field(ge=0)
    max_speed_kmh: float = Field(ge=0)
    runs_count: int = Field(ge=0)
    note: str | None = Field(default=None, max_length=2000)


class DayLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trip_id: int
    user_id: int
    date: date
    distance_km: float
    elevation_gain_m: int
    max_speed_kmh: float
    runs_count: int
    note: str | None
    created_at: datetime
