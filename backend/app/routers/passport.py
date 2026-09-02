from datetime import date
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session, joinedload

from app.achievements import compute_achievements
from app.database import get_db
from app.models import (
    AnalysisResult,
    AssessmentResult,
    DayLog,
    SeasonReview,
    SkiRating,
    TrainingPlan,
    Trip,
    User,
    VideoUpload,
)
from app.models.enums import Discipline, SkiLevel
from app.routers.day_logs import create_day_log
from app.routers.trips import create_trip, get_or_create_join_code, get_trip_or_404, get_trip_ranking, join_trip
from app.routers.users import create_user, get_user_or_404
from app.routers.video_uploads import upload_video
from app.schemas.day_log import DayLogCreate
from app.schemas.trip import TripCreate, TripJoinRequest
from app.schemas.user import UserCreate
from app.season_review_comparison import compare_analysis_patterns
from app.training_plan_formatting import parse_training_plan_blocks

router = APIRouter(tags=["passport"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _find_matching_analysis(
    db: Session, user_id: int, discipline: str | None, confidence_score: int | None
) -> AnalysisResult | None:
    """Encuentra el AnalysisResult del video que probablemente corresponde a
    un snapshot rating_before/rating_after de un SeasonReview.

    No hay FK directa entre SeasonReview y VideoUpload -- rating_before /
    rating_after son snapshots numericos sueltos (ver admin.create_season_review).
    Como heuristica, matcheamos por (disciplina, confidence_score) del video
    mas reciente; si no hay coincidencia (por ejemplo el score "despues" lo
    tipeo el coach a mano sin que exista un video con ese confidence exacto),
    devolvemos None y el caller lo muestra como "sin datos" -- no inventamos
    una relacion que no esta en los datos.
    """
    if not discipline or confidence_score is None:
        return None

    return (
        db.query(AnalysisResult)
        .join(VideoUpload, VideoUpload.id == AnalysisResult.video_id)
        .filter(
            VideoUpload.user_id == user_id,
            VideoUpload.discipline_tag == discipline,
            AnalysisResult.confidence_score == confidence_score,
        )
        .order_by(VideoUpload.uploaded_at.desc())
        .first()
    )


@router.get("/passport/{user_id}")
def passport(request: Request, user_id: int, db: Session = Depends(get_db)):
    """Vista de solo lectura del lado del usuario (spec seccion 7, pantallas
    5-7): Ski Passport (perfil + historial de viajes), Ski Card (rating por
    disciplina) y los training plans cargados por el fundador. Sin login
    todavia -- se accede por URL con el user_id, igual que el panel admin.
    """
    user = get_user_or_404(db, user_id)

    trips = db.query(Trip).filter(Trip.user_id == user_id).order_by(Trip.start_date.desc()).all()
    videos = (
        db.query(VideoUpload)
        .options(joinedload(VideoUpload.trip), joinedload(VideoUpload.analysis_result))
        .filter(VideoUpload.user_id == user_id)
        .order_by(VideoUpload.uploaded_at.desc())
        .all()
    )
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
    day_logs = db.query(DayLog).filter(DayLog.user_id == user_id).all()
    achievements = compute_achievements(day_logs)
    latest_assessment = (
        db.query(AssessmentResult)
        .filter(AssessmentResult.user_id == user_id)
        .order_by(AssessmentResult.completed_at.desc())
        .first()
    )
    training_plans_view = [
        {"plan": plan, "blocks": parse_training_plan_blocks(plan.content)} for plan in training_plans
    ]
    season_reviews_view = []
    for sr in season_reviews:
        before_analysis = _find_matching_analysis(
            db, user_id, sr.rating_before.get("discipline"), sr.rating_before.get("confidence_score")
        )
        after_analysis = _find_matching_analysis(
            db, user_id, sr.rating_after.get("discipline"), sr.rating_after.get("confidence_score")
        )
        season_reviews_view.append(
            {
                "review": sr,
                "before_analysis": before_analysis,
                "after_analysis": after_analysis,
                "pattern_rows": compare_analysis_patterns(before_analysis, after_analysis),
            }
        )
    # "Rating principal" para la tarjeta resumen: la disciplina con mejor
    # score (no hay un concepto de "disciplina favorita" en el modelo).
    top_rating = max(ratings, key=lambda r: r.score, default=None)
    earned_achievements = [a for a in achievements if a.earned]

    return templates.TemplateResponse(
        request,
        "passport.html",
        {
            "user": user,
            "trips": trips,
            "videos": videos,
            "ratings": ratings,
            "top_rating": top_rating,
            "training_plans": training_plans_view,
            "season_reviews": season_reviews_view,
            "achievements": achievements,
            "earned_achievements": earned_achievements,
            "latest_assessment": latest_assessment,
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


# ---------------------------------------------------------------------------
# Day Recap (spec seccion 7 etapa 2). Sin tracking GPS real: el usuario carga
# los numeros a mano despues de esquiar.
# ---------------------------------------------------------------------------

@router.get("/passport/{user_id}/trips/{trip_id:int}/day-logs/new")
def new_day_log_form(request: Request, user_id: int, trip_id: int, db: Session = Depends(get_db)):
    user = get_user_or_404(db, user_id)
    trip = get_trip_or_404(db, trip_id)
    return templates.TemplateResponse(request, "day_log_form.html", {"user": user, "trip": trip, "error": None})


@router.post("/passport/{user_id}/trips/{trip_id:int}/day-logs")
def new_day_log_submit(
    request: Request,
    user_id: int,
    trip_id: int,
    date: date = Form(...),
    distance_km: float = Form(...),
    elevation_gain_m: int = Form(...),
    max_speed_kmh: float = Form(...),
    runs_count: int = Form(...),
    note: str = Form(default=""),
    db: Session = Depends(get_db),
):
    user = get_user_or_404(db, user_id)
    trip = get_trip_or_404(db, trip_id)
    try:
        payload = DayLogCreate(
            date=date,
            distance_km=distance_km,
            elevation_gain_m=elevation_gain_m,
            max_speed_kmh=max_speed_kmh,
            runs_count=runs_count,
            note=note or None,
        )
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "day_log_form.html",
            {"user": user, "trip": trip, "error": "Revisa los datos ingresados (ningun valor puede ser negativo)."},
            status_code=422,
        )

    create_day_log(user_id, trip_id, payload, db)
    return RedirectResponse(url=f"/passport/{user_id}", status_code=status.HTTP_303_SEE_OTHER)


# ---------------------------------------------------------------------------
# Social Ride (spec seccion 7 etapa 2): vista de un viaje (participantes +
# ranking) y el flujo para sumarse con un codigo de invitacion.
# ---------------------------------------------------------------------------

@router.get("/passport/{user_id}/trips/{trip_id:int}")
def trip_detail(request: Request, user_id: int, trip_id: int, db: Session = Depends(get_db)):
    user = get_user_or_404(db, user_id)
    trip = get_trip_or_404(db, trip_id)

    participants = (
        db.query(User).filter(User.id.in_(trip.participant_user_ids)).order_by(User.name).all()
    )
    ranking = get_trip_ranking(trip_id, db)
    day_logs = (
        db.query(DayLog)
        .options(joinedload(DayLog.user))
        .filter(DayLog.trip_id == trip_id)
        .order_by(DayLog.date.desc())
        .all()
    )

    return templates.TemplateResponse(
        request,
        "trip_detail.html",
        {
            "user": user,
            "trip": trip,
            "is_owner": trip.user_id == user_id,
            "participants": participants,
            "ranking": ranking,
            "day_logs": day_logs,
        },
    )


@router.post("/passport/{user_id}/trips/{trip_id:int}/join-code")
def generate_join_code(user_id: int, trip_id: int, db: Session = Depends(get_db)):
    get_user_or_404(db, user_id)
    get_or_create_join_code(trip_id, db)
    return RedirectResponse(url=f"/passport/{user_id}/trips/{trip_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/passport/{user_id}/trips/join")
def join_trip_form(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = get_user_or_404(db, user_id)
    return templates.TemplateResponse(request, "trip_join_form.html", {"user": user, "error": None})


@router.post("/passport/{user_id}/trips/join")
def join_trip_submit(request: Request, user_id: int, code: str = Form(...), db: Session = Depends(get_db)):
    user = get_user_or_404(db, user_id)
    try:
        payload = TripJoinRequest(code=code)
        trip = join_trip(user_id, payload, db)
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "trip_join_form.html",
            {"user": user, "error": "El codigo tiene que tener entre 6 y 12 caracteres."},
            status_code=422,
        )
    except HTTPException as exc:
        return templates.TemplateResponse(
            request,
            "trip_join_form.html",
            {"user": user, "error": exc.detail},
            status_code=exc.status_code,
        )

    return RedirectResponse(url=f"/passport/{user_id}/trips/{trip.id}", status_code=status.HTTP_303_SEE_OTHER)
