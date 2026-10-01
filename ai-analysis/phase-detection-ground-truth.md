# Detección de fase en carving: ground truth y comparación de señales (Sprint phase-aware, punto 0)

**Solo diagnóstico.** No se modificó `analyze_ski_video.py` ni ninguna otra parte del
pipeline. El código nuevo vive en `phase_detection/`: el ground truth, el script de
medición y los reportes. Importa las funciones del pipeline tal cual.

## Resumen

- **Recomendación**: detectar la fase **combinando dos señales que el pipeline ya
  calcula**, cada una para el evento en el que es mejor:
  - **Transición** = cruce por cero del centro de masa lateral **relativo a los
    tobillos** (`com_x − tobillos_x`, normalizado por torso). Error a 8 fps:
    sesgo −0,05 s, dispersión 0,05 s, máximo 0,11 s, 7/8 detectadas.
  - **Ápice** = extremo de `trunk_lean` (con el mismo suavizado de producción)
    entre dos transiciones. Error a 8 fps: sesgo +0,03 s, dispersión 0,10 s,
    máximo 0,18 s, 7/7 detectados.
  - **Entrada**: con la resolución de producción **no se distingue como punto
    propio**: cae ~1 muestra después de la transición. Conviene tratarla como
    ventana (ver §5).
- **Margen de confianza a 8 fps**: transición ±0,11 s (≈1 muestra), ápice ±0,18 s
  (≈1,5 muestras), sobre giros de ~1 s.
- **La flexión de rodilla queda descartada**: es errática entre giros.
- **Hallazgo que bloqueó la primera medición, y bug de producción aparte**: el
  video 17 tiene **fps variable** y el pipeline asume fps constante. Sus
  timestamps atrasan **hasta 0,61 s** respecto del tiempo real. Sin corregir el
  reloj, ninguna señal se parecía al ground truth (ver §3).

## 1. Correcciones a supuestos del documento del sprint

- **`segment_turns` no usa el centro de masa lateral**: segmenta por cruces por
  cero de `trunk_lean` (inclinación del tronco respecto de la vertical de la
  imagen), suavizado con media móvil de 5 frames (`SMOOTHING_WINDOW`). El centro
  de masa lateral no se usa hoy para nada en la segmentación. Igual se evaluó
  como candidata, junto con `trunk_lean`, que funciona como línea base.
- **La cámara va detrás del esquiador**, no de frente (se lee "CLUB LACAR" en la
  espalda). La lleva otra persona que también esquía, así que se mueve y rota.
  Por eso el centro de masa en coordenadas de imagen es mala señal: mezcla el
  movimiento del esquiador con el de la cámara.

## 2. Ground truth manual

**Definiciones (confirmadas con el usuario antes de marcar):**

- **Transición**: el cruce, cuando el cuerpo pasa por encima de los esquís y los
  cantos quedan planos.
- **Entrada**: desde el cambio de cantos hasta que el esquí empieza a cargar el
  canto nuevo. Se marca su *inicio*: el primer frame con el canto nuevo visible.
- **Ápice**: el momento de máxima inclinación y carga.

**Método**:

1. Vista general del video completo, un frame cada 0,5 s, para elegir el tramo.
   Se eligió **16–24 s**: giros sostenidos de carving, esquiador relativamente
   cerca. Entre 0 y 9 s hay una bajada de arranque cerca de la cámara, y más tarde
   el esquiador se ve más lejos.
2. Grillas recortadas al centro del frame, **un frame cada 0,1 s**, 1 s por
   imagen. Los frames se buscaron por tiempo real del contenedor
   (`CAP_PROP_POS_MSEC`); se verificó después que esa búsqueda devuelve
   exactamente el frame pedido (diferencia de imagen 0,00).
3. Marcado visual frame a frame. Criterios: transición = cuerpo derecho y esquís
   debajo y apuntando a la línea de pendiente; entrada = primer frame con los
   esquís desplazados hacia el lado nuevo; ápice = máxima separación lateral
   entre cuerpo y esquís, con la cadera más baja.
4. **El ground truth se guardó en `phase_detection/ground_truth.json` antes de
   calcular cualquier señal.** No se modificó después.

**Resultado** (tiempo real del contenedor, en segundos):

