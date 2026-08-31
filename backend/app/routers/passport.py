from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import SeasonReview, SkiRating, TrainingPlan, Trip
from app.routers.users import get_user_or_404

router = APIRouter(tags=["passport"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/passport/{user_id}")
def passport(request: Request, user_id: int, db: Session = Depends(get_db)):
    """Vista de solo lectura del lado del usuario (spec seccion 7, pantallas
    5-7): Ski Passport (perfil + historial de viajes), Ski Card (rating por
    disciplina) y los training plans cargados por el fundador. Sin login
    todavia -- se accede por URL con el user_id, igual que el panel admin.
    """
    user = get_user_or_404(db, user_id)

    trips = db.query(Trip).filter(Trip.user_id == user_id).order_by(Trip.start_date.desc()).all()
    ratings = db.query(SkiRating).filter(SkiRating.user_id == user_id).order_by(SkiRating.discipline).all()
    training_plans = (
        db.query(TrainingPlan)
        .options(joinedload(TrainingPlan.trip))
        .filter(TrainingPlan.user_id == user_id)
        .order_by(TrainingPlan.created_at.desc())
        .all()
    )
    season_reviews = (
        db.query(SeasonReview)
        .options(joinedload(SeasonReview.trip))
        .filter(SeasonReview.user_id == user_id)
        .order_by(SeasonReview.created_at.desc())
        .all()
    )

    return templates.TemplateResponse(
        request,
        "passport.html",
        {
            "user": user,
            "trips": trips,
            "ratings": ratings,
            "training_plans": training_plans,
            "season_reviews": season_reviews,
        },
    )
