import uuid
from pathlib import Path

from fastapi import UploadFile

from app.config import settings

MEDIA_ROOT = (Path(__file__).resolve().parent.parent / settings.video_upload_dir).resolve()


def save_video(user_id: int, upload: UploadFile) -> str:
    user_dir = MEDIA_ROOT / str(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(upload.filename or "").suffix
    filename = f"{uuid.uuid4().hex}{suffix}"
    dest = user_dir / filename

    with dest.open("wb") as out:
        while chunk := upload.file.read(1024 * 1024):
            out.write(chunk)

    return f"/media/videos/{user_id}/{filename}"
