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

# Umbral de confidence_score bajo el cual no hay datos suficientes para
# senalar nada con certeza -- mismo criterio que build_summary() en
# ai-analysis/analyze_ski_video.py (no se importa: backend y ai-analysis
# viven en venvs separados a proposito, ver app/analysis_job.py).
_LOW_CONFIDENCE_THRESHOLD = 30

# Frases en tono simple, para el resumen de "Mis videos" (capa 1). Separadas
# de PATTERN_LABELS (que es la etiqueta tecnica de la capa 2/admin) porque
# ahi el tono tiene que ser mucho mas coloquial y corto.
_PATTERN_SIMPLE_PHRASES = {
    "asimetria_izq_der": "tu técnica cambia bastante entre los giros a la izquierda y a la derecha",
    "perdida_de_balance": "perdiste el balance en algunos momentos",
    "rotacion_excesiva_tren_superior": "tu tren superior rota de más respecto a las piernas",
    "inconsistencia_entre_giros": "tu técnica varía bastante entre giros seguidos",
    "peso_hacia_atras": "tu peso se va hacia atrás en algunos giros",
    "salto_detectado": "hiciste saltos en este video",
    "aterrizaje_inestable": "algunos aterrizajes fueron inestables",
    "posible_caida": "puede haber una caída en este video",
}


def _parse_ts_seconds(ts: str | None) -> float | None:
    """Convierte un timestamp "MM:SS.ss" (format_ts() en analyze_ski_video.py)
    a segundos totales, para poder usarlo como video.currentTime en el <video>
    embebido.
    """
    if not ts:
        return None
    minutes, _, seconds = ts.partition(":")
    try:
        return round(int(minutes) * 60 + float(seconds), 2)
    except ValueError:
        return None


def _describe_occurrence(occ: dict) -> dict:
    """Arma una ocurrencia lista para mostrar y para saltar el video a ese
    momento exacto. Este timestamp ya existia en el JSON interno (se usaba
    solo en ai-analysis/debug_turns.py para calibracion) -- esto lo expone
    al usuario por primera vez.
    """
    if "direction" in occ:
        seek_ts = occ.get("t_peak")
        label = f"{occ['direction']} {occ.get('t_start', '?')}–{occ.get('t_end', '?')} (pico {occ.get('t_peak', '?')})"
    else:
        seek_ts = occ.get("t")
        label = occ.get("t", "?")
    return {"label": label, "seconds": _parse_ts_seconds(seek_ts)}


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
                "occurrences": [_describe_occurrence(occ) for occ in p.get("occurrences") or []],
            }
        )
    return rows


def build_user_summary(detected_patterns: list[dict] | None, confidence_score: int | None) -> str:
    """Resumen de 2-3 oraciones en lenguaje simple para la capa 1 de "Mis
    videos" (spec: nada de jerga tecnica como "aproximacion 2D" o "pose
    estimada" -- eso queda en analysis_result.summary, que solo se muestra en
    la capa 2/detallada). Nunca se afirma una causa fisica, solo se describe
    lo que el screening noto (mismo criterio que build_summary() en
    ai-analysis/analyze_ski_video.py).
    """
    if confidence_score is None or confidence_score < _LOW_CONFIDENCE_THRESHOLD:
        return (
            "No encontramos suficiente información en este video para darte un análisis "
            "confiable — probá con un video donde te veas más de cerca y por más tiempo."
        )

    if not detected_patterns:
        return "No notamos ningún patrón para mejorar en este video — seguí así."

    phrases = [
        _PATTERN_SIMPLE_PHRASES.get(p.get("pattern"), PATTERN_LABELS.get(p.get("pattern"), p.get("pattern")))
        for p in detected_patterns[:2]
    ]
    joined = phrases[0] if len(phrases) == 1 else " y ".join(phrases)

    return f"Notamos que {joined}. Mirá el informe detallado para ver exactamente en qué momentos pasó."
