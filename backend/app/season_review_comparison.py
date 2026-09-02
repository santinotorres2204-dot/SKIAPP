from __future__ import annotations

from app.models import AnalysisResult

# Mismas etiquetas que prompt_builder.py (se duplican a proposito, ver el
# comentario ahi -- es solo texto de presentacion).
_PATTERN_LABELS = {
    "asimetria_izq_der": "Asimetria entre giros izquierda/derecha",
    "perdida_de_balance": "Perdida de balance",
    "rotacion_excesiva_tren_superior": "Rotacion excesiva del tren superior",
    "inconsistencia_entre_giros": "Inconsistencia entre giros consecutivos",
}

_SEVERITY_RANK = {"baja": 1, "media": 2, "alta": 3}
# Reusa las 3 clases de tag que ya existen en el sistema de diseno: alta
# severidad = acento bengala (llama la atencion), baja = quiet (bajo control).
_SEVERITY_CLASS = {"alta": "tag-flare", "media": "", "baja": "tag-quiet"}

_STATUS_LABELS = {
    "mejoro": "Mejoró",
    "empeoro": "Empeoró",
    "desaparecio": "Desapareció",
    "nuevo": "Nuevo",
    "sin_cambios": "Sin cambios",
    "sin_datos": "Sin datos suficientes",
}
_STATUS_CLASS = {
    "mejoro": "tag-quiet",
    "empeoro": "tag-flare",
    "desaparecio": "tag-quiet",
    "nuevo": "tag-flare",
    "sin_cambios": "",
    "sin_datos": "",
}


def _pattern_map(analysis: AnalysisResult | None) -> dict[str, str]:
    if analysis is None:
        return {}
    return {p["pattern"]: p["severity"] for p in analysis.detected_patterns}


def _severity_cell(severity: str | None, has_data: bool) -> dict:
    if not has_data:
        return {"text": "Sin datos", "css_class": "", "muted": True}
    if severity is None:
        return {"text": "No detectado", "css_class": "tag-quiet", "muted": False}
    return {"text": severity, "css_class": _SEVERITY_CLASS.get(severity, ""), "muted": False}


def _status(
    before_sev: str | None,
    after_sev: str | None,
    before_analysis: AnalysisResult | None,
    after_analysis: AnalysisResult | None,
) -> str:
    if before_analysis is None or after_analysis is None:
        return "sin_datos"
    if before_sev is None and after_sev is not None:
        return "nuevo"
    if before_sev is not None and after_sev is None:
        return "desaparecio"
    before_rank = _SEVERITY_RANK.get(before_sev, 0)
    after_rank = _SEVERITY_RANK.get(after_sev, 0)
    if after_rank < before_rank:
        return "mejoro"
    if after_rank > before_rank:
        return "empeoro"
    return "sin_cambios"


def compare_analysis_patterns(
    before_analysis: AnalysisResult | None, after_analysis: AnalysisResult | None
) -> list[dict]:
    """Compara los patrones detectados de dos AnalysisResult (evolucion real
    de un Season Review, no solo scores). Devuelve una fila por cada patron
    presente en cualquiera de los dos lados, con severidad antes/despues y
    el estado (mejoro/empeoro/desaparecio/nuevo/sin cambios/sin datos).

    Si un lado no tiene AnalysisResult (video sin analizar, o no se pudo
    encontrar el video correspondiente), esas celdas quedan en "sin datos"
    en vez de intentar adivinar un estado.
    """
    before_map = _pattern_map(before_analysis)
    after_map = _pattern_map(after_analysis)
    pattern_keys = sorted(set(before_map) | set(after_map))

    rows = []
    for key in pattern_keys:
        before_sev = before_map.get(key)
        after_sev = after_map.get(key)
        status = _status(before_sev, after_sev, before_analysis, after_analysis)
        rows.append(
            {
                "label": _PATTERN_LABELS.get(key, key),
                "before": _severity_cell(before_sev, before_analysis is not None),
                "after": _severity_cell(after_sev, after_analysis is not None),
                "status_text": _STATUS_LABELS[status],
                "status_class": _STATUS_CLASS[status],
            }
        )
    return rows
