#!/usr/bin/env python3
"""
Prototipo standalone de heuristicas de PARK (saltos) — primera version.

Separado a proposito de analyze_ski_video.py: la logica de esa spec
(segment_turns, detect_asymmetry, etc.) esta calibrada para el vaivén
alternado izquierda/derecha de los giros en carving/freeride/all_mountain.
Un salto de park no genera esa secuencia, asi que necesita sus propios
patrones de screening. Reutiliza de analyze_ski_video.py solo lo que es
geometria generica y no especifica de giros: extraccion de pose (MediaPipe),
metricas por frame (centro de masa, escala de torso, inclinacion de tronco)
y utilidades (_moving_average, format_ts, _severity_from_thresholds).

Patrones que intenta detectar (todos como screening visual, no biomecanica
de precision — igual disclaimer que analyze_ski_video.py):

  1. salto_detectado        — pico brusco en la elevacion de caderas/hombros
                               (centro de masa), distinto al vaivén gradual
                               de un giro. Se usa como ancla temporal para
                               los dos patrones siguientes.
  2. aterrizaje_inestable   — desplazamiento brusco del centro de masa en los
                               frames posteriores al aterrizaje del salto.
  3. posible_caida          — el tronco se inclina a un angulo casi horizontal
                               de forma repentina despues de un salto. Se
                               distingue explicitamente de una perdida de
                               tracking de MediaPipe (ver mas abajo).

Sobre el punto 3: si en la ventana posterior al aterrizaje MediaPipe dejo de
detectar pose en una proporcion alta de frames muestreados (mala calidad de
camara/encuadre — ver NOTES.md), esa ventana se reporta por separado como
"insufficient_data_events", NUNCA como posible_caida. Frames faltantes no son
evidencia de caida, son datos que no existen.

*** ESTE ES UN PROTOTIPO, NO UNA VERSION CALIBRADA ***
Con 4 videos de referencia (park1-4.mp4) no hay forma de calibrar umbrales
con rigor estadistico. Los valores de mas abajo son placeholders razonables
para validar que la logica corre end-to-end, igual que se hizo al principio
con analyze_ski_video.py (ver spec seccion 6/9). El confidence_score en este
modo tiene un tope duro bajo (ver PARK_PROTOTYPE_MAX_CONFIDENCE) sea cual sea
la cantidad de datos, precisamente porque el prototipo en si no esta
calibrado — mas frames no arreglan umbrales adivinados.

Uso:
  python analyze_park_video.py park1.mp4
  python analyze_park_video.py park1.mp4 -o resultado_park1.json --pretty
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from analyze_ski_video import (
    MIN_VISIBILITY_DEFAULT,
    SAMPLE_FPS_DEFAULT,
    FrameMetrics,
    PoseFrame,
    _moving_average,
    _severity_from_thresholds,
    compute_frame_metrics,
    extract_pose_sequence,
    format_ts,
)

# ---------------------------------------------------------------------------
# Constantes / umbrales — PLACEHOLDERS sin calibrar (ver disclaimer arriba)
# ---------------------------------------------------------------------------

PROTOTYPE_LABEL = "prototipo park - primera version, requiere mas datos para calibrar"
PARK_PROTOTYPE_MAX_CONFIDENCE = 25  # tope duro: nunca reporta mas confianza que esto en este modo

# Deteccion de salto: la "elevacion" es -com_y (com de compute_frame_metrics,
# promedio de hombros+caderas), normalizada por la escala de torso mediana
# del clip (mismo truco que detect_balance_loss en analyze_ski_video: evita
# que el umbral dependa de la distancia/zoom de la camara).
JUMP_BASELINE_WINDOW_SEC = 2.0     # ventana ancha para estimar "nivel de piso" y aislar el pico
JUMP_PEAK_HALF_WINDOW_SEC = 0.5    # radio de busqueda de maximo local
JUMP_MIN_RISE_TORSOS = 0.55        # elevacion minima (en alturas de torso) para candidatear un salto
JUMP_MIN_FALL_TORSOS = 0.35        # debe bajar al menos esto despues del pico (confirma arco, no deriva de camara)
JUMP_MIN_SEPARATION_SEC = 1.0      # picos mas cerca que esto se funden en uno (se queda el mas alto)
LANDING_SEARCH_SEC = 1.5           # ventana post-pico donde se busca el "aterrizaje" (minimo local de elevacion)

# Estabilidad de aterrizaje: desplazamiento de centro de masa frame a frame
# (normalizado por torso), igual formula que detect_balance_loss.
LANDING_INSTABILITY_WINDOW_SEC = 0.75
LANDING_INSTABILITY_SEVERITY = {"baja": 0.14, "media": 0.22, "alta": 0.32}

# Posible caida: angulo de tronco respecto a la vertical (trunk_lean de
# compute_frame_metrics) cercano a horizontal, buscado en una ventana corta
# despues del aterrizaje.
FALL_CONTEXT_WINDOW_SEC = 1.0
FALL_ANGLE_SEVERITY_DEG = {"baja": 55.0, "media": 65.0, "alta": 75.0}

# Perdida de tracking vs caida real: si en la ventana de analisis post-salto
# falto mas de esta proporcion de los frames muestreados esperados (gap entre
# frames validos), se reporta como dato insuficiente, no como caida.
FALL_GAP_RATIO_THRESHOLD = 0.35

TARGET_JUMPS_FOR_PROTOTYPE = 5  # a partir de esta cantidad de saltos, "cobertura" maxima por ese factor


# ---------------------------------------------------------------------------
# Deteccion de saltos
# ---------------------------------------------------------------------------

@dataclass
class JumpEvent:
    peak_idx: int
    landing_idx: int
    rise_torsos: float   # elevacion del pico sobre el baseline, en alturas de torso
    fall_torsos: float   # cuanto bajo desde el pico hasta el aterrizaje, en alturas de torso


def find_jumps(metrics: list[FrameMetrics], effective_fps: float) -> tuple[list[JumpEvent], float]:
    """Busca picos bruscos de elevacion (com_y invertido) que suben y vuelven
    a bajar dentro de una ventana corta — a diferencia del vaivén gradual y
    mayormente lateral de un giro, que no genera este patron de elevacion.

    Devuelve (saltos_confirmados, escala_de_torso_de_referencia).
    """
    n = len(metrics)
    if n < 3:
        return [], 0.0

    elevation = np.array([-m.com[1] for m in metrics])  # y de MediaPipe crece hacia abajo
    torso_scale = np.array([m.torso_scale for m in metrics])
    ref_scale = float(np.median(torso_scale))
    if ref_scale < 1e-6:
        return [], ref_scale

    baseline_window = max(3, round(effective_fps * JUMP_BASELINE_WINDOW_SEC))
    baseline = _moving_average(elevation, baseline_window)
    deviation = (elevation - baseline) / ref_scale

    half_window = max(1, round(effective_fps * JUMP_PEAK_HALF_WINDOW_SEC))
    fall_search_frames = max(1, round(effective_fps * LANDING_SEARCH_SEC))

    candidates: list[JumpEvent] = []
    for i in range(n):
        if deviation[i] < JUMP_MIN_RISE_TORSOS:
            continue
        lo, hi = max(0, i - half_window), min(n, i + half_window + 1)
        if deviation[i] < np.max(deviation[lo:hi]) - 1e-9:
            continue  # no es maximo local dentro de su ventana

        hi_fall = min(n, i + 1 + fall_search_frames)
        if hi_fall <= i + 1:
            continue  # pico pegado al final del clip, no hay forma de confirmar el arco
        future = deviation[i + 1:hi_fall]
        min_future_offset = int(np.argmin(future))
        fall_amount = float(deviation[i] - future[min_future_offset])
        if fall_amount < JUMP_MIN_FALL_TORSOS:
            continue  # no vuelve a bajar lo suficiente: probablemente deriva de camara, no salto

        candidates.append(JumpEvent(
            peak_idx=i,
            landing_idx=i + 1 + min_future_offset,
            rise_torsos=float(deviation[i]),
            fall_torsos=fall_amount,
        ))

    # de-duplicar picos muy cercanos entre si, quedandose con el mas alto
    candidates.sort(key=lambda j: j.peak_idx)
    min_sep_frames = max(1, round(effective_fps * JUMP_MIN_SEPARATION_SEC))
    deduped: list[JumpEvent] = []
    for c in candidates:
        if deduped and c.peak_idx - deduped[-1].peak_idx < min_sep_frames:
            if c.rise_torsos > deduped[-1].rise_torsos:
                deduped[-1] = c
            continue
        deduped.append(c)

    return deduped, ref_scale


# ---------------------------------------------------------------------------
# Evaluacion de cada aterrizaje: estabilidad + posible caida vs tracking loss
# ---------------------------------------------------------------------------

@dataclass
class LandingEvaluation:
    jump: JumpEvent
    unstable: bool
    max_com_delta_torsos: float
    possible_fall: bool
    max_trunk_angle_deg: float
    tracking_insufficient: bool
    gap_ratio: float


def evaluate_landing(
    jump: JumpEvent,
    metrics: list[FrameMetrics],
    frames: list[PoseFrame],
    ref_scale: float,
    effective_fps: float,
) -> LandingEvaluation:
    n = len(metrics)
    landing_idx = jump.landing_idx

    # --- estabilidad del aterrizaje: desplazamiento de COM frame a frame ---
    instability_frames = max(1, round(effective_fps * LANDING_INSTABILITY_WINDOW_SEC))
    stab_end = min(n, landing_idx + 1 + instability_frames)
    coms = np.array([m.com for m in metrics[landing_idx:stab_end]])
    max_com_delta = 0.0
    if len(coms) >= 2 and ref_scale > 1e-6:
        deltas = np.linalg.norm(np.diff(coms, axis=0), axis=1) / ref_scale
        max_com_delta = float(np.max(deltas))
    unstable = max_com_delta >= LANDING_INSTABILITY_SEVERITY["baja"]

    # --- posible caida vs perdida de tracking ---
    fall_context_frames = max(1, round(effective_fps * FALL_CONTEXT_WINDOW_SEC))
    fall_end = min(n, landing_idx + 1 + fall_context_frames)
    fall_metrics_segment = metrics[landing_idx:fall_end]
    fall_frames_segment = frames[landing_idx:fall_end]

    max_trunk_angle = 0.0
    if fall_metrics_segment:
        max_trunk_angle = float(max(abs(m.trunk_lean) for m in fall_metrics_segment))
    near_horizontal = max_trunk_angle >= FALL_ANGLE_SEVERITY_DEG["baja"]

    # gap_ratio: proporcion de frames muestreados que MediaPipe NO pudo trackear
    # dentro de esta ventana (frames.index es la posicion en el stream muestreado
    # completo; un salto entre indices consecutivos > 1 significa frames perdidos).
    gap_ratio = 0.0
    if len(fall_frames_segment) >= 2:
        idx_span = fall_frames_segment[-1].index - fall_frames_segment[0].index
        expected = idx_span + 1
        if expected > 0:
            gap_ratio = 1.0 - (len(fall_frames_segment) / expected)
    elif len(fall_frames_segment) <= 1 and fall_end > landing_idx + 1:
        # se esperaban varios frames en la ventana y no quedo casi ninguno valido
        gap_ratio = 1.0

    tracking_insufficient = gap_ratio >= FALL_GAP_RATIO_THRESHOLD
    possible_fall = near_horizontal and not tracking_insufficient

    return LandingEvaluation(
        jump=jump,
        unstable=unstable,
        max_com_delta_torsos=max_com_delta,
        possible_fall=possible_fall,
        max_trunk_angle_deg=max_trunk_angle,
        tracking_insufficient=tracking_insufficient,
        gap_ratio=gap_ratio,
    )


# ---------------------------------------------------------------------------
# Empaquetado de patrones / occurrences
# ---------------------------------------------------------------------------

def _jump_occurrence(ev: LandingEvaluation, metrics: list[FrameMetrics]) -> dict:
    return {
        "t_peak": format_ts(metrics[ev.jump.peak_idx].t),
        "t_landing": format_ts(metrics[ev.jump.landing_idx].t),
        "rise_estimate_torsos": round(ev.jump.rise_torsos, 3),
    }


def build_detected_patterns(evaluations: list[LandingEvaluation], metrics: list[FrameMetrics]) -> list[dict]:
    patterns: list[dict] = []

    if evaluations:
        patterns.append({
            "pattern": "salto_detectado",
            "severity": None,  # informativo, no es una senal de riesgo en si misma
            "sample_size": len(evaluations),
            "occurrences": [_jump_occurrence(ev, metrics) for ev in evaluations],
        })

    unstable_evs = [ev for ev in evaluations if ev.unstable]
    if unstable_evs:
        max_delta = max(ev.max_com_delta_torsos for ev in unstable_evs)
        severity = _severity_from_thresholds(max_delta, LANDING_INSTABILITY_SEVERITY)
        patterns.append({
            "pattern": "aterrizaje_inestable",
            "severity": severity,
            "sample_size": len(evaluations),
            "occurrences": [
                {**_jump_occurrence(ev, metrics), "com_delta_torsos": round(ev.max_com_delta_torsos, 3)}
                for ev in unstable_evs
            ],
        })

    fall_evs = [ev for ev in evaluations if ev.possible_fall]
    if fall_evs:
        max_angle = max(ev.max_trunk_angle_deg for ev in fall_evs)
        severity = _severity_from_thresholds(max_angle, FALL_ANGLE_SEVERITY_DEG) or "baja"
        patterns.append({
            "pattern": "posible_caida",
            "severity": severity,
            "sample_size": len(evaluations),
            "occurrences": [
                {**_jump_occurrence(ev, metrics), "trunk_angle_deg": round(ev.max_trunk_angle_deg, 1)}
                for ev in fall_evs
            ],
        })

    return patterns


def build_insufficient_data_events(evaluations: list[LandingEvaluation], metrics: list[FrameMetrics]) -> list[dict]:
    """Ventanas post-salto donde MediaPipe perdio tracking: se reportan aparte
    de detected_patterns a proposito, para que nunca se lean como caida (ver
    NOTES.md y el disclaimer al inicio de este archivo)."""
    return [
        {
            **_jump_occurrence(ev, metrics),
            "gap_ratio": round(ev.gap_ratio, 2),
            "note": (
                "MediaPipe perdio tracking en una porcion alta de los frames posteriores "
                "a este aterrizaje; no hay datos suficientes para evaluar caida en esta ventana "
                "(esto no es evidencia de caida, es ausencia de datos)."
            ),
        }
        for ev in evaluations if ev.tracking_insufficient
    ]


# ---------------------------------------------------------------------------
# Confidence score (tope bajo fijo — ver disclaimer de prototipo)
# ---------------------------------------------------------------------------

def compute_confidence_score_park(valid_frames: int, sampled_frames: int, n_jumps: int) -> int:
    frame_coverage = (valid_frames / sampled_frames) if sampled_frames > 0 else 0.0
    jump_coverage = min(1.0, n_jumps / TARGET_JUMPS_FOR_PROTOTYPE)
    raw = 100.0 * (0.5 * frame_coverage + 0.5 * jump_coverage)
    capped = min(raw, PARK_PROTOTYPE_MAX_CONFIDENCE)
    return int(round(np.clip(capped, 0, PARK_PROTOTYPE_MAX_CONFIDENCE)))


# ---------------------------------------------------------------------------
# Resumen en lenguaje simple
# ---------------------------------------------------------------------------

def build_summary(
    evaluations: list[LandingEvaluation],
    insufficient_events: list[dict],
    confidence_score: int,
) -> str:
    prefix = (
        f"[{PROTOTYPE_LABEL}] Confianza {confidence_score}/100 (tope bajo fijo en este modo, "
        "todavia sin calibrar con suficientes videos). "
    )

    if not evaluations:
        return prefix + (
            "No se detecto ningun salto con el patron de elevacion brusca que busca este "
            "prototipo. Puede ser que el video no tenga saltos, o que la camara/encuadre no "
            "haya permitido verlos con claridad."
        )

    n_jumps = len(evaluations)
    n_unstable = sum(1 for ev in evaluations if ev.unstable)
    n_falls = sum(1 for ev in evaluations if ev.possible_fall)
    n_insufficient = len(insufficient_events)

    parts = [f"Se detectaron {n_jumps} salto(s)."]
    if n_unstable:
        parts.append(f"{n_unstable} aterrizaje(s) mostraron desplazamiento brusco del centro de masa (posible inestabilidad).")
    if n_falls:
        parts.append(f"{n_falls} aterrizaje(s) mostraron el tronco cerca de la horizontal de forma repentina (posible caida).")
    if n_insufficient:
        parts.append(
            f"En {n_insufficient} caso(s) MediaPipe perdio tracking despues del aterrizaje: no se pudo "
            "evaluar caida ahi por falta de datos, no se interpreta como caida."
        )
    if not n_unstable and not n_falls:
        parts.append("Los aterrizajes analizados no mostraron señales de inestabilidad o caida con estos umbrales.")

    return prefix + " ".join(parts)


# ---------------------------------------------------------------------------
# Orquestacion
# ---------------------------------------------------------------------------

def analyze_park_video(
    video_path: str,
    sample_fps: float = SAMPLE_FPS_DEFAULT,
    min_visibility: float = MIN_VISIBILITY_DEFAULT,
) -> dict:
    frames, sampled_count, effective_fps = extract_pose_sequence(
        video_path, sample_fps, min_visibility, model_complexity=1
    )

    if not frames:
        return {
            "video": video_path,
            "mode": "park_prototype",
            "prototype_notice": PROTOTYPE_LABEL,
            "detected_patterns": [],
            "insufficient_data_events": [],
            "confidence_score": 0,
            "summary": (
                f"[{PROTOTYPE_LABEL}] No se pudo detectar la pose del esquiador/snowboarder en "
                "ningun frame muestreado del video, por lo que no fue posible generar ningun analisis."
            ),
            "meta": {
                "frames_sampled": sampled_count,
                "frames_with_valid_pose": 0,
                "jumps_detected": 0,
            },
        }

    metrics = compute_frame_metrics(frames)
    jumps, ref_scale = find_jumps(metrics, effective_fps)
    evaluations = [evaluate_landing(j, metrics, frames, ref_scale, effective_fps) for j in jumps]

    detected_patterns = build_detected_patterns(evaluations, metrics)
    insufficient_events = build_insufficient_data_events(evaluations, metrics)
    confidence_score = compute_confidence_score_park(len(frames), sampled_count, len(jumps))
    summary = build_summary(evaluations, insufficient_events, confidence_score)

    return {
        "video": video_path,
        "mode": "park_prototype",
        "prototype_notice": PROTOTYPE_LABEL,
        "detected_patterns": detected_patterns,
        "insufficient_data_events": insufficient_events,
        "confidence_score": confidence_score,
        "summary": summary,
        "meta": {
            "frames_sampled": sampled_count,
            "frames_with_valid_pose": len(frames),
            "effective_fps": round(effective_fps, 2),
            "jumps_detected": len(jumps),
            "reference_torso_scale": round(ref_scale, 4),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="[PROTOTIPO] Analiza un video de park (saltos) con MediaPipe Pose y "
                     "heuristicas de salto/aterrizaje/posible caida, sin calibrar todavia."
    )
    parser.add_argument("video", help="Path al archivo de video (mp4, mov, etc.)")
    parser.add_argument("-o", "--output", help="Path donde guardar el JSON de salida")
    parser.add_argument("--sample-fps", type=float, default=SAMPLE_FPS_DEFAULT,
                         help=f"FPS a los que submuestrear el video (default: {SAMPLE_FPS_DEFAULT})")
    parser.add_argument("--min-visibility", type=float, default=MIN_VISIBILITY_DEFAULT,
                         help=f"Visibilidad minima de MediaPipe por keypoint (default: {MIN_VISIBILITY_DEFAULT})")
    parser.add_argument("--pretty", action="store_true", help="Indentar el JSON de salida")

    args = parser.parse_args()

    if not Path(args.video).exists():
        print(f"Error: no existe el archivo '{args.video}'", file=sys.stderr)
        sys.exit(1)

    result = analyze_park_video(
        args.video,
        sample_fps=args.sample_fps,
        min_visibility=args.min_visibility,
    )

    indent = 2 if args.pretty else None
    output_json = json.dumps(result, indent=indent, ensure_ascii=False)

    print(output_json)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"\nGuardado en {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
