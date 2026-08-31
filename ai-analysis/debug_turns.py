#!/usr/bin/env python3
"""
Utilidad de debug/calibracion (no es parte del pipeline de produccion).

Corre el mismo pipeline de deteccion de pose y segmentacion de giros que
analyze_ski_video.py, pero en lugar de devolver solo el JSON de patrones,
ubica cada giro detectado en el timeline del video original e imprime sus
timestamps, y guarda capturas (inicio/pico/fin de cada giro) con el
esqueleto de MediaPipe dibujado encima, para poder cotejar visualmente
contra el video que corres vos.

Uso:
  python debug_turns.py video.mp4 --out-dir turns_debug
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

from analyze_ski_video import (
    MIN_VISIBILITY_DEFAULT,
    SAMPLE_FPS_DEFAULT,
    compute_frame_metrics,
    extract_pose_sequence,
    format_ts,
    segment_turns,
)

SKELETON_EDGES = [
    ("left_shoulder", "right_shoulder"),
    ("left_hip", "right_hip"),
    ("left_shoulder", "left_hip"),
    ("right_shoulder", "right_hip"),
    ("left_hip", "left_knee"),
    ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"),
    ("right_knee", "right_ankle"),
]


def draw_skeleton(frame: np.ndarray, points: dict, w: int, h: int) -> np.ndarray:
    px = {name: (int(p[0] * w), int(p[1] * h)) for name, p in points.items()}
    for a, b in SKELETON_EDGES:
        cv2.line(frame, px[a], px[b], (0, 255, 0), 2)
    for pt in px.values():
        cv2.circle(frame, pt, 5, (0, 0, 255), -1)
    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video")
    parser.add_argument("--out-dir", default="turns_debug")
    parser.add_argument("--sample-fps", type=float, default=SAMPLE_FPS_DEFAULT)
    parser.add_argument("--min-visibility", type=float, default=MIN_VISIBILITY_DEFAULT)
    args = parser.parse_args()

    frames, _sampled_count, effective_fps = extract_pose_sequence(
        args.video, args.sample_fps, args.min_visibility, model_complexity=1
    )
    if not frames:
        print("No se detecto pose valida en ningun frame.", file=sys.stderr)
        sys.exit(1)

    metrics = compute_frame_metrics(frames)
    turns = segment_turns(metrics, effective_fps)

    if not turns:
        print("No se detectaron giros.", file=sys.stderr)
        sys.exit(0)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(args.video)
    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def grab_frame(video_frame_idx: int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, video_frame_idx)
        ok, frame = cap.read()
        return frame if ok else None

    header = f"{'#':<3} {'direccion':<10} {'inicio':<9} {'fin':<9} {'dur(s)':<7} {'rodilla_flex':<13} {'tronco_lean_abs':<16} {'rot_diff_abs':<12}"
    print(header)
    print("-" * len(header))

    for i, turn in enumerate(turns, start=1):
        segment_leans = [abs(metrics[j].trunk_lean) for j in range(turn.start_idx, turn.end_idx + 1)]
        peak_idx = turn.start_idx + int(np.argmax(segment_leans))

        t_start = frames[turn.start_idx].t
        t_end = frames[turn.end_idx].t
        t_peak = frames[peak_idx].t

        print(f"{i:<3} {turn.direction:<10} {format_ts(t_start):<9} {format_ts(t_end):<9} "
              f"{t_end - t_start:<7.2f} {turn.mean_knee_flex:<13.1f} {turn.mean_trunk_lean_abs:<16.1f} "
              f"{turn.mean_rotation_diff_abs:<12.1f}")

        for label, idx in [("inicio", turn.start_idx), ("pico", peak_idx), ("fin", turn.end_idx)]:
            video_frame_idx = round(frames[idx].t * source_fps)
            raw_frame = grab_frame(video_frame_idx)
            if raw_frame is None:
                continue
            annotated = draw_skeleton(raw_frame.copy(), frames[idx].points, w, h)
            cv2.putText(
                annotated,
                f"giro {i} ({turn.direction}) - {label} - t={frames[idx].t:.2f}s",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2,
            )
            out_path = out_dir / f"giro{i:02d}_{label}_{turn.direction}_t{frames[idx].t:.2f}s.jpg"
            cv2.imwrite(str(out_path), annotated)

    cap.release()
    print(f"\nCapturas guardadas en {out_dir}/")


if __name__ == "__main__":
    main()