| Giro | Lado de inclinación (imagen) | Inicio de entrada | Ápice | Transición siguiente |
|---|---|---|---|---|
| (previa) | — | — | — | 16,35 (16,30–16,40) |
| 1 | derecha | 16,50 | 16,90 (16,80–17,00) | 17,35 (17,30–17,40) |
| 2 | izquierda | 17,50 | 17,95 (17,90–18,00) | 18,25 (18,20–18,30) |
| 3 | derecha | 18,40 | 18,90 (18,80–19,00) | 19,25 (19,20–19,30) |
| 4 | izquierda | 19,40 | 19,70 (19,60–19,80) | 20,05 (20,00–20,10) |
| 5 | derecha | 20,20 | 20,70 (20,60–20,80) | 21,15 (21,10–21,20) |
| 6 | izquierda | 21,30 | 21,80 (21,70–21,90) | 22,15 (22,10–22,20) |
| 7 | derecha | 22,30 | 22,70 (22,60–22,80) | 23,25 (23,20–23,30) |

7 giros completos, 8 transiciones. Período de giro ~1,0 s. Del inicio de entrada
al ápice hay 0,3–0,5 s; del ápice a la transición, 0,35–0,55 s.

**Limitaciones del ground truth**:

- **Un solo marcador** (yo), sin segunda opinión. La incertidumbre propia es de
  ±0,05–0,1 s (la grilla es de 0,1 s y en muchos casos el evento cae entre dos
  frames, de ahí los rangos).
- **La entrada no es independiente de la transición**: en los 7 giros quedó
  marcada exactamente 0,15 s después del cruce. Es un artefacto de la grilla de
  0,1 s (el canto nuevo se ve en el frame siguiente al rango del cruce), no una
  medición fina. La entrada queda, en la práctica, sin validar como evento propio.
- **Circularidad parcial**: el ápice se marcó por "máxima inclinación visible", y
  `trunk_lean` mide inclinación. Que coincidan es en parte esperable por
  definición. "Máxima carga" no se puede validar sin datos de fuerza.
- **Un solo video, un solo esquiador, cámara detrás, y un tramo elegido por ser
  claro.** No dice nada todavía sobre cámara de frente o lateral (ver §6).

## 3. Hallazgo: el video 17 tiene fps variable y el pipeline asume fps constante

`extract_pose_sequence` lee los frames en secuencia y asigna `t = frame_idx /
CAP_PROP_FPS`. El video 17 (`.mov`, 1803 frames, "56,08 fps" de promedio) tiene
fps variable: los frames duran entre 12 y 35 ms (mediana 16,7 ms, o sea 60 fps
nominales con caídas). El reloj del pipeline se va atrasando respecto del real:

| frame | t pipeline | t real (contenedor) | desfase |
|---|---|---|---|
| 280 | 4,99 | 5,22 | +0,23 |
| 897 | 15,99 | 16,58 | **+0,59** |
| 1000 | 17,83 | 18,34 | +0,51 |
| 1300 | 23,18 | 23,58 | +0,40 |
| 1790 | 31,92 | 31,92 | 0,00 |

**Efecto en esta medición**: la primera corrida, con el reloj del pipeline, dio
resultados casi aleatorios (por ejemplo `trunk_lean`: 3/8 transiciones y 3/7
ápices). El gráfico mostraba las señales desfasadas un cuarto de ciclo: ~0,5 s
sobre giros de ~1 s. También produjo un overlay de pose "fantasma" (pose de un
frame dibujada sobre la imagen de otro), que en un momento pareció un fallo de
MediaPipe con el esquiador inclinado y no lo era. **Todos los números de este
documento usan el reloj real**: cada frame del pipeline se remapea a su
timestamp de contenedor. La versión con reloj del pipeline queda en
`phase_detection/report_pipeline_time.json`.

**Alcance**: se revisaron los 17 videos del dataset y de `backend/media`. Solo el
video 17 tiene desfase relevante (0,61 s); el resto queda en ≤0,033 s (un frame).

**Qué afecta y qué no**:

- **No afecta qué frame es ápice o transición**: la detección de fase trabaja
  sobre la secuencia de frames, que es la misma con cualquier reloj.
- **Sí afecta**, en videos con fps variable: los timestamps de `occurrences` que
  ve el usuario y que usa el Passport para saltar a ese momento del video
  (`pattern_display._parse_ts_seconds`), los umbrales en segundos
  (`MIN_TURN_DURATION_SEC`, ventanas en segundos) y el muestreo (1 de cada 7
  frames ya no son intervalos iguales de tiempo).
