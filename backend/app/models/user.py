from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import SkiLevel, sql_in_values


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(f"ski_level IN ({sql_in_values(SkiLevel)})", name="ck_users_ski_level"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    ski_level: Mapped[str] = mapped_column(String(20), nullable=False)
    years_skiing: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    trips = relationship("Trip", back_populates="user", cascade="all, delete-orphan")
    video_uploads = relationship("VideoUpload", back_populates="user", cascade="all, delete-orphan")
    ski_ratings = relationship("SkiRating", back_populates="user", cascade="all, delete-orphan")
    training_plans = relationship("TrainingPlan", back_populates="user", cascade="all, delete-orphan")
    season_reviews = relationship("SeasonReview", back_populates="user", cascade="all, delete-orphan")
    day_logs = relationship("DayLog", back_populates="user", cascade="all, delete-orphan")
    joined_trip_links = relationship("TripParticipant", back_populates="user", cascade="all, delete-orphan")
    runs = relationship("Run", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    assessment_results = relationship("AssessmentResult", back_populates="user", cascade="all, delete-orphan")
    trick_cards = relationship("TrickCard", back_populates="user", cascade="all, delete-orphan")
    freeride_runs = relationship("FreerideRun", back_populates="user", cascade="all, delete-orphan")
