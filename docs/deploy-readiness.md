# Preparación para deploy en Railway — auditoría

Fecha: 2026-10-05. Estado del repo: `e8051a9` (master, árbol limpio). Esto es solo un
diagnóstico: no se modificó código ni se creó ningún archivo de deploy.

Las cifras marcadas como **medido** se tomaron en esta máquina (Windows, Python 3.11.9).
Las marcadas como **estimado** son proyecciones para Linux/Railway y hay que confirmarlas
con el primer build.

---

## 1. Empaquetado

### Cómo funciona hoy

- `backend/` tiene su venv (FastAPI, SQLAlchemy, psycopg2…), sin OpenCV ni MediaPipe.
- `ai-analysis/` tiene otro venv con `mediapipe`, `opencv-python` y `numpy`.
- El backend llama a ese venv como **subproceso** en dos lugares:
  - `backend/app/analysis_job.py:18` → `analyze_ski_video.py` (análisis, timeout 600 s).
  - `backend/app/storage.py:20` → `probe_video.py` (valida que el upload sea un video que
    se pueda decodificar, timeout 60 s), **de forma sincrónica dentro de la request de subida**.
- El intérprete se resuelve así: `ai-analysis/.venv/Scripts/python.exe` y, si no existe,
  `ai-analysis/.venv/bin/python` (`analysis_job.py:17-19`). En Linux el fallback sirve,
  pero solo si el venv está exactamente en esa ruta dentro del contenedor.

### Problemas encontrados

1. **El modelo de pose no está en el repo.** `ai-analysis/models/` está en `.gitignore`.
   `analyze_ski_video.py:150-157` descarga `pose_landmarker_lite.task` (5,8 MB) desde
   `storage.googleapis.com` **la primera vez que corre un análisis**. En el contenedor eso
   implica:
   - una dependencia de red en runtime;
   - que el modelo se pierde en cada redeploy, porque queda fuera del volumen;
   - una **condición de carrera**: `urlretrieve` escribe directo sobre la ruta final, así
     que dos análisis simultáneos al arrancar pueden leer un `.task` a medio escribir.

   → Hay que descargarlo **en el build** (`RUN python -c "...ensure_pose_landmarker_model()"`
   o un `curl` en el Dockerfile).
2. **Hay dos OpenCV instalados a la vez.** `mediapipe 1.0.1` depende de `opencv-contrib-python`,
   y `ai-analysis/requirements.txt` agrega además `opencv-python`. Los dos escriben en el
   mismo paquete `cv2/`, y cuál queda depende del orden de instalación. Además, en Linux
   las dos variantes "no headless" necesitan `libGL.so.1` y `libglib2.0`, que **no
   vienen en `python:3.11-slim`** (el `import cv2` falla con `ImportError: libGL.so.1`).
   → Hay que sacar `opencv-python` de `requirements.txt` (mediapipe ya trae contrib) y hacer
   `apt-get install libgl1 libglib2.0-0` en la imagen.
3. **Faltan dependencias transitivas pesadas.** `mediapipe` también arrastra `matplotlib`
   y `sounddevice`, que no se usan en producción pero no se pueden excluir sin `--no-deps`
   (frágil). Se aceptan.
4. **El decoder de video cambia entre Windows y Linux.** En Windows OpenCV puede usar el
   backend MSMF. En Linux usa siempre el FFmpeg incluido en el wheel. El arreglo de fps
   variable (`2e77963`, que lee el tiempo real del contenedor) y el probe de "truncated"
   dependen de cómo responde ese backend. → Hay que **re-validar en el contenedor** con
   los videos de ground truth y con un `.mov` HEVC de iPhone.

### ¿Un Dockerfile con dos entornos o unificar?

**Recomendación: una sola imagen y un solo entorno de Python, pero manteniendo el
subproceso.**

- No hay conflictos de versiones entre los dos `requirements.txt` (no comparten
  paquetes) y ambos venvs usan Python 3.11.9.
- El aislamiento que importa en producción es el **de proceso**, no el de venv. El
  subproceso es lo que hoy permite cortar por timeout, que un crash nativo de MediaPipe no
  tire abajo al servidor web y que la memoria de MediaPipe se libere al terminar cada
  análisis. Conviene conservarlo.
- El cambio de código necesario es chico: hacer que `AI_ANALYSIS_PYTHON` sea configurable
  (variable de entorno, con `sys.executable` como default) en vez de buscar
  `.venv/Scripts/python.exe`.
