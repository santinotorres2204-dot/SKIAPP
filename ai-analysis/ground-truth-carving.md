# Ground truth manual — transición arranque → carving real

Sprint "confiabilidad de carving", punto 2: requisito obligatorio antes de medir señales
candidatas de filtrado de actividad.

## Video: `video17_influencer` (04f639126caf45d89f80f3d5418b20cd.mov)

**Marca manual: t ≈ 4.0 segundos.**

Metodología: revisión visual frame a frame de los primeros ~9 segundos del video
(frames extraídos con overlay de pose, mismo mecanismo que `debug_turns.py`).

| Timestamp | Evidencia |
|---|---|
| t=2.12s | Cartel/gente visibles del sector de arranque cerca del telesilla (`giro_baja_intensidad_t02.12s_idx17.jpg`, del sprint de auditoría anterior) |
| t=3.37s | **Todavía** se ve el cartel amarillo de la pista y gente parada al costado (`ground_truth_frames/ground_truth_scan_idx27_t3.37s.jpg`) — el esquiador va prácticamente derecho |
| t=4.12s | El cartel/gente **ya no están en cuadro** — pendiente abierta con árboles, sin señales del sector de arranque (`ground_truth_frames/ground_truth_scan_idx33_t4.12s.jpg`) |
| t=8.24s | Giro dinámico claro, inclinación 45.8°, ladera abierta (`giro05_pico_derecha.jpg`) — carving real inequívoco |

La transición visual ocurre entre t=3.37s y t=4.12s. Se fija el ground truth en
**t=4.0s** (punto medio de esa ventana, redondeado). No se pretende precisión de
milisegundos — es una marca manual de referencia, no una medición automática.

## Nota sobre el giro 5 (segmentación existente)

El giro que segmenta `segment_turns` como "#5" abarca t=3.37s–8.86s (32 frames) — el
ground truth (t=4.0s) cae **dentro** de ese giro, no en un límite entre giros. Esto es
esperable: el algoritmo de segmentación actual no sabe nada sobre "sector de arranque",
solo sigue cruces por cero de la inclinación de tronco — el giro 5 mezcla el tramo final
del arranque con el inicio del primer giro real porque el `trunk_lean` no volvió a cruzar
la banda muerta en el medio. Cualquier estrategia de filtrado que opere a nivel de
*giros completos* (no de frames individuales) va a heredar esta imprecisión — se
documenta explícitamente en `activity-filter-decision.md` al evaluar cada candidato
contra este ground truth.

## Otros videos del dataset

No se marcó ground truth manual en video1/video2/video16 — el pedido explícito era "al
menos uno de los videos de referencia", y video17 es el que motivó este punto del sprint
(tiene un tramo de arranque claramente distinguible). Se re-corrieron los 4 igual con la
estrategia elegida para confirmar que no rompe nada en los demás (ver
`activity-filter-decision.md`, sección de resultados).
