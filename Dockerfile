# Imagen unica para Railway: backend (FastAPI) + ai-analysis (MediaPipe/OpenCV)
# en un solo entorno de Python. El analisis sigue corriendo como subproceso
# (analysis_job.py / storage.py): el aislamiento que importa en produccion es
# el de proceso (timeout, crash nativo, memoria liberada al terminar), no el
# de venv. Ver docs/deploy-readiness.md.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# libmediapipe.so (la libreria C que carga la Tasks API) enlaza contra EGL y
# GLES aunque corra en CPU; sin estas dos, PoseLandmarker.create_from_options
# falla con "libEGL.so.1: cannot open shared object file". `import mediapipe`
# solo NO lo detecta: la libreria se carga recien al crear el landmarker.
RUN apt-get update  && apt-get install -y --no-install-recommends libegl1 libgles2  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Misma version que trae mediapipe 1.0.1 (opencv-contrib-python), pero
# headless: sin GUI, no necesita libGL/libglib en la imagen.
ARG OPENCV_VERSION=5.0.0.93

COPY backend/requirements.txt backend/requirements.txt
COPY ai-analysis/requirements.txt ai-analysis/requirements.txt
RUN pip install -r backend/requirements.txt -r ai-analysis/requirements.txt \
 && pip uninstall -y opencv-contrib-python opencv-python \
 && pip install --no-deps "opencv-contrib-python-headless==${OPENCV_VERSION}" \
 && python -c "import cv2, mediapipe; print('cv2', cv2.__version__, '| mediapipe', mediapipe.__version__)"

COPY ai-analysis/analyze_ski_video.py ai-analysis/probe_video.py ai-analysis/

# El modelo de pose se baja en el build, no en el primer analisis: sin red en
# runtime, sin carrera entre dos analisis simultaneos y sin perderlo en cada
# redeploy. La URL es "latest": el hash detecta si Google lo cambia (habria
# que re-validar contra el ground truth antes de aceptar el nuevo).
ARG POSE_MODEL_SHA256=59929e1d1ee95287735ddd833b19cf4ac46d29bc7afddbbf6753c459690d574a
RUN python -c "import sys; sys.path.insert(0, 'ai-analysis'); import analyze_ski_video as a; a.ensure_pose_landmarker_model()" \
 && echo "${POSE_MODEL_SHA256}  ai-analysis/models/pose_landmarker_lite.task" | sha256sum -c -

COPY backend/ backend/

ENV AI_ANALYSIS_PYTHON=/usr/local/bin/python \
    AI_ANALYSIS_DIR=/app/ai-analysis \
    MEDIA_ROOT=/app/backend/media \
    HOST=0.0.0.0 \
    PORT=8000

# Montar aca el volumen (Railway o compose): videos/, season_reviews/ y
# _incoming/ quedan en el mismo filesystem.
VOLUME ["/app/backend/media"]

WORKDIR /app/backend
EXPOSE 8000

# Un solo proceso uvicorn (sin --workers): la cola de analisis y el retomado
# de pending al arrancar suponen un unico proceso (ver analysis_job.py).
# Las migraciones NO corren aca: en Railway van como pre-deploy command
# (alembic upgrade head).
CMD ["sh", "-c", "exec uvicorn app.main:app --host \"$HOST\" --port \"$PORT\" --proxy-headers --forwarded-allow-ips='*'"]
