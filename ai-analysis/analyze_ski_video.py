#!/usr/bin/env python3
"""
Prototipo standalone del modulo de analisis de IA (spec seccion 6).

Recibe un video de un usuario esquiando, corre MediaPipe Pose sobre los
frames, y aplica reglas heuristicas de screening (no biomecanica de
precision) para detectar:

  - asimetria_izq_der            (comparacion giros izquierda vs derecha)
  - perdida_de_balance           (desplazamiento brusco del centro de masa)
  - rotacion_excesiva_tren_superior (separacion hombros/cadera)
  - inconsistencia_entre_giros   (varianza alta entre giros consecutivos)

Salida: JSON con la forma descripta en la spec:
  {
    "detected_patterns": [{"pattern": ..., "severity": ..., "sample_size": ...}],
    "confidence_score": 0-100
  }

Uso:
  pip install -r requirements.txt
  python analyze_ski_video.py video.mp4
  python analyze_ski_video.py video.mp4 -o resultado.json --pretty

Este script es deliberadamente aislado de la app (sin DB, sin backend):
la idea es poder probar y calibrar la logica de deteccion antes de
integrarla al pipeline async de la Etapa 1.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core.base_options import BaseOptions

# ---------------------------------------------------------------------------
# Constantes / umbrales (todos calibrables — ver nota al final del archivo)
# ---------------------------------------------------------------------------

SAMPLE_FPS_DEFAULT = 8          # frames por segundo a analizar (submuestreo)
MIN_VISIBILITY_DEFAULT = 0.5    # visibilidad minima de MediaPipe por keypoint
SMOOTHING_WINDOW = 5            # ventana de suavizado (frames) para segmentar giros
LEAN_DEAD_ZONE_DEG = 3.0        # banda muerta alrededor de 0 para evitar flicker
MIN_TURN_DURATION_SEC = 0.4     # duracion minima para contar un giro como tal

# Umbrales de severidad. Son placeholders razonables para un screening
# visual, no derivados de literatura biomecanica — el objetivo de este
# prototipo es tener la logica corriendo end-to-end y poder ajustarlos
# mirando videos reales, tal como pide la spec (seccion 6 / 9).
ASYMMETRY_THRESHOLDS = {"baja": 0.12, "media": 0.22, "alta": 0.35}       # diff relativa
ROTATION_THRESHOLDS_DEG = {"baja": 20.0, "media": 30.0, "alta": 40.0}    # grados promedio
INCONSISTENCY_CV_THRESHOLDS = {"baja": 0.25, "media": 0.40, "alta": 0.60}  # coef. variacion
BALANCE_LOSS_PROPORTION_THRESHOLDS = {"baja": 0.02, "media": 0.05, "alta": 0.09}

MIN_TURNS_FOR_ASYMMETRY = 2   # por lado
MIN_TURNS_FOR_INCONSISTENCY = 3
MIN_VALID_FRAMES_FOR_BALANCE = 20

# Mediapipe >= 1.0 saco la API legacy `mediapipe.solutions.pose`; el reemplazo
# es la Tasks API, que necesita un modelo .task descargado aparte. Se cachea
# localmente y se descarga solo la primera vez que se corre el script.
POSE_LANDMARKER_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
)
POSE_LANDMARKER_MODEL_PATH = Path(__file__).parent / "models" / "pose_landmarker_lite.task"

# Indices del esqueleto de 33 puntos de BlazePose/PoseLandmarker (estables
# entre versiones de mediapipe): https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker
REQUIRED_LANDMARKS = {
    "left_shoulder": 11,
    "right_shoulder": 12,
    "left_hip": 23,
    "right_hip": 24,
    "left_knee": 25,
    "right_knee": 26,
    "left_ankle": 27,
    "right_ankle": 28,
}


def ensure_pose_landmarker_model() -> Path:
    """Descarga el modelo .task de PoseLandmarker si todavia no esta cacheado."""
    if not POSE_LANDMARKER_MODEL_PATH.exists():
        POSE_LANDMARKER_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        print(f"Descargando modelo PoseLandmarker a {POSE_LANDMARKER_MODEL_PATH} ...", file=sys.stderr)
        urllib.request.urlretrieve(POSE_LANDMARKER_MODEL_URL, POSE_LANDMARKER_MODEL_PATH)
    return POSE_LANDMARKER_MODEL_PATH


# ---------------------------------------------------------------------------
# Extraccion de pose
# ---------------------------------------------------------------------------

@dataclass
class PoseFrame:
    index: int
    t: float
    points: dict  # nombre -> np.array([x, y, z]) en coords normalizadas de MediaPipe


def extract_pose_sequence(
    video_path: str,
    sample_fps: float,
    min_visibility: float,
    model_complexity: int,
) -> tuple[list[PoseFrame], int, float]:
    """Corre MediaPipe PoseLandmarker sobre el video submuestreado a sample_fps.

    Devuelve (frames_validos, total_frames_muestreados, fps_efectivo).
    Un frame se descarta si MediaPipe no detecta ninguna persona o si algun
    keypoint clave tiene visibilidad por debajo del umbral (evita meter
    ruido de poses parcialmente ocluidas/incompletas en las metricas).

    `model_complexity` se ignora con la Tasks API actual (el modelo
    "lite" cacheado localmente ya balancea velocidad/precision); se deja
    el parametro por compatibilidad de la interfaz del script.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"No se pudo abrir el video: {video_path}")

    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_interval = max(1, round(source_fps / sample_fps))
    effective_fps = source_fps / frame_interval

    model_path = ensure_pose_landmarker_model()
    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path)),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    frames: list[PoseFrame] = []
    sampled_count = 0
    frame_idx = 0
    last_timestamp_ms = -1

    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ok, frame = cap.read()
            if not ok:
                break

            if frame_idx % frame_interval == 0:
                sampled_count += 1
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

                # detect_for_video exige timestamps estrictamente crecientes.
                timestamp_ms = max(int(frame_idx / source_fps * 1000), last_timestamp_ms + 1)
                last_timestamp_ms = timestamp_ms

                result = landmarker.detect_for_video(mp_image, timestamp_ms)

                if result.pose_landmarks:
                    landmarks = result.pose_landmarks[0]
                    points = {}
                    visible_enough = True
                    for name, lm_idx in REQUIRED_LANDMARKS.items():
                        lm = landmarks[lm_idx]
                        if lm.visibility < min_visibility:
                            visible_enough = False
                            break
                        points[name] = np.array([lm.x, lm.y, lm.z])

                    if visible_enough:
                        t = frame_idx / source_fps
                        frames.append(PoseFrame(index=sampled_count - 1, t=t, points=points))

            frame_idx += 1

    cap.release()
    return frames, sampled_count, effective_fps


