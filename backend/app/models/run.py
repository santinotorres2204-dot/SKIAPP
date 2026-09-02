from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, Float, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Run(Base):
    """Bajada trackeada en vivo por GPS (Ride Mode). started_at se fija al
    arrancar (POST /api/runs/start); el resto de las metricas se completa
    recien al terminar (POST /api/runs/{id}/end), asi que quedan nullable
    mientras el run esta en curso."""

    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint("duration_seconds >= 0", name="ck_runs_duration_seconds_range"),
        CheckConstraint("max_speed_kmh >= 0", name="ck_runs_max_speed_range"),
        CheckConstraint("avg_speed_kmh >= 0", name="ck_runs_avg_speed_range"),
        CheckConstraint("distance_km >= 0", name="ck_runs_distance_km_range"),
        CheckConstraint("elevation_gain_m >= 0", name="ck_runs_elevation_gain_range"),
        CheckConstraint("elevation_loss_m >= 0", name="ck_runs_elevation_loss_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_gain_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    elevation_loss_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    gps_track: Mapped[list | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="runs")
