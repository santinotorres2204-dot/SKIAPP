from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import ChatRole, sql_in_values


class ChatMessage(Base):
    """Un mensaje del historial de AI Ski Coach Chat. Por ahora las respuestas
    'assistant' las genera app/services/coach.generate_mock_response() (mock
    sin API externa); el modelo ya queda listo para cuando eso se reemplace
    por una llamada real a Claude."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(f"role IN ({sql_in_values(ChatRole)})", name="ck_chat_messages_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="chat_messages")
