from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AnalysisResult(Base):
    __tablename__ = "analysis_results"
    __table_args__ = (
        CheckConstraint("confidence_score >= 0 AND confidence_score <= 100", name="ck_analysis_results_confidence_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # unique=True: un AnalysisResult por VideoUpload (relacion uno a uno).
    video_id: Mapped[int] = mapped_column(
        ForeignKey("video_uploads.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    detected_patterns: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    confidence_score: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_pose_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Resumen en lenguaje simple para el panel de administrador (spec seccion 6/9).
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    video = relationship("VideoUpload", back_populates="analysis_result")
    training_plans = relationship("TrainingPlan", back_populates="based_on_analysis")
