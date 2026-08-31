from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import SkiRating
from app.models.enums import Discipline
from app.routers.users import get_user_or_404
from app.schemas.ski_rating import SkiRatingRead, SkiRatingUpsert

router = APIRouter(tags=["ski-ratings"])


@router.put("/users/{user_id}/ski-ratings/{discipline}", response_model=SkiRatingRead)
def upsert_ski_rating(
    user_id: int,
    discipline: Discipline,
    payload: SkiRatingUpsert,
    db: Session = Depends(get_db),
) -> SkiRating:
    get_user_or_404(db, user_id)

    rating = (
        db.query(SkiRating)
        .filter(SkiRating.user_id == user_id, SkiRating.discipline == discipline.value)
        .one_or_none()
    )
    if rating is None:
        rating = SkiRating(user_id=user_id, discipline=discipline.value)
        db.add(rating)

    rating.score = payload.score
    rating.confidence_score = payload.confidence_score
    rating.coach_verified = payload.coach_verified

    db.commit()
    db.refresh(rating)
    return rating


@router.get("/users/{user_id}/ski-ratings", response_model=list[SkiRatingRead])
def list_ski_ratings(user_id: int, db: Session = Depends(get_db)) -> list[SkiRating]:
    get_user_or_404(db, user_id)
    return db.query(SkiRating).filter(SkiRating.user_id == user_id).order_by(SkiRating.discipline).all()
