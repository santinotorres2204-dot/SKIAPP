import json
import os
import subprocess
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import BACKEND_DIR, settings

_MEDIA_BASE = settings.media_root if settings.media_root.is_absolute() else BACKEND_DIR / settings.media_root
_MEDIA_BASE = _MEDIA_BASE.resolve()
MEDIA_ROOT = _MEDIA_BASE / "videos"
SEASON_REVIEWS_ROOT = _MEDIA_BASE / "season_reviews"
# Los uploads se escriben aca primero y solo se mueven a MEDIA_ROOT /
# SEASON_REVIEWS_ROOT (servidos como estaticos en main.py) despues de validar.
# Este directorio NO esta montado: un archivo a medio subir o rechazado nunca
# queda accesible por URL.
INCOMING_ROOT = _MEDIA_BASE / "_incoming"

VIDEOS_URL_PREFIX = "/media/videos"
SEASON_REVIEWS_URL_PREFIX = "/media/season_reviews"

PROBE_SCRIPT = settings.ai_analysis_dir / "probe_video.py"
PROBE_TIMEOUT_SECONDS = 60
MAX_UPLOAD_BYTES = settings.max_video_upload_mb * 1024 * 1024


def _is_iso_bmff(head: bytes) -> bool:
    # MP4/MOV/M4V: caja "ftyp" (o, en .mov viejos, otra caja de nivel raiz)
    # en el offset 4.
    return len(head) >= 12 and head[4:8] in (b"ftyp", b"moov", b"mdat", b"wide", b"free", b"skip")


def _is_ebml(head: bytes) -> bool:
    # WebM/MKV
    return head[:4] == b"\x1a\x45\xdf\xa3"


def _is_avi(head: bytes) -> bool:
    return head[:4] == b"RIFF" and head[8:12] == b"AVI "


# Extension aceptada -> chequeo de firma del contenedor. La extension con la
# que se guarda sale de esta lista (nunca se copia tal cual la del cliente),
# asi un archivo servido como estatico no puede terminar en .html/.py/etc.
_ALLOWED_VIDEO_TYPES = {
    ".mp4": _is_iso_bmff,
    ".m4v": _is_iso_bmff,
    ".mov": _is_iso_bmff,
    ".webm": _is_ebml,
    ".mkv": _is_ebml,
    ".avi": _is_avi,
}


def _reject(status_code: int, detail: str) -> HTTPException:
    return HTTPException(status_code, detail=detail)


def _stream_to_incoming(upload: UploadFile) -> Path:
    """Copia el upload a INCOMING_ROOT cortando apenas supera MAX_UPLOAD_BYTES."""
    INCOMING_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = INCOMING_ROOT / f"{uuid.uuid4().hex}.part"
    written = 0
    try:
        with tmp.open("wb") as out:
            while chunk := upload.file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise _reject(
                        status.HTTP_413_CONTENT_TOO_LARGE,
                        f"El video supera el tamaño máximo permitido ({settings.max_video_upload_mb} MB).",
                    )
                out.write(chunk)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    if written == 0:
        tmp.unlink(missing_ok=True)
        raise _reject(status.HTTP_400_BAD_REQUEST, "El archivo está vacío.")
    return tmp


# Motivos de rechazo de ai-analysis/probe_video.py ("code"), redactados para
# mostrarle al usuario.
_PROBE_REASONS = {
    "not_openable": "no se pudo abrir como video",
    "no_video_track": "no tiene una pista de video válida",
    "no_fps": "no tiene una frecuencia de cuadros válida",
    "no_frames": "no se pudo decodificar ningún cuadro",
    "truncated": "está incompleto o dañado (no se puede reproducir hasta el final)",
    "decoder_error": "no se pudo decodificar",
}


def _probe_decodable(path: Path) -> str | None:
    """Devuelve None si OpenCV decodifica el video, o el motivo si no."""
    try:
        proc = subprocess.run(
            [settings.ai_analysis_python, str(PROBE_SCRIPT), str(path)],
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
        result = json.loads(proc.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return "no se pudo verificar el archivo"
    if result.get("ok"):
        return None
    return _PROBE_REASONS.get(result.get("code"), "no es un video válido")


def _validate_video(tmp: Path, filename: str | None) -> str:
    """Valida extension + firma del contenedor + decodificacion real. Devuelve
    la extension normalizada con la que se va a guardar."""
    suffix = Path(filename or "").suffix.lower()
    signature_check = _ALLOWED_VIDEO_TYPES.get(suffix)
    allowed = ", ".join(sorted(_ALLOWED_VIDEO_TYPES))
    if signature_check is None:
        raise _reject(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Formato no soportado. Subí un video ({allowed}).",
        )

    with tmp.open("rb") as f:
        head = f.read(16)
    if not signature_check(head):
        raise _reject(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"El archivo no es un video {suffix} válido (su contenido no coincide con la extensión).",
        )

    reason = _probe_decodable(tmp)
    if reason is not None:
        raise _reject(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"El archivo no es un video reproducible: {reason}.",
        )
    return suffix


def _save_file(root: Path, url_prefix: str, owner_id: int, upload: UploadFile) -> tuple[str, Path]:
    tmp = _stream_to_incoming(upload)
    try:
        suffix = _validate_video(tmp, upload.filename)
        owner_dir = root / str(owner_id)
        owner_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid.uuid4().hex}{suffix}"
        dest = owner_dir / filename
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)

    return f"{url_prefix}/{owner_id}/{filename}", dest


def save_video(user_id: int, upload: UploadFile) -> tuple[str, Path]:
    """Valida y guarda un video de analisis; devuelve (file_url, path_en_disco).

    Lanza HTTPException 413/415/400 si el archivo no pasa la validacion.
    """
    return _save_file(MEDIA_ROOT, VIDEOS_URL_PREFIX, user_id, upload)


def save_season_review_video(user_id: int, upload: UploadFile) -> tuple[str, Path]:
    """Valida y guarda el video comparativo (editado a mano) de un Season Review."""
    return _save_file(SEASON_REVIEWS_ROOT, SEASON_REVIEWS_URL_PREFIX, user_id, upload)


def video_path_from_url(file_url: str) -> Path | None:
    """Ruta en disco de un video de analisis a partir de su file_url, o None
    si la URL no es de MEDIA_ROOT o apunta fuera de el."""
    prefix = VIDEOS_URL_PREFIX + "/"
    if not file_url.startswith(prefix):
        return None
    path = (MEDIA_ROOT / file_url[len(prefix):]).resolve()
    if not path.is_relative_to(MEDIA_ROOT):
        return None
    return path


def clean_incoming() -> int:
    """Borra uploads a medio escribir que quedaron de un proceso anterior
    (corte durante la subida). Solo se llama al arrancar, cuando no puede
    haber una subida en curso en este proceso."""
    if not INCOMING_ROOT.exists():
        return 0
    removed = 0
    for part in INCOMING_ROOT.glob("*.part"):
        part.unlink(missing_ok=True)
        removed += 1
    return removed
