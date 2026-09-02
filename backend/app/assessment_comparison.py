from __future__ import annotations

from app.models import AssessmentResult

# (atributo, etiqueta, unidad) -- las 6 metricas numericas del assessment,
# todas "mas alto es mejor" (segundos aguantados o repeticiones).
METRICS: list[tuple[str, str, str]] = [
    ("wall_sit_seconds", "Wall Sit", "s"),
    ("single_leg_squat_left", "Single Leg Squat (izq.)", "reps"),
    ("single_leg_squat_right", "Single Leg Squat (der.)", "reps"),
    ("jump_squat_reps", "Jump Squat", "reps"),
    ("plank_seconds", "Plank", "s"),
    ("lateral_bound_reps", "Lateral Bound", "reps"),
]


def compare_assessments(baseline: AssessmentResult, target: AssessmentResult) -> list[dict]:
    """Compara dos AssessmentResult metrica por metrica (baseline -> target).

    Se usa tanto para "vs. el assessment anterior" (POST /submit) como para
    "vs. tu primer assessment" (seccion de progreso de /assessment) -- el
    caller decide que par de resultados pasar.
    """
    rows = []
    for key, label, unit in METRICS:
        before = getattr(baseline, key)
        after = getattr(target, key)
        if after > before:
            direction = "up"
        elif after < before:
            direction = "down"
        else:
            direction = "same"

        scale = max(before, after, 1)
        rows.append(
            {
                "key": key,
                "label": label,
                "unit": unit,
                "before": before,
                "after": after,
                "delta": after - before,
                "direction": direction,
                "before_pct": round(before / scale * 100),
                "after_pct": round(after / scale * 100),
            }
        )
    return rows


def leg_asymmetry_pct(result: AssessmentResult) -> float:
    """% de diferencia entre pierna izquierda y derecha en single leg squat,
    relativo a la pierna mas fuerte. 0 si ambas dieron 0 (sin datos utiles)."""
    left, right = result.single_leg_squat_left, result.single_leg_squat_right
    biggest = max(left, right)
    if biggest == 0:
        return 0.0
    return abs(left - right) / biggest * 100
