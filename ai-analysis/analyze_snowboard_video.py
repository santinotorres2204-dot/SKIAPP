#!/usr/bin/env python3
"""
Prototipo standalone de analisis de snowboard — primera version.

*** SIN VALIDAR CONTRA NINGUN VIDEO REAL DE SNOWBOARD ***
Este modulo esta basado unicamente en referencia tecnica documentada (ver
mas abajo), no en calibracion contra material real — no tenemos todavia
ningun video de snowboard en el repo. NO USAR para dar feedback real a un
usuario hasta conseguir videos de prueba. Se valido unicamente con datos
sinteticos (secuencias de keypoints simuladas), lo cual solo confirma que
la logica corre sin errores estructurales, NO que el resultado tenga
sentido biomecanico en la practica — ver "Validacion" en NOTES.md.

Separado a proposito de analyze_ski_video.py (no es una modificacion de ese
archivo): la mecanica de snowboard es fundamentalmente distinta a la de ski,
no un ajuste de umbrales sobre la misma logica —
  - El cuerpo esta de costado a la direccion de desplazamiento (no de frente
    como en ski), por lo que el "vaiven lateral de tronco" que usa
    segment_turns() en ski no aplica de la misma forma.
  - Los giros NO son simetricos izquierda/derecha: son toe-side (peso sobre
    los dedos) y heel-side (peso sobre el talon), mecanicamente distintos
    a proposito. Comparar toe-side contra heel-side no tiene sentido (no es
    una asimetria a corregir, es la naturaleza del movimiento) — a
    diferencia de ski, donde comparar izquierda contra derecha si es un
    chequeo valido.

Reutiliza de analyze_ski_video.py solo lo que es geometria generica y no
depende de la orientacion del cuerpo ni de la simetria de los giros:
extraccion de pose (MediaPipe), metricas de centro de masa/escala de torso
(compute_frame_metrics), la deteccion de perdida de balance tal cual
(detect_balance_loss — ver mas abajo por que esta si es portable), y
utilidades (_moving_average, format_ts, _severity_from_thresholds,
INCONSISTENCY_CV_THRESHOLDS).

Referencia tecnica (validada por el fundador, instructor certificado):
  - TOE-SIDE: se inicia con peso en el pie delantero, sobre los dedos. En
    el apex, peso centrado entre ambos pies. Rodillas siguiendo la
    direccion de los dedos.
  - HEEL-SIDE: se inicia con peso todavia adelantado, se traslada hacia el
    pie trasero y el talon al completar el giro. Hombros y cabeza apuntando
    en la direccion de descenso, torso relativamente calmo.
  - Es esperable que haya diferencias de ejecucion entre toe-side y
    heel-side en el mismo rider — eso NO es un error en si mismo, es la
    naturaleza del movimiento (son mecanicamente distintos a proposito).
    Por eso este modulo NUNCA compara toe-side contra heel-side; la
    inconsistencia solo se evalua puertas adentro de cada tipo.

Patrones que intenta detectar (todos como screening visual, no biomecanica
de precision — igual disclaimer que analyze_ski_video.py):

  1. perdida_de_balance      — reutilizado tal cual de analyze_ski_video.py
                                (desplazamiento brusco del centro de masa).
                                Portable sin cambios porque no depende de
                                hacia donde mira o esta orientado el cuerpo,
                                solo de cuanto salta el centro de masa entre
                                frames consecutivos.
  2. inconsistencia_entre_giros (x2, uno por turn_type) — varianza alta
                                entre giros consecutivos del MISMO tipo
                                (toe-side entre si, heel-side entre si).
                                Nunca se compara un tipo contra el otro.

Segmentacion de giros: en vez del cruce por cero del angulo de tronco lateral
que usa ski (segment_turns), este modulo usa el cambio de orientacion
cadera-hombro respecto a la direccion de desplazamiento como proxy del
cambio de canto — ver compute_edge_orientation_series() y
compute_edge_deviation() para el detalle y las limitaciones (es una
aproximacion 2D monocular, con una convencion de signo arbitraria para
toe_side/heel_side que no se puede confirmar sin video real).

Uso:
  python analyze_snowboard_video.py video.mp4
  python analyze_snowboard_video.py video.mp4 -o resultado.json --pretty
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
    INCONSISTENCY_CV_THRESHOLDS,
    MIN_VISIBILITY_DEFAULT,
    SAMPLE_FPS_DEFAULT,
    SMOOTHING_WINDOW,
    FrameMetrics,
    PoseFrame,
    _moving_average,
    _severity_from_thresholds,
    compute_frame_metrics,
    detect_balance_loss,
    extract_pose_sequence,
    format_ts,
)

# ---------------------------------------------------------------------------
# Constantes / umbrales — PLACEHOLDERS sin calibrar, mas aun que en ski/park:
# no hay NINGUN video real de referencia todavia (ver disclaimer arriba).
# ---------------------------------------------------------------------------

PROTOTYPE_LABEL = (
    "prototipo snowboard - sin validar contra ningun video real, basado solo en "
    "referencia tecnica documentada. No usar para dar feedback real a un usuario "
    "hasta conseguir videos de prueba."
)
SNOWBOARD_PROTOTYPE_MAX_CONFIDENCE = 15  # tope mas bajo que park (25): ahi al menos hay 4 videos reales de referencia, aca no hay ninguno

MIN_TURN_DURATION_SEC = 0.4

# Deteccion de cambio de canto: ver compute_edge_orientation_series() y
# compute_edge_deviation(). El angulo crudo tiene un offset base esperable
# de ~90 grados (el rider viaja de costado a la direccion de desplazamiento
# en postura neutra), por eso se resta un baseline movil ancho en vez de
# comparar contra cero como hace ski con trunk_lean (ese offset variaria
# ademas segun encuadre de camara y stance regular/goofy del rider).
EDGE_ANGLE_BASELINE_WINDOW_SEC = 2.0
EDGE_ANGLE_DEAD_ZONE_DEG = 8.0  # banda muerta sobre la desviacion del baseline, para evitar flicker
MIN_EDGE_TRAVEL_RATIO = 0.02    # desplazamiento minimo de COM entre frames (relativo a torso_scale) para confiar en la direccion de desplazamiento de ese frame

MIN_TURNS_FOR_INCONSISTENCY = 3  # por turn_type (toe_side y heel_side se evaluan por separado, cada uno necesita este minimo)
TARGET_TURNS_FOR_PROTOTYPE = 10  # a partir de esta cantidad de giros, "cobertura" maxima por ese factor


# ---------------------------------------------------------------------------
# Proxy de cambio de canto: orientacion cadera-hombro vs. direccion de viaje
# ---------------------------------------------------------------------------

def compute_edge_orientation_series(
    frames: list[PoseFrame], metrics: list[FrameMetrics]
) -> tuple[np.ndarray, np.ndarray]:
    """Angulo (grados, signado) entre la linea cadera-hombro del rider y la
    direccion de desplazamiento de su centro de masa entre frames
    consecutivos.

    En snowboard el rider viaja de costado (no de frente como en ski), asi
    que la linea que cruza su cuerpo de lado a lado (hip_vec + shoulder_vec,
    ambos en el plano x,y de la imagen) es un proxy de que tan "abierto" o
    "cerrado" esta el torso respecto al recorrido — eso rota de forma
    continua a medida que el canto cambia de toe a heel y viceversa.

    No se normalizan los vectores antes de tomar arctan2(cross, dot): esa
    combinacion es invariante a escalar cualquiera de los dos vectores por
    un numero positivo, asi que la magnitud de body_vec o de travel no
    afecta el angulo resultante, solo sus direcciones.

    Devuelve (angle_deg, valid_mask). Un frame queda invalido (angle=0.0,
    valid=False) cuando el desplazamiento de COM respecto al frame anterior
    es demasiado chico para confiar en una direccion (rider casi estatico,
    o primer frame de la secuencia) — se descarta en vez de adivinar signo,
    mismo criterio que usa _trunk_fore_aft_deg en analyze_ski_video.py para
    la ambiguedad analoga en ski.
    """
    n = len(frames)
    angle = np.zeros(n)
    valid = np.zeros(n, dtype=bool)

    for i in range(1, n):
        travel = metrics[i].com - metrics[i - 1].com
        if float(np.linalg.norm(travel)) < MIN_EDGE_TRAVEL_RATIO * metrics[i].torso_scale:
            continue

        p = frames[i].points
        hip_vec = p["right_hip"][:2] - p["left_hip"][:2]
        shoulder_vec = p["right_shoulder"][:2] - p["left_shoulder"][:2]
        body_vec = hip_vec + shoulder_vec
        if float(np.linalg.norm(body_vec)) < 1e-6:
            continue

        cross = travel[0] * body_vec[1] - travel[1] * body_vec[0]
        dot = travel[0] * body_vec[0] + travel[1] * body_vec[1]
        angle[i] = float(np.degrees(np.arctan2(cross, dot)))
        valid[i] = True

    return angle, valid


def compute_edge_deviation(angle_deg: np.ndarray, effective_fps: float) -> np.ndarray:
    """Resta un baseline movil ancho al angulo crudo de
    compute_edge_orientation_series(), para aislar el vaiven de canto del
    offset base (~90 grados esperable, ver docstring de esa funcion) sin
    necesitar conocerlo de antemano — mismo truco que usa find_jumps() en
    analyze_park_video.py para separar el pico de un salto del nivel de piso
    de la elevacion.
    """
    smoothed = _moving_average(angle_deg, SMOOTHING_WINDOW)
    baseline_window = max(3, round(effective_fps * EDGE_ANGLE_BASELINE_WINDOW_SEC))
    baseline = _moving_average(smoothed, baseline_window)
    return smoothed - baseline


# ---------------------------------------------------------------------------
# Segmentacion de giros toe-side / heel-side
# ---------------------------------------------------------------------------

@dataclass
class EdgeTurn:
    start_idx: int
    end_idx: int
    turn_type: str  # "toe_side" | "heel_side" — ver caveat de convencion arbitraria abajo
    max_deviation_abs: float
    mean_deviation_abs: float


def segment_edge_turns(
    deviation: np.ndarray, valid: np.ndarray, effective_fps: float
) -> list[EdgeTurn]:
    """Segmenta la secuencia en giros por cruces de signo de `deviation`
    (ver compute_edge_deviation) — mismo mecanismo que segment_turns() en
    analyze_ski_video.py, pero sobre la desviacion respecto al baseline en
    vez del angulo lateral crudo.

    CAVEAT importante (mas fuerte que el de izquierda/derecha en ski): la
    etiqueta toe_side/heel_side asignada a cada signo es una CONVENCION
    ARBITRARIA de este prototipo (positivo = toe_side), no una deteccion
    real de que borde esta cargado. Sin un video real filmado con stance y
    encuadre de camara conocidos no hay forma de confirmar cual signo
    corresponde a cual tipo de giro. Lo que si es valido con esta
    aproximacion es que ambos signos alternan de forma consistente DENTRO
    del mismo video y corresponden a los dos tipos de giro reales (sean
    cuales sean) — por eso alcanza para separar "giros del mismo tipo entre
    si" para el chequeo de inconsistencia, aunque la etiqueta en si no este
    confirmada.

    Los frames invalidos (sin direccion de desplazamiento confiable, ver
    compute_edge_orientation_series) no arrancan ni cortan un giro por si
    solos: se tratan como "sin señal" (signo 0), igual que la banda muerta.
    """
    n = len(deviation)
    if n < 3:
        return []

    signs = np.where(deviation > EDGE_ANGLE_DEAD_ZONE_DEG, 1, np.where(deviation < -EDGE_ANGLE_DEAD_ZONE_DEG, -1, 0))
    signs = np.where(valid, signs, 0)

    min_turn_frames = max(3, round(effective_fps * MIN_TURN_DURATION_SEC))

    raw_segments: list[tuple[int, Optional[int], int]] = []
    current_sign = 0
    current_start = None
    last_nonzero_idx = None

    for i, s in enumerate(signs):
        if s == 0:
            continue
        if current_sign == 0:
            current_sign = s
            current_start = i
        elif s != current_sign:
            raw_segments.append((current_start, last_nonzero_idx, current_sign))
            current_sign = s
            current_start = i
        last_nonzero_idx = i

    if current_sign != 0 and current_start is not None:
        raw_segments.append((current_start, last_nonzero_idx, current_sign))

    turns: list[EdgeTurn] = []
    for start, end, sign in raw_segments:
        if end is None or (end - start + 1) < min_turn_frames:
            continue
        segment_dev = np.abs(deviation[start:end + 1])
        turns.append(EdgeTurn(
            start_idx=start,
            end_idx=end,
            turn_type="toe_side" if sign > 0 else "heel_side",
            max_deviation_abs=float(np.max(segment_dev)),
            mean_deviation_abs=float(np.mean(segment_dev)),
        ))

    return turns


def _turn_occurrence(turn: EdgeTurn, deviation: np.ndarray, metrics: list[FrameMetrics]) -> dict:
    segment_dev = np.abs(deviation[turn.start_idx:turn.end_idx + 1])
    peak_idx = turn.start_idx + int(np.argmax(segment_dev))
    return {
        "turn_type": turn.turn_type,
        "t_start": format_ts(metrics[turn.start_idx].t),
        "t_peak": format_ts(metrics[peak_idx].t),
        "t_end": format_ts(metrics[turn.end_idx].t),
    }


# ---------------------------------------------------------------------------
# Deteccion de patrones
# ---------------------------------------------------------------------------

def detect_inconsistency_by_type(
    turns: list[EdgeTurn], deviation: np.ndarray, metrics: list[FrameMetrics], turn_type: str
) -> Optional[dict]:
    """Inconsistencia entre giros del MISMO turn_type (nunca cruzado con el
    otro tipo — ver disclaimer del modulo: la diferencia toe-side vs
    heel-side es esperable por diseño, no un error)."""
    subset = [t for t in turns if t.turn_type == turn_type]
    if len(subset) < MIN_TURNS_FOR_INCONSISTENCY:
        return None

    intensities = np.array([t.max_deviation_abs for t in subset])
    mean_intensity = float(np.mean(intensities))
    if mean_intensity < 1e-6:
        return None

    cv = float(np.std(intensities) / mean_intensity)
    severity = _severity_from_thresholds(cv, INCONSISTENCY_CV_THRESHOLDS)
    if severity is None:
        return None

    return {
        "pattern": "inconsistencia_entre_giros",
        "turn_type": turn_type,
        "severity": severity,
        "sample_size": len(subset),
        "occurrences": [_turn_occurrence(t, deviation, metrics) for t in subset],
    }


def detect_inconsistency(turns: list[EdgeTurn], deviation: np.ndarray, metrics: list[FrameMetrics]) -> list[dict]:
    results = []
    for turn_type in ("toe_side", "heel_side"):
        result = detect_inconsistency_by_type(turns, deviation, metrics, turn_type)
        if result:
            results.append(result)
    return results


# ---------------------------------------------------------------------------
# Confidence score (tope bajo fijo — ver disclaimer de prototipo)
# ---------------------------------------------------------------------------

def compute_confidence_score_snowboard(valid_frames: int, sampled_frames: int, n_turns: int) -> int:
    frame_coverage = (valid_frames / sampled_frames) if sampled_frames > 0 else 0.0
    turn_coverage = min(1.0, n_turns / TARGET_TURNS_FOR_PROTOTYPE)
    raw = 100.0 * (0.5 * frame_coverage + 0.5 * turn_coverage)
    capped = min(raw, SNOWBOARD_PROTOTYPE_MAX_CONFIDENCE)
    return int(round(np.clip(capped, 0, SNOWBOARD_PROTOTYPE_MAX_CONFIDENCE)))


# ---------------------------------------------------------------------------
# Resumen en lenguaje simple
# ---------------------------------------------------------------------------

def build_summary(
    turns: list[EdgeTurn],
    balance_pattern: Optional[dict],
    inconsistency_patterns: list[dict],
    confidence_score: int,
) -> str:
    prefix = (
        f"[{PROTOTYPE_LABEL}] Confianza {confidence_score}/100 (tope bajo fijo en este modo, "
        "sin ningun video real de referencia todavia). "
    )

    if not turns:
        return prefix + (
            "No se detecto ningun giro con el proxy de cambio de canto que usa este prototipo "
            "(orientacion cadera-hombro respecto a la direccion de desplazamiento). Puede ser que "
            "el video no tenga giros claros, o que la camara/encuadre no haya permitido verlos."
        )

    n_toe = sum(1 for t in turns if t.turn_type == "toe_side")
    n_heel = sum(1 for t in turns if t.turn_type == "heel_side")
    parts = [f"Se detectaron {len(turns)} giro(s) ({n_toe} toe-side, {n_heel} heel-side segun la convencion de signo de este prototipo)."]

    if balance_pattern:
        parts.append(f"Se detecto perdida de balance (severidad {balance_pattern['severity']}).")

    for p in inconsistency_patterns:
        label = "toe-side" if p["turn_type"] == "toe_side" else "heel-side"
        parts.append(f"Inconsistencia entre giros {label} entre si (severidad {p['severity']}).")

    if not balance_pattern and not inconsistency_patterns:
        parts.append("No se detectaron los patrones que evalua este prototipo con estos umbrales.")

    return prefix + " ".join(parts)


# ---------------------------------------------------------------------------
# Orquestacion
# ---------------------------------------------------------------------------

def analyze_snowboard_video(
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
            "mode": "snowboard_prototype",
            "prototype_notice": PROTOTYPE_LABEL,
            "detected_patterns": [],
            "confidence_score": 0,
            "summary": (
                f"[{PROTOTYPE_LABEL}] No se pudo detectar la pose del rider en ningun frame "
                "muestreado del video, por lo que no fue posible generar ningun analisis."
            ),
            "meta": {
                "frames_sampled": sampled_count,
                "frames_with_valid_pose": 0,
                "turns_detected": 0,
            },
        }

    metrics = compute_frame_metrics(frames)
    raw_angle, valid = compute_edge_orientation_series(frames, metrics)
    deviation = compute_edge_deviation(raw_angle, effective_fps)
    turns = segment_edge_turns(deviation, valid, effective_fps)

    balance_pattern = detect_balance_loss(metrics, len(turns))
    inconsistency_patterns = detect_inconsistency(turns, deviation, metrics)

    detected_patterns = ([balance_pattern] if balance_pattern else []) + inconsistency_patterns
    confidence_score = compute_confidence_score_snowboard(len(frames), sampled_count, len(turns))
    summary = build_summary(turns, balance_pattern, inconsistency_patterns, confidence_score)

    return {
        "video": video_path,
        "mode": "snowboard_prototype",
        "prototype_notice": PROTOTYPE_LABEL,
        "detected_patterns": detected_patterns,
        "confidence_score": confidence_score,
        "summary": summary,
        "meta": {
            "frames_sampled": sampled_count,
            "frames_with_valid_pose": len(frames),
            "effective_fps": round(effective_fps, 2),
            "turns_detected": len(turns),
            "turns_toe_side": sum(1 for t in turns if t.turn_type == "toe_side"),
            "turns_heel_side": sum(1 for t in turns if t.turn_type == "heel_side"),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="[PROTOTIPO, SIN VALIDAR CON VIDEO REAL] Analiza un video de snowboard con "
                     "MediaPipe Pose y heuristicas de canto toe-side/heel-side + perdida de balance."
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

    result = analyze_snowboard_video(
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