- **Probablemente afecta `audit-carving-video.md`**: esa auditoría usó el video 17
  y razonó sobre la fase del giro y frames concretos a partir de timestamps del
  pipeline. Sus correspondencias "tal timestamp cae en tal fase" pueden estar
  corridas 0,4–0,6 s. No se re-verificó.

Arreglarlo (usar `CAP_PROP_POS_MSEC` en `extract_pose_sequence`) queda **fuera de
este sprint** y pendiente de decisión. Anotado en NOTES.md.

## 4. Comparación de señales candidatas

**Metodología** (misma lógica que el filtro de actividad): para cada señal se
derivan eventos con una regla fija y se compara cada evento marcado a mano con el
predicho más cercano del mismo tipo, dentro de ±0,4 s (menos de medio período de
giro; fuera de eso, "no detectado").

- **Señales oscilantes** (`trunk_lean`, centro de masa): transición = cruce por
  cero (interpolado, sin interpolar sobre huecos de tracking de más de 0,4 s);
  ápice = extremo de |señal| entre dos cruces; entrada = primer instante tras el
  cruce con |señal| ≥ 25% del pico del giro.
- **Flexión de rodilla**: ápice = máximo local (ventana ±0,35 s); transición =
  mínimo local.
- **Suavizado**: liviano y común a todas (media centrada de ±0,19 s), para no
  favorecer a ninguna. `trunk_lean` se evaluó además con el suavizado exacto de
  producción.
- **Métricas**: sesgo = error medio con signo (+ = la señal llega tarde);
  dispersión = desvío estándar (si es baja, el error es consistente y
  corregible); máx = peor caso absoluto.

### A 8 fps (muestreo de producción, ~0,117 s reales entre muestras)

| Señal | Evento | Detectados | Sesgo | Dispersión | Error medio abs. | Máx |
|---|---|---|---|---|---|---|
| **com_x − tobillos** | **transición** | **7/8** | −0,050 | **0,054** | **0,062** | **0,112** |
| com_x − tobillos | ápice | 6/7 | −0,145 | 0,110 | 0,156 | 0,313 |
| com_x − tobillos | entrada | 6/7 | −0,114 | 0,034 | 0,114 | 0,148 |
| **trunk_lean (suavizado de producción)** | transición | 7/8 | +0,123 | 0,132 | 0,123 | 0,391 |
| **trunk_lean (suavizado de producción)** | **ápice** | **7/7** | +0,025 | 0,101 | **0,093** | **0,180** |
| trunk_lean (suavizado de producción) | entrada | 7/7 | +0,053 | 0,101 | 0,079 | 0,265 |
| trunk_lean (suavizado liviano) | ápice | 6/7 | +0,064 | 0,079 | 0,086 | 0,180 |
| com_x en imagen (sin tendencia, ventana 1 s) | transición | 6/8 | −0,174 | 0,051 | 0,174 | 0,257 |
| com_x en imagen (sin tendencia, ventana 1 s) | ápice | 5/7 | +0,012 | 0,193 | 0,143 | 0,378 |
| flexión de rodilla | transición | 6/8 (+2 de más) | +0,095 | 0,100 | 0,105 | 0,240 |
| flexión de rodilla | ápice | 7/7 (+1 de más) | +0,077 | 0,146 | 0,139 | 0,275 |

### A 28 fps (referencia: cuánto del error es muestreo y cuánto es la señal)

| Señal | Evento | Detectados | Sesgo | Dispersión | Máx |
|---|---|---|---|---|---|
| trunk_lean (suavizado liviano) | ápice | 5/7 | +0,009 | **0,017** | **0,037** |
| trunk_lean (suavizado liviano) | transición | 5/8 | +0,006 | 0,088 | 0,149 |
| com_x − tobillos | transición | 4/8 | −0,053 | 0,069 | 0,142 |
| com_x − tobillos | ápice | 5/7 | −0,185 | 0,091 | 0,297 |
| flexión de rodilla | ápice | 6/7 (+3 de más) | +0,073 | 0,176 | 0,312 |

A 28 fps hay **más huecos de tracking** (el más largo, 0,60 s, contra 0,47 s a
8 fps) y eso hace perder detecciones. Donde detecta, el ápice por `trunk_lean` es
casi exacto (±0,04 s). Es decir: la señal sirve, y a 8 fps el error del ápice es
mayormente de muestreo.

Gráfico: `phase_detection/signals_realtime.png` (verde = transición, rojo =
ápice, naranja = entrada, todo marcado a mano).

### Lectura

