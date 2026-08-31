from __future__ import annotations

from app.models import AnalysisResult, VideoUpload

# Etiquetas legibles para los patrones que devuelve analyze_ski_video.py.
# Se duplican (en vez de importarse) porque backend y ai-analysis viven en
# venvs separados a proposito (ver app/analysis_job.py) -- esto es solo texto
# de presentacion, bajo riesgo de desincronizarse con la logica de deteccion.
PATTERN_LABELS = {
    "asimetria_izq_der": "Asimetria entre giros izquierda/derecha",
    "perdida_de_balance": "Perdida de balance",
    "rotacion_excesiva_tren_superior": "Rotacion excesiva del tren superior",
    "inconsistencia_entre_giros": "Inconsistencia entre giros consecutivos",
}


def _format_occurrences(occurrences: list[dict]) -> str:
    if not occurrences:
        return "sin timestamps registrados"

    parts = []
    for occ in occurrences:
        if "direction" in occ:
            parts.append(f"{occ['direction']} {occ['t_start']}-{occ['t_end']} (pico {occ['t_peak']})")
        else:
            parts.append(str(occ.get("t", "?")))
    return ", ".join(parts)


def build_training_prompt(video: VideoUpload, analysis: AnalysisResult) -> str:
    """Arma un prompt en texto plano, listo para copiar y pegar en una
    conversacion con una IA, pidiendo una propuesta de rutina de
    entrenamiento fisico a partir del resultado del screening de MediaPipe.

    No llama a ninguna IA -- solo compone el texto con los datos ya
    persistidos (analysis_result, usuario, viaje).
    """
    user = video.user
    trip = video.trip

    lines = [
        "Sos un entrenador fisico especializado en preparacion para esqui. Te paso el "
        "resultado de un screening automatico de video (deteccion de patrones de "
        "movimiento con MediaPipe + reglas heuristicas -- NO es un diagnostico medico "
        "ni biomecanico certero) de un esquiador, para que me propongas una rutina de "
        "entrenamiento fisico (fuera de la nieve) orientada a trabajar los patrones "
        "detectados.",
        "",
        "Perfil del esquiador:",
        f"- Nivel: {user.ski_level}",
        f"- Anios esquiando: {user.years_skiing}",
        f"- Disciplina analizada en el video: {video.discipline_tag}",
    ]

    if trip is not None:
        lines.append(f"- Viaje asociado: {trip.destination} (inicio {trip.start_date})")
    else:
        lines.append("- Viaje asociado: ninguno")

    lines += [
        "",
        "Resultado del analisis (screening automatico):",
        f"- Confidence score: {analysis.confidence_score}/100",
        f"- Resumen: {analysis.summary or '(sin resumen disponible)'}",
        "",
        "Patrones detectados:",
    ]

    if not analysis.detected_patterns:
        lines.append("- Ninguno.")
    else:
        for p in analysis.detected_patterns:
            label = PATTERN_LABELS.get(p["pattern"], p["pattern"])
            occurrences = _format_occurrences(p.get("occurrences", []))
            lines.append(f"- {label} (severidad {p['severity']}) -- timestamps: {occurrences}")

    lines += [
        "",
        "Con esta informacion, proponeme una rutina de entrenamiento fisico de 2 a 4 "
        "semanas enfocada en trabajar estos patrones, considerando el nivel y la "
        "experiencia del esquiador. Recorda que esto es una senal preliminar de un "
        "screening automatico, no un diagnostico certero.",
    ]

    return "\n".join(lines)
