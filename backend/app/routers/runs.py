from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Run
from app.routers.users import get_user_or_404
from app.schemas.run import RunEndRequest, RunRead, RunStartRequest, RunStartResponse

router = APIRouter(prefix="/api/runs", tags=["runs"])


def get_run_or_404(db: Session, run_id: int) -> Run:
    run = db.get(Run, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Run no encontrado")
    return run


@router.post("/start", response_model=RunStartResponse, status_code=status.HTTP_201_CREATED)
def start_run(payload: RunStartRequest, db: Session = Depends(get_db)) -> RunStartResponse:
    get_user_or_404(db, payload.user_id)
    run = Run(user_id=payload.user_id)
    db.add(run)
    db.commit()
    db.refresh(run)
    return RunStartResponse(run_id=run.id)


@router.post("/{run_id}/end", response_model=RunRead)
def end_run(run_id: int, payload: RunEndRequest, db: Session = Depends(get_db)) -> Run:
    run = get_run_or_404(db, run_id)
    if run.ended_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Este run ya fue terminado")

    now = datetime.now(timezone.utc)
    started_at = run.started_at if run.started_at.tzinfo else run.started_at.replace(tzinfo=timezone.utc)

    run.ended_at = now
    run.duration_seconds = max(0, round((now - started_at).total_seconds()))
    run.gps_track = payload.gps_track
    run.max_speed_kmh = payload.max_speed_kmh
    run.avg_speed_kmh = payload.avg_speed_kmh
    run.distance_km = payload.distance_km
    run.elevation_gain_m = payload.elevation_gain_m
    run.elevation_loss_m = payload.elevation_loss_m
    run.notes = payload.notes
    db.commit()
    db.refresh(run)
    return run


@router.get("/today", response_model=list[RunRead])
def list_today_runs(user_id: int, db: Session = Depends(get_db)) -> list[Run]:
    get_user_or_404(db, user_id)
    today_start = datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc)
    today_end = today_start + timedelta(days=1)
    return (
        db.query(Run)
        .filter(Run.user_id == user_id, Run.started_at >= today_start, Run.started_at < today_end)
        .order_by(Run.started_at.desc())
        .all()
    )


@router.get("/{run_id}", response_model=RunRead)
def get_run(run_id: int, db: Session = Depends(get_db)) -> Run:
    return get_run_or_404(db, run_id)
