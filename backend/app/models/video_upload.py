from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import AnalysisStatus, Discipline, TerrainTag, sql_in_values


class VideoUpload(Base):
    __tablename__ = "video_uploads"
    __table_args__ = (
        CheckConstraint(f"discipline_tag IN ({sql_in_values(Discipline)})", name="ck_video_uploads_discipline_tag"),
        CheckConstraint(f"analysis_status IN ({sql_in_values(AnalysisStatus)})", name="ck_video_uploads_analysis_status"),
        CheckConstraint(
            f"terrain_tag IS NULL OR terrain_tag IN ({sql_in_values(TerrainTag)})",
            name="ck_video_uploads_terrain_tag",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Nullable: la spec aclara que un video puede subirse fuera de un viaje activo.
    trip_id: Mapped[int | None] = mapped_column(ForeignKey("trips.id", ondelete="SET NULL"), nullable=True, index=True)
    file_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    discipline_tag: Mapped[str] = mapped_column(String(20), nullable=False)
    # Nullable: videos subidos antes de agregar este campo no tienen dato.
    # Se pide obligatorio en el formulario para subidas nuevas (ver
    # video_uploads.upload_video), pero no se retroactiva a lo ya cargado.
    terrain_tag: Mapped[str | None] = mapped_column(String(20), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    analysis_status: Mapped[str] = mapped_column(String(20), nullable=False, default=AnalysisStatus.PENDING.value)

    user = relationship("User", back_populates="video_uploads")
    trip = relationship("Trip", back_populates="video_uploads")
    analysis_result = relationship(
        "AnalysisResult", back_populates="video", uselist=False, cascade="all, delete-orphan"
    )