- **com_x − tobillos es la mejor señal para la transición**: error chico,
  consistente entre giros (dispersión 0,05) y sin detecciones de más. Tiene
  sentido físico: es lo mismo que se mira a ojo ("el cuerpo pasa por encima de
  los esquís"). Para el ápice llega sistemáticamente antes (−0,15 s): el
  desplazamiento cuerpo-pies llega a su máximo antes que la inclinación del
  tronco.
- **`trunk_lean` es la mejor señal para el ápice** y la única que detectó los 7.
  Para la transición llega tarde y con dispersión alta (+0,12 ± 0,13, con un caso
  de 0,39 s): el tronco se endereza después de que el cuerpo ya cruzó.
- **La combinación de las dos** usa lo mejor de cada una, y las dos ya se
  calculan en `compute_frame_metrics`. Los tobillos ya están en `PoseFrame`, así
  que no hace falta ningún modelo ni señal nueva.
- **La flexión de rodilla no sirve como proxy de fase en este video**: tiene picos
  grandes solo en algunos giros (por ejemplo ~19,0 y ~22,7 s), con dispersión de
  0,15 s y detecciones de más. No sigue el ritmo de los giros de forma confiable.
- **El centro de masa en coordenadas de imagen** pierde contra el relativo a los
  tobillos en todo: mezcla el movimiento de la cámara.

## 5. Recomendación y margen de error

**Detección de fase propuesta** (para el punto 1, si el usuario la aprueba):

1. **Transiciones**: cruces por cero de `(com_x − tobillos_x) / torso`, con
   suavizado liviano. Sin interpolar sobre huecos de tracking: si hay un hueco,
   esa transición queda sin detectar en vez de inventada.
2. **Ápice**: entre dos transiciones consecutivas, el frame de |`trunk_lean`|
   máximo, con el suavizado de producción.
3. **Entrada**: **una ventana, no un punto**: desde la transición hasta el primer
   frame con |com_x − tobillos| ≥ 25% del pico del giro. En el ground truth la
   entrada empieza ~0,15 s después del cruce, o sea ~1 muestra a 8 fps. Un
   patrón evaluado "en la entrada" se apoyaría en 1–2 frames por giro, salvo que
   se suba el muestreo para carving.

**Margen con el que se puede confiar, a 8 fps** (7 giros, video 17):

| Evento | Margen típico | Peor caso | En muestras |
|---|---|---|---|
| Transición | ±0,06 s | 0,11 s | ≈1 |
| Ápice | ±0,10 s | 0,18 s | ≈1,5 |
| Entrada | no validable como punto | — | — |

Con giros de ~1 s, el ápice queda ubicado dentro de ±18% del giro en el peor
caso. Alcanza para "evaluar en la zona del ápice" (por ejemplo, una ventana de
±1 muestra alrededor del ápice detectado). No alcanza para "evaluar en el frame
exacto del ápice".

**Condición de éxito del Sprint 0** (sección 4 del documento): se cumple *para
este video*. La combinación se acerca al ground truth en 7 de 7 ápices y 7 de 8
transiciones, con el margen documentado arriba.

## 6. Qué falta antes de confiar en esto para el punto 1 (para decidir)

- **Un solo video y cámara detrás.** com_x − tobillos mide desplazamiento lateral
  *en la imagen*. Con cámara de frente se invierte el signo, pero los cruces por
  cero siguen sirviendo. Con cámara **lateral**, el desplazamiento lateral pasa a
  ser profundidad y la señal debería fallar. Para validar sobre prueba1-4
  (sección 3 del documento) habría que marcar ground truth en al menos uno más,
  idealmente con otro ángulo de cámara.
- **Huecos de tracking**: la transición de 22,15 no se detectó por un hueco de
  0,4 s. La regla elegida prefiere perder un evento antes que inventarlo.
- **El bug de fps variable** no bloquea la detección de fase (que trabaja por
  frame), pero sí cualquier umbral en segundos y los timestamps que ve el
  usuario en videos con fps variable. Decidir si se arregla antes del punto 1.

## Archivos

- `phase_detection/ground_truth.json`: marcas manuales (guardadas antes de medir).
- `phase_detection/measure_phase_signals.py`: medición reproducible
  (`--pipeline-time` para ver el resultado con el reloj del pipeline).
- `phase_detection/report.json` / `report_pipeline_time.json`: resultados
  completos, giro por giro.
- `phase_detection/signals_realtime.png`: señales contra el ground truth.
