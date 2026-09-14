from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import PatternSeverity, sql_in_values


class InstructorEvaluation(Base):
    """Evaluacion manual del instructor sobre un video, cargada ANTES de ver
    el resultado de la IA (flujo instructor-antes-que-IA, ver admin.py).

    Guarda los mismos 3 patrones que ya detecta el sistema (asimetria,
    perdida de balance, inconsistencia -- ver ai-analysis/analyze_ski_video.py)
    pero calificados a mano, en una tabla separada de AnalysisResult para que
    ninguno de los dos lados pueda pisar al otro y despues se puedan comparar
    lado a lado (ver app/instructor_comparison.py).
    """

    __tablename__ = "instructor_evaluations"
    __table_args__ = (
        CheckConstraint(
            f"asimetria_severity IS NULL OR asimetria_severity IN ({sql_in_values(PatternSeverity)})",
            name="ck_instructor_evaluations_asimetria_severity",
        ),
        CheckConstraint(
            f"balance_severity IS NULL OR balance_severity IN ({sql_in_values(PatternSeverity)})",
            name="ck_instructor_evaluations_balance_severity",
        ),
        CheckConstraint(
            f"inconsistencia_severity IS NULL OR inconsistencia_severity IN ({sql_in_values(PatternSeverity)})",
            name="ck_instructor_evaluations_inconsistencia_severity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # unique=True: una evaluacion de instructor por VideoUpload, mismo criterio
    # uno-a-uno que AnalysisResult.
    video_id: Mapped[int] = mapped_column(
        ForeignKey("video_uploads.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    # NULL = el instructor no marco este patron (equivalente a "no detectado",
    # mismo criterio que el ausente en AnalysisResult.detected_patterns).
    asimetria_severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    asimetria_sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    balance_severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    balance_sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inconsistencia_severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    inconsistencia_sample_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Nullable y sin poblar todavia: no existe login/auth de instructores en el
    # sistema (el panel admin no tiene sesion, ver routers/admin.py), asi que
    # no hay de donde sacar este dato por ahora. Se agrega la columna para no
    # tener que migrar de nuevo cuando exista.
    instructor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    video = relationship("VideoUpload", back_populates="instructor_evaluation")
