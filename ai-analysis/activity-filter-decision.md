# Decisión — filtro de actividad válida (sprint "confiabilidad de carving", punto 2)

Ground truth: `ground-truth-carving.md` (t=4.0s en video17). Script de medición:
`activity_filter_candidates.py`. Resultado crudo: `activity_filter_scores.json`.

## Candidatas evaluadas contra el ground truth

| Candidata | Señal | t predicho | Δ vs ground truth | Frames de arranque que deja pasar | Frames de carving real que descarta | ¿Corta un giro a la mitad? |
|---|---|---|---|---|---|---|
| C1 — amplitud+duración por giro | 1 giro que supera 15°/0.4s | 0.00s | **-4.00s** | 33 | 0 | No |
| C2 — alternancia de dirección | primer giro | 0.00s | **-4.00s** | 33 | 0 | No |
| C3 — std móvil de `trunk_lean` sostenida | ventana 8 frames, umbral 8°, sostenido 8 frames | 8.74s | +4.74s | 0 | 24 | **Sí, giro 5** |
| C4 — amplitud por-frame sostenida | `\|lean\|≥12°` sostenido 10 frames | 7.49s | +3.49s | 0 | 14 | **Sí, giro 5** |
| **C5 — mín. giros consecutivos válidos** | 3 giros seguidos que cumplen 15°/0.4s cada uno | **3.37s** | **-0.63s** | 6 | 0 | **No** |

## Por qué las otras 4 no sirven (medido, no "a ojo")

- **C1 y C2 no filtran nada** (t=0.00s): el giro 1 (right al lado del cartel de arranque)
  ya tiene 17.6° de inclinación máxima y dura 1.0s — supera igual de largo el umbral de
  un solo giro que cualquier giro real más adelante. Un umbral de amplitud/duración
  aplicado a **un solo giro** no distingue el arranque de carving real en este video.
- **C2 en particular es una señal sin información**: `segment_turns` ya garantiza
  alternancia estricta entre giros consecutivos *por construcción* (un segmento nuevo
  solo arranca cuando el signo de `trunk_lean` cambia) — nunca puede haber dos giros
  seguidos del mismo lado en la salida de `segment_turns`, así que "requerir
  alternancia" es siempre verdad desde el primer giro. Se deja documentado como
  candidata evaluada y descartada por esta razón específica, no omitida sin más.
- **C3 y C4 sobre-corrigen**: exigir que la señal esté sostenida por-frame (no por-giro)
  tarda demasiado en "engancharse" — el giro 5 empieza con inclinación baja que va
  creciendo gradualmente, así que para cuando la ventana/racha por-frame cruza el
  umbral, ya se comió más de la mitad del giro 5 real. Las dos **cortan un giro
  genuino**, que es exactamente lo que el criterio de éxito del sprint pide evitar
  ("sin eliminar los primeros giros reales de una secuencia normal").

## Candidata elegida: C5

Único candidato que:
1. Se acerca al ground truth (0.63s de diferencia — el propio ground truth es una marca
   manual con margen, no un instante exacto).
2. No corta ningún giro a la mitad.
3. Dejar pasar 6 frames de arranque (de ~33 totales antes del ground truth) es un costo
   aceptable frente a la alternativa de cortar un giro real.

**Por qué funciona**: los giros 2, 3 y 4 (dentro del sector de arranque) tienen
inclinaciones de 15.0°/9.4°/8.7° y duraciones de apenas 0.25s/0.37s/0.37s — ninguno pasa
el umbral de duración (0.4s) salvo el giro 2 por muy poco en amplitud pero no en
duración. Al exigir **3 giros seguidos** que cumplan ambos umbrales, ningún tramo dentro
del arranque arma una racha de 3 — la primera racha real empieza justo en el giro 5.

## Implementación

`find_activity_start_idx()` en `analyze_ski_video.py`, con
`VALID_ACTIVITY_MIN_LEAN_DEG=15.0`, `VALID_ACTIVITY_MIN_DURATION_SEC=0.4` (reusa
`MIN_TURN_DURATION_SEC`, ya eran el mismo valor) y
`VALID_ACTIVITY_MIN_CONSECUTIVE_TURNS=3`. Si no se encuentra ninguna racha así (video
corto, o ningún giro cruza el umbral), devuelve 0 — **no filtra nada**, se sigue
analizando el video completo como antes de este sprint. No hay forma de que este filtro
termine vaciando el análisis de un video por no encontrar el patrón esperado.

Se aplica DESPUÉS de `segment_turns` (necesita los giros ya armados para poder medir
amplitud/duración por giro) y ANTES de los 5 detectores de patrones — asimetría e
inconsistencia reciben la lista de giros ya filtrada (indexando contra la lista completa
de frames, sin recortar); balance/rotación/peso-atrás reciben directamente la porción de
frames ya recortada. Mismo criterio en `instrument_video.py` (importa la misma función,
no la reimplementa, para que el reporte de debug nunca se desincronice de producción).

## Resultado en los 4 videos del dataset

| Video | Frames descartados | t de inicio detectado | ¿Cambió algún patrón? |
|---|---|---|---|
| video17 (sólido) | 27 de 238 | 3.37s | **Sí** — `inconsistencia_entre_giros` deja de dispararse (los 4 giros de baja intensidad del arranque ya no contaminan el cálculo de varianza) |
| video1 (mixto) | 2 de 95 | 1.47s | No — los 2 frames descartados son simplemente los primeros frames con pose válida, no un arranque real; mismos 2 patrones antes y después |
| video2 (errores conocidos) | 1 de 37 | 5.45s | No — mismo caso, prácticamente nada que filtrar; los 3 patrones conocidos (incluida la asimetría alta) siguen intactos |
| video16 (casi sin datos) | 0 de 9 | 1.87s | No — sin cambios, ya era un caso degenerado |

**Confirma el criterio de éxito**: el arranque cercano al lift queda excluido en el único
video donde existía ese problema, sin tocar los patrones reales de los otros 3 videos —
en particular, video2 sigue marcando su asimetría "alta" conocida sin cambios, que es
exactamente la prueba de que el filtro no está "limpiando de más".

## Chequeo de generalización en los otros 3 videos (no es una confirmación completa)

Revisando el primer giro segmentado de cada video: video1 arranca con 55.6° de
inclinación y 1.74s de duración; video2 con 27.8° y 0.54s; video16 (único giro) con
44.5° y 12.9s. **Los tres superan el umbral (15°/0.4s) desde el primer giro** — ninguno
tiene una fase de arranque de baja intensidad como la del influencer. El filtro **no fue
puesto a prueba contra un segundo caso real de arranque contaminante**, porque ese
segundo caso no existe en el dataset actual. Lo que sí queda confirmado es que el filtro
no descarta actividad válida cuando no hay nada que filtrar — no que la lógica de
detección de arranques generalice a otro video con ese problema. Validar la
generalización requiere un video nuevo con un arranque de baja intensidad conocido,
pendiente para cuando haya más material (mismo tipo de limitación ya documentada para el
caso positivo de rotación).
