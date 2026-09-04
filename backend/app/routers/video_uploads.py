from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.analysis_job import run_analysis_job
from app.database import get_db
from app.models import VideoUpload
from app.models.enums import Discipline, SportType, TerrainTag
from app.routers.trips import get_trip_or_404
from app.routers.users import get_user_or_404
from app.schemas.video_upload import VideoUploadRead
from app.storage import save_video

router = APIRouter(tags=["video-uploads"])


@router.post("/users/{user_id}/videos", response_model=VideoUploadRead, status_code=status.HTTP_201_CREATED)
def upload_video(
    user_id: int,
    background_tasks: BackgroundTasks,
    discipline_tag: Discipline = Form(...),
    terrain_tag: TerrainTag = Form(...),
    sport_type: SportType = Form(...),
    trip_id: int | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> VideoUpload:
    get_user_or_404(db, user_id)
    if trip_id is not None:
        trip = get_trip_or_404(db, trip_id)
        if trip.user_id != user_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="El viaje no pertenece a este usuario")

    file_url, video_path = save_video(user_id, file)

    video = VideoUpload(
        user_id=user_id,
        trip_id=trip_id,
        file_url=file_url,
        discipline_tag=discipline_tag.value,
        terrain_tag=terrain_tag.value,
        sport_type=sport_type.value,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    background_tasks.add_task(run_analysis_job, video.id, video_path)
    return video


@router.get("/users/{user_id}/videos", response_model=list[VideoUploadRead])
def list_user_videos(user_id: int, db: Session = Depends(get_db)) -> list[VideoUpload]:
    get_user_or_404(db, user_id)
    return (
        db.query(VideoUpload)
        .filter(VideoUpload.user_id == user_id)
        .order_by(VideoUpload.uploaded_at.desc())
        .all()
    )


@router.get("/trips/{trip_id}/videos", response_model=list[VideoUploadRead])
def list_trip_videos(trip_id: int, db: Session = Depends(get_db)) -> list[VideoUpload]:
    get_trip_or_404(db, trip_id)
    return (
        db.query(VideoUpload)
        .filter(VideoUpload.trip_id == trip_id)
        .order_by(VideoUpload.uploaded_at.desc())
        .all()
    )


@router.get("/videos/{video_id}", response_model=VideoUploadRead)
def get_video(video_id: int, db: Session = Depends(get_db)) -> VideoUpload:
    video = db.get(VideoUpload, video_id)
    if video is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Video no encontrado")
    return video
