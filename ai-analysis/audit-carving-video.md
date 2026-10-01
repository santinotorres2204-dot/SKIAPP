# Auditoría diagnóstica profunda — video de carving

> **Nota (2026-09-30): los timestamps de esta auditoría pueden estar
> desfasados hasta 0,6 s.** El video auditado (`video_id=17`, `.mov`) tiene
> fps variable, y cuando se escribió esta auditoría el pipeline calculaba
> `t = frame_idx / CAP_PROP_FPS`, que asume fps constante. Todos los
> timestamps de abajo están en ese reloj viejo, que va **atrasado** respecto
> del tiempo real del video. Para ubicar un momento en el video real hay que
> sumarle aproximadamente:
>
> | t en esta auditoría | 0–4 s | 6–10 s | 12 s | 14 s | 16 s | 18–22 s | 24 s | 26–28 s | 30–32 s |
> |---|---|---|---|---|---|---|---|---|---|
> | sumar | +0,0–0,2 | +0,1–0,2 | +0,27 | +0,41 | **+0,59** | +0,44–0,49 | +0,37 | +0,18–0,24 | +0,0–0,1 |
>
> **Qué sigue siendo válido**: los valores de las métricas, los umbrales,
> qué frame dispara cada patrón y las conclusiones por patrón. El fix no
> cambia qué frames se analizan: el pipeline actual da los mismos patrones y
> la misma confianza sobre este video con el fix y sin él. Ojo: eso no
> significa que coincidan con los de esta auditoría, porque los sprints
> posteriores (rotación en XY, filtro de actividad, asimetría) ya los
> cambiaron.
>
> **Qué puede estar mal**: las correspondencias "tal timestamp cae en tal
> fase del giro" (sección 10 de cada patrón) y cualquier frame que se haya
> buscado en el video por tiempo. En el tramo 14–24 s el corrimiento
> (0,4–0,6 s) es cerca de medio giro, así que una "entrada" o "transición"
> inferida ahí puede ser en realidad la otra fase. No se re-verificaron una
> por una. Ver `phase-detection-ground-truth.md` §3 y NOTES.md.

**Sprint de solo diagnóstico — no se modificó `analyze_ski_video.py`.** Este documento
audita, patrón por patrón (dispare o no), la geometría, los umbrales y la evidencia
visual detrás de cada evaluación que hace el pipeline sobre un video real.

## 1. Video elegido y por qué

De los 4 videos etiquetados `carving` que existen en la base (`video_id` 1, 2, 16, 17),
se eligió el **`video_id=17`** (`backend/media/videos/1/04f639126caf45d89f80f3d5418b20cd.mov`):

| video_id | confidence_score | patrones detectados |
|---|---|---|
| 1 | 64 | `perdida_de_balance` (baja), `inconsistencia_entre_giros` (baja) — solo 8 giros |
| 2 | 38 | `asimetria_izq_der` (**alta**), `perdida_de_balance` (media) — técnica visiblemente irregular |
| 16 | 5 | sin datos suficientes (casi sin pose válida) |
| **17** | **97** | `rotacion_excesiva_tren_superior` (baja), `inconsistencia_entre_giros` (baja) |

`video_id=17` es el candidato correcto para esta auditoría: máxima confianza (97/100,
238/258 frames válidos = 92%), máxima cantidad de datos (**27 giros** en ~32s — el video
más largo y completo de los cuatro) y solo severidades **bajas**, justo el perfil de
"técnica visualmente sólida que igual dispara patrones límite" que vale la pena
auditar en profundidad. Confirmé además (`app/analysis_job.py`) que el pipeline real
corre con `--discipline carving` (viene de `video.discipline_tag`), así que esta
auditoría reproduce exactamente el análisis que ya corrió en producción.

**Meta del análisis**: 258 frames muestreados a 8fps → 238 válidos (92.2%) → 27 giros
segmentados (14 izquierda, 13 derecha) → confidence_score 97/100.

## 2. Visibilidad de landmarks — hallazgo transversal

Antes de entrar patrón por patrón: instrumenté la extracción de pose para capturar la
visibilidad **cruda** de MediaPipe en cada landmark (el pipeline de producción la usa
solo para aceptar/rechazar el frame entero, no la expone). Sobre los 254 frames donde
MediaPipe detectó alguna persona:

