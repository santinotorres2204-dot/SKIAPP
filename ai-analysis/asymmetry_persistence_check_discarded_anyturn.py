"""Explora la definicion elegida por el usuario para la condicion 3
(persistencia): direccion consistente + sostenida en al menos 2 giros, no
un solo giro atipico. Se opera como leave-one-out: para cada metrica
(knee_flex, trunk_lean) por separado, se chequea si el LADO favorecido
(derecha vs izquierda) se mantiene igual al sacar CUALQUIER giro individual.
Si se mantiene para todos los giros, la metrica es "robusta" (2+ giros la
sostienen). Si se puede hacer flip sacando 1 solo giro, esa metrica no
cuenta para la severidad final.
"""
import json
import numpy as np
from analyze_ski_video import (
    extract_pose_sequence, compute_frame_metrics, segment_turns,
    find_activity_start_idx, SAMPLE_FPS_DEFAULT, MIN_VISIBILITY_DEFAULT,
    ASYMMETRY_THRESHOLDS,
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


def side_means(turns, attr):
    l = [getattr(t, attr) for t in turns if t.direction == "izquierda"]
    r = [getattr(t, attr) for t in turns if t.direction == "derecha"]
    if not l or not r:
        return None, None
    return float(np.mean(l)), float(np.mean(r))


def metric_robust(turns, attr):
    """True si el lado favorecido no cambia al sacar ningun giro individual."""
    l0, r0 = side_means(turns, attr)
    if l0 is None:
        return None, None, None
    full_diff = rel_diff(l0, r0)
    full_dir = "derecha" if r0 > l0 else "izquierda"
    flips = 0
    total_checked = 0
    for i in range(len(turns)):
        subset = turns[:i] + turns[i + 1:]
        l, r = side_means(subset, attr)
        if l is None:
            continue  # se quedo sin giros de un lado, no se puede evaluar ese caso
        total_checked += 1
        d = "derecha" if r > l else "izquierda"
        if d != full_dir:
            flips += 1
    robust = (flips == 0) and total_checked > 0
    return robust, full_diff, full_dir


for label, path in VIDEOS.items():
    print(f"=== {label} ===")
    frames, sampled_count, effective_fps = extract_pose_sequence(
        path, SAMPLE_FPS_DEFAULT, MIN_VISIBILITY_DEFAULT, 1
    )
    metrics = compute_frame_metrics(frames)
    turns_all = segment_turns(metrics, effective_fps)
    start_idx = find_activity_start_idx(turns_all, metrics)
    turns = [t for t in turns_all if t.start_idx >= start_idx]

    for attr in ("mean_knee_flex", "mean_trunk_lean_abs"):
        robust, diff, direction = metric_robust(turns, attr)
        if robust is None:
            print(f"  {attr}: no computable (falta un lado)")
        else:
            print(f"  {attr}: diff={round(diff,4) if diff else diff} direccion_favorecida={direction} robusta_a_sacar_1_giro={robust}")
