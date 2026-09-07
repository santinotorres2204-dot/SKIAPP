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
    FreerideRun,
    SeasonReview,
    SkiRating,
    TrainingPlan,
    TrickCard,
    Trip,
    User,
    VideoUpload,
)
from app.models.enums import Discipline, SkiLevel, SportType, TerrainTag
from app.routers.day_logs import create_day_log
from app.routers.freeride_runs import create_freeride_run
from app.routers.trick_cards import create_trick_card
from app.routers.trips import create_trip, get_or_create_join_code, get_trip_or_404, get_trip_ranking, join_trip
from app.routers.users import create_user, get_user_or_404
from app.routers.video_uploads import get_video_or_404, upload_video
from app.schemas.day_log import DayLogCreate
from app.schemas.freeride_run import FreerideRunCreate
from app.schemas.trick_card import TrickCardCreate
from app.schemas.trip import TripCreate, TripJoinRequest
from app.schemas.user import UserCreate
from app.season_review_comparison import compare_analysis_patterns
from app.training_plan_formatting import parse_training_plan_blocks

router = APIRouter(tags=["passport"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))

# ---------------------------------------------------------------------------
# Flash messages (via query param en el redirect post-submit, sin sesion ni
# cookies). No son mensajes tecnicos: "guardado" o "no se pudo guardar" no
# alcanza para que el usuario entienda que paso -- ver revision de UX de
# formularios. "created" confirma un guardado exitoso (banda verde);
# "error" explica por que una accion no se pudo completar (banda naranja,
# mismo estilo que los errores de formulario).
# ---------------------------------------------------------------------------

SUCCESS_MESSAGES = {
    "account": "¡Tu cuenta se creó correctamente! Bienvenido a Ski App.",
    "trip": "¡Viaje creado! Ya podés subir videos o cargar días una vez que estés en la nieve.",
    "video": "¡Video subido! El análisis se procesa en segundo plano — va a aparecer en tu perfil en unos minutos.",
    "trick_card": "¡Trick Card guardada!",
    "freeride_run": "¡Freeride Run guardado!",
    "day_log": "¡Día cargado! Sumamos tus stats al ranking del viaje.",
    "trip_join": "¡Te uniste al viaje!",
}

ERROR_MESSAGES = {
    "trick_card_wrong_discipline": "Ese video no tiene disciplina \"park\", así que no se le puede cargar una Trick Card.",
    "freeride_run_wrong_discipline": "Ese video no tiene disciplina \"freeride\", así que no se le puede cargar un Freeride Run.",
}


def _flash_messages(request: Request) -> tuple[str | None, str | None]:
    success_message = SUCCESS_MESSAGES.get(request.query_params.get("created", ""))
    error_message = ERROR_MESSAGES.get(request.query_params.get("error", ""))
    return success_message, error_message


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
    trick_cards = (
        db.query(TrickCard)
        .options(joinedload(TrickCard.video))
        .filter(TrickCard.user_id == user_id)
        .order_by(TrickCard.created_at.desc())
        .all()
    )
    freeride_runs = (
        db.query(FreerideRun)
        .options(joinedload(FreerideRun.video))
        .filter(FreerideRun.user_id == user_id)
        .order_by(FreerideRun.created_at.desc())
        .all()
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
    success_message, error_message = _flash_messages(request)

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
            "trick_cards": trick_cards,
            "freeride_runs": freeride_runs,
            "success_message": success_message,
            "error_message": error_message,
        },
    )


# ---------------------------------------------------------------------------
# Home / login por email. Sin auth ni sesion todavia -- resuelve unicamente
# "como llego a mi perfil sin memorizar el user_id".
# ---------------------------------------------------------------------------

@router.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {"error": None})


