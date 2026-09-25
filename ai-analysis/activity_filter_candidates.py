#!/usr/bin/env python3
"""
Sprint "confiabilidad de carving", punto 2: medir señales candidatas para
filtrar "actividad no relevante" (arranque cerca del lift) antes de
segmentar giros, contra un ground truth marcado a mano.

Ground truth para video17 (ai-analysis/ground-truth-carving.md):
  t = 4.0s -- confirmado visualmente cruzando frames en
  debug_reports/baseline/frames/video17_influencer/ y
  ground_truth_scan_idx*.jpg (a t=3.37s todavia se ve el cartel/gente del
  sector de arranque; a t=4.12s ya no).

No fija todavia cual señal usar -- mide cada una contra el ground truth y
deja el resultado documentado en activity-filter-decision.md.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))

from analyze_ski_video import (
    compute_frame_metrics, segment_turns, format_ts, SAMPLE_FPS_DEFAULT,
    MIN_VISIBILITY_DEFAULT,
)
from instrument_video import extract_with_visibility

VIDEO = r"C:\Users\santi\ski-app\backend\media\videos\1\04f639126caf45d89f80f3d5418b20cd.mov"
GROUND_TRUTH_T = 4.0


def score(name, predicted_start_t, frames, metrics, turns):
    """Compara el timestamp de inicio predicho contra el ground truth, y
    mide cuantos frames de cada lado quedan mal clasificados."""
    gt = GROUND_TRUTH_T
    delta = predicted_start_t - gt

    # frames "arranque" (t < gt) que la señal deja pasar como validos (falso negativo)
    fn = sum(1 for f in frames if f.t < gt and f.t >= predicted_start_t)
    # frames "carving real" (t >= gt) que la señal descarta por error (falso positivo de descarte)
    fp = sum(1 for f in frames if f.t >= gt and f.t < predicted_start_t)

    # se mantienen intactos los giros reales (5 en adelante, que arrancan en t=3.37)?
    # un giro se considera "cortado" si predicted_start_t cae DENTRO de su rango
    # (start, end), no antes ni despues.
    cut_turn = None
    for i, t in enumerate(turns, start=1):
        t_start, t_end = frames[t.start_idx].t, frames[t.end_idx].t
        if t_start < predicted_start_t < t_end:
            cut_turn = i
            break

    return {
        "name": name,
        "predicted_start_t": round(predicted_start_t, 2),
        "delta_vs_ground_truth_s": round(delta, 2),
        "frames_arranque_dejados_pasar": fn,
        "frames_carving_real_descartados": fp,
        "corta_un_giro_a_la_mitad": cut_turn,
    }


def candidate_amplitud_duracion_por_giro(frames, metrics, turns, min_lean=15.0, min_dur=0.5):
    """C1: un giro cuenta como 'actividad valida' si su amplitud maxima de
    lean supera min_lean Y dura al menos min_dur segundos. El inicio
    predicho es el comienzo del primer giro que cumple ambas."""
    for t in turns:
        dur = frames[t.end_idx].t - frames[t.start_idx].t
        if t.max_trunk_lean_abs >= min_lean and dur >= min_dur:
            return frames[t.start_idx].t
    return frames[0].t if frames else 0.0


def candidate_alternancia_consistente(frames, metrics, turns, window=3):
    """C2: primer giro que arranca una racha de >=window giros alternando
    direccion sin cortes. NOTA (ver resultado): segment_turns ya garantiza
    alternancia estricta entre giros CONSECUTIVOS por construccion (un
    segmento nuevo solo arranca cuando el signo cambia) -- este candidato
    es, por diseño del segmentador, siempre verdadero desde el primer
    giro. Se deja implementado para dejar constancia medida de por que se
    descarta, no se omite sin mas."""
    return frames[turns[0].start_idx].t if turns else (frames[0].t if frames else 0.0)


def candidate_rolling_std_lean(frames, metrics, turns, window_frames=8, std_threshold=8.0, sustain_frames=8):
    """C3: 'movimiento lateral sostenido' -- desviacion estandar movil de
    trunk_lean (ventana de window_frames). Arranca la actividad valida en
    el primer frame donde esa std supera std_threshold de forma sostenida
    (sustain_frames consecutivos por encima)."""
    lean = np.array([m.trunk_lean for m in metrics])
    n = len(lean)
    rolling_std = np.zeros(n)
    for i in range(n):
        lo = max(0, i - window_frames + 1)
        rolling_std[i] = np.std(lean[lo:i + 1]) if i - lo >= 2 else 0.0

    over = rolling_std >= std_threshold
    run = 0
    for i in range(n):
        run = run + 1 if over[i] else 0
        if run >= sustain_frames:
            start_idx = i - sustain_frames + 1
            return frames[start_idx].t
    return frames[0].t if frames else 0.0


def candidate_amplitud_frame_sostenida(frames, metrics, turns, min_lean=12.0, sustain_frames=10):
    """C4: por-frame (no por-giro): primer punto donde abs(trunk_lean) se
    mantiene por encima de min_lean durante sustain_frames consecutivos."""
    lean = np.array([abs(m.trunk_lean) for m in metrics])
    over = lean >= min_lean
    run = 0
    for i in range(len(lean)):
        run = run + 1 if over[i] else 0
        if run >= sustain_frames:
            start_idx = i - sustain_frames + 1
            return frames[start_idx].t
    return frames[0].t if frames else 0.0


def candidate_min_giros_consecutivos_validos(frames, metrics, turns, min_lean=15.0, min_dur=0.4, n_consecutivos=3):
    """C5 (compuesto): primer giro que arranca una racha de N giros
    consecutivos que TODOS cumplen amplitud+duracion minima."""
    def ok(t):
        dur = frames[t.end_idx].t - frames[t.start_idx].t
        return t.max_trunk_lean_abs >= min_lean and dur >= min_dur

    for i in range(len(turns) - n_consecutivos + 1):
        window = turns[i:i + n_consecutivos]
        if all(ok(t) for t in window):
            return frames[window[0].start_idx].t
    return frames[0].t if frames else 0.0


def main():
    frames, all_sampled, sampled_count, eff_fps = extract_with_visibility(
        VIDEO, SAMPLE_FPS_DEFAULT, MIN_VISIBILITY_DEFAULT
    )
    metrics = compute_frame_metrics(frames)
    turns = segment_turns(metrics, eff_fps)

    candidates = [
        ("C1_amplitud_duracion_por_giro", candidate_amplitud_duracion_por_giro),
        ("C2_alternancia_consistente", candidate_alternancia_consistente),
        ("C3_rolling_std_lean_sostenido", candidate_rolling_std_lean),
        ("C4_amplitud_frame_sostenida", candidate_amplitud_frame_sostenida),
        ("C5_min_giros_consecutivos_validos", candidate_min_giros_consecutivos_validos),
    ]

    results = []
    for name, fn in candidates:
        t_pred = fn(frames, metrics, turns)
        results.append(score(name, t_pred, frames, metrics, turns))

    for r in results:
        print(r)

    import json
    Path("activity_filter_scores.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
