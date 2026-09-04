from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FreerideRun
from app.routers.users import get_user_or_404
from app.routers.video_uploads import get_video_or_404
from app.schemas.freeride_run import FreerideRunCreate, FreerideRunRead

router = APIRouter(tags=["freeride-runs"])


@router.post("/videos/{video_id}/freeride-runs", response_model=FreerideRunRead, status_code=status.HTTP_201_CREATED)
def create_freeride_run(video_id: int, payload: FreerideRunCreate, db: Session = Depends(get_db)) -> FreerideRun:
    video = get_video_or_404(db, video_id)
    if video.discipline_tag != "freeride":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden cargar Freeride Runs en videos con disciplina 'freeride'",
        )
    freeride_run = FreerideRun(video_id=video_id, user_id=video.user_id, **payload.model_dump())
    db.add(freeride_run)
    db.commit()
    db.refresh(freeride_run)
    return freeride_run


@router.get("/videos/{video_id}/freeride-runs", response_model=list[FreerideRunRead])
def list_video_freeride_runs(video_id: int, db: Session = Depends(get_db)) -> list[FreerideRun]:
    get_video_or_404(db, video_id)
    return (
        db.query(FreerideRun)
        .filter(FreerideRun.video_id == video_id)
        .order_by(FreerideRun.created_at.desc())
        .all()
    )


@router.get("/users/{user_id}/freeride-runs", response_model=list[FreerideRunRead])
def list_user_freeride_runs(user_id: int, db: Session = Depends(get_db)) -> list[FreerideRun]:
    get_user_or_404(db, user_id)
    return (
        db.query(FreerideRun)
        .filter(FreerideRun.user_id == user_id)
        .order_by(FreerideRun.created_at.desc())
        .all()
    )
