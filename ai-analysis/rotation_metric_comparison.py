#!/usr/bin/env python3
"""
Sprint "confiabilidad de carving", punto 1: comparar implementaciones
candidatas de rotacion_excesiva_tren_superior ANTES de tocar
analyze_ski_video.py. No cambia produccion -- reusa compute_frame_metrics
para todo lo que no sea la formula de rotacion, y recalcula la rotacion
desde los PoseFrame originales (necesita los puntos 3D crudos, no solo
FrameMetrics, para poder probar variantes con y sin Z).

Candidatos:
  A) actual (Z)     -- angulo de la linea hombro y linea cadera en el
                        plano (x, z) de MediaPipe.
  B) XY simple       -- mismo calculo pero en el plano (x, y) de la
                        imagen (dropea Z).
  C) XY relativo a direccion de desplazamiento -- angulo de la linea de
                        hombros y de cadera respecto a hacia donde se
                        mueve el centro de masa entre frames consecutivos
                        (mismo principio que ya usa analyze_snowboard_video.py
                        para su proxy de edge orientation -- reusa una
                        idea ya validada en este mismo repo, no inventada
                        de cero).

Cada candidato se evalua en 2 variantes de agregacion:
  - "mean"      -- promedio de |valor| sobre todo el video (como hoy)
  - "sustained" -- proporcion de frames individuales que superan un
                    umbral por-frame, exigiendo sostenido (mismo patron
                    que ya usa detect_weight_position/SUSTAINED_BACKWARD_PROPORTION)

Y con/sin suavizado temporal (misma _moving_average de 5 frames que ya
usa trunk_lean para segmentar giros).

Uso:
  python rotation_metric_comparison.py <video> [--discipline carving] [--label x]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from analyze_ski_video import (
    compute_frame_metrics, segment_turns, format_ts, _moving_average,
    SAMPLE_FPS_DEFAULT, MIN_VISIBILITY_DEFAULT, SMOOTHING_WINDOW,
    ROTATION_THRESHOLDS_DEG,
)
from instrument_video import extract_with_visibility


def _wrap_180(a):
    return (a + 180.0) % 360.0 - 180.0


def rotation_z_current(p):
    """Formula actual (analyze_ski_video.py:325-329), reproducida para
    poder compararla lado a lado -- NO se importa de analyze_ski_video
    porque ahi esta atada a compute_frame_metrics, no expuesta suelta."""
    shoulder_vec = p["right_shoulder"] - p["left_shoulder"]
    hip_vec = p["right_hip"] - p["left_hip"]
    shoulder_angle = np.degrees(np.arctan2(shoulder_vec[2], shoulder_vec[0]))
    hip_angle = np.degrees(np.arctan2(hip_vec[2], hip_vec[0]))
    return _wrap_180(shoulder_angle - hip_angle)


def rotation_xy_simple(p):
    """Candidato B: mismo calculo, plano (x, y) de la imagen en vez de
    (x, z). Deja de depender de la coordenada de profundidad de MediaPipe
    (la menos confiable), a costa de medir algo geometricamente distinto:
    esto YA NO es "rotacion axial" en el sentido estricto (una torsion
    alrededor del eje vertical del cuerpo es, por definicion, invisible
    en 2D puro sin profundidad) -- es un diferencial de INCLINACION entre
    la linea de hombros y la linea de cadera dentro del plano de la
    imagen. Relacionado pero no identico al concepto original; se
    documenta la diferencia explicitamente en NOTES.md."""
    shoulder_vec = p["right_shoulder"] - p["left_shoulder"]
    hip_vec = p["right_hip"] - p["left_hip"]
    shoulder_angle = np.degrees(np.arctan2(shoulder_vec[1], shoulder_vec[0]))
    hip_angle = np.degrees(np.arctan2(hip_vec[1], hip_vec[0]))
    return _wrap_180(shoulder_angle - hip_angle)


def rotation_xy_traveldir(p_curr, p_prev):
    """Candidato C: angulo de la linea de hombros y de la linea de cadera
    respecto a la DIRECCION DE DESPLAZAMIENTO del centro de masa entre
    frame anterior y actual (plano x,y). Mismo principio que ya usa
    analyze_snowboard_video.py (compute_edge_orientation_series, ver
    NOTES.md) para su proxy de orientacion de canto -- no es una tecnica
    nueva en este repo, es la misma idea ya validada ahi, aplicada a
    hombro-vs-cadera en vez de hombro+cadera combinados.
    Devuelve None si no hay desplazamiento significativo entre frames
    (mismo problema de "dividir por casi cero" que ya maneja
    _trunk_fore_aft_deg con su banda muerta de rodilla)."""
    com_curr = (p_curr["left_hip"][:2] + p_curr["right_hip"][:2] + p_curr["left_shoulder"][:2] + p_curr["right_shoulder"][:2]) / 4.0
    com_prev = (p_prev["left_hip"][:2] + p_prev["right_hip"][:2] + p_prev["left_shoulder"][:2] + p_prev["right_shoulder"][:2]) / 4.0
    travel = com_curr - com_prev
    travel_norm = np.linalg.norm(travel)
    if travel_norm < 1e-4:
        return None
    travel_angle = np.degrees(np.arctan2(travel[1], travel[0]))

    shoulder_vec = p_curr["right_shoulder"][:2] - p_curr["left_shoulder"][:2]
    hip_vec = p_curr["right_hip"][:2] - p_curr["left_hip"][:2]
    shoulder_angle = np.degrees(np.arctan2(shoulder_vec[1], shoulder_vec[0]))
    hip_angle = np.degrees(np.arctan2(hip_vec[1], hip_vec[0]))

    shoulder_rel = _wrap_180(shoulder_angle - travel_angle)
    hip_rel = _wrap_180(hip_angle - travel_angle)
    return _wrap_180(shoulder_rel - hip_rel)


def evaluate_candidate(name, raw_values, valid_mask, per_frame_threshold=None):
    """raw_values puede tener None (frames sin senal, ej. sin desplazamiento
    para el candidato C) -- se filtran antes de agregar."""
    vals = np.array([abs(v) for v, ok in zip(raw_values, valid_mask) if ok and v is not None])
    if len(vals) == 0:
        return {"name": name, "n": 0}

    thr = per_frame_threshold or ROTATION_THRESHOLDS_DEG
    mean_v = float(np.mean(vals))
    std_v = float(np.std(vals))
    median_v = float(np.median(vals))
    max_v = float(np.max(vals))

    def sev(v, t):
        if v >= t["alta"]:
            return "alta"
        if v >= t["media"]:
            return "media"
        if v >= t["baja"]:
            return "baja"
        return None

    mean_severity = sev(mean_v, thr)

    over_baja = vals >= thr["baja"]
    proportion = float(np.mean(over_baja))
    # "sostenido": mismo umbral de proporcion que ya usa peso_hacia_atras (0.35)
    sustained_fires = proportion >= 0.35

    return {
        "name": name, "n": len(vals),
        "mean": round(mean_v, 2), "std": round(std_v, 2),
        "median": round(median_v, 2), "max": round(max_v, 2),
        "mean_severity": mean_severity,
        "proportion_over_baja": round(proportion, 3),
        "sustained_fires_at_baja": sustained_fires,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--discipline", default="carving")
    ap.add_argument("--label", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    label = args.label or Path(args.video).stem
    frames, all_sampled, sampled_count, eff_fps = extract_with_visibility(
        args.video, SAMPLE_FPS_DEFAULT, MIN_VISIBILITY_DEFAULT
    )
    if not frames:
        print("Sin frames validos.", file=sys.stderr)
        return

    metrics = compute_frame_metrics(frames)
    turns = segment_turns(metrics, eff_fps)

    z_vals, xy_vals, travel_vals = [], [], []
    for i, f in enumerate(frames):
        z_vals.append(rotation_z_current(f.points))
        xy_vals.append(rotation_xy_simple(f.points))
        if i == 0:
            travel_vals.append(None)
        else:
            travel_vals.append(rotation_xy_traveldir(f.points, frames[i - 1].points))

    valid_mask = [True] * len(frames)

    results = {
        "video": args.video, "label": label, "n_frames": len(frames), "n_turns": len(turns),
        "candidates": {
            "A_z_actual": evaluate_candidate("A_z_actual", z_vals, valid_mask),
            "B_xy_simple": evaluate_candidate("B_xy_simple", xy_vals, valid_mask),
            "C_xy_traveldir": evaluate_candidate("C_xy_traveldir", travel_vals, valid_mask),
        },
    }

    # suavizado temporal (ventana 5, misma que trunk_lean) sobre cada serie --
    # a los None de C se les asigna 0 solo para poder promediar (frames raros,
    # <1% del video tipicamente); se documenta la proporcion de Nones aparte.
    def smoothed_eval(name, raw_values):
        clean = np.array([v if v is not None else 0.0 for v in raw_values])
        sm = _moving_average(clean, SMOOTHING_WINDOW)
        return evaluate_candidate(name + "_smoothed5", list(sm), valid_mask)

    results["candidates"]["A_z_actual_smoothed5"] = smoothed_eval("A_z_actual", z_vals)
    results["candidates"]["B_xy_simple_smoothed5"] = smoothed_eval("B_xy_simple", xy_vals)
    results["candidates"]["C_xy_traveldir_smoothed5"] = smoothed_eval("C_xy_traveldir", travel_vals)

    results["n_none_traveldir"] = sum(1 for v in travel_vals if v is None)

    # top-5 frames mas extremos de cada candidato, con timestamp, para
    # poder ir a mirar el video en ese punto exacto.
    for key, raw in [("A_z_actual", z_vals), ("B_xy_simple", xy_vals), ("C_xy_traveldir", travel_vals)]:
        idxs = sorted(
            [i for i, v in enumerate(raw) if v is not None],
            key=lambda i: -abs(raw[i])
        )[:5]
        results["candidates"][key]["top5"] = [
            {"idx": i, "t": format_ts(frames[i].t), "value": round(float(raw[i]), 1)} for i in idxs
        ]

    out = args.out or f"rotation_comparison_{label}.json"
    Path(out).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nGuardado en {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