| landmark | min | media | max |
|---|---|---|---|
| left/right_shoulder | 0.999 | ~1.0 | 1.0 |
| left/right_hip | 0.999 | ~0.999 | 1.0 |
| left_knee | 0.547 | 0.718 | 0.904 |
| right_knee | 0.527 | 0.688 | 0.935 |
| **left_ankle** | **0.439** | **0.638** | 0.768 |
| **right_ankle** | **0.470** | **0.645** | 0.848 |

Hombros y caderas están prácticamente siempre en visibilidad ~1.0. **Los tobillos son,
por lejos, el eslabón más débil** — y confirmé mirando los frames rechazados
(`rejected_frames_sample`) que el motivo de rechazo es consistentemente el tobillo
cayendo debajo de 0.5, nunca hombro/cadera. Esto importa porque dos métricas dependen
directamente del tobillo: `knee_flex_*` (ángulo cadera-rodilla-tobillo) y
`trunk_fore_aft_deg` (usa `mid_ankle` como origen del vector). Son, por construcción,
las métricas más expuestas a ruido de landmark — se confirma más abajo con evidencia
visual concreta.

## 3. Tabla de los 27 giros (referencia temporal completa)

| # | dirección | inicio | pico | fin | frames | max\|lean\| |
|---|---|---|---|---|---|---|
| 1 | derecha | 00:00.00 | 00:00.00 | 00:01.00 | 9 | 17.6 |
| 2 | izquierda | 00:01.37 | 00:01.37 | 00:01.62 | 3 | 15.0 |
| 3 | derecha | 00:02.00 | 00:02.12 | 00:02.37 | 4 | 9.4 |
| 4 | izquierda | 00:02.75 | 00:03.00 | 00:03.12 | 4 | 8.7 |
| 5 | derecha | 00:03.37 | 00:08.24 | 00:08.86 | **32** | 45.8 |
| 6 | izquierda | 00:08.99 | 00:09.74 | 00:10.23 | 11 | 51.4 |
| 7 | derecha | 00:10.36 | 00:10.73 | 00:11.11 | 7 | 37.6 |
| 8 | izquierda | 00:11.23 | 00:11.73 | 00:12.23 | 9 | 42.9 |
| 9 | derecha | 00:12.48 | 00:12.73 | 00:12.98 | 5 | 29.5 |
| 10 | izquierda | 00:13.11 | 00:13.60 | 00:14.10 | 9 | 42.5 |
| 11 | derecha | 00:14.23 | 00:14.48 | 00:14.85 | 6 | 34.4 |
| 12 | izquierda | 00:14.98 | 00:15.35 | 00:15.85 | 8 | 43.2 |
| 13 | derecha | 00:15.98 | 00:16.35 | 00:16.72 | 6 | 46.0 |
| 14 | izquierda | 00:16.85 | 00:17.35 | 00:17.72 | 8 | 41.2 |
| 15 | derecha | 00:17.85 | 00:18.47 | 00:18.97 | 10 | 44.4 |
| 16 | izquierda | 00:19.10 | 00:19.35 | 00:19.47 | 4 | 23.9 |
| 17 | derecha | 00:19.72 | 00:20.34 | 00:20.97 | 11 | 52.5 |
| 18 | derecha | 00:21.84 | 00:22.47 | 00:22.97 | 10 | 47.4 |
| 19 | izquierda | 00:23.22 | 00:23.34 | 00:23.46 | 3 | 17.5 |
| 20 | derecha | 00:23.71 | 00:24.46 | 00:24.96 | 11 | 42.0 |
| 21 | izquierda | 00:25.09 | 00:25.34 | 00:25.71 | 6 | 32.8 |
| 22 | derecha | 00:25.96 | 00:26.34 | 00:26.96 | 6 | 36.6 |
| 23 | izquierda | 00:27.08 | 00:27.33 | 00:27.71 | 6 | 31.7 |
| 24 | derecha | 00:27.83 | 00:28.46 | 00:29.08 | 11 | 48.4 |
| 25 | izquierda | 00:29.21 | 00:29.46 | 00:29.58 | 4 | 22.8 |
| 26 | derecha | 00:29.83 | 00:30.45 | 00:30.83 | 9 | 48.1 |
| 27 | izquierda | 00:31.08 | 00:31.45 | 00:31.70 | 6 | 36.1 |

