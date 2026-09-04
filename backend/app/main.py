from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from pathlib import Path

from app.database import engine
from app.routers import (
    achievements,
    admin,
    assessment,
    chat,
    coach,
    day_logs,
    freeride_runs,
    mental,
    passport,
    ride,
    runs,
    ski_ratings,
    trick_cards,
    trips,
    users,
    video_uploads,
)
from app.storage import MEDIA_ROOT, SEASON_REVIEWS_ROOT

app = FastAPI(title="Ski App API", version="0.1.0")

STATIC_ROOT = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")

MEDIA_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/media/videos", StaticFiles(directory=MEDIA_ROOT), name="media")

SEASON_REVIEWS_ROOT.mkdir(parents=True, exist_ok=True)
app.mount("/media/season_reviews", StaticFiles(directory=SEASON_REVIEWS_ROOT), name="media_season_reviews")

app.include_router(users.router)
app.include_router(trips.router)
app.include_router(video_uploads.router)
app.include_router(day_logs.router)
app.include_router(achievements.router)
app.include_router(ski_ratings.router)
app.include_router(admin.router)
app.include_router(passport.router)
app.include_router(runs.router)
app.include_router(ride.router)
app.include_router(chat.router)
app.include_router(coach.router)
app.include_router(assessment.router)
app.include_router(assessment.page_router)
app.include_router(mental.router)
app.include_router(mental.page_router)
app.include_router(trick_cards.router)
app.include_router(freeride_runs.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/db")
def health_db() -> dict:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}
