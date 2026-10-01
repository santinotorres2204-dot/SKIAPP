"""Mide senales candidatas de fase (entrada/apice/transicion) contra el ground
truth manual de video_id=17. Ver phase-detection-ground-truth.md.

Se corrio DESPUES de cerrar ground_truth.json. No modifica nada del pipeline:
importa extract_pose_sequence / compute_frame_metrics tal cual.

Uso (desde ai-analysis/, con su venv):
  python phase_detection/measure_phase_signals.py                 # tiempo real del contenedor
  python phase_detection/measure_phase_signals.py --pipeline-time # reloj del pipeline (frame_idx / fps)
"""
import json
import pickle
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import analyze_ski_video as A  # noqa: E402

VIDEO = str(HERE.parent.parent / "backend" / "media" / "videos" / "1" / "04f639126caf45d89f80f3d5418b20cd.mov")
GT = json.loads((HERE / "ground_truth.json").read_text(encoding="utf-8"))
CACHE_DIR = Path(tempfile.gettempdir()) / "ski_phase_detection_cache"
WIN = (16.20, 23.40)          # tramo marcado a mano
MATCH_TOL = 0.40              # < medio periodo de giro (~1 s)
ENTRY_FRACTION = 0.25         # "entrada" = primer instante tras el cruce con |senal| >= 25% del pico del giro
REAL_TIME = "--pipeline-time" not in sys.argv


def container_timestamps() -> np.ndarray:
    """Timestamp real (contenedor) de cada frame, en orden de lectura secuencial."""
    cache = CACHE_DIR / "container_ts.npy"
    if cache.exists():
        return np.load(cache)
    cap = cv2.VideoCapture(VIDEO)
    ts = []
    while cap.grab():
        ts.append(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000)
    np.save(cache, np.array(ts))
    return np.array(ts)


def load(fps):
    cache = CACHE_DIR / f"pose_{fps}.pkl"
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    frames, n, eff = A.extract_pose_sequence(VIDEO, fps, A.MIN_VISIBILITY_DEFAULT, model_complexity=1)
    cache.write_bytes(pickle.dumps((frames, n, eff)))
    return frames, n, eff


def time_mean(t, x, half):
    return np.array([x[np.abs(t - ti) <= half + 1e-9].mean() for ti in t])


def signals(frames, eff, container_ts, source_fps):
    m = A.compute_frame_metrics(frames)
    # El video es VFR: el pipeline usa t = frame_idx / fps_promedio, que en este
    # tramo atrasa 0.4-0.6 s respecto del tiempo real. El ground truth esta en
    # tiempo real del contenedor, asi que se remapea cada frame a ese reloj.
    if REAL_TIME:
        t = np.array([container_ts[round(x.t * source_fps)] for x in m])
    else:
        t = np.array([x.t for x in m])
    lean = np.array([x.trunk_lean for x in m])
    knee = np.array([(x.knee_flex_left + x.knee_flex_right) / 2 for x in m])
    com_x = np.array([x.com[0] for x in m])
    torso = np.array([x.torso_scale for x in m])
    ankle_x = np.array([(f.points["left_ankle"][0] + f.points["right_ankle"][0]) / 2 for f in frames])
    ref = np.median(torso)
    # suavizado liviano comun a todas (~0.375 s centrado), para no favorecer a ninguna
    half = 0.19
    s = {
        "trunk_lean (actual)": time_mean(t, lean, half),
        "trunk_lean prod (MA 5 frames)": A._moving_average(lean, A.SMOOTHING_WINDOW) if eff < 10 else time_mean(t, lean, 0.31),
        "com_x imagen (detrend 1 s)": time_mean(t, com_x - time_mean(t, com_x, 0.5), half) / ref,
        "com_x - tobillos (/torso)": time_mean(t, (com_x - ankle_x) / ref, half),
        "flexion rodilla": time_mean(t, knee, half),
    }
    return t, s


def zero_crossings(t, x):
    out = []
    for i in range(len(x) - 1):
        if x[i] == 0 or np.sign(x[i]) != np.sign(x[i + 1]):
            if t[i + 1] - t[i] > 0.4:      # no interpolar a traves de huecos de tracking
                continue
            a = abs(x[i]) / (abs(x[i]) + abs(x[i + 1]) + 1e-12)
            out.append(t[i] + a * (t[i + 1] - t[i]))
    return out