**Nota sobre el giro 5** (32 frames / 5.49s — 3-10x más largo que cualquier otro): mirando
el video en ese tramo, corresponde a los primeros segundos reales de descenso después
del arranque (giros 1-4, ver punto 6 más abajo, son el inicio cerca del lift, casi sin
inclinación). No hay evidencia de que sea un error de segmentación (el `trunk_lean`
efectivamente no cruza el "dead zone" de 3° en ese tramo), pero es la clase de caso
límite que vale la pena tener presente: `segment_turns` asume una cadencia de giros
más o menos regular, y un giro real inusualmente largo se mezcla sin distinción con
giros cortos de 3-4 frames en las mismas comparaciones agregadas (asimetría,
inconsistencia).

## 4. Patrón por patrón

### 4.1 `asimetria_izq_der` — NO disparó (a 5.7% del umbral)

| Punto | Valor |
|---|---|
| **1. Variable** | `max(rel_diff(knee_flex_izq/der), rel_diff(trunk_lean_abs_izq/der))` — diferencia relativa promedio entre giros izquierda y derecha |
| **2. Valor medido** | 0.1132 (11.3%) — la diferencia de inclinación de tronco (`lean`) domina sobre la de rodilla (`knee`: 0.051) |
| **3. Threshold** | `ASYMMETRY_THRESHOLDS["baja"] = 0.12` (`analyze_ski_video.py:69`) |
| **4. Frames usados** | Los de los 27 giros completos (todos los `start_idx..end_idx`) |
| **5. Visibilidad** | Hombro/cadera ~1.0 en todos; rodilla 0.53-0.94 (ver §2) — la pata de `knee_flex` de esta métrica hereda ese ruido, pero pesó menos que `lean` en este video |
| **6. Sample size** | 27 giros (14 izq, 13 der) |
| **7. Timestamps** | Cubre todo el video, 00:00.00–00:31.70 |
| **8. Pico vs sostenido** | No aplica — es un promedio agregado por lado, no un evento puntual |
| **9. Dirección** | Ambas comparadas entre sí (13 vs 14 giros) |
| **10. Fase del giro** | No aplica — usa `mean_trunk_lean_abs`/`mean_knee_flex` de cada giro completo, no un frame puntual |

**A 0.0068 de distancia del umbral "baja"** (gap = 5.7% del propio umbral) — el caso
límite más ajustado de los cinco. `lean_right_mean=22.78` vs `lean_left_mean=20.34`:
una asimetría real pero pequeña, del tipo que un instructor humano probablemente
también notaría pero calificaría como "leve, normal", no como un defecto a corregir.

**Clasificación: (D)** — la geometría es correcta y el threshold está razonablemente
calibrado como para no disparar acá; el fenómeno que mide (ligera preferencia de un
lado) es real pero de magnitud tan chica que interpretarlo como "asimetría a corregir"
sería sobre-alarmar sobre una variación esperable incluso en técnica sólida.

### 4.2 `rotacion_excesiva_tren_superior` — DISPARÓ (baja) — el más problemático de los cinco

| Punto | Valor |
|---|---|
| **1. Variable** | `mean(abs(rotation_diff))` sobre TODO el video — `rotation_diff` = diferencia angular entre la línea de hombros y la línea de cadera, proyectadas sobre el plano (x, z) de MediaPipe (`z` = profundidad relativa) |
| **2. Valor medido** | 26.02° (mediana 20.22°, std **23.69°** — casi tan grande como la media) |
| **3. Threshold** | `ROTATION_THRESHOLDS_DEG["baja"] = 20.0°` (`analyze_ski_video.py:70`); a solo 3.98° de "media" (30°) |
| **4. Frames usados** | Los 238 frames válidos completos (es un promedio de video entero, no por giro) |
| **5. Visibilidad** | Hombro/cadera ~1.0 — en principio la métrica más confiable en cuanto a landmarks de entrada... |
| **6. Sample size** | 238 frames (reportado como 27 giros en el JSON de salida, pero el cálculo real es sobre frames) |
| **7. Timestamps** | Los 5 frames más extremos: 00:24.46 (152.5°), 00:13.98 (135.1°), 00:19.97 (132.7°), 00:09.24 (105.1°), 00:00.12 (85.3°) |
| **8. Pico vs sostenido** | **Ninguno de los dos, es un promedio** — pero 50.8% de los frames superan igual el umbral "baja" individualmente, así que no es un puñado de outliers arrastrando una mayoría tranquila; hay dispersión real en toda la serie |
| **9. Dirección** | No distingue — es agregado de todo el video |
| **10. Fase del giro** | El frame más extremo (152.5°, t=00:24.46) cae en el **ápice** del giro 20 (pico en t=00:24.46 exacto) |

