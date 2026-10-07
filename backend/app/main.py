import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import text

from app.analysis_job import resume_pending_analyses
from app.config import settings
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
from app.site_auth import SiteBasicAuthMiddleware, public_paths
from app.storage import MEDIA_ROOT, SEASON_REVIEWS_ROOT, clean_incoming

# Uvicorn solo configura sus propios loggers; sin esto los logger.info de
# app.* (analisis retomados, limpieza de _incoming) no se ven.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")
logger = logging.getLogger(__name__)

if settings.is_production and not settings.site_password:
    # En desarrollo, sin SITE_PASSWORD el sitio queda abierto a proposito. En
    # produccion eso seria exponerlo todo por un olvido: mejor no arrancar.
    raise RuntimeError("APP_ENV=production requiere SITE_PASSWORD")


@asynccontextmanager
async def lifespan(app: FastAPI):
    removed = clean_incoming()
    if removed:
        logger.info("Borrados %d uploads incompletos de una ejecucion anterior", removed)
    resume_pending_analyses()
    yield


# En produccion no se publica el mapa de la API: hay que apagar los tres, con
# solo /docs apagado /openapi.json lo sigue exponiendo entero.
_docs = {} if not settings.is_production else {"docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(title="Ski App API", version="0.1.0", lifespan=lifespan, **_docs)

STATIC_ROOT = Path(__file__).resolve().parent.parent / "static"

if settings.site_password:
    app.add_middleware(
        SiteBasicAuthMiddleware,
        password=settings.site_password,
        username=settings.site_user,
        public=public_paths(STATIC_ROOT / "manifest.json"),
    )
app.mount("/static", StaticFiles(directory=STATIC_ROOT), name="static")


@app.get("/sw.js", include_in_schema=False)
def service_worker() -> FileResponse:
    # Se sirve desde la raiz (no /static/sw.js) a proposito: el scope de un
    # service worker por defecto es la carpeta desde donde se sirve, y
    # necesitamos que cubra todo el sitio ("/") para poder interceptar los
    # fetch de imagenes que disparan paginas fuera de /static/, no solo
    # pedidos ya hechos a /static/. El archivo en si vive junto al resto de
    # los assets estaticos (backend/static/sw.js).
    return FileResponse(STATIC_ROOT / "sw.js", media_type="application/javascript")

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
