from pathlib import Path

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.assessment_comparison import compare_assessments, leg_asymmetry_pct
from app.database import get_db
from app.models import AssessmentResult, User
from app.routers.users import get_user_or_404
from app.schemas.assessment import AssessmentRead, AssessmentSubmit, AssessmentSubmitResponse

router = APIRouter(prefix="/api/assessment", tags=["assessment"])
page_router = APIRouter(tags=["assessment-page"])

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _latest(db: Session, user_id: int) -> AssessmentResult | None:
    return (
        db.query(AssessmentResult)
        .filter(AssessmentResult.user_id == user_id)
        .order_by(AssessmentResult.completed_at.desc())
        .first()
    )


@router.post("/submit", response_model=AssessmentSubmitResponse, status_code=status.HTTP_201_CREATED)
def submit_assessment(
    user_id: int, payload: AssessmentSubmit, db: Session = Depends(get_db)
) -> AssessmentSubmitResponse:
    get_user_or_404(db, user_id)

    previous = _latest(db, user_id)

    result = AssessmentResult(user_id=user_id, **payload.model_dump())
    db.add(result)
    db.commit()
    db.refresh(result)

    comparison = compare_assessments(previous, result) if previous is not None else None

    return AssessmentSubmitResponse(result=AssessmentRead.model_validate(result), comparison=comparison)


@router.get("/history", response_model=list[AssessmentRead])
def get_history(user_id: int, db: Session = Depends(get_db)) -> list[AssessmentResult]:
    get_user_or_404(db, user_id)
    return (
        db.query(AssessmentResult)
        .filter(AssessmentResult.user_id == user_id)
        .order_by(AssessmentResult.completed_at.desc())
        .limit(10)
        .all()
    )


@router.get("/latest", response_model=AssessmentRead | None)
def get_latest(user_id: int, db: Session = Depends(get_db)) -> AssessmentResult | None:
    get_user_or_404(db, user_id)
    return _latest(db, user_id)


@page_router.get("/assessment")
def assessment_page(request: Request, user_id: int | None = None, db: Session = Depends(get_db)):
    """Physical Assessment. Sin login todavia (ver app/routers/passport.py) --
    mismo criterio que /ride y /coach: sin ?user_id= caemos al primer usuario
    registrado."""
    if user_id is not None:
        user = get_user_or_404(db, user_id)
    else:
        user = db.query(User).order_by(User.id).first()
        if user is None:
            return RedirectResponse(url="/register", status_code=303)

    assessments = (
        db.query(AssessmentResult)
        .filter(AssessmentResult.user_id == user.id)
        .order_by(AssessmentResult.completed_at.asc())
        .all()
    )

    progress = None
    asymmetry_warning = False
    if len(assessments) >= 2:
        oldest, newest = assessments[0], assessments[-1]
        progress = compare_assessments(oldest, newest)
        asymmetry_warning = leg_asymmetry_pct(newest) > 20

    return templates.TemplateResponse(
        request,
        "assessment.html",
        {
            "user": user,
            "assessment_count": len(assessments),
            "progress": progress,
            "asymmetry_warning": asymmetry_warning,
        },
    )