- La alternativa con dos venvs en la imagen (`/opt/venv-web` y `/opt/venv-ai`) también
  funciona sin tocar código si se replica la ruta `ai-analysis/.venv/bin/python`. Solo
  suma ~50 MB, pero complica el Dockerfile y no aporta aislamiento real.

### Tamaño de imagen (estimado, Linux x86_64)

| Componente | Tamaño instalado |
|---|---|
| `python:3.11-slim` base | ~125 MB |
| `libgl1` + `libglib2.0-0` | ~30–50 MB |
| Dependencias del backend | ~50 MB |
| `opencv-contrib-python` | ~180–200 MB |
| `mediapipe` | ~100–120 MB |
| `numpy`, `matplotlib`, `fonttools`, resto | ~120 MB |
| Código, estáticos, modelo `.task` | ~15 MB |
| **Total** | **~0,6–0,7 GB** (~0,85 GB si queda también `opencv-python`) |

Referencia **medida**: el venv de `ai-analysis` en Windows ocupa 357 MB, de los cuales
`cv2` son 139 MB y `mediapipe` 58 MB. Railway no tiene problema con imágenes de ese
tamaño. Solo hacen más lentos los builds.

### Memoria (medido + estimado)

- **Análisis medido**: el video más grande subido hasta hoy (76 MB, 888×1458 a 56 fps,
  32 s, 1803 cuadros) usa un **pico de 305 MB** en el proceso hijo y tarda **4,6 s** en
  esta máquina.
- **Estimado para un video 4K**: cada cuadro decodificado pesa ~25 MB contra ~4 MB a esa
  resolución, así que el pico puede subir a ~450–600 MB.
- **Proceso web** (uvicorn + FastAPI + SQLAlchemy): ~100–150 MB estimado.
- **Probe**: menos de 150 MB, dura ~0,3 s.

