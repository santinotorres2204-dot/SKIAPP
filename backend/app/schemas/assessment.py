from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AssessmentSubmit(BaseModel):
    wall_sit_seconds: int = Field(ge=0)
    single_leg_squat_left: int = Field(ge=0)
    single_leg_squat_right: int = Field(ge=0)
    jump_squat_reps: int = Field(ge=0)
    plank_seconds: int = Field(ge=0)
    lateral_bound_reps: int = Field(ge=0)
    notes: str | None = Field(default=None, max_length=2000)


class AssessmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    completed_at: datetime
    wall_sit_seconds: int
    single_leg_squat_left: int
    single_leg_squat_right: int
    jump_squat_reps: int
    plank_seconds: int
    lateral_bound_reps: int
    notes: str | None


class AssessmentComparisonRow(BaseModel):
    key: str
    label: str
    unit: str
    before: int
    after: int
    delta: int
    direction: str
    before_pct: int
    after_pct: int


class AssessmentSubmitResponse(BaseModel):
    result: AssessmentRead
    comparison: list[AssessmentComparisonRow] | None
