"""Scratch de analisis para el sprint de asimetria (punto 3, ahora si implementado).
Mide cada una de las 3 condiciones candidatas por separado contra el dataset de
referencia, ANTES de definir minimos concretos. No modifica analyze_ski_video.py.
"""
import json
import numpy as np

from analyze_ski_video import (
    extract_pose_sequence, compute_frame_metrics, segment_turns,
    find_activity_start_idx, MIN_TURNS_FOR_ASYMMETRY, ASYMMETRY_THRESHOLDS,
    SAMPLE_FPS_DEFAULT, MIN_VISIBILITY_DEFAULT,
)

VIDEOS = {
    "video17_influencer": "C:/Users/santi/ski-app/backend/media/videos/1/04f639126caf45d89f80f3d5418b20cd.mov",
    "video1_carving_bueno": "C:/Users/santi/ski-app/backend/media/videos/1/39f865208d164135be348a94310a3a3e.mp4",
    "video2_errores_conocidos": "C:/Users/santi/ski-app/backend/media/videos/1/12eb1401de9b4c27b1d63712a46fdcd3.mp4",
    "video16_malo_corto": "C:/Users/santi/ski-app/backend/media/videos/1/1783043e34d74c4dafd21f4f81eb1dfe.mp4",
}


def rel_diff(a, b):
    d = (a + b) / 2.0
    return abs(a - b) / d if d > 1e-9 else 0.0


def diff_for(turns):
    left = [t for t in turns if t.direction == "izquierda"]
    right = [t for t in turns if t.direction == "derecha"]
    if not left or not right:
        return None
    knee_l, knee_r = np.mean([t.mean_knee_flex for t in left]), np.mean([t.mean_knee_flex for t in right])
    lean_l, lean_r = np.mean([t.mean_trunk_lean_abs for t in left]), np.mean([t.mean_trunk_lean_abs for t in right])
    return max(rel_diff(knee_l, knee_r), rel_diff(lean_l, lean_r))


results = {}
for label, path in VIDEOS.items():
    print(f"=== {label} ===")
    frames, sampled_count, effective_fps = extract_pose_sequence(
        path, SAMPLE_FPS_DEFAULT, MIN_VISIBILITY_DEFAULT, 1
    )
    metrics = compute_frame_metrics(frames)
    turns_all = segment_turns(metrics, effective_fps)
    start_idx = find_activity_start_idx(turns_all, metrics)
    turns = [t for t in turns_all if t.start_idx >= start_idx]

    left = [t for t in turns if t.direction == "izquierda"]
    right = [t for t in turns if t.direction == "derecha"]
    print(f"  n_turns_valid_activity={len(turns)}  n_left={len(left)}  n_right={len(right)}")

    per_turn = [
        {"start_idx": t.start_idx, "dir": t.direction, "knee": round(t.mean_knee_flex, 2), "lean": round(t.mean_trunk_lean_abs, 2)}
        for t in turns
    ]
    for row in per_turn:
        print("   ", row)

    base_diff = diff_for(turns)
    print(f"  diff agregado (todos los giros de actividad valida) = {base_diff}")

    # --- Condicion 2: sensibilidad leave-one-out por tamano de muestra ---
    # Para cada lado, si se remueve el giro mas "atipico" (el que mas cambia
    # el promedio), cuanto se mueve el diff? Esto simula el riesgo real de
    # que UN giro fuera de rango decida la severidad con muestras chicas.
    loo_deltas = []
    for i, t in enumerate(turns):
        remaining = turns[:i] + turns[i + 1:]
        d2 = diff_for(remaining)
        if d2 is not None and base_diff is not None:
            loo_deltas.append(round(abs(d2 - base_diff), 4))
    if loo_deltas:
        print(f"  leave-one-out: max delta en diff al sacar 1 giro cualquiera = {max(loo_deltas)} (mean={round(float(np.mean(loo_deltas)),4)})")

    # --- Condicion 3: persistencia (mitad temporal 1 vs 2) ---
    half = len(turns) // 2
    def half_diff(ts):
        l = [t.mean_trunk_lean_abs for t in ts if t.direction == "izquierda"]
        r = [t.mean_trunk_lean_abs for t in ts if t.direction == "derecha"]
        if not l or not r:
            return None
        return round(float(rel_diff(np.mean(l), np.mean(r))), 4)
    first_half = half_diff(turns[:half]) if half >= 1 else None
    second_half = half_diff(turns[half:]) if len(turns) - half >= 1 else None
    print(f"  persistence: 1ra mitad={first_half}  2da mitad={second_half}")

    results[label] = {
        "n_left": len(left), "n_right": len(right), "base_diff": base_diff,
        "loo_max_delta": max(loo_deltas) if loo_deltas else None,
        "first_half": first_half, "second_half": second_half,
        "per_turn": per_turn,
    }

with open("asymmetry_condition_scores.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print("\nGuardado en asymmetry_condition_scores.json")
