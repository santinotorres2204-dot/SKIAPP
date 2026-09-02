from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RunStartRequest(BaseModel):
    # Sin login todavia (ver app/routers/passport.py) -- el user_id viaja
    # explicito en el body, igual que en el resto de la app.
    user_id: int


class RunStartResponse(BaseModel):
    run_id: int


class RunEndRequest(BaseModel):
    gps_track: list[dict[str, Any]] = Field(default_factory=list)
    max_speed_kmh: float = Field(ge=0)
    avg_speed_kmh: float = Field(ge=0)
    distance_km: float = Field(ge=0)
    elevation_gain_m: float = Field(ge=0)
    elevation_loss_m: float = Field(ge=0)
    notes: str | None = Field(default=None, max_length=2000)


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: int | None
    max_speed_kmh: float | None
    avg_speed_kmh: float | None
    distance_km: float | None
    elevation_gain_m: float | None
    elevation_loss_m: float | None
    gps_track: list[dict[str, Any]] | None
    notes: str | None
    created_at: datetime