**Evidencia visual — esto es lo que cambia la clasificación.** Comparé el frame del
outlier extremo (`rotacion_outlier_t24.46s_idx179.jpg`, -152.5°) contra un frame de
rotación "típica" cercana al umbral (`rotacion_tipica_t08.24s_idx53.jpg`, -21.3°):

- En el frame típico, el esqueleto dibujado (hombros-cadera-rodillas-tobillos) tiene
  una forma anatómicamente coherente con la postura real del esquiador en la foto.
- En el frame outlier, **el esqueleto dibujado colapsa en un cuadrilátero angosto y
  retorcido** cerca del costado derecho del cuerpo — visualmente no se corresponde con
  la postura real (el esquiador se ve en una curva controlada, bastones detrás, sin
  ningún indicio de una rotación de 152° entre hombros y cadera, que sería casi un giro
  completo del tronco). Los puntos de hombro/cadera claramente NO están donde deberían.

**Clasificación: (A) con contribución de (B).** Es Causa A porque el frame más extremo
(y varios de los otros top-5) muestran evidencia visual directa de landmarks mal
ubicados, no una rotación real. Pero también hay una Causa B de fondo: la fórmula usa
`z` (profundidad) de MediaPipe, que la propia documentación de MediaPipe marca como
la coordenada menos confiable en pose 2D-monocular — construir una métrica de
"screening" sobre esa coordenada la hace estructuralmente más ruidosa que las que solo
usan `x, y` (como `trunk_lean` o `knee_flex`). El std de 23.69° (casi = a la media) es
consistente con una señal dominada por ruido de medición, no con una rotación de tren
superior sostenida y real. **Este es el patrón que más until amerita revisión de
threshold/fórmula antes de usarse para feedback real a un usuario.**

### 4.3 `inconsistencia_entre_giros` — DISPARÓ (baja) — cerca de "media"

| Punto | Valor |
|---|---|
| **1. Variable** | Coeficiente de variación (`std/mean`) de `max_trunk_lean_abs` entre los 27 giros |
| **2. Valor medido** | CV = 0.362 (media 35.16°, std 12.71°) |
| **3. Threshold** | `INCONSISTENCY_CV_THRESHOLDS["baja"] = 0.25` (`analyze_ski_video.py:71`) — ya superado por 0.112; a solo 0.038 de "media" (0.40) |
| **4. Frames usados** | El pico (`max_trunk_lean_abs`) de cada uno de los 27 giros |
| **5. Visibilidad** | Hereda la de `trunk_lean`: hombro/cadera ~1.0, sin dependencia de rodilla/tobillo — esta métrica en particular está limpia de landmarks débiles |
| **6. Sample size** | 27 giros |
| **7. Timestamps** | Ver tabla §3 completa |
| **8. Pico vs sostenido** | Es varianza entre giros, no aplica pico/sostenido en el sentido temporal |
| **9. Dirección** | Mezcla ambas direcciones sin distinguir |
| **10. Fase del giro** | No aplica (usa el pico de cada giro, ya es "la fase de mayor inclinación" por definición de `max_trunk_lean_abs`) |

**Los 5 giros que más se apartan del promedio son, en orden: 4, 3, 2 y 1** (los cuatro
primeros del video) **y 19**. Los giros 1-4 tienen `max_trunk_lean_abs` de 8.7-17.6° —
muy por debajo de la media de 35.16° del resto. Revisé el frame del giro 3
(`giro_baja_intensidad_t02.12s_idx17.jpg`, t=00:02.12): **el esquiador está saliendo
del sector del lift** (se ven carteles, gente parada, la aerosilla) — es el arranque
del video, prácticamente bajando derecho, no un giro de carving real todavía.

**Clasificación: (E).** El CV es una medición correcta de que estos 4 giros son mucho
menos intensos que el resto — eso no está mal calculado. El problema es que el sistema
no distingue "fase del video" (calentamiento/arranque vs. esquí en régimen): mete en la
misma comparación agregada giros que son literalmente parte de arrancar a bajar la
pista con los giros de carving reales que vienen después. Un instructor humano
descartaría los primeros segundos como "no es esquí todavía" antes de evaluar
consistencia — el algoritmo no tiene ese concepto.

### 4.4 `perdida_de_balance` — NO disparó (a 3.6% del umbral)

