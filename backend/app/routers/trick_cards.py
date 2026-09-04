from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import TrickCard
from app.routers.users import get_user_or_404
from app.routers.video_uploads import get_video_or_404
from app.schemas.trick_card import TrickCardCreate, TrickCardRead

router = APIRouter(tags=["trick-cards"])


@router.post("/videos/{video_id}/trick-cards", response_model=TrickCardRead, status_code=status.HTTP_201_CREATED)
def create_trick_card(video_id: int, payload: TrickCardCreate, db: Session = Depends(get_db)) -> TrickCard:
    video = get_video_or_404(db, video_id)
    if video.discipline_tag != "park":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden cargar Trick Cards en videos con disciplina 'park'",
        )
    trick_card = TrickCard(video_id=video_id, user_id=video.user_id, **payload.model_dump())
    db.add(trick_card)
    db.commit()
    db.refresh(trick_card)
    return trick_card


@router.get("/videos/{video_id}/trick-cards", response_model=list[TrickCardRead])
def list_video_trick_cards(video_id: int, db: Session = Depends(get_db)) -> list[TrickCard]:
    get_video_or_404(db, video_id)
    return (
        db.query(TrickCard)
        .filter(TrickCard.video_id == video_id)
        .order_by(TrickCard.created_at.desc())
        .all()
    )


@router.get("/users/{user_id}/trick-cards", response_model=list[TrickCardRead])
def list_user_trick_cards(user_id: int, db: Session = Depends(get_db)) -> list[TrickCard]:
    get_user_or_404(db, user_id)
    return (
        db.query(TrickCard)
        .filter(TrickCard.user_id == user_id)
        .order_by(TrickCard.created_at.desc())
        .all()
    )
