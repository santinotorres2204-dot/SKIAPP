"""Version mas literal de la condicion elegida: "no depende de UN giro
atipico" -- se identifica, por metrica, el giro individual mas influyente
(el que al sacarlo reduce mas el diff = el que mas esta empujando el
resultado), y se chequea si sacando ESE giro puntual la direccion se
mantiene y el diff se mantiene sobre el umbral 'baja'."""
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


def most_influential_removed(turns, attr):
    l0, r0 = side_means(turns, attr)
    if l0 is None:
        return None
    full_diff = rel_diff(l0, r0)
    full_dir = "derecha" if r0 > l0 else "izquierda"
    best = None  # (delta_reduction, idx, new_diff, new_dir)
    for i in range(len(turns)):
        subset = turns[:i] + turns[i + 1:]
        l, r = side_means(subset, attr)
        if l is None:
            continue
        d = rel_diff(l, r)
        dirn = "derecha" if r > l else "izquierda"
        reduction = full_diff - d if dirn == full_dir else full_diff + d  # flip cuenta como reduccion total
        if best is None or reduction > best[0]:
            best = (reduction, i, d, dirn)
    if best is None:
        return None
    reduction, idx, new_diff, new_dir = best
    return {
        "full_diff": round(full_diff, 4), "full_dir": full_dir,
        "most_influential_turn_idx": idx,
        "diff_without_it": round(new_diff, 4), "dir_without_it": new_dir,
        "direction_holds": new_dir == full_dir,
        "still_over_baja": new_diff >= ASYMMETRY_THRESHOLDS["baja"],
    }


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
        res = most_influential_removed(turns, attr)
        print(f"  {attr}: {res}")
