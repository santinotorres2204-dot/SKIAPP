from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TripParticipant(Base):
    """Usuario sumado a un viaje ajeno via codigo de invitacion -- Social
    Ride (spec seccion 7 etapa 2). El dueno del viaje (trips.user_id) no
    necesita fila propia aca; se lo trata como participante implicito."""

    __tablename__ = "trip_participants"
    __table_args__ = (
        UniqueConstraint("trip_id", "user_id", name="uq_trip_participants_trip_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    trip = relationship("Trip", back_populates="participant_links")
    user = relationship("User", back_populates="joined_trip_links")
