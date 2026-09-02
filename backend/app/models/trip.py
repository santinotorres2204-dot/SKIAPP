from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import TripStatus, sql_in_values


class Trip(Base):
    __tablename__ = "trips"
    __table_args__ = (
        CheckConstraint(f"status IN ({sql_in_values(TripStatus)})", name="ck_trips_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    destination: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=TripStatus.PREPARING.value)
    # Codigo corto para invitar participantes (Social Ride, spec seccion 7
    # etapa 2). Nulo hasta que el dueno del viaje lo genera por primera vez.
    join_code: Mapped[str | None] = mapped_column(String(12), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="trips")
    video_uploads = relationship("VideoUpload", back_populates="trip")
    training_plans = relationship("TrainingPlan", back_populates="trip", cascade="all, delete-orphan")
    season_reviews = relationship("SeasonReview", back_populates="trip", cascade="all, delete-orphan")
    day_logs = relationship("DayLog", back_populates="trip", cascade="all, delete-orphan")
    participant_links = relationship("TripParticipant", back_populates="trip", cascade="all, delete-orphan")

    @property
    def participant_user_ids(self) -> set[int]:
        """Dueno + todos los que se sumaron por codigo de invitacion."""
        return {self.user_id} | {link.user_id for link in self.participant_links}
