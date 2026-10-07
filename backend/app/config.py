from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


def _default_ai_analysis_python() -> str:
    # En desarrollo, ai-analysis tiene su propio venv (Windows o Linux). En el
    # contenedor no hay venv: se pasa AI_ANALYSIS_PYTHON explicito.
    venv = REPO_ROOT / "ai-analysis" / ".venv"
    for candidate in (venv / "Scripts" / "python.exe", venv / "bin" / "python"):
        if candidate.exists():
            return str(candidate)
    return "python"


class Settings(BaseSettings):
    # .env se busca junto a backend/, no en el directorio actual: asi uvicorn
    # y alembic leen lo mismo sin importar desde donde se lancen.
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # Sin default a proposito: si falta, la app no arranca (en vez de caer
    # silenciosamente a un localhost que en produccion no existe).
    database_url: str

    # "production" apaga /docs, /redoc y /openapi.json y exige SITE_PASSWORD.
    app_env: str = "development"

    # Contrasena compartida para todo el sitio (HTTP Basic Auth, ver
    # site_auth.py). Vacia = middleware inactivo (desarrollo local).
    # site_user vacio acepta cualquier usuario: solo importa la clave.
    site_password: str = ""
    site_user: str = ""

    # Raiz de todos los archivos subidos: videos/, season_reviews/ y
    # _incoming/ cuelgan de aca. Tienen que quedar en el mismo filesystem
    # (storage.py usa os.replace de _incoming al destino), por eso es una
    # sola raiz y no una ruta por carpeta. En Railway: el punto de montaje
    # del volumen.
    media_root: Path = BACKEND_DIR / "media"
    # Tope por archivo subido (videos de analisis y de Season Review). El video
    # real mas grande hasta hoy pesa 80 MB (32 s de .mov a 60 fps); 500 MB deja
    # margen para clips de un par de minutos sin aceptar cualquier cosa.
    max_video_upload_mb: int = 500

    # ai-analysis corre como subproceso (ver analysis_job.py).
    ai_analysis_dir: Path = REPO_ROOT / "ai-analysis"
    ai_analysis_python: str = _default_ai_analysis_python()
    # Cada analisis es un subproceso de ~300-600 MB; el limite de memoria del
    # contenedor incluye a los subprocesos. Los que excedan esperan su turno.
    max_concurrent_analyses: int = 1

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


settings = Settings()
