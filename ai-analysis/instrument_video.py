#!/usr/bin/env python3
"""
Instrumentacion del pipeline de analisis (sprint "confiabilidad de carving",
punto 4) -- NO cambia el comportamiento de analyze_ski_video.py, lo importa
y lo reusa tal cual. Genera, para un video:

  - un reporte por-frame (timestamp, landmarks, visibility, valores
    geometricos raw y suavizados, giro al que pertenece, si fue
    considerado "actividad valida")
  - un reporte por-instancia para cada patron (disparo o no, motivo,
    threshold aplicado, gap)
  - screenshots con pose overlay (mismo mecanismo que debug_turns.py) para
    los frames mas relevantes de cada patron

Salida: <out_dir>/<label>.json (todo el detalle, machine-readable) y
<out_dir>/<label>.md (tabla resumen human-readable) + <out_dir>/frames/.

Uso:
  python instrument_video.py video.mp4 --discipline carving --label baseline_video17 --out-dir debug_reports/baseline
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import vision
from mediapipe.tasks.python.core.base_options import BaseOptions

sys.path.insert(0, str(Path(__file__).parent))

from analyze_ski_video import (
    REQUIRED_LANDMARKS, PoseFrame, compute_frame_metrics, segment_turns,
    format_ts, ensure_pose_landmarker_model, _moving_average,
    ASYMMETRY_THRESHOLDS, ROTATION_THRESHOLDS_DEG, INCONSISTENCY_CV_THRESHOLDS,
    BALANCE_LOSS_PROPORTION_THRESHOLDS, BACKWARD_LEAN_THRESHOLDS_DEG,
    MIN_TURNS_FOR_ASYMMETRY, MIN_TURNS_FOR_INCONSISTENCY, MIN_VALID_FRAMES_FOR_BALANCE,
    MIN_VALID_FRAMES_FOR_ROTATION, SUSTAINED_ROTATION_PROPORTION,
    MIN_VALID_FRAMES_FOR_WEIGHT_POSITION, SUSTAINED_BACKWARD_PROPORTION,
    SAMPLE_FPS_DEFAULT, MIN_VISIBILITY_DEFAULT, SMOOTHING_WINDOW, LEAN_DEAD_ZONE_DEG,
    _severity_from_thresholds, detect_asymmetry, detect_balance_loss,
    detect_rotation_excessive, detect_inconsistency, detect_weight_position,
    compute_confidence_score, analyze_video,
)
from debug_turns import draw_skeleton


# ---------------------------------------------------------------------------
# Extraccion con visibilidad cruda (igual criterio que audit-carving-video.md)
# ---------------------------------------------------------------------------

def extract_with_visibility(video_path, sample_fps, min_visibility):
    cap = cv2.VideoCapture(str(video_path))
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

    frames, all_sampled = [], []
    frame_idx, sampled_count, last_ts = 0, 0, -1

    with vision.PoseLandmarker.create_from_options(options) as landmarker:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % frame_interval == 0:
                sampled_count += 1
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                ts_ms = max(int(frame_idx / source_fps * 1000), last_ts + 1)
                last_ts = ts_ms
                result = landmarker.detect_for_video(mp_image, ts_ms)

                t = frame_idx / source_fps
                rec = {"video_frame_idx": frame_idx, "t": t, "detected": False,
                       "visibility": {}, "valid": False}
                if result.pose_landmarks:
                    landmarks = result.pose_landmarks[0]
                    rec["detected"] = True
                    points, visible_enough = {}, True
                    for name, lm_idx in REQUIRED_LANDMARKS.items():
                        lm = landmarks[lm_idx]
                        rec["visibility"][name] = round(float(lm.visibility), 4)
                        if lm.visibility < min_visibility:
                            visible_enough = False
                        points[name] = np.array([lm.x, lm.y, lm.z])
                    rec["valid"] = visible_enough
                    if visible_enough:
                        frames.append(PoseFrame(index=sampled_count - 1, t=t, points=points))
                all_sampled.append(rec)
            frame_idx += 1
    cap.release()
    return frames, all_sampled, sampled_count, effective_fps


def which_turn(frame_idx, turns):
    """A que giro (1-based) pertenece un indice de la lista de frames
    validos, o None si cae en un tramo descartado (dead zone / giro
    demasiado corto para contar segun MIN_TURN_DURATION_SEC)."""
    for i, t in enumerate(turns, start=1):
        if t.start_idx <= frame_idx <= t.end_idx:
            return i
    return None


# ---------------------------------------------------------------------------
# Reporte por-frame
# ---------------------------------------------------------------------------

def build_frame_rows(frames, metrics, turns, valid_activity_mask=None):
    lean = np.array([m.trunk_lean for m in metrics])
    smoothed = _moving_average(lean, SMOOTHING_WINDOW) if len(lean) else lean

    rows = []
    for i, (f, m) in enumerate(zip(frames, metrics)):
        rows.append({
            "frame_idx": i,
            "video_frame_idx": f.index,
            "t": round(f.t, 3),
            "t_fmt": format_ts(f.t),
            "turn": which_turn(i, turns),
            "trunk_lean_raw": round(float(lean[i]), 2),
            "trunk_lean_smoothed": round(float(smoothed[i]), 2),
            "knee_flex_left": round(m.knee_flex_left, 1),
            "knee_flex_right": round(m.knee_flex_right, 1),
            "rotation_diff_deg_zaxis": round(m.rotation_diff, 1),
            "trunk_fore_aft_deg": round(m.trunk_fore_aft_deg, 1),
            "valid_activity": bool(valid_activity_mask[i]) if valid_activity_mask is not None else True,
            "valid_activity_note": "sin filtro de actividad todavia (punto 2 del sprint, pendiente)" if valid_activity_mask is None else None,
        })
    return rows


def attach_visibility(rows, frames, all_sampled):
    by_t = {round(r["t"], 6): r for r in all_sampled}
    for row, f in zip(rows, frames):
        rec = by_t.get(round(f.t, 6))
        row["visibility"] = rec["visibility"] if rec else {}
    return rows


# ---------------------------------------------------------------------------
# Reporte por-patron (igual metodologia que audit-carving-video.md, pero
# formalizado para correr sobre cualquier video)
# ---------------------------------------------------------------------------

def build_pattern_report(metrics, turns, discipline_tag, metrics_full=None):
    """metrics: lista ya recortada por el filtro de actividad valida (se
    usa para los patrones por-frame: rotacion/balance/peso-atras).
    metrics_full: lista COMPLETA sin recortar -- turn.start_idx/end_idx
    (de segment_turns) siempre indexan contra esta, nunca contra la
    recortada, asi que asimetria/inconsistencia (que resuelven ocurrencias
    via esos indices) necesitan la version completa aunque `turns` ya
    venga filtrado a los giros de actividad valida. Si no se pasa, se
    asume que metrics YA es la completa (compatibilidad con el uso
    original de esta funcion, pre-filtro de actividad)."""
    if metrics_full is None:
        metrics_full = metrics
    report = {}

    # asimetria_izq_der -- sprint "confiabilidad de carving", punto 3:
    # diagnostico extra (diff exacta por metrica, variabilidad por lado,
    # PERSISTENCIA de la diferencia en el tiempo). No cambia si el patron
    # dispara o no (eso sigue siendo detect_asymmetry sin tocar) -- es
    # evidencia adicional para decidir si la logica necesita cambiar, ver
    # asymmetry-review.md.
    left = [t for t in turns if t.direction == "izquierda"]
    right = [t for t in turns if t.direction == "derecha"]
    asym = detect_asymmetry(turns, metrics_full)
    if len(left) >= MIN_TURNS_FOR_ASYMMETRY and len(right) >= MIN_TURNS_FOR_ASYMMETRY:
        def rel_diff(a, b):
            d = (a + b) / 2.0
            return abs(a - b) / d if d > 1e-9 else 0.0
        knee_l, knee_r = np.mean([t.mean_knee_flex for t in left]), np.mean([t.mean_knee_flex for t in right])
        lean_l, lean_r = np.mean([t.mean_trunk_lean_abs for t in left]), np.mean([t.mean_trunk_lean_abs for t in right])
        diff_knee = rel_diff(knee_l, knee_r)
        diff_lean = rel_diff(lean_l, lean_r)
        diff = max(diff_knee, diff_lean)

        # persistencia: se parte la secuencia de giros (en orden temporal,
        # no por lado) en 2 mitades y se mide la asimetria de lean por
        # separado en cada una -- una diferencia "real y estable" deberia
        # verse parecida en ambas mitades; si una mitad esta muy por
        # encima de la otra, el agregado de todo el video puede estar
        # escondiendo una tendencia (ej. fatiga) en vez de describir un
        # sesgo constante.
        half = len(turns) // 2
        def half_asym(ts):
            l = [t.mean_trunk_lean_abs for t in ts if t.direction == "izquierda"]
            r = [t.mean_trunk_lean_abs for t in ts if t.direction == "derecha"]
            if not l or not r:
                return None
            return round(float(rel_diff(np.mean(l), np.mean(r))), 4)
        persistence_first_half = half_asym(turns[:half]) if half >= MIN_TURNS_FOR_ASYMMETRY else None
        persistence_second_half = half_asym(turns[half:]) if len(turns) - half >= MIN_TURNS_FOR_ASYMMETRY else None

        report["asimetria_izq_der"] = {
            "fired": asym is not None, "severity": asym["severity"] if asym else None,
            "value": round(float(diff), 4), "diff_knee_pct": round(diff_knee * 100, 2),
            "diff_lean_pct": round(diff_lean * 100, 2),
            "n_left": len(left), "n_right": len(right),
            "std_lean_left": round(float(np.std([t.mean_trunk_lean_abs for t in left])), 2) if left else None,
            "std_lean_right": round(float(np.std([t.mean_trunk_lean_abs for t in right])), 2) if right else None,
            "cv_lean_left": round(float(np.std([t.mean_trunk_lean_abs for t in left]) / lean_l), 4) if left and lean_l > 1e-6 else None,
            "cv_lean_right": round(float(np.std([t.mean_trunk_lean_abs for t in right]) / lean_r), 4) if right and lean_r > 1e-6 else None,
            "persistence_first_half": persistence_first_half,
            "persistence_second_half": persistence_second_half,
            "thresholds": ASYMMETRY_THRESHOLDS,
            "gap_to_baja": round(ASYMMETRY_THRESHOLDS["baja"] - diff, 4),
        }
    else:
        report["asimetria_izq_der"] = {"fired": False, "reason": f"insuficientes giros (izq={len(left)}, der={len(right)})", "thresholds": ASYMMETRY_THRESHOLDS}

    # rotacion_excesiva_tren_superior (sprint "confiabilidad de carving":
    # formula (x,y) + criterio de sostenido, ver rotation-metric-decision.md)
    rot = detect_rotation_excessive(metrics, turns)
    rot_vals = np.array([abs(m.rotation_diff) for m in metrics]) if metrics else np.array([])
    proportion_over_baja = float(np.mean(rot_vals >= ROTATION_THRESHOLDS_DEG["baja"])) if len(rot_vals) else None
    report["rotacion_excesiva_tren_superior"] = {
        "fired": rot is not None, "severity": rot["severity"] if rot else None,
        "mean": round(float(np.mean(rot_vals)), 2) if len(rot_vals) else None,
        "std": round(float(np.std(rot_vals)), 2) if len(rot_vals) else None,
        "proportion_over_baja": round(proportion_over_baja, 3) if proportion_over_baja is not None else None,
        "sustained_proportion_required": SUSTAINED_ROTATION_PROPORTION,
        "thresholds": ROTATION_THRESHOLDS_DEG,
    }

    # inconsistencia_entre_giros
    inc = detect_inconsistency(turns, metrics_full)
    if len(turns) >= MIN_TURNS_FOR_INCONSISTENCY:
        intens = np.array([t.max_trunk_lean_abs for t in turns])
        mean_i = float(np.mean(intens))
        cv = float(np.std(intens) / mean_i) if mean_i >= 1e-6 else None
        report["inconsistencia_entre_giros"] = {
            "fired": inc is not None, "severity": inc["severity"] if inc else None,
            "cv": round(cv, 4) if cv is not None else None, "n_turns": len(turns),
            "thresholds": INCONSISTENCY_CV_THRESHOLDS,
        }
    else:
        report["inconsistencia_entre_giros"] = {"fired": False, "reason": f"insuficientes giros ({len(turns)})", "thresholds": INCONSISTENCY_CV_THRESHOLDS}

    # perdida_de_balance
    bal = detect_balance_loss(metrics, len(turns))
    report["perdida_de_balance"] = {
        "fired": bal is not None, "severity": bal["severity"] if bal else None,
        "thresholds_proportion": BALANCE_LOSS_PROPORTION_THRESHOLDS,
    }

    # peso_hacia_atras
    w = detect_weight_position(metrics, discipline_tag)
    report["peso_hacia_atras"] = {
        "fired": w is not None, "severity": w["severity"] if w else None,
        "applicable": discipline_tag in BACKWARD_LEAN_THRESHOLDS_DEG,
    }

    return report


# ---------------------------------------------------------------------------
# Frames con overlay para los momentos mas relevantes
# ---------------------------------------------------------------------------

def save_key_frames(video_path, frames, metrics, turns, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    source_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def grab(vfi):
        cap.set(cv2.CAP_PROP_POS_FRAMES, vfi)
        ok, fr = cap.read()
        return fr if ok else None

    saved = []

    def save(label, idx, extra=""):
        if idx is None or idx >= len(frames):
            return
        f = frames[idx]
        vfi = round(f.t * source_fps)
        raw = grab(vfi)
        if raw is None:
            return
        annotated = draw_skeleton(raw.copy(), f.points, w, h)
        cv2.putText(annotated, f"{label} t={f.t:.2f}s {extra}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        path = out_dir / f"{label}.jpg"
        cv2.imwrite(str(path), annotated)
        saved.append(str(path))

    # pico de cada giro (siempre util como referencia visual rapida)
    for i, turn in enumerate(turns, start=1):
        seg = [abs(metrics[j].trunk_lean) for j in range(turn.start_idx, turn.end_idx + 1)]
        peak_idx = turn.start_idx + int(np.argmax(seg))
        save(f"giro{i:02d}_pico_{turn.direction}", peak_idx, f"lean={metrics[peak_idx].trunk_lean:.1f}")

    # frames mas extremos de rotacion y peso-atras (mismos criterios que la auditoria)
    if metrics:
        rot_vals = [abs(m.rotation_diff) for m in metrics]
        top_rot = int(np.argmax(rot_vals))
        save("rotacion_extremo", top_rot, f"rot={metrics[top_rot].rotation_diff:.1f}deg")

        fore_aft = [m.trunk_fore_aft_deg for m in metrics]
        top_back = int(np.argmax(fore_aft))
        save("peso_atras_extremo", top_back, f"fore_aft={metrics[top_back].trunk_fore_aft_deg:.1f}deg")

    cap.release()
    return saved


# ---------------------------------------------------------------------------
# Orquestacion
# ---------------------------------------------------------------------------

def instrument(video_path, discipline_tag, label, out_dir, sample_fps=SAMPLE_FPS_DEFAULT,
               min_visibility=MIN_VISIBILITY_DEFAULT, save_frames=True):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    frames, all_sampled, sampled_count, eff_fps = extract_with_visibility(video_path, sample_fps, min_visibility)
    metrics = compute_frame_metrics(frames)
    turns = segment_turns(metrics, eff_fps)

    # Sprint "confiabilidad de carving", punto 2: mismo filtro de actividad
    # valida que ya corre dentro de analyze_video() -- se importa la MISMA
    # funcion (find_activity_start_idx) en vez de reimplementar el criterio
    # a mano, para que este reporte de debug nunca se desincronice de lo
    # que produccion realmente hace.
    from analyze_ski_video import build_summary, build_discipline_note, find_activity_start_idx
    activity_start_idx = find_activity_start_idx(turns, metrics)
    metrics_va = metrics[activity_start_idx:]
    turns_va = [t for t in turns if t.start_idx >= activity_start_idx]

    # resultado "oficial" -- exactamente el mismo calculo que analyze_video()
    # (no se vuelve a correr MediaPipe una tercera vez, se reusan frames/
    # metrics/turns ya extraidos -- deterministicamente el mismo resultado).
    weight_pattern = detect_weight_position(metrics_va, discipline_tag)
    detections = [
        detect_asymmetry(turns_va, metrics), detect_balance_loss(metrics_va, len(turns_va)),
        detect_rotation_excessive(metrics_va, turns_va), detect_inconsistency(turns_va, metrics),
        weight_pattern,
    ]
    detected_patterns = [d for d in detections if d is not None]
    confidence = compute_confidence_score(len(metrics_va), sampled_count, len(turns_va))
    official = {
        "detected_patterns": detected_patterns,
        "confidence_score": confidence,
        "discipline_note": build_discipline_note(discipline_tag, weight_pattern),
        "summary": build_summary(detected_patterns, confidence, len(turns_va)),
        "meta": {
            "frames_sampled": sampled_count, "frames_with_valid_pose": len(frames),
            "effective_fps": round(eff_fps, 2), "turns_detected": len(turns),
            "turns_izquierda": sum(1 for t in turns if t.direction == "izquierda"),
            "turns_derecha": sum(1 for t in turns if t.direction == "derecha"),
            "activity_filter_start_t": round(metrics[activity_start_idx].t, 2) if metrics else None,
            "activity_filter_frames_discarded": activity_start_idx,
            "turns_valid_activity": len(turns_va),
            "frames_valid_activity": len(metrics_va),
        },
    }

    frame_rows = build_frame_rows(frames, metrics, turns, valid_activity_mask=[i >= activity_start_idx for i in range(len(metrics))])
    attach_visibility(frame_rows, frames, all_sampled)
    pattern_report = build_pattern_report(metrics_va, turns_va, discipline_tag, metrics_full=metrics)

    saved_frame_paths = []
    if save_frames:
        saved_frame_paths = save_key_frames(video_path, frames, metrics, turns, out_dir / "frames" / label)

    report = {
        "label": label,
        "video": str(video_path),
        "discipline_tag": discipline_tag,
        "sample_fps": sample_fps,
        "min_visibility": min_visibility,
        "sampled_count": sampled_count,
        "valid_frames": len(frames),
        "effective_fps": round(eff_fps, 2),
        "n_turns": len(turns),
        "official_result": official,
        "pattern_report": pattern_report,
        "turns": [
            {"n": i + 1, "direction": t.direction, "start_idx": t.start_idx, "end_idx": t.end_idx,
             "n_frames": t.end_idx - t.start_idx + 1,
             "t_start": format_ts(frames[t.start_idx].t), "t_end": format_ts(frames[t.end_idx].t),
             "max_trunk_lean_abs": round(t.max_trunk_lean_abs, 1)}
            for i, t in enumerate(turns)
        ],
        "frame_rows": frame_rows,
        "saved_frames": saved_frame_paths,
    }

    json_path = out_dir / f"{label}.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    md_path = out_dir / f"{label}.md"
    md_path.write_text(render_markdown(report), encoding="utf-8")

    print(f"JSON: {json_path}", file=sys.stderr)
    print(f"MD:   {md_path}", file=sys.stderr)
    return report


def render_markdown(report) -> str:
    lines = [f"# Debug report — {report['label']}", ""]
    lines.append(f"- Video: `{report['video']}`")
    lines.append(f"- Disciplina: `{report['discipline_tag']}`")
    lines.append(f"- Frames muestreados: {report['sampled_count']} | válidos: {report['valid_frames']} "
                  f"({report['valid_frames']/report['sampled_count']*100:.1f}%) | fps efectivo: {report['effective_fps']}")
    lines.append(f"- Giros detectados: {report['n_turns']}")
    m = report['official_result']['meta']
    lines.append(f"- Filtro de actividad válida: descarta {m.get('activity_filter_frames_discarded', 0)} "
                  f"frames iniciales (arranca en t={m.get('activity_filter_start_t')}s) → "
                  f"quedan {m.get('turns_valid_activity')} giros / {m.get('frames_valid_activity')} frames para los patrones")
    lines.append(f"- **confidence_score: {report['official_result']['confidence_score']}**")
    lines.append("")
    lines.append("## Patrones")
    lines.append("")
    lines.append("| Patrón | Disparó | Severidad | Detalle |")
    lines.append("|---|---|---|---|")
    for name, p in report["pattern_report"].items():
        detail = ", ".join(f"{k}={v}" for k, v in p.items() if k not in ("fired", "severity", "thresholds", "thresholds_proportion"))
        lines.append(f"| `{name}` | {'Sí' if p.get('fired') else 'No'} | {p.get('severity') or '—'} | {detail} |")
    lines.append("")
    lines.append("## Giros")
    lines.append("")
    lines.append("| # | dirección | inicio | fin | frames | max\\|lean\\| |")
    lines.append("|---|---|---|---|---|---|")
    for t in report["turns"]:
        lines.append(f"| {t['n']} | {t['direction']} | {t['t_start']} | {t['t_end']} | {t['n_frames']} | {t['max_trunk_lean_abs']} |")
    lines.append("")
    lines.append(f"## Frames guardados ({len(report['saved_frames'])})")
    lines.append("")
    for p in report["saved_frames"]:
        lines.append(f"- `{p}`")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("video")
    ap.add_argument("--discipline", default=None)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--sample-fps", type=float, default=SAMPLE_FPS_DEFAULT)
    ap.add_argument("--min-visibility", type=float, default=MIN_VISIBILITY_DEFAULT)
    ap.add_argument("--no-frames", action="store_true")
    args = ap.parse_args()

    instrument(args.video, args.discipline, args.label, args.out_dir,
               sample_fps=args.sample_fps, min_visibility=args.min_visibility,
               save_frames=not args.no_frames)


if __name__ == "__main__":
    main()
