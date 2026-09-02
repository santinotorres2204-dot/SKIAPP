from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AssessmentResult(Base):
    """Resultado de un Physical Assessment: 5 tests de preparacion fisica
    especifica para ski/snowboard, cargados a mano cada vez que el usuario
    los repite (spec sugiere cada 2 semanas)."""

    __tablename__ = "assessment_results"
    __table_args__ = (
        CheckConstraint("wall_sit_seconds >= 0", name="ck_assessment_results_wall_sit_range"),
        CheckConstraint("single_leg_squat_left >= 0", name="ck_assessment_results_sls_left_range"),
        CheckConstraint("single_leg_squat_right >= 0", name="ck_assessment_results_sls_right_range"),
        CheckConstraint("jump_squat_reps >= 0", name="ck_assessment_results_jump_squat_range"),
        CheckConstraint("plank_seconds >= 0", name="ck_assessment_results_plank_range"),
        CheckConstraint("lateral_bound_reps >= 0", name="ck_assessment_results_lateral_bound_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    wall_sit_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    single_leg_squat_left: Mapped[int] = mapped_column(Integer, nullable=False)
    single_leg_squat_right: Mapped[int] = mapped_column(Integer, nullable=False)
    jump_squat_reps: Mapped[int] = mapped_column(Integer, nullable=False)
    plank_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    lateral_bound_reps: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="assessment_results")
