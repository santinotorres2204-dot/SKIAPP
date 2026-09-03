from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.sql import func
from app.database import Base
import enum

class FearType(str, enum.Enum):
    velocidad = "velocidad"
    pendiente = "pendiente"
    caidas = "caidas"
    exposicion = "exposicion"
    otro = "otro"

class Technique(str, enum.Enum):
    respiracion = "respiracion"
    visualizacion = "visualizacion"
    self_talk = "self_talk"
    escalera = "escalera"

class MentalSession(Base):
    __tablename__ = "mental_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    fear_type = Column(SAEnum(FearType), nullable=False)
    intensity_before = Column(Integer, nullable=False)  # 1-10
    intensity_after = Column(Integer, nullable=True)    # 1-10, se carga al final
    technique_used = Column(SAEnum(Technique), nullable=False)
    duration_minutes = Column(Integer, nullable=True)
    notes = Column(String, nullable=True)
