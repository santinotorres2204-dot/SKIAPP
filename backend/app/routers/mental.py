from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel
from app.database import get_db
from app.models.mental_session import MentalSession, FearType, Technique
from app.models.user import User

router = APIRouter(prefix="/api/mental", tags=["mental"])
page_router = APIRouter(tags=["mental-page"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


@page_router.get("/mental")
def mental_page(request: Request, user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return templates.TemplateResponse(request, "mental.html", {"user": user})

class SessionCreate(BaseModel):
    user_id: int
    fear_type: str
    intensity_before: int
    technique_used: str
    notes: Optional[str] = None

class SessionUpdate(BaseModel):
    intensity_after: int
    duration_minutes: Optional[int] = None

@router.post("/session")
def create_session(data: SessionCreate, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == data.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    session = MentalSession(
        user_id=data.user_id,
        fear_type=data.fear_type,
        intensity_before=data.intensity_before,
        technique_used=data.technique_used,
        notes=data.notes
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {"session_id": session.id, "message": "Sesión iniciada"}

@router.patch("/session/{session_id}")
def complete_session(session_id: int, data: SessionUpdate, db: Session = Depends(get_db)):
    session = db.query(MentalSession).filter(MentalSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    session.intensity_after = data.intensity_after
    session.duration_minutes = data.duration_minutes
    db.commit()
    reduction = session.intensity_before - data.intensity_after
    return {
        "message": "Sesión completada",
        "reduction": reduction,
        "great": reduction >= 2
    }

@router.get("/history")
def get_history(user_id: int, db: Session = Depends(get_db)):
    sessions = (
        db.query(MentalSession)
        .filter(MentalSession.user_id == user_id)
        .order_by(desc(MentalSession.created_at))
        .limit(10)
        .all()
    )
    return [
        {
            "id": s.id,
            "fear_type": s.fear_type,
            "intensity_before": s.intensity_before,
            "intensity_after": s.intensity_after,
            "technique_used": s.technique_used,
            "duration_minutes": s.duration_minutes,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "reduction": (s.intensity_before - s.intensity_after) if s.intensity_after else None
        }
        for s in sessions
    ]

@router.get("/stats")
def get_stats(user_id: int, db: Session = Depends(get_db)):
    sessions = (
        db.query(MentalSession)
        .filter(MentalSession.user_id == user_id, MentalSession.intensity_after.isnot(None))
        .all()
    )
    if not sessions:
        return {"total": 0, "avg_reduction": 0, "best_technique": None, "fears": {}}

    total = len(sessions)
    avg_reduction = sum(s.intensity_before - s.intensity_after for s in sessions) / total

    by_technique = {}
    for s in sessions:
        t = s.technique_used
        if t not in by_technique:
            by_technique[t] = []
        by_technique[t].append(s.intensity_before - s.intensity_after)

    best_technique = max(by_technique, key=lambda t: sum(by_technique[t])/len(by_technique[t]))

    fears = {}
    for s in sessions:
        f = s.fear_type
        fears[f] = fears.get(f, 0) + 1

    return {
        "total": total,
        "avg_reduction": round(avg_reduction, 1),
        "best_technique": best_technique,
        "fears": fears
    }