| Punto | Valor |
|---|---|
| **1. Variable** | Salto normalizado del centro de masa (`com`, promedio hombro+cadera) entre frames consecutivos, dividido por la escala de torso del frame |
| **2. Valor medido** | proporción de frames "flageados" = 0.0127 (3 de 237 deltas) |
| **3. Threshold** | Adaptativo por video: `max(media + 2.5·std, 0.12)` → acá dio **0.752** (muy por encima del piso de 0.12, porque el propio video tiene mucha variación de movimiento normal); la severidad se evalúa sobre la *proporción* de frames que superan ese threshold, con `BALANCE_LOSS_PROPORTION_THRESHOLDS["baja"] = 0.02` (`analyze_ski_video.py:72`) |
| **4. Frames usados** | Los 238 frames válidos, en pares consecutivos (237 deltas) |
| **5. Visibilidad** | Usa `com` (hombro+cadera, ~1.0 de visibilidad) y `torso_scale` (misma base) — la métrica en sí está limpia; no depende de rodilla/tobillo |
| **6. Sample size** | 27 giros (reportado), 237 deltas evaluados |
| **7. Timestamps** | Los 3 frames flageados: 00:16.60, 00:21.72 (el mayor, 2.26x el threshold), 00:26.83 |
| **8. Pico vs sostenido** | Los 3 son **picos aislados** (frame único, sin frames vecinos también flageados) — nunca sostenido |
| **9. Dirección** | No aplica — es sobre desplazamiento de centro de masa, no de giro |
| **10. Fase del giro** | 00:21.72 cae justo antes del pico del giro 18 (00:22.47) — es decir, en la **transición hacia** ese giro |

**Evidencia visual** (`balance_flag2_t21.72s_idx156.jpg`, el mayor de los 3): el
esquiador se ve en un momento dinámico de cambio de filo, con las piernas en una
posición de transición — no hay ninguna señal visual de caída, tropiezo o pérdida real
de control. Se ve como una transición de giro brusca pero controlada, del tipo esperable
en carving a buen ritmo.

**Clasificación: (D).** La geometría mide correctamente un salto real y grande del
centro de masa — el "fenómeno real" existe. Pero interpretarlo como "posible pérdida de
balance" no encaja con lo que se ve: es una transición de giro normal, no un evento
negativo. El hecho de que el propio umbral de "sostenido" (proporción mínima) exista y
haya evitado que esto dispare es, en este caso, el diseño funcionando bien — vale la
pena notar que si esos 3 picos aislados fueran ligeramente más frecuentes (a 3.6% de
cruzar "baja"), directamente empezarían a etiquetarse como "pérdida de balance" pese a
ser, visualmente, transiciones normales.

### 4.5 `peso_hacia_atras` — NO disparó (lejos del umbral, pero con hallazgos)

| Punto | Valor |
|---|---|
| **1. Variable** | `trunk_fore_aft_deg` — ángulo del tronco relativo a la línea tobillo-rodilla (ver `analyze_ski_video.py:257-292`) |
| **2. Valor medido** | proporción de frames sobre "baja" = 0.1218 (12.2%) — lejos del 35% requerido para "sostenido" |
| **3. Threshold** | `BACKWARD_LEAN_THRESHOLDS_DEG["carving"]["baja"] = 6.0°` + `SUSTAINED_BACKWARD_PROPORTION = 0.35` (`analyze_ski_video.py:90, 96`) |
| **4. Frames usados** | Los 238 frames válidos — pero **63 de ellos (26.5%) se descartan como "rodilla ambigua"** (`knee_offset < 4% del largo de la pierna`) y se guardan como `0.0`, no como una medición real |
| **5. Visibilidad** | Esta es la métrica más expuesta de las cinco: usa `mid_ankle` como origen del vector — hereda directamente el problema de visibilidad de tobillo documentado en §2 |
| **6. Sample size** | 238 frames (175 con signo confiable, 63 descartados) |
| **7. Timestamps** | Los 5 frames más "atrás": 00:22.34 (**+76.9°**, extremo), 00:15.60 (+39.4°), 00:29.71 (+38.2°), 00:13.98 (+33.0°), 00:15.35 (+30.0°) |
| **8. Pico vs sostenido** | Ninguno sostenido — el promedio del video es **-12.53°** (negativo = adelante, buena técnica), y el propio mecanismo de "sostenido" (35% mínimo) existe justamente para no marcar picos aislados como estos |
| **9. Dirección** | No distingue — es por frame, no por giro |
| **10. Fase del giro** | El outlier de +76.9° (00:22.34) cae en la **entrada** del giro 18 (que empieza en 00:21.84 y llega al pico en 00:22.47) |

