from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import SkiLevel


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    ski_level: SkiLevel
    years_skiing: int = Field(ge=0)


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    ski_level: SkiLevel | None = None
    years_skiing: int | None = Field(default=None, ge=0)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    ski_level: SkiLevel
    years_skiing: int
    created_at: datetime
