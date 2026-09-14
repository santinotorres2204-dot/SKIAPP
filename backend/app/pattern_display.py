from __future__ import annotations

from app.prompt_builder import PATTERN_LABELS

# La mayoria de los patrones cuentan giros (ver MIN_TURNS_FOR_* en
# ai-analysis/analyze_ski_video.py); los que cuentan otra unidad se listan
# aca explicitamente en vez de asumir "giros" para todos.
_SAMPLE_UNIT_OVERRIDES = {
    "peso_hacia_atras": "frames",
    "salto_detectado": "saltos",
    "aterrizaje_inestable": "saltos",
    "posible_caida": "saltos",
}
_DEFAULT_SAMPLE_UNIT = "giros"


def describe_detected_patterns(detected_patterns: list[dict] | None) -> list[dict]:
    """Arma la confianza por-patron a partir de detected_patterns (spec:
    reemplazar la prominencia de un unico confidence_score global por la
    confianza de cada patron detectado -- el sample_size ya existe en el JSON
    que produce cada modulo de ai-analysis, esto solo le agrega una etiqueta
    legible y la unidad de medida para mostrarlo).
    """
    if not detected_patterns:
        return []
    rows = []
    for p in detected_patterns:
        pattern_key = p.get("pattern")
        rows.append(
            {
                "pattern": pattern_key,
                "label": PATTERN_LABELS.get(pattern_key, pattern_key),
                "severity": p.get("severity"),
                "sample_size": p.get("sample_size"),
                "sample_unit": _SAMPLE_UNIT_OVERRIDES.get(pattern_key, _DEFAULT_SAMPLE_UNIT),
                "occurrences": p.get("occurrences"),
            }
        )
    return rows
