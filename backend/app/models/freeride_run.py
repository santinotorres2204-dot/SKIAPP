from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class FreerideRun(Base):
    """Auto-registro manual de una bajada de freeride, cargada por el usuario
    despues de la bajada. Sin analisis automatico de IA todavia -- los
    scores son una autoevaluacion del propio usuario."""

    __tablename__ = "freeride_runs"
    __table_args__ = (
        CheckConstraint("flow_score BETWEEN 0 AND 100", name="ck_freeride_runs_flow_range"),
        CheckConstraint("control_score BETWEEN 0 AND 100", name="ck_freeride_runs_control_range"),
        CheckConstraint("line_choice_score BETWEEN 0 AND 100", name="ck_freeride_runs_line_choice_range"),
        CheckConstraint("difficulty_score BETWEEN 0 AND 100", name="ck_freeride_runs_difficulty_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    video_id: Mapped[int] = mapped_column(
        ForeignKey("video_uploads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    location_name: Mapped[str] = mapped_column(String(255), nullable=False)
    vertical_m: Mapped[float] = mapped_column(Float, nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    max_gradient: Mapped[float] = mapped_column(Float, nullable=False)
    flow_score: Mapped[int] = mapped_column(Integer, nullable=False)
    control_score: Mapped[int] = mapped_column(Integer, nullable=False)
    line_choice_score: Mapped[int] = mapped_column(Integer, nullable=False)
    difficulty_score: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    video = relationship("VideoUpload", back_populates="freeride_runs")
    user = relationship("User", back_populates="freeride_runs")
