from __future__ import annotations

from app.models import AnalysisResult, InstructorEvaluation
from app.prompt_builder import PATTERN_LABELS

# Reusa las clases .badge-* que ya existen en el panel admin (base.html) --
# distintas de las .tag-* que usa el lado usuario (season_review_comparison.py).
_SEVERITY_CLASS = {"alta": "badge-failed", "media": "badge-pending", "baja": "badge-processed"}

# Los unicos 3 patrones que el instructor califica a mano (ver
# InstructorEvaluation): mapea el pattern key de detected_patterns a los
# campos severity/sample_size correspondientes del modelo.
_COMPARABLE_PATTERNS = [
    ("asimetria_izq_der", "asimetria_severity", "asimetria_sample_size", "giros"),
    ("perdida_de_balance", "balance_severity", "balance_sample_size", "giros"),
    ("inconsistencia_entre_giros", "inconsistencia_severity", "inconsistencia_sample_size", "giros"),
]


def _severity_cell(severity: str | None, sample_size: int | None, sample_unit: str, has_data: bool) -> dict:
    if not has_data:
        return {"text": "Sin datos", "css_class": "", "muted": True, "sample": None}
    if severity is None:
        return {"text": "No detectado", "css_class": "", "muted": False, "sample": None}
    sample = f"{sample_size} {sample_unit}" if sample_size is not None else None
    return {"text": severity, "css_class": _SEVERITY_CLASS.get(severity, ""), "muted": False, "sample": sample}


def compare_ai_vs_instructor(
    analysis: AnalysisResult | None, evaluation: InstructorEvaluation
) -> list[dict]:
    """Compara, patron por patron, lo que detecto la IA contra lo que califico
    el instructor a mano -- para el flujo instructor-antes-que-IA (ver
    admin.video_detail): solo tiene sentido llamarla despues de que el
    instructor ya guardo su evaluacion.
    """
    ai_map = {p["pattern"]: p for p in (analysis.detected_patterns if analysis else [])}

    rows = []
    for pattern_key, severity_field, sample_field, unit in _COMPARABLE_PATTERNS:
        ai_pattern = ai_map.get(pattern_key)
        ai_severity = ai_pattern["severity"] if ai_pattern else None
        ai_sample = ai_pattern.get("sample_size") if ai_pattern else None
        instructor_severity = getattr(evaluation, severity_field)
        instructor_sample = getattr(evaluation, sample_field)

        rows.append(
            {
                "label": PATTERN_LABELS.get(pattern_key, pattern_key),
                "ai": _severity_cell(ai_severity, ai_sample, unit, analysis is not None),
                "instructor": _severity_cell(instructor_severity, instructor_sample, unit, True),
                "agree": (ai_severity == instructor_severity) if analysis is not None else None,
            }
        )
    return rows