Railway cobra por uso real ($10/GB/mes de RAM), con un tope de 8 GB por servicio en el
plan Hobby ([pricing](https://docs.railway.com/pricing/plans)). **Entra cómodo**: en reposo
son ~150 MB (≈ $1,5/mes), y con un análisis en curso ~0,5–0,75 GB. El problema no es el
tamaño de un análisis sino **la concurrencia sin límite** (ver §6): el límite de memoria se
aplica al contenedor entero, **subprocesos incluidos**.

CPU: Railway usa vCPU compartidas. Es razonable esperar que un análisis tarde 2–4× más que
acá (~10–20 s para un clip de 30 s). El timeout de 600 s alcanza de sobra.

---

## 2. Videos

### Cómo funciona hoy

Todo vive bajo `backend/media/` (130 MB hoy, ignorado por git):

| Ruta | Definida en | Configurable |
|---|---|---|
| `media/videos/<user_id>/<uuid>.<ext>` | `storage.py:12` | Sí, con `VIDEO_UPLOAD_DIR` (relativa a `backend/`) |
| `media/season_reviews/<user_id>/…` | `storage.py:13` | **No, hardcodeada** |
| `media/_incoming/*.part` | `storage.py:17` | **No, hardcodeada** |

En la DB se guarda `file_url` como URL relativa (`/media/videos/3/abc.mp4`), no como ruta
absoluta del disco. Eso es bueno: los datos son portables.

### Qué pasa si el contenedor se reinicia

Sin volumen, **todo lo escrito en el filesystem se pierde en cada redeploy o reinicio**.
Las filas de `video_uploads` y `season_reviews` siguen en Postgres, pero apuntan a
archivos que ya no existen (404 en el reproductor). El modelo `.task` también se pierde
(ver §1).

### Qué hay que cambiar

1. Crear un **volumen de Railway** (5 GB por defecto, redimensionable, $0,15/GB/mes) y
   montarlo **en `/app/backend/media`**, o en la ruta equivalente según el `WORKDIR`.
   Montándolo justo en el padre de las tres carpetas, **no hace falta tocar código**.
2. **`_incoming` tiene que quedar en el mismo filesystem que los destinos.**
   `storage.py:121` usa `os.replace(tmp, dest)`, que falla con `EXDEV` si origen y destino
   están en filesystems distintos. Si un día se monta el volumen solo en `media/videos`,
   las subidas se rompen. Montarlo en `media/` lo resuelve.
3. Opcional pero recomendable: una sola variable `MEDIA_ROOT` absoluta de la que se
   deriven las tres rutas, en vez de una configurable y dos hardcodeadas.
4. Permisos: si la imagen corre con un usuario no root, el volumen se monta como root y
   hace falta `RAILWAY_RUN_UID=0` o un `chown` en el start command.
5. El volumen se monta **al arrancar**, no durante el build ni durante el pre-deploy
   ([docs](https://docs.railway.com/volumes)). Los `mkdir` de `main.py:47-50` corren al
   arrancar, así que funcionan.
6. Con volumen, Railway no permite dos deployments activos a la vez sobre el mismo
   servicio: **cada redeploy tiene unos segundos de corte**. Si en ese momento hay
   análisis en curso, se pierden (ver §6).
7. Los archivos `.part` que queden huérfanos en `_incoming` por un corte durante la
   subida no se limpian nunca. Es menor, pero el volumen es finito.

A futuro, la spec ya prevé S3 o equivalente. Para la etapa actual, un volumen alcanza.

---

## 3. Configuración

### Variables que el código lee hoy (`app/config.py`)

| Variable | Default en código | En Railway |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg2://ski_app:ski_app@localhost:5432/ski_app` | `${{Postgres.DATABASE_URL}}` (red privada). El formato `postgresql://` de Railway funciona tal cual: SQLAlchemy usa psycopg2 por defecto. |
| `VIDEO_UPLOAD_DIR` | `media/videos` | Dejar el default si el volumen va en `media/`. |
| `MAX_VIDEO_UPLOAD_MB` | `500` | Opcional (ver nota sobre el proxy abajo). |

No hay ningún `os.environ` ni `getenv` fuera de `config.py`. Tampoco hay API keys: el
coach es un mock (`services/coach.py`).

### Variables que harían falta para el deploy (no existen todavía)

| Variable | Para qué |
|---|---|
| `PORT` | La inyecta Railway. Uvicorn tiene que escuchar en `0.0.0.0:$PORT`. Hoy no hay start command, Procfile ni Dockerfile. |
| `SITE_PASSWORD` (y opcionalmente `SITE_USER`) | Basic Auth (§5). |
| `ENV` o `ENABLE_DOCS` | Para desactivar `/docs`, `/redoc` y `/openapi.json` en producción (§5). |
| `AI_ANALYSIS_PYTHON` | Intérprete del análisis (§1). |
| `MEDIA_ROOT` | Opcional (§2). |
| `MAX_CONCURRENT_ANALYSES` | Opcional (§6). |

### Lo que está hardcodeado

- **`config.py:7`: el default de `DATABASE_URL` apunta a `localhost`.** Si en Railway falta
  la variable, la app arranca igual y falla recién en la primera query. `/health` daría
  200 de todas formas, porque no toca la DB. Conviene que en producción no haya default
  y que falle al arrancar.
- **`config.py:5`: `env_file=".env"` es relativo al directorio actual.** En Railway no
  importa, porque se usan variables reales.
- **`analysis_job.py:17`: la ruta Windows `.venv/Scripts/python.exe`**, con fallback a
  `.venv/bin/python`.
- **`analysis_job.py:21`: `ANALYSIS_TIMEOUT_SECONDS = 600`** y **`storage.py:21`:
  `PROBE_TIMEOUT_SECONDS = 60`**. Son razonables y no bloquean nada.
- **`storage.py:13` y `storage.py:17`**: las rutas `media/season_reviews` y
  `media/_incoming`.
- **`analyze_ski_video.py:131`**: la URL de descarga del modelo en runtime.
- **`docker-compose.yml`**: credenciales `ski_app/ski_app`. Es solo para desarrollo local
  y no se usa en Railway.
- **No hay `localhost` ni `127.0.0.1`** en templates, `sw.js` ni `manifest.json`: todas las
  URLs son relativas. Bien.

### Proxy de Railway

- Las URLs de `RedirectResponse` son relativas (`/passport/{id}`), así que no hace falta
  `--proxy-headers` para que funcionen. Conviene agregarlo igual (`--proxy-headers
  --forwarded-allow-ips="*"`) por si algún día se usa `request.url_for`.
- Subir 500 MB a través del proxy de Railway desde una conexión móvil puede tardar varios
  minutos. **Hay que probar una subida grande real** antes de prometer ese límite. Bajar
  `MAX_VIDEO_UPLOAD_MB` a ~200 es una opción conservadora (el video real más grande pesa
  80 MB).

---

## 4. Base de datos

### Migraciones

- `alembic/env.py` ya lee `settings.database_url`, así que toma `DATABASE_URL` del entorno
  sin cambios.
- Hay que configurar en Railway un **Pre-deploy Command**: `cd backend && alembic upgrade head`
  (o `alembic upgrade head` si el `WORKDIR` ya es `backend/`). Corre antes de cada
  deploy, y si falla, el deploy no se activa. No necesita el volumen, que no está
  montado en ese momento.
- La DB local está en la revisión `0012` (head) y la cadena de migraciones arranca desde
  `0001_initial_schema`, así que una base vacía se crea completa con `upgrade head`.
- **Pendiente**: verificar que `0001→0012` corra limpio contra una base vacía. Las
  migraciones solo se aplicaron incrementalmente en la base local. Se puede probar con un
  Postgres descartable en Docker antes del deploy.

### Datos actuales

Estado **medido** de la base local: 6 usuarios, 4 viajes, 7 videos (0 pendientes),
9 MB. Postgres 16.15.

**Opción A: arrancar limpio (recomendada).** Los datos actuales son de prueba. Con
`upgrade head` sobre la base vacía alcanza.

**Opción B: llevar los datos.**

```bash
# 1. dump desde el contenedor local (formato custom)
docker compose exec -T db pg_dump -U ski_app -d ski_app -Fc --no-owner --no-acl > ski_app.dump

# 2. restore a Railway usando la URL PÚBLICA de la DB (DATABASE_PUBLIC_URL),
#    con un cliente de versión >= a la del server de Railway:
docker run --rm -i postgres:16 pg_restore --no-owner --no-acl -d "<DATABASE_PUBLIC_URL>" < ski_app.dump
```

- El dump incluye la tabla `alembic_version` (0012), así que el pre-deploy queda como
  no-op. Hay que restaurar **antes** del primer deploy, o sobre una base vacía sin
  migrar; si el pre-deploy ya creó las tablas, el restore choca.
- Revisar la versión de Postgres que provisiona Railway. Si es mayor que 16, el restore
  igual funciona (dump viejo → server nuevo), pero conviene usar la imagen cliente
  correspondiente.
- **Los datos sin los archivos quedan rotos**: hay que copiar también `backend/media/`
  (130 MB) al volumen. Railway no tiene un "upload al volumen" directo. Las opciones
  son `railway ssh` con un `tar` por stdin o un endpoint temporal. Esto también inclina
  la balanza hacia la opción A.

---

## 5. Seguridad

### Estado actual: no hay autenticación en ninguna ruta

Se confirmó listando el OpenAPI y buscando `auth`, `Depends(get_current…)` y cookies:
no existe ningún mecanismo. El "login" (`POST /`, `passport.py:234`) solo busca el usuario
por email y redirige a `/passport/{id}`, sin contraseña ni sesión. Cualquiera que llegue a
la URL puede:

| Superficie | Qué expone |
|---|---|
| `/admin/videos`, `/admin/videos/{id}`, `/admin/trips`, `/admin/trips/{id}/season-review` | Todo el panel del instructor: ver todos los videos, cargar evaluaciones y planes de entrenamiento, **subir videos** de Season Review. |
| `/passport/{user_id}` y todas sus subrutas | El perfil completo de cualquier usuario cambiando el número (IDOR): viajes, videos, day logs, y crear contenido en su nombre. |
| `POST /` | Enumerar emails ("No encontramos ninguna cuenta con ese email" vs redirect). |
| `POST /users/{id}/videos`, `POST /passport/{id}/videos` | **Subida de videos** (hasta 500 MB) y disparo del análisis, para cualquier usuario y sin límite de frecuencia. Es el vector más caro: disco y CPU/RAM. |
| `GET /users/{id}`, `/users/{id}/videos`, `/trips/{id}/…`, `/videos/{id}` | La API JSON completa, incluido el `file_url` de cada video. |
| `/media/videos/**`, `/media/season_reviews/**` | Los archivos estáticos. Los nombres son UUID, pero la API de arriba los lista. |
| `/api/runs/*`, `/api/chat/*`, `/api/assessment/*`, `/api/mental/*` | Reciben `user_id` en el body o en la query: escriben y leen como cualquier usuario. |
| `/docs`, `/redoc`, `/openapi.json` | El mapa completo de la API con un cliente interactivo. |
| `/health`, `/health/db` | Inofensivos. Hay que dejarlos abiertos para el healthcheck de Railway. |

### Protección mínima propuesta

**1. Contraseña compartida con HTTP Basic Auth, como middleware global.**

- Un middleware ASGI puro (no `BaseHTTPMiddleware`, que interfiere con uploads en
  streaming) agregado en `main.py` antes de los `mount`, para que cubra también
  `/static` y `/media`.
- Lee `SITE_PASSWORD` (y `SITE_USER` opcional) del entorno. Si la variable no está
  definida en producción, **la app no arranca**: mejor que quedar abierta por un olvido.
- Compara con `secrets.compare_digest` y responde `401` con
  `WWW-Authenticate: Basic realm="Ski App"`.
- Excepciones: `/health` y `/health/db`. Hay que evaluar también `/static/manifest.json`
  y los íconos: los navegadores piden el manifest **sin credenciales** salvo que el
  `<link>` tenga `crossorigin="use-credentials"`, así que la instalación como PWA puede
  fallar. Hay que probar el service worker (`/sw.js`) en el navegador real.
- Railway sirve todo por HTTPS, así que Basic Auth no viaja en claro.

**Qué no resuelve:** cualquiera que tenga la clave sigue pudiendo ver el passport y el
panel admin de todos. Es adecuado para una **beta cerrada con gente de confianza**. Antes
de abrir el registro hace falta auth real por usuario y separar `/admin` (como mínimo,
una segunda contraseña para `/admin/*`).

**2. Desactivar la documentación en producción.**
`FastAPI(docs_url=None, redoc_url=None, openapi_url=None)` cuando `ENV=production` o
`ENABLE_DOCS` sea falso. Hay que apagar los tres: con solo `/docs`, `/openapi.json` sigue
publicando el mapa.

**3. Ajustes baratos que conviene sumar:**
- Bajar `MAX_VIDEO_UPLOAD_MB`.
- Limitar los análisis concurrentes (§6), que funciona también como freno contra abusos.

---

## 6. Trabajo en background

### Cómo funciona hoy

- `upload_video` (`video_uploads.py:54`) hace `background_tasks.add_task(run_analysis_job, …)`.
  `run_analysis_job` es una función **sincrónica**, así que Starlette la corre en el
  threadpool de anyio (40 hilos por defecto) **después de enviar la respuesta**.
  El hilo queda bloqueado en `subprocess.run` hasta que termina el análisis.
- El event loop no se bloquea y el servidor sigue atendiendo. El trabajo pesado corre en
  otro proceso. Hasta acá, bien.
- La subida en sí también es sincrónica y bloquea un hilo mientras escribe el archivo y
  corre el probe (~0,3 s).

### ¿Alcanza para producción?

**Para una beta chica, sí, con dos arreglos. Como diseño final, no.** Los problemas son:

1. **Concurrencia sin límite y memoria compartida.** Cada subida lanza un subproceso de
   ~300–600 MB, sin tope (hasta los 40 hilos del pool). El límite de memoria de Railway
   es del **contenedor**: con 5 subidas simultáneas de video 4K se llega a ~3 GB. Si el
   OOM killer elige al proceso de uvicorn en vez de a un subproceso, **se cae el sitio
   entero**. Si elige a un subproceso, el video queda en `failed` (returncode ≠ 0,
   manejado en `analysis_job.py:41`).
   → Agregar un `threading.Semaphore(N)` (N=1–2) alrededor de `_run_mediapipe`. Las demás
   tareas esperan en cola en lugar de correr en paralelo. Es un cambio de pocas líneas.
2. **Los trabajos se pierden en cada reinicio o redeploy.** La "cola" vive en memoria. Si
   el contenedor se reinicia (deploy, crash, OOM, o el corte inevitable de los redeploys
   con volumen) con análisis en curso o en espera, esos videos quedan
   **`pending` para siempre**: no hay timeout, reintento ni barrido.
   → Agregar un barrido al arrancar (lifespan) que re-encole o marque `failed` los
   `pending` de más de X minutos. El archivo sigue en el volumen, así que re-encolar
   es posible.
3. **El timeout de 600 s está bien** como red de seguridad. Con los tiempos medidos (~5 s
   local, ~20 s estimado en Railway) no debería dispararse. Si se dispara, `TimeoutExpired`
   cae en el `except Exception` y el video queda `failed`. Correcto.
4. **Una excepción en una tarea no tira el servidor.** Starlette la loguea y sigue.

**Más adelante:** un worker separado (otro servicio de Railway con la misma imagen) que
tome trabajos de una tabla en Postgres (`SELECT … FOR UPDATE SKIP LOCKED`) en vez de
BackgroundTasks. Eso aísla la memoria del análisis del web y sobrevive a reinicios.
Pero obliga a compartir los videos entre servicios, y **un volumen de Railway no se puede
montar en dos servicios**. O sea que ese paso va de la mano con mover los videos a object
storage (S3/R2). No hace falta para la primera publicación.

---

## 7. Riesgos (de mayor a menor) y orden de pasos

### Riesgos

| # | Riesgo | Impacto | Mitigación |
|---|---|---|---|
| 1 | **Sitio público sin autenticación**: cualquiera ve y edita todo, sube videos y usa el admin | Exposición de datos personales y videos, abuso de disco/CPU | Basic Auth global + desactivar docs (§5). **Bloqueante.** |
| 2 | **Videos en disco efímero** | Pérdida de todos los videos en el primer redeploy | Volumen montado en `backend/media` (§2). **Bloqueante.** |
| 3 | **OOM por análisis concurrentes** | El sitio entero se cae, no solo un análisis | Semáforo de concurrencia (§6). |
| 4 | **El análisis no funciona en Linux**: falta `libGL`, OpenCV duplicado, modelo descargado en runtime | Todas las subidas fallan en el probe (415) o el análisis queda `failed` | Dockerfile con `libgl1 libglib2.0-0`, sin `opencv-python`, modelo bajado en el build (§1). |
| 5 | **Resultados distintos en Linux** (backend FFmpeg vs MSMF; timestamps con fps variable) | Análisis sutilmente incorrectos sin error visible | Correr los videos de ground truth dentro del contenedor y comparar con los JSON actuales (§1). |
| 6 | **Videos `pending` para siempre** después de un reinicio | La UX queda trabada y el usuario no sabe qué pasó | Barrido al arrancar (§6). |
| 7 | **`DATABASE_URL` con default a localhost** | Deploy "verde" que falla en la primera request | Sin default en producción y healthcheck contra `/health/db` (§3). |
| 8 | **Migraciones nunca probadas desde cero** | El primer deploy falla en el pre-deploy | `alembic upgrade head` contra un Postgres vacío local (§4). |
| 9 | **Subidas grandes a través del proxy** | Timeouts en uploads de cientos de MB | Probarlo y bajar el límite (§3). |
| 10 | **Corte breve en cada redeploy** por usar volumen | Segundos de 503 y pérdida de análisis en curso | Aceptarlo en beta. El riesgo 6 lo hace recuperable. |
| 11 | **Archivos `.part` huérfanos** en `_incoming` | Crecimiento lento del volumen | Limpieza al arrancar. Menor. |

### Orden de pasos propuesto

1. **Código, en local y sin Railway todavía:**
   1. Middleware de Basic Auth con `SITE_PASSWORD`, más docs desactivables por variable.
   2. `DATABASE_URL` sin default en producción; `AI_ANALYSIS_PYTHON` configurable.
   3. Semáforo de concurrencia para análisis; barrido de `pending` y `.part` al arrancar.
   4. Sacar `opencv-python` de `ai-analysis/requirements.txt`.
2. **Dockerfile** (un entorno, `python:3.11-slim` + `libgl1 libglib2.0-0`, modelo `.task`
   bajado en el build, `CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`).
3. **Validación local del contenedor** contra el Postgres de `docker-compose`:
   - `alembic upgrade head` sobre una base **vacía**;
   - subir los videos de ground truth y los `prueba*/park*` y comparar contra
     `ai-analysis/resultado_*.json`;
   - un `.mov` HEVC de iPhone;
   - medir RSS con `docker stats` durante 2–3 análisis simultáneos.
4. **Railway:** proyecto + Postgres → servicio web desde el repo con el Dockerfile →
   variables (`DATABASE_URL=${{Postgres.DATABASE_URL}}`, `SITE_PASSWORD`, `ENV=production`)
   → volumen en `/app/backend/media` → pre-deploy `alembic upgrade head` → healthcheck
   `/health/db`.
5. **Datos:** arrancar limpio (opción A). Solo si hace falta, pg_dump/restore + copia de
   `media/` antes del primer deploy (§4).
6. **Smoke test en producción:** Basic Auth pide clave, `/docs` da 404, registro → subida →
   análisis `processed` → redeploy → el video sigue reproduciéndose.
7. **Después de la beta:** auth real por usuario, separar `/admin`, object storage y
   worker separado.

---

Fuentes de Railway (consultadas el 2026-10-05):
[Pricing Plans](https://docs.railway.com/pricing/plans) ·
[Volumes reference](https://docs.railway.com/volumes/reference) ·
[Using Volumes](https://docs.railway.com/volumes)
