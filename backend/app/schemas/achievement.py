from pydantic import BaseModel


class AchievementStatus(BaseModel):
    id: str
    title: str
    description: str
    earned: bool
