from datetime import date as date_type, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DayLog(Base):
    """Recap diario cargado a mano por el usuario (spec seccion 7 etapa 2:
    Day Recap). Sin tracking GPS real -- eso queda para la app nativa."""

    __tablename__ = "day_logs"
    __table_args__ = (
        CheckConstraint("distance_km >= 0", name="ck_day_logs_distance_km_range"),
        CheckConstraint("elevation_gain_m >= 0", name="ck_day_logs_elevation_gain_range"),
        CheckConstraint("max_speed_kmh >= 0", name="ck_day_logs_max_speed_range"),
        CheckConstraint("runs_count >= 0", name="ck_day_logs_runs_count_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    elevation_gain_m: Mapped[int] = mapped_column(Integer, nullable=False)
    max_speed_kmh: Mapped[float] = mapped_column(Float, nullable=False)
    runs_count: Mapped[int] = mapped_column(Integer, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    trip = relationship("Trip", back_populates="day_logs")
    user = relationship("User", back_populates="day_logs")
