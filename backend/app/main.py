from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.database import engine
from app.routers import trips, users, video_uploads
from app.storage import MEDIA_ROOT

app = FastAPI(title="Ski App API", version="0.1.0")

MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/media/videos", StaticFiles(directory=MEDIA_ROOT), name="media")

app.include_router(users.router)
app.include_router(trips.router)
app.include_router(video_uploads.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/db")
def health_db() -> dict:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