**Evidencia visual** (`peso_atras_outlier_t22.34s_idx162.jpg`): a diferencia del outlier
de rotación (§4.2), acá el esqueleto dibujado se ve razonablemente coherente con la
postura real — el esquiador está en una flexión dinámica, bastones atrás, en un momento
de carga del giro. No hay una señal visual tan clara de landmark roto como en 4.2, así
que no lo clasifico como error de MediaPipe con la misma confianza.

**Clasificación: (D), con nota sobre la fiabilidad de la métrica.** El resultado final
(no disparar) es correcto y el promedio del video (-12.53°, adelantado) coincide con lo
que se espera de "técnica sólida" en carving. Pero el 26.5% de frames descartados por
rodilla ambigua es una proporción alta — vale la pena trackear esto en más videos (la
propia `NOTES.md` ya lo señala como limitación abierta, confirmado acá con un caso
real). El pico aislado de +76.9° probablemente sea una combinación de (D) — un instante
real de carga hacia atrás en la entrada de un giro dinámico, normal en carving agresivo
— sin evidencia visual suficiente para acusar directamente a MediaPipe como en 4.2.

## 5. Tabla resumen — clasificación de causas

| Patrón | ¿Disparó? | Severidad | Gap al umbral más cercano | Causa |
|---|---|---|---|---|
| `asimetria_izq_der` | No | — | 0.0068 (5.7%) por debajo de "baja" | **D** — real pero menor, correctamente no marcado |
| `rotacion_excesiva_tren_superior` | **Sí** | baja | 3.98° por debajo de "media" | **A + B** — outliers con landmarks visiblemente mal ubicados, sobre una fórmula (eje Z) estructuralmente ruidosa |
| `inconsistencia_entre_giros` | **Sí** | baja | 0.038 por debajo de "media" | **E** — no distingue arranque/calentamiento de esquí en régimen |
| `perdida_de_balance` | No | — | 0.0073 (3.6%) por debajo de "baja" | **D** — mide una transición de giro real, no una caída |
| `peso_hacia_atras` | No | — | 0.228 (65%) por debajo del mínimo sostenido | **D**, con nota de fiabilidad (26.5% de frames descartados por rodilla ambigua) |

**Ningún patrón cae limpiamente en (C)** ("la geometría es correcta pero el threshold
está mal calibrado a secas") — en los cinco casos hay algo más específico: o un
problema de landmarks/fórmula (rotación), o el sistema detectando algo real que un
instructor humano contextualizaría distinto (inconsistencia, balance, peso atrás,
asimetría).

## 6. Frames guardados (`ai-analysis/audit_carving_frames/`)

Mismo mecanismo de overlay que `debug_turns.py` (esqueleto verde, keypoints rojos):

- `rotacion_outlier_t24.46s_idx179.jpg` / `rotacion_tipica_t08.24s_idx53.jpg` — evidencia central de la Causa A/B en rotación.
- `peso_atras_outlier_t22.34s_idx162.jpg` / `peso_adelante_tipico_t19.72s_idx144.jpg` / `peso_adelante_t08.99s_idx59.jpg`.
- `balance_flag1/2/3_*.jpg` — los 3 picos aislados de centro de masa.
- `rodilla_anomala_t15.35s_idx110.jpg` / `rodilla_anomala_t22.47s_idx163.jpg` — evidencia de landmark de tobillo/rodilla mal ubicado.
- `giro_izquierda_t09.74s_idx65.jpg` / `giro_derecha_t20.34s_idx149.jpg` — giros representativos de alta intensidad.
- `giro_baja_intensidad_t02.12s_idx17.jpg` — evidencia visual de que los primeros giros son el arranque cerca del lift, no carving real.

## 7. Notas de proceso

- No se tocó `analyze_ski_video.py` ni `debug_turns.py` — se importaron y reusaron tal
  cual. El único código nuevo vive fuera del repo de producción (scripts de diagnóstico
  en el scratchpad de esta sesión, no commiteados).
- Todos los valores de "gap al umbral" y clasificaciones de causa están basados en
  recalcular exactamente la misma fórmula que usa cada función `detect_*`, no en
  aproximaciones.
- La inferencia de "fase del giro" (entrada/ápice/transición) es post-hoc, a partir de
  la posición relativa del frame dentro del segmento que ya arma `segment_turns` — no
  existe como feature explícita en el código hoy (confirmado leyendo el pipeline
  completo).
