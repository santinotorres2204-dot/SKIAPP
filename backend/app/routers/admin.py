from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import AnalysisResult, TrainingPlan, Trip, VideoUpload

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
            joinedload(VideoUpload.analysis_result).joinedload(AnalysisResult.training_plans),
        )
        .filter(VideoUpload.id == video_id)
        .one_or_none()
    )
    if video is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Video no encontrado")

    trips = db.query(Trip).filter(Trip.user_id == video.user_id).order_by(Trip.created_at.desc()).all()

    return templates.TemplateResponse(request, "admin/video_detail.html", {"video": video, "trips": trips})


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