@router.post("/")
def home_login(request: Request, email: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return templates.TemplateResponse(
            request,
            "index.html",
            {"error": "No encontramos ninguna cuenta con ese email."},
            status_code=404,
        )
    return RedirectResponse(url=f"/passport/{user.id}", status_code=status.HTTP_303_SEE_OTHER)


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
    # ski_level/years_skiing como str: si se declaran tipados aca (Enum/int),
    # FastAPI los valida ANTES de entrar a la funcion y devuelve su propio
    # JSON crudo de error en vez de pasar por el try/except de abajo. Se
    # valida todo a mano con UserCreate para que cualquier dato invalido
    # (email con formato raro, años negativos, nivel inexistente) termine
    # siempre en el mismo mensaje amigable.
    ski_level: str = Form(...),
    years_skiing: str = Form(...),
    db: Session = Depends(get_db),
):
    try:
        payload = UserCreate(name=name, email=email, ski_level=ski_level, years_skiing=years_skiing)
        user = create_user(payload, db)
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "register.html",
            {
                "error": "Revisá los datos ingresados: el nombre no puede estar vacío, el email tiene que ser válido y los años esquiando no pueden ser negativos.",
                "ski_levels": list(SkiLevel),
            },
            status_code=422,
        )
    except HTTPException as exc:
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": exc.detail, "ski_levels": list(SkiLevel)},
            status_code=exc.status_code,
        )

    return RedirectResponse(url=f"/passport/{user.id}?created=account", status_code=status.HTTP_303_SEE_OTHER)


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
    # str en vez de date: si se declara "date" aca, FastAPI valida el formato
    # ANTES de entrar a la funcion y devuelve su propio JSON crudo de error
    # en vez del template de abajo. Se valida a mano con TripCreate.
    start_date: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_user_or_404(db, user_id)
    try:
        payload = TripCreate(destination=destination, start_date=start_date)
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "trip_form.html",
            {"user": user, "error": "Revisá los datos ingresados: el destino no puede estar vacío y la fecha tiene que ser válida."},
            status_code=422,
        )

    create_trip(user_id, payload, db)
    return RedirectResponse(url=f"/passport/{user_id}?created=trip", status_code=status.HTTP_303_SEE_OTHER)


# ---------------------------------------------------------------------------
# Subir video (spec seccion 7, pantalla 4).
# ---------------------------------------------------------------------------

def _video_form_context(db: Session, user: User, error: str | None = None) -> dict:
    trips = db.query(Trip).filter(Trip.user_id == user.id).order_by(Trip.created_at.desc()).all()
    return {
        "user": user,
        "trips": trips,
        "disciplines": list(Discipline),
        "terrains": list(TerrainTag),
        "sports": list(SportType),
        "error": error,
    }


