from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import AnalysisResult, SeasonReview, SkiRating, TrainingPlan, Trip, VideoUpload
from app.models.enums import Discipline
from app.prompt_builder import build_training_prompt
from app.routers.ski_ratings import upsert_ski_rating_row
from app.storage import save_season_review_video

router = APIRouter(prefix="/admin", tags=["admin"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@router.get("/videos")
def list_videos(request: Request, estado: str = "pendientes", db: Session = Depends(get_db)):
    videos = (
        db.query(VideoUpload)
        .options(
            joinedload(VideoUpload.user),
            joinedload(VideoUpload.analysis_result).joinedload(AnalysisResult.training_plans),
        )
        .order_by(VideoUpload.uploaded_at.desc())
        .all()
    )

    rows = [
        {"video": v, "reviewed": bool(v.analysis_result and v.analysis_result.training_plans)}
        for v in videos
    ]
    if estado != "todos":
        rows = [r for r in rows if not r["reviewed"]]

    return templates.TemplateResponse(request, "admin/videos_list.html", {"rows": rows, "estado": estado})


@router.get("/videos/{video_id}")
def video_detail(request: Request, video_id: int, db: Session = Depends(get_db)):
    video = (
        db.query(VideoUpload)
        .options(
            joinedload(VideoUpload.user),
            joinedload(VideoUpload.trip),
            joinedload(VideoUpload.analysis_result).joinedload(AnalysisResult.training_plans),
        )
        .filter(VideoUpload.id == video_id)
        .one_or_none()
    )
    if video is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Video no encontrado")

    trips = db.query(Trip).filter(Trip.user_id == video.user_id).order_by(Trip.created_at.desc()).all()

    prompt = build_training_prompt(video, video.analysis_result) if video.analysis_result else None

    return templates.TemplateResponse(
        request, "admin/video_detail.html", {"video": video, "trips": trips, "prompt": prompt}
    )


@router.post("/videos/{video_id}/training-plan")
def create_training_plan(
    video_id: int,
    trip_id: int = Form(...),
    content: str = Form(...),
    db: Session = Depends(get_db),
):
    video = db.get(VideoUpload, video_id)
    if video is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Video no encontrado")
    if video.analysis_result is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="El video todavia no tiene un analisis")
    if not content.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="El contenido del plan no puede estar vacio")

    trip = db.get(Trip, trip_id)
    if trip is None or trip.user_id != video.user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="El viaje no pertenece a este usuario")

    plan = TrainingPlan(
        user_id=video.user_id,
        trip_id=trip_id,
        content=content,
        based_on_analysis_id=video.analysis_result.id,
    )
    db.add(plan)
    db.commit()

    return RedirectResponse(url=f"/admin/videos/{video_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/trips")
def list_trips(request: Request, estado: str = "pendientes", db: Session = Depends(get_db)):
    trips = (
        db.query(Trip)
        .options(joinedload(Trip.user), joinedload(Trip.season_reviews))
        .order_by(Trip.start_date.desc())
        .all()
    )

    rows = [{"trip": t, "reviewed": bool(t.season_reviews)} for t in trips]
    if estado != "todos":
        rows = [r for r in rows if not r["reviewed"]]

    return templates.TemplateResponse(request, "admin/trips_list.html", {"rows": rows, "estado": estado})


@router.get("/trips/{trip_id}/season-review")
def season_review_form(request: Request, trip_id: int, db: Session = Depends(get_db)):
    trip = (
        db.query(Trip)
        .options(joinedload(Trip.user), joinedload(Trip.season_reviews))
        .filter(Trip.id == trip_id)
        .one_or_none()
    )
    if trip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Viaje no encontrado")

    ratings = db.query(SkiRating).filter(SkiRating.user_id == trip.user_id).order_by(SkiRating.discipline).all()

    return templates.TemplateResponse(
        request,
        "admin/season_review_form.html",
        {"trip": trip, "ratings": ratings, "disciplines": list(Discipline)},
    )


@router.post("/trips/{trip_id}/season-review")
def create_season_review(
    trip_id: int,
    discipline: Discipline = Form(...),
    score_after: int = Form(...),
    confidence_after: int = Form(...),
    video: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    trip = db.get(Trip, trip_id)
    if trip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Viaje no encontrado")
    if not (0 <= score_after <= 100) or not (0 <= confidence_after <= 100):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Score y confidence deben estar entre 0 y 100")

    existing = (
        db.query(SkiRating)
        .filter(SkiRating.user_id == trip.user_id, SkiRating.discipline == discipline.value)
        .one_or_none()
    )
    rating_before = {
        "discipline": discipline.value,
        "score": existing.score if existing else None,
        "confidence_score": existing.confidence_score if existing else None,
    }

    # coach_verified=True: esta actualizacion la hace el fundador a mano, a
    # diferencia del PUT /ski-ratings generico (que no lo fuerza).
    rating = upsert_ski_rating_row(
        db, trip.user_id, discipline.value, score_after, confidence_after, coach_verified=True
    )
    rating_after = {
        "discipline": discipline.value,
        "score": rating.score,
        "confidence_score": rating.confidence_score,
    }

    video_url, _ = save_season_review_video(trip.user_id, video)

    review = SeasonReview(
        user_id=trip.user_id,
        trip_id=trip.id,
        comparison_video_url=video_url,
        rating_before=rating_before,
        rating_after=rating_after,
    )
    db.add(review)
    db.commit()

    return RedirectResponse(url=f"/admin/trips/{trip_id}/season-review", status_code=status.HTTP_303_SEE_OTHER)
