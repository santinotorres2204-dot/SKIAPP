from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.achievements import compute_achievements
from app.database import get_db
from app.models import DayLog
from app.routers.users import get_user_or_404
from app.schemas.achievement import AchievementStatus

router = APIRouter(tags=["achievements"])


@router.get("/users/{user_id}/achievements", response_model=list[AchievementStatus])
def list_user_achievements(user_id: int, db: Session = Depends(get_db)) -> list[AchievementStatus]:
    get_user_or_404(db, user_id)
    day_logs = db.query(DayLog).filter(DayLog.user_id == user_id).all()
    return compute_achievements(day_logs)
