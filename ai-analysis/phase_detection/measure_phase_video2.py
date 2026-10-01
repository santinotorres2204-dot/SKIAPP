"""Valida la deteccion de fase recomendada en el punto 0 (transicion = cruce
por cero de com_x - tobillos; apice = extremo de trunk_lean con suavizado de
produccion) contra un segundo set de ground truth (ground_truth_video2.json:
prueba4, camara detras; prueba2, camara de frente).

Misma metodologia y mismas reglas de eventos que measure_phase_signals.py
(se importan de ahi, sin cambios). Se corrio DESPUES de cerrar
ground_truth_video2.json.

Uso (desde ai-analysis/, con su venv):
  python phase_detection/measure_phase_video2.py
"""
import json
import pickle
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import measure_phase_signals as M  # noqa: E402

REPO = HERE.parent.parent
GT2 = json.loads((HERE / "ground_truth_video2.json").read_text(encoding="utf-8"))
SIGNALS = ["com_x - tobillos (/torso)", "trunk_lean prod (MA 5 frames)", "trunk_lean (actual)", "flexion rodilla"]


def load(video: Path, fps: int):
    cache = M.CACHE_DIR / f"pose_{video.stem}_{fps}.pkl"
    if cache.exists():
        return pickle.loads(cache.read_bytes())
    frames, n, eff = M.A.extract_pose_sequence(str(video), fps, M.A.MIN_VISIBILITY_DEFAULT, model_complexity=1)
    cache.write_bytes(pickle.dumps((frames, n, eff)))
    return frames, n, eff


def container_ts(video: Path) -> np.ndarray:
    cap = cv2.VideoCapture(str(video))
    ts = []
    while cap.grab():
        ts.append(cap.get(cv2.CAP_PROP_POS_MSEC) / 1000)
    return np.array(ts)


def gt_events(spec: dict, only_high: bool) -> dict:
    ok = (lambda e: e["confianza"] == "alta") if only_high else (lambda e: True)
    return {
        "transicion": [c["t"] for c in spec["crossings"] if ok(c)],
        "apice": [t["apice"] for t in spec["turns"] if t["apice"] is not None and ok(t)],
        "entrada": [t["entrada"] for t in spec["turns"] if ok(t)],
    }


def main():
    M.CACHE_DIR.mkdir(exist_ok=True)
    report = {}
    for name, spec in GT2["videos"].items():
        video = REPO / spec["file"]
        M.WIN = (spec["tramo"][0] - 0.05, spec["tramo"][1] + 0.05)
        cts = container_ts(video)
        source_fps = cv2.VideoCapture(str(video)).get(cv2.CAP_PROP_FPS)
        report[name] = {}
        for fps in (8, 28):
            frames, n, eff = load(video, fps)
            t, sig = M.signals(frames, eff, cts, source_fps)
            inwin = (t >= M.WIN[0]) & (t <= M.WIN[1])
            gaps = np.diff(t[inwin])
            print(f"\n===== {name} @ {fps} fps (efectivo {eff:.2f}) - frames validos en tramo: {inwin.sum()}"
                  f" / gap max {gaps.max() if len(gaps) else float('nan'):.3f}s")
            report[name][fps] = {"frames_validos_tramo": int(inwin.sum())}
            for sname in SIGNALS:
                x = sig[sname]
                ev = M.events_knee(t, x) if sname.startswith("flexion") else M.events_oscillating(t, x)
                report[name][fps][sname] = {}
                for scope, only_high in (("alta", True), ("todos", False)):
                    gt = gt_events(spec, only_high)
                    for kind in ("transicion", "apice", "entrada"):
                        if not ev[kind] or not gt[kind]:
                            continue
                        r = M.compare(ev[kind], gt[kind])
                        report[name][fps][sname].setdefault(scope, {})[kind] = r
                        if scope == "alta" or kind != "entrada":
                            print(f"{sname:32} [{scope:5}] {kind:10} det={r['detectados']:4} extra={r['extra']}  sesgo={r['sesgo']}"
                                  f"  disp={r['dispersion']}  max={r['max_abs']}  {r['errores']}")
    (HERE / "report_video2.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
