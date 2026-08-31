from datetime import date
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import SeasonReview, SkiRating, TrainingPlan, Trip
from app.models.enums import Discipline, SkiLevel
from app.routers.trips import create_trip
from app.routers.users import create_user, get_user_or_404
from app.routers.video_uploads import upload_video
from app.schemas.trip import TripCreate
from app.schemas.user import UserCreate

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


# ---------------------------------------------------------------------------
# Registro (spec seccion 7, pantallas 1-2: registro/login + onboarding).
# Sin auth todavia, asi que ambas colapsan en un unico formulario de perfil.
# ---------------------------------------------------------------------------

@router.get("/register")
def register_form(request: Request):
    return templates.TemplateResponse(request, "register.html", {"error": None, "ski_levels": list(SkiLevel)})


@router.post("/register")
def register_submit(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    ski_level: SkiLevel = Form(...),
    years_skiing: int = Form(..., ge=0),
    db: Session = Depends(get_db),
):
    try:
        payload = UserCreate(name=name, email=email, ski_level=ski_level, years_skiing=years_skiing)
        user = create_user(payload, db)
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Revisa los datos ingresados (el email no parece valido).", "ski_levels": list(SkiLevel)},
            status_code=422,
        )
    except HTTPException as exc:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": exc.detail, "ski_levels": list(SkiLevel)},
            status_code=exc.status_code,
        )

    return RedirectResponse(url=f"/passport/{user.id}", status_code=status.HTTP_303_SEE_OTHER)


# ---------------------------------------------------------------------------
# Crear viaje (spec seccion 7, pantalla 3).
# ---------------------------------------------------------------------------

@router.get("/passport/{user_id}/trips/new")
def new_trip_form(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = get_user_or_404(db, user_id)
    return templates.TemplateResponse(request, "trip_form.html", {"user": user, "error": None})


@router.post("/passport/{user_id}/trips")
def new_trip_submit(
    request: Request,
    user_id: int,
    destination: str = Form(...),
    start_date: date = Form(...),
    db: Session = Depends(get_db),
):
    user = get_user_or_404(db, user_id)
    try:
        payload = TripCreate(destination=destination, start_date=start_date)
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "trip_form.html",
            {"user": user, "error": "El destino no puede estar vacio."},
            status_code=422,
        )

    create_trip(user_id, payload, db)
    return RedirectResponse(url=f"/passport/{user_id}", status_code=status.HTTP_303_SEE_OTHER)


# ---------------------------------------------------------------------------
# Subir video (spec seccion 7, pantalla 4).
# ---------------------------------------------------------------------------

@router.get("/passport/{user_id}/videos/new")
def new_video_form(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = get_user_or_404(db, user_id)
    trips = db.query(Trip).filter(Trip.user_id == user_id).order_by(Trip.created_at.desc()).all()
    return templates.TemplateResponse(
        request,
        "video_form.html",
        {"user": user, "trips": trips, "disciplines": list(Discipline)},
    )


@router.post("/passport/{user_id}/videos")
def new_video_submit(
    user_id: int,
    background_tasks: BackgroundTasks,
    discipline_tag: Discipline = Form(...),
    # str en vez de int|None: un <select> con la opcion "sin viaje" manda "",
    # que Pydantic no puede parsear como int -- se convierte a mano abajo.
    trip_id: str = Form(default=""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    trip_id_value = int(trip_id) if trip_id else None
    upload_video(user_id, background_tasks, discipline_tag, trip_id_value, file, db)
    return RedirectResponse(url=f"/passport/{user_id}", status_code=status.HTTP_303_SEE_OTHER)
