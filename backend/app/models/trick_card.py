from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TrickCard(Base):
    """Auto-registro manual de un truco de park, cargado por el usuario
    despues de la bajada. Sin analisis automatico de IA todavia (la
    deteccion de patrones de park queda para mas adelante) -- los scores
    son una autoevaluacion del propio usuario."""

    __tablename__ = "trick_cards"
    __table_args__ = (
        CheckConstraint("difficulty BETWEEN 1 AND 10", name="ck_trick_cards_difficulty_range"),
        CheckConstraint("execution_score BETWEEN 0 AND 100", name="ck_trick_cards_execution_range"),
        CheckConstraint("landing_score BETWEEN 0 AND 100", name="ck_trick_cards_landing_range"),
        CheckConstraint("style_score BETWEEN 0 AND 100", name="ck_trick_cards_style_range"),
        CheckConstraint("consistency_score BETWEEN 0 AND 100", name="ck_trick_cards_consistency_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(
        ForeignKey("video_uploads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    trick_name: Mapped[str] = mapped_column(String(255), nullable=False)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)
    execution_score: Mapped[int] = mapped_column(Integer, nullable=False)
    landing_score: Mapped[int] = mapped_column(Integer, nullable=False)
    style_score: Mapped[int] = mapped_column(Integer, nullable=False)
    consistency_score: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    video = relationship("VideoUpload", back_populates="trick_cards")
    user = relationship("User", back_populates="trick_cards")
