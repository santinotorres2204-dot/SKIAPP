from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ChatMessage
from app.models.enums import ChatRole
from app.routers.users import get_user_or_404
from app.schemas.chat import ChatMessageRead, ChatMessageRequest, ChatMessageResponse
from app.services.coach import generate_mock_response

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/message", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
def post_message(user_id: int, payload: ChatMessageRequest, db: Session = Depends(get_db)) -> ChatMessageResponse:
    # Sin login todavia (ver app/routers/passport.py) -- user_id viaja por
    # query param, igual criterio que /api/runs.
    user = get_user_or_404(db, user_id)

    user_message = ChatMessage(user_id=user_id, role=ChatRole.USER.value, content=payload.message)
    db.add(user_message)
    db.commit()

    response_text = generate_mock_response(payload.message, user)

    assistant_message = ChatMessage(user_id=user_id, role=ChatRole.ASSISTANT.value, content=response_text)
    db.add(assistant_message)
    db.commit()
    db.refresh(assistant_message)

    return ChatMessageResponse(response=response_text, message_id=assistant_message.id)


@router.get("/history", response_model=list[ChatMessageRead])
def get_history(user_id: int, db: Session = Depends(get_db)) -> list[ChatMessage]:
    get_user_or_404(db, user_id)
    # Ultimos 50 por created_at desc y despues invertimos: la UI del chat
    # necesita orden cronologico ascendente para pintar los mensajes.
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(50)
        .all()
    )
    return list(reversed(messages))