def events_oscillating(t, x):
    """Cruce = cruce por cero; apice = extremo de |x| entre cruces; entrada = primer
    instante tras el cruce con |x| >= ENTRY_FRACTION * pico."""
    cr = zero_crossings(t, x)
    ap, en = [], []
    for c0, c1 in zip(cr, cr[1:]):
        idx = np.nonzero((t > c0) & (t < c1))[0]
        if len(idx) == 0:
            continue
        k = idx[np.argmax(np.abs(x[idx]))]
        ap.append(t[k])
        peak = abs(x[k])
        for j in idx:
            if abs(x[j]) >= ENTRY_FRACTION * peak:
                # interpolar contra el frame previo (o el cruce)
                if j == idx[0]:
                    t0, v0 = c0, 0.0
                else:
                    t0, v0 = t[j - 1], abs(x[j - 1])
                v1 = abs(x[j])
                a = (ENTRY_FRACTION * peak - v0) / (v1 - v0 + 1e-12)
                en.append(t0 + a * (t[j] - t0))
                break
    return {"transicion": cr, "apice": ap, "entrada": en}


def events_knee(t, x):
    """Rodilla: apice = maximo local de flexion; cruce = minimo local (extension)."""
    def extrema(sign):
        out = []
        for i in range(1, len(x) - 1):
            w = np.nonzero(np.abs(t - t[i]) <= 0.35)[0]
            if sign * x[i] >= np.max(sign * x[w]) - 1e-9:
                out.append(t[i])
        return out
    return {"apice": extrema(+1), "transicion": extrema(-1), "entrada": []}


def gt_events():
    return {
        "transicion": [c["t"] for c in GT["crossings"]],
        "apice": [tr["apice"] for tr in GT["turns"]],
        "entrada": [tr["entrada"] for tr in GT["turns"]],
    }


def compare(pred, gt):
    pred_w = [p for p in pred if WIN[0] <= p <= WIN[1]]
    errs, used = [], set()
    for g in gt:
        cands = [(abs(p - g), i, p) for i, p in enumerate(pred_w) if i not in used and abs(p - g) <= MATCH_TOL]
        if not cands:
            errs.append(None)
            continue
        _, i, p = min(cands)
        used.add(i)
        errs.append(float(p - g))
    found = [e for e in errs if e is not None]
    return {
        "errores": [None if e is None else round(e, 3) for e in errs],
        "detectados": f"{len(found)}/{len(gt)}",
        "extra": len(pred_w) - len(used),
        "sesgo": round(float(np.mean(found)), 3) if found else None,
        "dispersion": round(float(np.std(found)), 3) if found else None,
        "max_abs": round(float(np.max(np.abs(found))), 3) if found else None,
        "mae": round(float(np.mean(np.abs(found))), 3) if found else None,
    }


def main():
    CACHE_DIR.mkdir(exist_ok=True)
    container_ts = container_timestamps()
    source_fps = cv2.VideoCapture(VIDEO).get(cv2.CAP_PROP_FPS)
    gt = gt_events()
    report = {}
    for fps in (8, 28):
        frames, n, eff = load(fps)
        t, sig = signals(frames, eff, container_ts, source_fps)
        inwin = (t >= WIN[0]) & (t <= WIN[1])
        print(f"\n===== {fps} fps (efectivo {eff:.2f}) - frames validos en tramo: {inwin.sum()} / gap max {np.max(np.diff(t[inwin])):.3f}s")
        report[fps] = {}
        for name, x in sig.items():
            ev = events_knee(t, x) if name.startswith("flexion") else events_oscillating(t, x)
            report[fps][name] = {}
            for kind in ("transicion", "apice", "entrada"):
                if not ev[kind]:
                    continue
                r = compare(ev[kind], gt[kind])
                report[fps][name][kind] = r
                print(f"{name:32} {kind:10} det={r['detectados']:4} extra={r['extra']}  sesgo={r['sesgo']}  disp={r['dispersion']}  mae={r['mae']}  max={r['max_abs']}  {r['errores']}")
    suffix = "" if REAL_TIME else "_pipeline_time"
    (HERE / f"report{suffix}.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
