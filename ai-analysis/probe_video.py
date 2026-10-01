#!/usr/bin/env python3
"""
Verifica que un archivo sea un video realmente decodificable, antes de que el
backend lo acepte (backend/app/storage.py). Corre en este venv porque OpenCV
vive aca y no en el backend (spec seccion 9, mismo motivo que analysis_job.py).

Imprime siempre un JSON en stdout y sale con codigo 0; el veredicto va en "ok"
(y, si es False, "code" estable para el backend + "reason" legible).
No basta con la extension ni con el content-type (se pueden falsear): se exige
que OpenCV abra el contenedor, reporte dimensiones y fps validos y decodifique
un cuadro real al principio y otro cerca del final (un archivo cortado abre
igual y decodifica el primero).

Uso:
  python probe_video.py archivo.mp4
"""

from __future__ import annotations

import json
import sys

import cv2


def probe(path: str) -> dict:
    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            return {"ok": False, "code": "not_openable", "reason": "no se pudo abrir como video"}

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if width <= 0 or height <= 0:
            return {"ok": False, "code": "no_video_track", "reason": "no tiene una pista de video con dimensiones validas"}
        if fps <= 0:
            return {"ok": False, "code": "no_fps", "reason": "no tiene una frecuencia de cuadros valida"}

        ok, frame = cap.read()
        if not ok or frame is None or frame.size == 0:
            return {"ok": False, "code": "no_frames", "reason": "no se pudo decodificar ningun cuadro"}

        # Un archivo cortado (subida interrumpida, o solo la cabecera de un
        # video real) abre y decodifica el primer cuadro igual, pero no llega
        # al final: se exige decodificar tambien un cuadro cerca del final.
        if frame_count > 1:
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(1, int(frame_count * 0.9)))
            ok, frame = cap.read()
            if not ok or frame is None or frame.size == 0:
                return {"ok": False, "code": "truncated", "reason": "el archivo esta incompleto o danado (no se puede reproducir hasta el final)"}

        return {
            "ok": True,
            "width": width,
            "height": height,
            "fps": round(fps, 3),
            "frame_count": frame_count,
            "duration_sec": round(frame_count / fps, 2) if frame_count > 0 else None,
        }
    finally:
        cap.release()


def main() -> None:
    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "code": "usage", "reason": "uso: probe_video.py <archivo>"}))
        return
    try:
        result = probe(sys.argv[1])
    except Exception as exc:  # cualquier fallo del decoder es "no es un video valido"
        result = {"ok": False, "code": "decoder_error", "reason": f"error al decodificar: {type(exc).__name__}"}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