# ---------------------------------------------------------------------------
# Metricas geometricas por frame
# ---------------------------------------------------------------------------

def _angle_deg(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Angulo en el vertice b, formado por a-b-c, en 2D (x, y), en grados."""
    ba = a[:2] - b[:2]
    bc = c[:2] - b[:2]
    denom = np.linalg.norm(ba) * np.linalg.norm(bc)
    if denom < 1e-9:
        return 0.0
    cos_angle = np.clip(np.dot(ba, bc) / denom, -1.0, 1.0)
    return float(np.degrees(np.arccos(cos_angle)))


def _wrap_180(angle: float) -> float:
    return (angle + 180.0) % 360.0 - 180.0


def format_ts(seconds: float) -> str:
    """Formatea un offset en segundos como MM:SS.ss (usado tambien por debug_turns.py)."""
    m = int(seconds // 60)
    s = seconds - m * 60
    return f"{m:02d}:{s:05.2f}"


@dataclass
class FrameMetrics:
    t: float
    knee_flex_left: float
    knee_flex_right: float
    trunk_lean: float          # signado: + = inclinacion hacia un lado, - hacia el otro
    rotation_diff: float       # separacion angular hombros vs cadera (grados)
    com: np.ndarray            # centro de masa aproximado (x, y)
    torso_scale: float         # distancia hombro-cadera, usada para normalizar desplazamientos


def compute_frame_metrics(frames: list[PoseFrame]) -> list[FrameMetrics]:
    metrics = []
    for f in frames:
        p = f.points

        knee_flex_left = 180.0 - _angle_deg(p["left_hip"], p["left_knee"], p["left_ankle"])
        knee_flex_right = 180.0 - _angle_deg(p["right_hip"], p["right_knee"], p["right_ankle"])

        mid_hip = (p["left_hip"][:2] + p["right_hip"][:2]) / 2.0
        mid_shoulder = (p["left_shoulder"][:2] + p["right_shoulder"][:2]) / 2.0
        trunk_vec = mid_shoulder - mid_hip
        vertical_ref = np.array([0.0, -1.0])  # "arriba" en la imagen = y menor
        denom = np.linalg.norm(trunk_vec) * np.linalg.norm(vertical_ref)
        raw_angle = 0.0
        if denom > 1e-9:
            cos_a = np.clip(np.dot(trunk_vec, vertical_ref) / denom, -1.0, 1.0)
            raw_angle = float(np.degrees(np.arccos(cos_a)))
        sign = 1.0 if trunk_vec[0] >= 0 else -1.0
        trunk_lean = sign * raw_angle

        # Rotacion tren superior vs inferior: se aproxima proyectando la linea
        # de hombros y la linea de cadera sobre el plano (x, z) — z es la
        # profundidad relativa que da MediaPipe. Es una aproximacion gruesa
        # (no una rotacion 3D real), consistente con el objetivo de "screening
        # visual" de la spec, no de biomecanica de precision.
        shoulder_vec = p["right_shoulder"] - p["left_shoulder"]
        hip_vec = p["right_hip"] - p["left_hip"]
        shoulder_angle = np.degrees(np.arctan2(shoulder_vec[2], shoulder_vec[0]))
        hip_angle = np.degrees(np.arctan2(hip_vec[2], hip_vec[0]))
        rotation_diff = _wrap_180(shoulder_angle - hip_angle)

        com = (p["left_hip"][:2] + p["right_hip"][:2] + p["left_shoulder"][:2] + p["right_shoulder"][:2]) / 4.0
        torso_scale = max(float(np.linalg.norm(mid_shoulder - mid_hip)), 1e-3)

        metrics.append(FrameMetrics(
            t=f.t,
            knee_flex_left=knee_flex_left,
            knee_flex_right=knee_flex_right,
            trunk_lean=trunk_lean,
            rotation_diff=rotation_diff,
            com=com,
            torso_scale=torso_scale,
        ))
    return metrics


# ---------------------------------------------------------------------------
# Segmentacion de giros
# ---------------------------------------------------------------------------

@dataclass
class Turn:
    start_idx: int
    end_idx: int
    direction: str  # "izquierda" | "derecha" (relativo a la camara, ver nota abajo)
    mean_knee_flex: float
    mean_trunk_lean_abs: float
    max_trunk_lean_abs: float
    mean_rotation_diff_abs: float


def _moving_average(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1 or len(values) < window:
        return values.copy()
    kernel = np.ones(window) / window
    return np.convolve(values, kernel, mode="same")


def segment_turns(metrics: list[FrameMetrics], effective_fps: float) -> list[Turn]:
    """Segmenta la secuencia en giros usando los cruces por cero de la
    inclinacion de tronco suavizada.

    Nota sobre "izquierda"/"derecha": la etiqueta depende de como esta
    encuadrado el video (camara de frente, de espaldas, lateral) y no se
    corresponde necesariamente con la izquierda/derecha anatomica del
    esquiador. Lo que importa para el chequeo de asimetria es distinguir
    de forma consistente los dos sentidos de giro dentro del mismo video,
    no la etiqueta en si.
    """
    if len(metrics) < 3:
        return []

    lean = np.array([m.trunk_lean for m in metrics])
    smoothed = _moving_average(lean, SMOOTHING_WINDOW)

    signs = np.where(smoothed > LEAN_DEAD_ZONE_DEG, 1, np.where(smoothed < -LEAN_DEAD_ZONE_DEG, -1, 0))

    min_turn_frames = max(3, round(effective_fps * MIN_TURN_DURATION_SEC))

    raw_segments: list[tuple[int, int, int]] = []
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

    turns: list[Turn] = []
    for start, end, sign in raw_segments:
        if end is None or (end - start + 1) < min_turn_frames:
            continue
        segment = metrics[start:end + 1]
        knee_flex_vals = [(m.knee_flex_left + m.knee_flex_right) / 2.0 for m in segment]
        lean_abs_vals = [abs(m.trunk_lean) for m in segment]
        rot_abs_vals = [abs(m.rotation_diff) for m in segment]

        turns.append(Turn(
            start_idx=start,
            end_idx=end,
            direction="derecha" if sign > 0 else "izquierda",
            mean_knee_flex=float(np.mean(knee_flex_vals)),
            mean_trunk_lean_abs=float(np.mean(lean_abs_vals)),
            max_trunk_lean_abs=float(np.max(lean_abs_vals)),
            mean_rotation_diff_abs=float(np.mean(rot_abs_vals)),
        ))

    return turns


def _turn_occurrence(turn: Turn, metrics: list[FrameMetrics]) -> dict:
    """Ubica un giro en el timeline del video (inicio/pico/fin), con la misma
    logica que usa debug_turns.py para nombrar sus capturas de calibracion.
    """
    segment_leans = [abs(metrics[j].trunk_lean) for j in range(turn.start_idx, turn.end_idx + 1)]
    peak_idx = turn.start_idx + int(np.argmax(segment_leans))
    return {
        "direction": turn.direction,
        "t_start": format_ts(metrics[turn.start_idx].t),
        "t_peak": format_ts(metrics[peak_idx].t),
        "t_end": format_ts(metrics[turn.end_idx].t),
    }


# ---------------------------------------------------------------------------
# Deteccion de patrones
# ---------------------------------------------------------------------------

def _severity_from_thresholds(value: float, thresholds: dict) -> Optional[str]:
    if value >= thresholds["alta"]:
        return "alta"
    if value >= thresholds["media"]:
        return "media"
    if value >= thresholds["baja"]:
        return "baja"
    return None


def detect_asymmetry(turns: list[Turn], metrics: list[FrameMetrics]) -> Optional[dict]:
    left = [t for t in turns if t.direction == "izquierda"]
    right = [t for t in turns if t.direction == "derecha"]

    if len(left) < MIN_TURNS_FOR_ASYMMETRY or len(right) < MIN_TURNS_FOR_ASYMMETRY:
        return None

    def rel_diff(a: float, b: float) -> float:
        denom = (a + b) / 2.0
        return abs(a - b) / denom if denom > 1e-9 else 0.0

    knee_left = np.mean([t.mean_knee_flex for t in left])
    knee_right = np.mean([t.mean_knee_flex for t in right])
    lean_left = np.mean([t.mean_trunk_lean_abs for t in left])
    lean_right = np.mean([t.mean_trunk_lean_abs for t in right])

    diff = max(rel_diff(knee_left, knee_right), rel_diff(lean_left, lean_right))
    severity = _severity_from_thresholds(diff, ASYMMETRY_THRESHOLDS)
    if severity is None:
        return None

    return {
        "pattern": "asimetria_izq_der",
        "severity": severity,
        "sample_size": len(turns),
        "occurrences": [_turn_occurrence(t, metrics) for t in turns],
    }


def detect_rotation_excessive(metrics: list[FrameMetrics], turns: list[Turn]) -> Optional[dict]:
    if not metrics:
        return None

    mean_rotation = float(np.mean([abs(m.rotation_diff) for m in metrics]))
    severity = _severity_from_thresholds(mean_rotation, ROTATION_THRESHOLDS_DEG)
    if severity is None:
        return None

    return {
        "pattern": "rotacion_excesiva_tren_superior",
        "severity": severity,
        "sample_size": len(turns) if turns else len(metrics),
        # Es un promedio de toda la secuencia (no un chequeo por giro), pero se
        # listan los giros como referencia temporal de donde se midio.
        "occurrences": [_turn_occurrence(t, metrics) for t in turns],
    }


def detect_inconsistency(turns: list[Turn], metrics: list[FrameMetrics]) -> Optional[dict]:
    if len(turns) < MIN_TURNS_FOR_INCONSISTENCY:
        return None

    intensities = np.array([t.max_trunk_lean_abs for t in turns])
    mean_intensity = float(np.mean(intensities))
    if mean_intensity < 1e-6:
        return None

    cv = float(np.std(intensities) / mean_intensity)
    severity = _severity_from_thresholds(cv, INCONSISTENCY_CV_THRESHOLDS)
    if severity is None:
        return None

    return {
        "pattern": "inconsistencia_entre_giros",
        "severity": severity,
        "sample_size": len(turns),
        "occurrences": [_turn_occurrence(t, metrics) for t in turns],
    }


def detect_balance_loss(metrics: list[FrameMetrics], n_turns: int) -> Optional[dict]:
    if len(metrics) < MIN_VALID_FRAMES_FOR_BALANCE:
        return None

    coms = np.array([m.com for m in metrics])
    scales = np.array([m.torso_scale for m in metrics])

    deltas = np.linalg.norm(np.diff(coms, axis=0), axis=1)
    # Normalizado por la escala corporal (hombro-cadera) del frame para que
    # el umbral no dependa de la distancia/zoom de la camara.
    normalized = deltas / scales[1:]

    mean_d = float(np.mean(normalized))
    std_d = float(np.std(normalized))
    threshold = max(mean_d + 2.5 * std_d, 0.12)  # piso absoluto para videos casi estaticos

    flagged_idx = np.where(normalized > threshold)[0]
    proportion = len(flagged_idx) / len(normalized)

    severity = _severity_from_thresholds(proportion, BALANCE_LOSS_PROPORTION_THRESHOLDS)
    if severity is None:
        return None

    # A diferencia de los demas patrones, este es por-frame, no por-giro:
    # normalized[i] es el salto entre metrics[i] y metrics[i+1], se reporta
    # el timestamp del frame de "llegada" de ese salto.
    occurrences = [{"t": format_ts(metrics[i + 1].t)} for i in flagged_idx]

    return {
        "pattern": "perdida_de_balance",
        "severity": severity,
        "sample_size": n_turns if n_turns > 0 else len(metrics),
        "occurrences": occurrences,
    }


# ---------------------------------------------------------------------------
# Confidence score
# ---------------------------------------------------------------------------

TARGET_TURNS_FOR_FULL_CONFIDENCE = 15  # a partir de esta cantidad de giros, confianza maxima por ese factor


def compute_confidence_score(valid_frames: int, sampled_frames: int, n_turns: int) -> int:
    """Confianza basada en CANTIDAD de datos disponibles (mas frames validos,
    mas giros analizados), no en que tan seguro esta el sistema de que el
    patron detectado sea real. Asi lo pide explicitamente la spec.
    """
    frame_coverage = (valid_frames / sampled_frames) if sampled_frames > 0 else 0.0
    turns_coverage = min(1.0, n_turns / TARGET_TURNS_FOR_FULL_CONFIDENCE)

    score = 100.0 * (0.4 * frame_coverage + 0.6 * turns_coverage)
    return int(round(np.clip(score, 0, 100)))


# ---------------------------------------------------------------------------
# Resumen en lenguaje simple
# ---------------------------------------------------------------------------

# Frases en lenguaje llano; se combinan en build_summary(). Redactadas como
# deteccion de patron/screening, nunca como causa fisica afirmada (spec
# seccion 6: "nunca como causa fisica afirmada").
PATTERN_DESCRIPTIONS = {
    "asimetria_izq_der": "una asimetria entre los giros hacia la izquierda y hacia la derecha",
    "perdida_de_balance": "perdida de balance en algunos momentos del video",
    "rotacion_excesiva_tren_superior": "una rotacion marcada del tren superior respecto al tren inferior",
    "inconsistencia_entre_giros": "inconsistencia en la tecnica entre giros consecutivos",
}


def build_summary(detected_patterns: list[dict], confidence_score: int, n_turns: int) -> str:
    """Resumen de 2-3 oraciones en lenguaje simple, pensado para el panel de
    administrador (screening, no diagnostico -- ver spec seccion 6).
    """
    if not detected_patterns:
        if confidence_score < 30:
            return (
                f"El analisis se corrio sobre {n_turns} giro(s) detectado(s), con un nivel de "
                f"confianza bajo ({confidence_score}/100). No hay datos suficientes para senalar "
                "ningun patron con certeza; conviene repetir el analisis con un video mas largo o "
                "con mejor visibilidad del esquiador."
            )
        return (
            f"Se analizaron {n_turns} giros con un nivel de confianza de {confidence_score}/100 y "
            "no se detecto ningun patron destacable en este screening. Es una senal preliminar de "
            "tecnica consistente, no un diagnostico certero."
        )

    descriptions = [
        f"{PATTERN_DESCRIPTIONS.get(p['pattern'], p['pattern'])} (severidad {p['severity']})"
        for p in detected_patterns
    ]
    patterns_text = descriptions[0] if len(descriptions) == 1 else (
        ", ".join(descriptions[:-1]) + " y " + descriptions[-1]
    )

    return (
        f"El screening detecto {patterns_text}, sobre {n_turns} giro(s) analizados. "
        f"El nivel de confianza es de {confidence_score}/100, asi que esto debe tomarse como una "
        "senal preliminar para revisar en video, no como un diagnostico biomecanico certero."
    )


# ---------------------------------------------------------------------------
# Orquestacion
# ---------------------------------------------------------------------------

def analyze_video(
    video_path: str,
    sample_fps: float = SAMPLE_FPS_DEFAULT,
    min_visibility: float = MIN_VISIBILITY_DEFAULT,
    model_complexity: int = 1,
) -> dict:
    frames, sampled_count, effective_fps = extract_pose_sequence(
        video_path, sample_fps, min_visibility, model_complexity
    )

    if not frames:
        return {
            "video": video_path,
            "detected_patterns": [],
            "confidence_score": 0,
            "summary": (
                "No se pudo detectar la pose del esquiador en ningun frame muestreado del video, "
                "por lo que no fue posible generar ningun analisis. Conviene probar con un video "
                "donde el cuerpo del esquiador se vea con mayor claridad."
            ),
            "meta": {
                "frames_sampled": sampled_count,
                "frames_with_valid_pose": 0,
                "turns_detected": 0,
                "note": "No se detecto pose valida en ningun frame muestreado.",
            },
        }

    metrics = compute_frame_metrics(frames)
    turns = segment_turns(metrics, effective_fps)

    detections = [
        detect_asymmetry(turns, metrics),
        detect_balance_loss(metrics, len(turns)),
        detect_rotation_excessive(metrics, turns),
        detect_inconsistency(turns, metrics),
    ]
    detected_patterns = [d for d in detections if d is not None]

    confidence_score = compute_confidence_score(len(frames), sampled_count, len(turns))
    summary = build_summary(detected_patterns, confidence_score, len(turns))

    return {
        "video": video_path,
        "detected_patterns": detected_patterns,
        "confidence_score": confidence_score,
        "summary": summary,
        "meta": {
            "frames_sampled": sampled_count,
            "frames_with_valid_pose": len(frames),
            "effective_fps": round(effective_fps, 2),
            "turns_detected": len(turns),
            "turns_izquierda": sum(1 for t in turns if t.direction == "izquierda"),
            "turns_derecha": sum(1 for t in turns if t.direction == "derecha"),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analiza un video de ski/snowboard con MediaPipe Pose y "
                     "devuelve un JSON de patrones detectados (spec seccion 6)."
    )
    parser.add_argument("video", help="Path al archivo de video (mp4, mov, etc.)")
    parser.add_argument("-o", "--output", help="Path donde guardar el JSON de salida")
    parser.add_argument("--sample-fps", type=float, default=SAMPLE_FPS_DEFAULT,
                         help=f"FPS a los que submuestrear el video (default: {SAMPLE_FPS_DEFAULT})")
    parser.add_argument("--min-visibility", type=float, default=MIN_VISIBILITY_DEFAULT,
                         help=f"Visibilidad minima de MediaPipe por keypoint (default: {MIN_VISIBILITY_DEFAULT})")
    parser.add_argument("--model-complexity", type=int, choices=[0, 1, 2], default=1,
                         help="Complejidad del modelo MediaPipe Pose (0=rapido, 2=preciso)")
    parser.add_argument("--pretty", action="store_true", help="Indentar el JSON de salida")

    args = parser.parse_args()

    if not Path(args.video).exists():
        print(f"Error: no existe el archivo '{args.video}'", file=sys.stderr)
        sys.exit(1)

    result = analyze_video(
        args.video,
        sample_fps=args.sample_fps,
        min_visibility=args.min_visibility,
        model_complexity=args.model_complexity,
    )

    indent = 2 if args.pretty else None
    output_json = json.dumps(result, indent=indent, ensure_ascii=False)

    print(output_json)

    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"\nGuardado en {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
