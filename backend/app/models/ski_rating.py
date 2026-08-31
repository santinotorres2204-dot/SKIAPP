from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import Discipline, sql_in_values


class SkiRating(Base):
    __tablename__ = "ski_ratings"
    __table_args__ = (
        CheckConstraint(f"discipline IN ({sql_in_values(Discipline)})", name="ck_ski_ratings_discipline"),
        CheckConstraint("score >= 0 AND score <= 100", name="ck_ski_ratings_score_range"),
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_ski_ratings_confidence_range"),
        # Asuncion: el rating es "el actual por disciplina" (por eso updated_at
        # y no created_at + historial), no un log de eventos.
        UniqueConstraint("user_id", "discipline", name="uq_ski_ratings_user_discipline"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    discipline: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False)
    coach_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="ski_ratings")
