from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import DayLog
from app.routers.trips import get_trip_or_404
from app.routers.users import get_user_or_404
from app.schemas.day_log import DayLogCreate, DayLogRead

router = APIRouter(tags=["day-logs"])


@router.post(
    "/users/{user_id}/trips/{trip_id}/day-logs",
    response_model=DayLogRead,
    status_code=status.HTTP_201_CREATED,
)
def create_day_log(user_id: int, trip_id: int, payload: DayLogCreate, db: Session = Depends(get_db)) -> DayLog:
    get_user_or_404(db, user_id)
    get_trip_or_404(db, trip_id)
    day_log = DayLog(trip_id=trip_id, user_id=user_id, **payload.model_dump())
    db.add(day_log)
    db.commit()
    db.refresh(day_log)
    return day_log


@router.get("/users/{user_id}/day-logs", response_model=list[DayLogRead])
def list_user_day_logs(user_id: int, db: Session = Depends(get_db)) -> list[DayLog]:
    get_user_or_404(db, user_id)
    return db.query(DayLog).filter(DayLog.user_id == user_id).order_by(DayLog.date.desc()).all()


@router.get("/trips/{trip_id}/day-logs", response_model=list[DayLogRead])
def list_trip_day_logs(trip_id: int, db: Session = Depends(get_db)) -> list[DayLog]:
    get_trip_or_404(db, trip_id)
    return db.query(DayLog).filter(DayLog.trip_id == trip_id).order_by(DayLog.date.desc()).all()
