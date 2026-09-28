from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.database import SessionLocal
from app.models import AnalysisResult, VideoUpload
from app.models.enums import AnalysisStatus

# ai-analysis vive fuera de backend/, con su propio venv (mediapipe/opencv son
# pesados y deliberadamente aislados del backend -- spec seccion 9). Se invoca
# como subproceso en vez de importarlo para no duplicar esas dependencias.
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AI_ANALYSIS_DIR = REPO_ROOT / "ai-analysis"
AI_ANALYSIS_SCRIPT = AI_ANALYSIS_DIR / "analyze_ski_video.py"
AI_ANALYSIS_PYTHON = AI_ANALYSIS_DIR / ".venv" / "Scripts" / "python.exe"
if not AI_ANALYSIS_PYTHON.exists():
    AI_ANALYSIS_PYTHON = AI_ANALYSIS_DIR / ".venv" / "bin" / "python"

ANALYSIS_TIMEOUT_SECONDS = 600


def _run_mediapipe(video_path: Path, discipline_tag: str | None) -> dict:
    cmd = [str(AI_ANALYSIS_PYTHON), str(AI_ANALYSIS_SCRIPT), str(video_path)]
    if discipline_tag:
        # Interpretacion especifica por disciplina (por ahora carving, moguls,
        # freeride y powder la usan; park y all_mountain ignoran el flag y
        # siguen con el analisis generico -- ver NOTES.md "Interpretacion por
        # disciplina").
        cmd += ["--discipline", discipline_tag]
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
