import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings

MEDIA_ROOT = (Path(__file__).resolve().parent.parent / settings.video_upload_dir).resolve()
SEASON_REVIEWS_ROOT = (Path(__file__).resolve().parent.parent / "media" / "season_reviews").resolve()


def _save_file(root: Path, url_prefix: str, owner_id: int, upload: UploadFile) -> tuple[str, Path]:
    owner_dir = root / str(owner_id)
    owner_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(upload.filename or "").suffix
    filename = f"{uuid.uuid4().hex}{suffix}"
    dest = owner_dir / filename

    with dest.open("wb") as out:
        while chunk := upload.file.read(1024 * 1024):
            out.write(chunk)

    return f"{url_prefix}/{owner_id}/{filename}", dest


def save_video(user_id: int, upload: UploadFile) -> tuple[str, Path]:
    """Guarda un video de analisis y devuelve (file_url, path_en_disco)."""
    return _save_file(MEDIA_ROOT, "/media/videos", user_id, upload)


def save_season_review_video(user_id: int, upload: UploadFile) -> tuple[str, Path]:
    """Guarda el video comparativo (editado a mano) de un Season Review."""
    return _save_file(SEASON_REVIEWS_ROOT, "/media/season_reviews", user_id, upload)