@router.get("/passport/{user_id}/videos/new")
def new_video_form(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = get_user_or_404(db, user_id)
    return templates.TemplateResponse(request, "video_form.html", _video_form_context(db, user))


@router.post("/passport/{user_id}/videos")
def new_video_submit(
    request: Request,
    user_id: int,
    background_tasks: BackgroundTasks,
    # str en vez de Discipline/TerrainTag/SportType: si se declaran tipados
    # aca, FastAPI los valida ANTES de entrar a la funcion y devuelve su
    # propio JSON crudo de error en vez del template de abajo. Se convierten
    # a mano en el try de abajo.
    discipline_tag: str = Form(...),
    terrain_tag: str = Form(...),
    sport_type: str = Form(...),
    # str en vez de int|None: un <select> con la opcion "sin viaje" manda "",
    # que Pydantic no puede parsear como int -- se convierte a mano abajo.
    trip_id: str = Form(default=""),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    user = get_user_or_404(db, user_id)
    try:
        discipline = Discipline(discipline_tag)
        terrain = TerrainTag(terrain_tag)
        sport = SportType(sport_type)
    except ValueError:
        return templates.TemplateResponse(
            request,
            "video_form.html",
            _video_form_context(db, user, error="Elegí un deporte, disciplina y terreno válidos de la lista."),
            status_code=422,
        )

    try:
        trip_id_value = int(trip_id) if trip_id else None
    except ValueError:
        return templates.TemplateResponse(
            request,
            "video_form.html",
            _video_form_context(db, user, error="El viaje seleccionado no es válido."),
            status_code=400,
        )

    try:
        upload_video(user_id, background_tasks, discipline, terrain, sport, trip_id_value, file, db)
    except HTTPException as exc:
        return templates.TemplateResponse(
            request,
            "video_form.html",
            _video_form_context(db, user, error=exc.detail),
            status_code=exc.status_code,
        )

    return RedirectResponse(url=f"/passport/{user_id}?created=video", status_code=status.HTTP_303_SEE_OTHER)


# ---------------------------------------------------------------------------
# Trick Card (park) y Freeride Run (freeride): auto-registro manual que el
# usuario carga sobre un video ya subido. Sin analisis automatico de IA
# todavia -- la deteccion de patrones de park/freeride queda para mas
# adelante; hoy los scores son una autoevaluacion del propio usuario.
# ---------------------------------------------------------------------------

def _get_own_video_or_404(db: Session, user_id: int, video_id: int) -> VideoUpload:
    video = get_video_or_404(db, video_id)
    if video.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Video no encontrado")
    return video


@router.get("/passport/{user_id}/videos/{video_id:int}/trick-card/new")
def new_trick_card_form(request: Request, user_id: int, video_id: int, db: Session = Depends(get_db)):
    user = get_user_or_404(db, user_id)
    video = _get_own_video_or_404(db, user_id, video_id)
    if video.discipline_tag != "park":
        # No hay un "formulario invalido" que reintentar aca (la disciplina
        # del video es un dato fijo, no algo que el usuario tipeo) -- se
        # vuelve al perfil con un mensaje claro en vez de una excepcion cruda.
        return RedirectResponse(
            url=f"/passport/{user_id}?error=trick_card_wrong_discipline", status_code=status.HTTP_303_SEE_OTHER
        )
    return templates.TemplateResponse(request, "trick_card_form.html", {"user": user, "video": video, "error": None})


@router.post("/passport/{user_id}/videos/{video_id:int}/trick-card")
def new_trick_card_submit(
    request: Request,
    user_id: int,
    video_id: int,
    trick_name: str = Form(...),
    # str en vez de int: si se declaran tipados aca, FastAPI los valida
    # ANTES de entrar a la funcion y devuelve su propio JSON crudo de error
    # en vez del template de abajo. Se valida a mano con TrickCardCreate.
    difficulty: str = Form(...),
    execution_score: str = Form(...),
    landing_score: str = Form(...),
    style_score: str = Form(...),
    consistency_score: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_user_or_404(db, user_id)
    video = _get_own_video_or_404(db, user_id, video_id)
    try:
        payload = TrickCardCreate(
            trick_name=trick_name,
            difficulty=difficulty,
            execution_score=execution_score,
            landing_score=landing_score,
            style_score=style_score,
            consistency_score=consistency_score,
        )
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "trick_card_form.html",
            {"user": user, "video": video, "error": "Revisa los datos ingresados (dificultad 1-10, scores 0-100)."},
            status_code=422,
        )

    create_trick_card(video_id, payload, db)
    return RedirectResponse(url=f"/passport/{user_id}?created=trick_card", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/passport/{user_id}/videos/{video_id:int}/freeride-run/new")
def new_freeride_run_form(request: Request, user_id: int, video_id: int, db: Session = Depends(get_db)):
    user = get_user_or_404(db, user_id)
    video = _get_own_video_or_404(db, user_id, video_id)
    if video.discipline_tag != "freeride":
        return RedirectResponse(
            url=f"/passport/{user_id}?error=freeride_run_wrong_discipline", status_code=status.HTTP_303_SEE_OTHER
        )
    return templates.TemplateResponse(
        request, "freeride_run_form.html", {"user": user, "video": video, "error": None}
    )


@router.post("/passport/{user_id}/videos/{video_id:int}/freeride-run")
def new_freeride_run_submit(
    request: Request,
    user_id: int,
    video_id: int,
    location_name: str = Form(...),
    # str en vez de float/int: si se declaran tipados aca, FastAPI los valida
    # ANTES de entrar a la funcion y devuelve su propio JSON crudo de error
    # en vez del template de abajo. Se valida a mano con FreerideRunCreate.
    vertical_m: str = Form(...),
    distance_km: str = Form(...),
    max_gradient: str = Form(...),
    flow_score: str = Form(...),
    control_score: str = Form(...),
    line_choice_score: str = Form(...),
    difficulty_score: str = Form(...),
    db: Session = Depends(get_db),
):
    user = get_user_or_404(db, user_id)
    video = _get_own_video_or_404(db, user_id, video_id)
    try:
        payload = FreerideRunCreate(
            location_name=location_name,
            vertical_m=vertical_m,
            distance_km=distance_km,
            max_gradient=max_gradient,
            flow_score=flow_score,
            control_score=control_score,
            line_choice_score=line_choice_score,
            difficulty_score=difficulty_score,
        )
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "freeride_run_form.html",
            {"user": user, "video": video, "error": "Revisa los datos ingresados (los scores van de 0 a 100)."},
            status_code=422,
        )

    create_freeride_run(video_id, payload, db)
    return RedirectResponse(url=f"/passport/{user_id}?created=freeride_run", status_code=status.HTTP_303_SEE_OTHER)


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
    # str en vez de date/float/int: si se declaran tipados aca, FastAPI los
    # valida ANTES de entrar a la funcion y devuelve su propio JSON crudo de
    # error en vez del template de abajo. Se valida a mano con DayLogCreate.
    date: str = Form(...),
    distance_km: str = Form(...),
    elevation_gain_m: str = Form(...),
    max_speed_kmh: str = Form(...),
    runs_count: str = Form(...),
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
            {
                "user": user,
                "trip": trip,
                "error": "Revisá los datos ingresados: la fecha tiene que ser válida y ningún valor puede ser negativo.",
            },
            status_code=422,
        )

    create_day_log(user_id, trip_id, payload, db)
    return RedirectResponse(url=f"/passport/{user_id}?created=day_log", status_code=status.HTTP_303_SEE_OTHER)


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
    success_message, error_message = _flash_messages(request)

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
            "success_message": success_message,
            "error_message": error_message,
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

    return RedirectResponse(
        url=f"/passport/{user_id}/trips/{trip.id}?created=trip_join", status_code=status.HTTP_303_SEE_OTHER
    )
