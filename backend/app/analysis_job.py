from __future__ import annotations

import json
import logging
import subprocess
import threading
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import AnalysisResult, VideoUpload
from app.models.enums import AnalysisStatus
from app.storage import video_path_from_url

logger = logging.getLogger(__name__)

# ai-analysis vive fuera de backend/ (mediapipe/opencv son pesados y
# deliberadamente aislados del backend -- spec seccion 9). Se invoca como
# subproceso en vez de importarlo: el timeout corta de verdad, un crash
# nativo de MediaPipe no tira abajo al servidor web y la memoria se libera al
# terminar cada analisis. En desarrollo el interprete es el venv de
# ai-analysis; en el contenedor, el python unico de la imagen
# (AI_ANALYSIS_PYTHON, ver config.py).
AI_ANALYSIS_SCRIPT = settings.ai_analysis_dir / "analyze_ski_video.py"

ANALYSIS_TIMEOUT_SECONDS = 600

# Tope de analisis simultaneos en este proceso. BackgroundTasks corre cada
# job en un hilo del threadpool (hasta 40); sin este tope, N subidas juntas
# lanzan N subprocesos de ~300-600 MB y el OOM killer del contenedor puede
# llevarse al servidor web entero. Los que exceden quedan bloqueados aca,
# en estado pending, hasta que se libera un lugar.
_analysis_slots = threading.BoundedSemaphore(max(1, settings.max_concurrent_analyses))


def _run_mediapipe(video_path: Path, discipline_tag: str | None) -> dict:
    cmd = [settings.ai_analysis_python, str(AI_ANALYSIS_SCRIPT), str(video_path)]
    if discipline_tag:
        # Interpretacion especifica por disciplina (por ahora carving, moguls,
        # freeride y powder la usan; park y all_mountain ignoran el flag y
        # siguen con el analisis generico -- ver NOTES.md "Interpretacion por
        # disciplina"). park sigue pasando por este script A PROPOSITO:
        # analyze_park_video.py da falsos positivos de caida/inestabilidad
        # con pose a distancia + paneo de camara, y queda desconectado
        # (igual que snowboard) hasta validarlo con mas videos reales -- ver
        # NOTES.md "Enrutamiento de park".
        cmd += ["--discipline", discipline_tag]
    with _analysis_slots:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=ANALYSIS_TIMEOUT_SECONDS,
        )
    if proc.returncode != 0:
        raise RuntimeError(f"analyze_ski_video.py salio con codigo {proc.returncode}: {proc.stderr[-4000:]}")
    return json.loads(proc.stdout)


def run_analysis_job(video_id: int, video_path: Path) -> None:
    """Corre MediaPipe sobre un VideoUpload ya guardado en disco y persiste
    el AnalysisResult, actualizando analysis_status (pending -> processed/failed).

    Se dispara via FastAPI BackgroundTasks (spec seccion 3: "job asincrono,
    cola simple") -- no bloquea la respuesta HTTP de la subida. Abre su
    propia sesion de DB porque corre despues de que la request que lo
    origino ya termino y cerro la suya.
    """
    db = SessionLocal()
    try:
        video = db.get(VideoUpload, video_id)
        if video is None:
            return

        try:
            result = _run_mediapipe(video_path, video.discipline_tag)
        except Exception:
            video.analysis_status = AnalysisStatus.FAILED.value
            db.commit()
            raise

        # discipline_note (carving/moguls/freeride/powder, ver NOTES.md) y
        # asymmetry_note (sprint "confiabilidad de carving", ver
        # asymmetry-fix-decision.md: evidencia insuficiente para evaluar
        # asimetria izq/der no debe quedar en silencio total) no tienen
        # columna propia todavia -- se anteponen al summary para no
        # perderlos al persistir, en vez de agregar una migracion para este
        # primer paso.
        summary = result.get("summary")
        discipline_note = result.get("discipline_note")
        if discipline_note:
            summary = f"{discipline_note}\n\n{summary}" if summary else discipline_note
        asymmetry_note = result.get("asymmetry_note")
        if asymmetry_note:
            summary = f"{asymmetry_note}\n\n{summary}" if summary else asymmetry_note

        analysis = AnalysisResult(
            video_id=video_id,
            detected_patterns=result["detected_patterns"],
            confidence_score=result["confidence_score"],
            # "meta" es diagnostico agregado (frames muestreados/validos, giros
            # detectados), no keypoints crudos frame a frame -- analyze_video()
            # no los retiene. Se guarda igual aca para trazabilidad/auditoria.
            raw_pose_data=result.get("meta"),
            summary=summary,
        )
        db.add(analysis)
        video.analysis_status = AnalysisStatus.PROCESSED.value
        db.commit()
    finally:
        db.close()


def _resume_pending(jobs: list[tuple[int, Path]]) -> None:
    for video_id, video_path in jobs:
        try:
            run_analysis_job(video_id, video_path)
        except Exception:
            logger.exception("Fallo el analisis retomado del video %s", video_id)


def resume_pending_analyses() -> int:
    """Re-encola los videos que quedaron en pending por un reinicio (la cola
    de BackgroundTasks vive en memoria y se pierde con el proceso).

    Se llama al arrancar, antes de aceptar requests, asi que ningun pending
    puede tener un job vivo en este proceso. Supone un unico proceso web
    (uvicorn sin --workers): con varios, cada uno retomaria los mismos.
    Corre en un hilo aparte para no demorar el arranque; los jobs pasan por
    el mismo semaforo que las subidas nuevas. Si el archivo ya no existe, el
    video queda failed (no hay nada que analizar).
    """
    db = SessionLocal()
    try:
        pending = db.scalars(
            select(VideoUpload)
            .where(VideoUpload.analysis_status == AnalysisStatus.PENDING.value)
            .order_by(VideoUpload.id)
        ).all()
        jobs: list[tuple[int, Path]] = []
        for video in pending:
            path = video_path_from_url(video.file_url)
            if path is None or not path.is_file():
                logger.warning("Video %s en pending sin archivo (%s): queda failed", video.id, video.file_url)
                video.analysis_status = AnalysisStatus.FAILED.value
            else:
                jobs.append((video.id, path))
        db.commit()
    finally:
        db.close()

    if jobs:
        logger.info("Retomando %d analisis en pending: %s", len(jobs), [vid for vid, _ in jobs])
        threading.Thread(target=_resume_pending, args=(jobs,), name="resume-pending-analyses", daemon=True).start()
    return len(jobs)
