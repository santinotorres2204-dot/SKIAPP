# Notas y limitaciones conocidas — módulo de análisis

## Recomendación de encuadre: tamaño del esquiador en el frame

El pipeline (MediaPipe Pose + reglas heurísticas) necesita que el esquiador
ocupe una porción mínima del alto del frame para trackear la pose de forma
confiable. Midiendo la altura hombro-tobillo (normalizada, promedio de los
8 keypoints requeridos) en los frames válidos de los 4 videos de referencia
que sí funcionaron bien (`prueba1-4.mp4`, con `--min-visibility` default 0.5):

| Video | Frames válidos | Altura del esqueleto (% del alto del frame) |
|---|---|---|
| prueba1 | 14/40 | min 7.1% · mediana 9.8% · max 14.6% |
| prueba2 | 37/84 | min 5.7% · mediana 10.6% · max 19.7% |
| prueba3 | 13/56 | min 6.3% · mediana 12.4% · max 23.0% |
| prueba4 | 95/118 | min 4.9% · mediana 12.5% · max 22.7% |

En los cuatro casos el piso observado ronda 5-7% del alto del frame. Por
debajo de eso la detección empieza a fallar sistemáticamente: en un video
de park (salto con caída al aterrizar) donde el esquiador ocupaba
visualmente ~2-3% del alto del frame (plano muy abierto, toda la ladera
visible, sujeto chico contra un fondo de árboles), MediaPipe no detectó
ninguna persona en el 96% de los frames muestreados (144/150), y en el 4%
restante devolvió falsos positivos — el "esqueleto" quedaba dibujado sobre
la arboleda del fondo, no sobre el esquiador real (visible comparando las
capturas con `debug_turns.py` / inspección manual de frames).

**Recomendación**: el esquiador debería ocupar al menos ~10% del alto del
frame (con margen sobre el piso empírico de 5-7%) para que el análisis
tenga chances razonables de funcionar. En la práctica: filmar relativamente
cerca o con zoom, evitando planos generales de toda la ladera.

No se relaja `min_visibility` (default 0.5) para compensar encuadres
lejanos — bajarlo generaría más falsos positivos como el de los árboles
del caso de park, no mejor detección real.

## Interpretación por disciplina: peso hacia atrás (carving, moguls, freeride, powder)

`analyze_ski_video.py` ahora acepta `--discipline` (mismos valores que
`discipline_tag`) y, solo para **carving**, **moguls**, **freeride** y
**powder**, interpreta una nueva métrica (`trunk_fore_aft_deg`) con umbrales
distintos por disciplina. **all_mountain** (y **park**) siguen con el
análisis genérico sin este agregado — no se tocó nada de lo existente para
ellas (que park siga pasando por este script es a propósito, ver
"Enrutamiento de park" más abajo). all_mountain queda afuera a propósito: al mezclar terrenos no tiene
una postura ideal única contra la cual evaluar peso adelante/atrás.

**La métrica** (`_trunk_fore_aft_deg` en el código): ángulo del tronco
(hombro) respecto a la línea tobillo-cadera, positivo cuando el hombro cae
por detrás de la dirección hacia la que flexiona la rodilla ("peso atrás"),
negativo cuando cae adelante. No se usa la vertical absoluta de la imagen
como referencia porque en 2D monocular no sabemos hacia qué lado del frame
mira el esquiador (mismo problema que ya afecta la etiqueta
izquierda/derecha de los giros — ver nota en `segment_turns`). En cambio, la
rodilla flexiona hacia adelante en cualquier postura funcional de esquí sin
importar el encuadre de cámara, así que se usa como referencia de "adelante"
frame a frame. Cuando la rodilla está casi alineada con la línea
tobillo-cadera (offset lateral menor al 4% del largo de la pierna), el
frame se descarta para esta métrica en particular (se guarda como `0.0`,
"no confiable") en vez de arriesgar un signo adivinado.

**Sigue siendo una aproximación 2D de pose, no una medición real de presión
sobre los esquís/botas** — se lo aclara explícitamente en `discipline_note`
del JSON de salida (ver más abajo), no solo acá.

**Contexto técnico** (referencia validada por el fundador, instructor
certificado):
- *Carving*: el peso debe ir adelante, presión sobre la lengüeta de la
  bota. Peso atrás es el error técnico más común a corregir → umbrales
  bajos (`BACKWARD_LEAN_THRESHOLDS_DEG["carving"]`).
- *Moguls*: mismo nivel de exigencia que carving — estar en el asiento
  trasero en un badenal es una receta para el desastre (se pierde el
  control de punta justo cuando más se lo necesita para absorber el
  siguiente badén) → mismos umbrales que carving.
- *Freeride*: el coaching moderno rechaza explícitamente el mito de
  "tirate para atrás" en nieve profunda/variable (una idea heredada de los
  esquís angostos de los 80-90); el objetivo es peso centrado, con presión
  pareja entre punta y talón. A diferencia de powder, freeride *no* tolera
  el margen extra de ir más atrás al iniciar el giro → umbrales más
  parecidos a carving/moguls que a powder, aunque un poco más laxos que
  carving por lo variable del terreno.
- *Powder*: se busca ir centrado (no "tirado atrás" como dice la creencia
  popular), pero se admite un centro de masa levemente más neutro/atrás que
  en carving, sobre todo al iniciar el giro, para mantener las puntas
  arriba de la nieve. Solo se marca si es *muy* pronunciado y sostenido →
  umbrales bastante más altos que carving.

En ambos casos se exige que sea **sostenido**: un pico aislado de
`trunk_fore_aft_deg` no alcanza, tiene que superar el umbral "baja" en al
menos `SUSTAINED_BACKWARD_PROPORTION` (35%) de los frames válidos del video
para generar el patrón `peso_hacia_atras`.

El JSON de salida ahora incluye `discipline_note`: una explicación en
lenguaje simple del criterio aplicado (ej. *"Este video fue analizado como
carving, donde se espera peso adelantado... No se detectó un patrón
sostenido de peso hacia atrás con los umbrales de esta disciplina."*), para
que quien lea el resultado entienda el porqué, no solo el resultado. Es
`null` si `discipline_tag` no es carving, moguls, freeride ni powder (o no
se pasó ninguno), en cuyo caso el comportamiento es idéntico al de antes de
este cambio (backward-compatible: sin `--discipline`, no se agrega ni el
patrón ni la nota).

**Validado corriendo `--discipline carving` contra `prueba1-4.mp4`** (las
referencias ya usadas para calibrar el resto del pipeline): el mecanismo
corre end-to-end sin romper nada de lo existente, produce valores de
`trunk_fore_aft_deg` con variación real (no degenerados — ej. prueba4: rango
-77° a +30°, mediana -2.7°) y **no dispara** `peso_hacia_atras` en ninguno
de los 4 (esperable, son videos de referencia con técnica razonable). Con
`--discipline powder`, `--discipline moguls` y `--discipline freeride` sobre
los mismos 4 videos tampoco dispara en ningún caso (consistente: los
umbrales de moguls son iguales a carving y los de freeride/powder son
iguales o más laxos, así que si carving no marca, el resto tampoco
debería). No hay videos de referencia etiquetados específicamente como
moguls o freeride disponibles todavía (los únicos videos del repo son
`prueba1-4.mp4` y una tanda de park) — se corrió contra los mismos 4 videos
genéricos solo para confirmar que el mecanismo no rompe nada, mismo criterio
ya usado para validar carving/powder. Tampoco hay un video de referencia con
un "peso atrás" real conocido para confirmar el caso positivo en ninguna
disciplina — pendiente para cuando haya más material. **Sin calibrar** como
el resto de los umbrales de este archivo: son placeholders razonables para
validar que la lógica corre, no valores derivados de un dataset etiquetado.

**Limitación abierta**: en algunos frames (ej. prueba2: ~51% del total) el
offset de rodilla es demasiado chico para confiar en el signo, y se
descartan de esta métrica en particular. Si esto resulta ser frecuente en
más videos, la señal de `peso_hacia_atras` va a tener menos frames útiles
de los que sugiere `frames_with_valid_pose` — vale la pena trackearlo por
separado si se sigue calibrando esto.

## Sprint "confiabilidad de carving": geometría de rotación y filtro de actividad válida

Motivado por una auditoría diagnóstica previa (`audit-carving-video.md`) sobre un video
real ("el influencer", video17) que reveló dos problemas de raíz, no de calibración:
`rotacion_excesiva_tren_superior` dependía del eje Z de MediaPipe (mucho más ruidoso que
X/Y en mono-cámara) y disparaba sobre un outlier de un solo frame con landmarks mal
ubicados; y la segmentación de giros no distinguía el tramo de arranque cerca del
telesilla (giros lentos, casi rectos) de carving real, contaminando el cálculo de
`inconsistencia_entre_giros`. Proceso completo, decisiones y evidencia:
`rotation-metric-decision.md`, `ground-truth-carving.md`, `activity-filter-decision.md`,
`asymmetry-review.md`, `before-after-comparison.md`.

**Rotación** (`compute_frame_metrics`, `detect_rotation_excessive`): la fórmula pasó de
usar `arctan2` sobre componentes (Z, X) de los vectores hombro-hombro/cadera-cadera a
usar (Y, X) — deja de medir rotación axial "real" en 3D y pasa a medir diferencial de
inclinación lateral en el plano de la imagen, pero esa pérdida es preferible a seguir
dependiendo de un eje que la auditoría mostró no confiable. Comparado empíricamente
contra la fórmula Z original y una tercera candidata (ángulo respecto a la dirección de
desplazamiento del centro de masa, reusando la técnica de
`compute_edge_orientation_series` de `analyze_snowboard_video.py`) sobre los 4 videos del
dataset — se descartó la candidata de dirección de desplazamiento por agregar una
dependencia extra (velocidad del centro de masa) sin evidencia de que mejore la señal.
Se agregó exigencia de sostenido (`SUSTAINED_ROTATION_PROPORTION=0.35`, mismo patrón que
`peso_hacia_atras`) y se recalibraron los umbrales (`{15,25,35}`, antes `{20,30,40}`) para
la nueva escala por-frame (antes eran sobre un promedio). **Limitación honesta**: no hay
ningún video de referencia con rotación excesiva real conocida en el dataset — se validó
que deja de dispararse por el landmark defectuoso del influencer, pero no hay caso
positivo confirmado para validar sensibilidad de detección.

**Filtro de actividad válida** (`find_activity_start_idx`): se agrega una etapa entre
`segment_turns` y los 5 detectores de patrones que descarta el tramo inicial hasta
encontrar `VALID_ACTIVITY_MIN_CONSECUTIVE_TURNS=3` giros seguidos que superen
`VALID_ACTIVITY_MIN_LEAN_DEG=15.0`/`VALID_ACTIVITY_MIN_DURATION_SEC=0.4` cada uno. Elegido
sobre otras 4 candidatas (amplitud/duración de un solo giro, alternancia de dirección,
std móvil sostenida, amplitud por-frame sostenida) midiendo cada una contra un ground
truth marcado a mano (t=4.0s en video17) — las otras 4 o no filtraban nada, o cortaban un
giro real a la mitad. Si no encuentra una racha así (video corto, o ningún giro cruza el
umbral) devuelve 0 y no filtra nada — no puede vaciar el análisis de un video por no
encontrar el patrón. `asimetria_izq_der`/`inconsistencia_entre_giros` reciben los giros ya
filtrados pero indexados contra la lista completa de frames; balance/rotación/peso-atrás
reciben directamente la porción de frames recortada.

**Resultado en los 4 videos del dataset** (detalle completo en
`before-after-comparison.md`): solo video17 cambió de comportamiento (perdió los 2
patrones contaminados por ruido de landmark y por el arranque), los otros 3 —incluido
video2 con errores técnicos reales conocidos— mantuvieron exactamente los mismos patrones
y severidades. Confirma que ambos fixes son quirúrgicos: corrigen el caso que los motivó
sin alterar el comportamiento en videos donde el problema original no existía.

**Importante — qué NO confirma ese resultado**: se verificó explícitamente que los otros
3 videos no tenían el tipo de caso que cada fix ataca (ver detalle en
`rotation-metric-decision.md` y `activity-filter-decision.md`, secciones "chequeo de
generalización"). Ruido real de Z sí existe en video1/video16 (picos de 100.2°/71.7°),
pero nunca fue suficiente para disparar el patrón con ninguna de las dos fórmulas, y la
fórmula nueva no reduce ese ruido de forma pareja (en video1/video2 el pico máximo sube,
no baja). Los 3 videos tampoco tienen una fase de arranque de baja intensidad como la del
influencer (todos arrancan su primer giro ya por encima del umbral de actividad válida).
Es decir: **"quedaron idénticos" confirma que los fixes no tienen efectos colaterales
donde el problema original no existía, no que generalicen a un segundo caso real del
mismo tipo** — ese segundo caso no existe todavía en el dataset.

**`asimetria_izq_der`**: no se tocó (instrucción explícita del sprint). Se agregó
diagnóstico extra a `instrument_video.py` (diferencia por separado de `knee_flex` vs
`trunk_lean`, variabilidad dentro de cada lado, persistencia primera/segunda mitad de los
giros) que reveló que la asimetría no es temporalmente estable en ninguno de los 3 videos
con suficientes giros por lado (incluido el que hoy dispara "alta"), y que ese disparo
descansa en apenas 2 vs 3 giros. Recomendación para un sprint aparte (no implementada):
subir `MIN_TURNS_FOR_ASYMMETRY`, y evaluar exigir estabilidad temporal solo para
severidades "alta"/"media" — requiere primero confirmación de dominio del founder, ver
`asymmetry-review.md`.

**Instrumentación**: `instrument_video.py` (nuevo, reusable) genera un reporte de debug
por video con timestamp/frame/landmarks/visibility/valores geométricos raw y suavizados/
threshold/disparo-o-no/motivo/giro/actividad-válida para los 5 detectores, más frames
clave con overlay de pose — reportes guardados en `debug_reports/` (baseline, después de
rotación, después de filtro de actividad) para las 3 etapas del sprint.

**Condición para pasar a phase-aware (entrada/ápice/transición)**: se considera
satisfecha con la evidencia de este sprint — los giros que entran a los detectores ya
excluyen el arranque no relevante (punto 2), las métricas de rotación ya no dependen del
eje Z ruidoso (punto 1), la exigencia de sostenido evita que un pico aislado dispare un
patrón, y cada patrón de los 4 videos tiene evidencia trazable en su reporte de debug
correspondiente. **No se avanzó a phase-aware** — queda para que el usuario lo confirme y
dé la orden de arranque explícita del próximo sprint.

## Sprint de seguimiento: `asimetria_izq_der` con evidencia suficiente

Implementa la recomendación que había quedado pendiente en el sprint anterior
(`asymmetry-review.md`): el patrón ahora exige 3 condiciones combinadas, no solo cruzar el
umbral de diferencia. Proceso completo y evidencia: `asymmetry-fix-decision.md`.

**Condición 2 (sample size)**: `MIN_TURNS_FOR_ASYMMETRY` sube de 2 a **5** por lado.
Justificado con leave-one-out sobre el dataset: con 2-3 giros de un lado, sacar un solo
giro puede mover el diff más que el rango completo de severidad; con 11-12, el mismo
movimiento es un orden de magnitud menor. Sin videos de referencia con 4-10 giros por lado
para afinar el punto exacto, 5 es un piso razonado con margen, no calibrado con rigor
estadístico completo (mismo tipo de limitación que los umbrales de rotación).

**Condición 3 (persistencia)**: implementada como "la métrica que decide la severidad no
puede depender de un solo giro atípico" — para `knee_flex` y `trunk_lean` por separado, se
identifica el giro individual más influyente y se chequea si el lado favorecido se
mantiene sin él; solo las métricas robustas a ese chequeo cuentan para la severidad. Un
primer intento (exigir el umbral "baja" en las dos mitades del video) se descartó con
evidencia: hacía desaparecer el único caso positivo confirmado del dataset (video2) sin
distinguir que su severidad "alta" venía casi enteramente de un solo giro con un valor de
`knee_flex` extremo (61.6° vs 9-13° en el resto), mientras que su señal de `trunk_lean` (más
chica pero potencialmente real, creciente hacia el final del video) quedaba descartada
junto con la anterior sin justificación.

**Hallazgo importante**: al re-verificar giro por giro (no por mitades), ninguna de las
dos métricas de video2 sobrevive ningún chequeo razonable de robustez — converge con la
condición 2 en que **5 giros totales es insuficiente para cualquier validación
estadística**, más allá de cómo se defina "persistente".

**Consecuencia aceptada, decidida junto con el usuario**: video2 (video propio con errores
conocidos) deja de marcar una asimetría que el usuario confirmó como real. No se relajó el
criterio para forzar que siguiera disparando (violaría el principio de no ajustar
thresholds para preservar un caso conocido) — se aceptó el trade-off con mitigación
explícita: nuevo campo `asymmetry_note` (antepuesto al `summary` en
`backend/app/analysis_job.py`, mismo mecanismo que `discipline_note`) que dice
explícitamente "no hay suficientes giros para evaluar con confianza" en vez de dejar la
ausencia del patrón en silencio total, que podría malinterpretarse como "sin problema".

**Resultado en los 4 videos**: solo video2 pierde el patrón (antes "alta", ahora nada, con
la nota explícita). video17, video1 y video16 no cambian de resultado — video1 y video16
ahora también reciben la nota explícita de evidencia insuficiente (antes quedaban
silenciosos igual, pero sin decir por qué). `confidence_score` no cambia en ningún caso.

## Enrutamiento de park: se intentó conectar `analyze_park_video.py` y se revirtió

**Estado final (2026-09-30)**: `backend/app/analysis_job.py` sigue
mandando **todos** los videos, park incluido, a `analyze_ski_video.py`.
Para park eso da un resultado sin sentido semántico ("giros" en un salto),
pero no hace afirmaciones específicas falsas como "posible caída", y eso es
lo que hoy haría el prototipo de park. `analyze_park_video.py` queda como
**prototipo no conectado a producción**, igual que snowboard: necesita más
videos reales de park para validarse, en particular contra el problema de
pose a distancia + paneo de cámara, que genera falsos positivos tanto de
`posible_caida` como de `aterrizaje_inestable` (detalle abajo). Las
mejoras de los puntos 1 y 2 sí quedan en el script, sin activar.

**Cómo se llegó a esto.** `analysis_job.py` nunca miraba `discipline_tag`
para elegir el script, así que `analyze_park_video.py` no se ejecutaba en
el flujo real. Se vio con el video id=18 (park, ski): el 15/100 guardado
parecía el tope de snowboard, pero era cobertura real de la fórmula de ski,
40·(19/109) + 60·(2/15) = 14,97. Se probó enrutar `discipline_tag ==
"park"` al script de park (snowboard sin tocar) y se re-corrió el id=18.

**Re-corrida del video id=18 con el script de park** (antes del fix):

| | Antes (ski) | Ahora (park) |
|---|---|---|
| Frames válidos | 19/109 | 19/109 (misma extracción) |
| Unidad analizada | 2 giros | 1 salto |
| Patrones | `rotacion_excesiva_tren_superior` baja (guardado 24/09; re-corrido hoy con ski ya no sale, porque `MIN_VALID_FRAMES_FOR_ROTATION=20`) | `salto_detectado` + `posible_caida` **alta** (tronco 93,8°) |
| Confianza | 15 | 19 = 50·(19/109) + 50·(1/5). No llega al tope de 25 |

**`posible_caida` alta es un falso positivo, confirmado mirando los
frames**: el esquiador salta (~7–8,8 s), cae limpio y se aleja esquiando de
pie (9,6 s y 10,1 s). Lo que lo produce:

1. El "aterrizaje" (`t_landing` 12,00 s) es el **último** frame válido del
   clip y llega después de un hueco de 14 frames muestreados (~1,9 s) sin
   pose. Las ventanas de `find_jumps` y `evaluate_landing` cuentan posición
   en la lista de frames válidos, no tiempo real, así que un frame a 3,2 s
   del pico termina tratado como el aterrizaje (`LANDING_SEARCH_SEC` = 1,5).
   Es la misma limitación ya anotada en el caso park1.
2. El chequeo de tracking insuficiente **no lo atrapa**: la ventana de caída
   tiene un solo frame (es el último del clip), y la rama
   `len(fall_frames_segment) <= 1` exige `fall_end > landing_idx + 1`, cosa
   que no pasa al final de la lista. Resultado: `gap_ratio = 0`. Además, el
   hueco que importa es el de *antes* del aterrizaje, y ese no se mide.
3. El esquiador es muy chico en el frame (escala de torso de referencia
   0,015, con valores por frame que van de 0,0016 a 0,166). A esa escala
   `trunk_lean` no tiene sentido: da ~90° en la aproximación y ±150° en el
   aire con el esquiador derecho. Es el mismo problema de encuadre
   documentado al principio de este archivo.

### Fix de los puntos 1 y 2 en `analyze_park_video.py` (incluido, sin conectar)

- **Punto 1**: todas las ventanas de `find_jumps` y `evaluate_landing` se
  miden en segundos sobre `FrameMetrics.t`: baseline, máximo local,
  búsqueda de aterrizaje, separación entre saltos, estabilidad y caída. El
  baseline pasó de `_moving_average` (que rellena con ceros en los bordes)
  a una media de los frames válidos que caen dentro de ±1 s.
- **Punto 2**: el `gap_ratio` se calcula desde el último frame válido
  *antes* del aterrizaje hasta el final de la ventana de caída. Un frame
  aislado después de un hueco largo ya no da 0% de pérdida de tracking.

**Hallazgo de la validación: park4 y el video id=18 son el mismo clip**
(mismo salto y esquiador, 109 frames muestreados en los dos; el id=18 es
una versión `.mov`). park1/2/3 dan 0 frames con pose a 8 fps. El set de
regresión real es, entonces, un solo salto más park1 a 15 fps.

| Video | Antes | Después |
|---|---|---|
| park1/2/3 (8 fps) | 0 frames, nada | igual |
| park1 (15 fps) | 21/81, 0 saltos | 1 salto + `aterrizaje_inestable` alta + evento de tracking insuficiente (`gap_ratio` 0,72). El video tiene una caída real; no se afirma por falta de datos, que es lo correcto |
| v18 | salto + `posible_caida` alta (falsa) | salto + evento de tracking insuficiente (`gap_ratio` 0,80). **La falsa caída desaparece** |
| park4 | salto, sin caída (correcto por casualidad: aterrizaje evaluado a 13,6 s, 4,4 s después del pico) | salto + `aterrizaje_inestable` alta + `posible_caida` alta, **ambas falsas** (frames revisados: a los 10,0 s está de pie carveando) |

La regresión de park4 no la causa el fix: el fix la deja a la vista. Al
evaluar el aterrizaje en el momento correcto (10,0 s), la pose de ese
momento es inutilizable. `trunk_lean` da entre −130° y −169° (hombros
*debajo* de las caderas) con el esquiador derecho, y el centro de masa
salta 1,75 torsos entre dos frames porque la cámara sigue al esquiador.
Antes, el bug del punto 1 evaluaba un frame 4,4 s más tarde que, por
casualidad, tenía una pose razonable.

**Por qué se revirtió el enrutamiento en vez de parchear.** Un filtro que
descarte el tronco invertido arreglaría `posible_caida` en park4, pero no
`aterrizaje_inestable` (que sale del paneo de cámara, no del ángulo), y
además ya es meterse en el problema de encuadre/distancia, que es de todo
el pipeline y no de este fix puntual. Con un solo salto real para validar,
no hay forma de saber si un parche así generaliza.

**Resultado guardado en la base para el id=18: no se actualizó** (sigue el
del 24/09, `rotacion_excesiva_tren_superior` baja, con la lógica de ski de
antes del sprint de carving). Decisión explícita: se deja como está.

**Para reconectar park** hace falta, como mínimo: más videos reales de park
con encuadre cercano (park4/id=18 es hoy el único salto con pose usable),
y resolver o acotar los falsos positivos de pose a distancia + paneo de
cámara en `posible_caida` y `aterrizaje_inestable`. Al reconectar, recordar
que `insufficient_data_events` no tiene columna propia y hay que
persistirlo (por ejemplo dentro de `raw_pose_data`), o se pierde.

### Hallazgo aparte: la confianza no refleja que la pose está al límite de lo utilizable

`compute_confidence_score_park` (igual que la de ski) solo mira *cuántos*
frames tienen pose y cuántos saltos o giros hay, no *qué tan usable* es
esa pose. En este clip:

- Escala de torso de referencia: 0,015 del alto del frame en el id=18
  (~29 px de 1920) y 0,027 en park4. Dentro del mismo clip la escala varía
  ~100× (0,0016 a 0,166), señal de keypoints inestables.
- Lecturas geométricamente imposibles para la situación: tronco invertido
  (|lean| > 120°) con el esquiador de pie, y ~90° durante la aproximación
  al salto en el id=18.

Con eso, el 19/100 del id=18 transmite "pocos datos", pero no "los datos
que hay no son confiables". Ideas para cuando se aborde el problema de
encuadre (no implementadas): ponderar la confianza por escala de torso
mediana y por su estabilidad dentro del clip, o descartar como inválidos
los frames con geometría implausible (por ejemplo tronco invertido fuera de
la fase aérea) antes de evaluar patrones.

## Subida de videos: validación real de contenido y límite de tamaño (2026-09-30)

**Qué había**: ninguna validación. `backend/app/storage.py::_save_file` (que
usan tanto la subida de videos de análisis como el video del Season Review
del panel de admin) copiaba al disco cualquier archivo, conservando la
extensión que mandaba el cliente. No miraba el content-type ni el contenido, y
no tenía límite de tamaño. Como `/media/videos` y `/media/season_reviews` se
sirven como estáticos (`main.py`), un `.html` subido se habría servido como
página desde el propio dominio (XSS almacenado).

**Evidencia**: dos archivos `.py` en `backend/media/videos/9/` (filas 13 y 14
de `video_uploads`, `analysis_status=failed`). Sin abrirlos se identificó que
son idénticos entre sí y byte a byte iguales a `backend/app/main.py` del
commit `7a1e260` (mismo SHA-256). Los subió una sesión anterior de Claude Code
el 2026-09-07, con `curl -F "file=@app/main.py;type=video/mp4"`, como video
de relleno para probar los formularios de Trick Card / Freeride Run y los
mensajes de error. El usuario 9 ("Dup", `dupcheck_<timestamp>@example.com`)
también lo creó ese script. Inofensivos, pero muestran el problema: el
content-type `video/mp4` del header se aceptó sin más.

**Qué se corrigió** (`backend/app/storage.py`, nuevo `ai-analysis/probe_video.py`):

1. **Límite de tamaño**: `max_video_upload_mb` en `config.py` (500 MB por
   defecto; el video real más grande hasta hoy pesa 80 MB). Se corta la copia
   apenas se supera y responde 413.
2. **Staging fuera de lo servido**: el archivo se escribe primero en
   `media/_incoming/` (no montado) y solo se mueve a `media/videos/` o
   `media/season_reviews/` después de pasar todos los chequeos. Un archivo
   rechazado o a medio subir nunca queda accesible por URL, y no deja basura.
3. **Lista blanca de extensiones**: `.mp4 .m4v .mov .webm .mkv .avi` (sin
   distinguir mayúsculas). La extensión con la que se guarda sale de esa lista,
   nunca se copia tal cual la del cliente. Si no está en la lista: 415.
4. **Firma del contenedor**: los primeros bytes tienen que coincidir con la
   extensión (caja `ftyp`/raíz ISO-BMFF para mp4/mov/m4v, EBML para webm/mkv,
   `RIFF…AVI` para avi). Un `.py` o un `.html` renombrado a `.mp4` se frena
   acá, sin llegar al decoder. Si no coincide: 415.
5. **Decodificación real**: `probe_video.py` corre en el venv de `ai-analysis`
   (OpenCV vive ahí, mismo patrón que `analysis_job.py`). Exige que el
   contenedor abra, que tenga dimensiones y fps válidos, y que decodifique un
   cuadro al principio **y otro cerca del final**. Lo último hace falta porque
   un archivo cortado (probado con los primeros 64 KB de `prueba1.mp4`) abre y
   decodifica el primer cuadro igual. Si falla: 415. Tarda ~0,2–0,3 s por video.
6. El content-type del header **no se usa**, a propósito: se puede falsear, y
   los chequeos 4 y 5 ya cubren lo que validaría.

Los errores son `HTTPException` con mensaje en castellano. La API los
devuelve como `{"detail": ...}`, y el formulario del Passport
(`/passport/{id}/videos`) ya los muestra como alerta, sin cambios en el
template.

**Validación**: los 16 videos reales del repo y de `backend/media` pasan,
incluido el `.mov` con fps variable del video 17. Se rechazan, cada uno con su
motivo: `.py`, `.py` renombrado a `.mp4`, HTML renombrado a `.mp4`, `.mp4`
truncado, archivo vacío, `.avi` con firma falsa, video real renombrado a
`.webm` y video que supera el límite. En ningún caso rechazado se crea una fila
en `video_uploads` ni queda un archivo en disco.

**Limitación que queda**: FastAPI/python-multipart recibe el cuerpo multipart
completo (a un temporal propio) **antes** de que corra el endpoint. El límite
de 500 MB impide guardarlo, pero no impide que el servidor lo reciba. En un
deploy real conviene limitar también el tamaño del request en el reverse proxy
(por ejemplo `client_max_body_size` en nginx).

**Para decidir**: borrar los dos `.py` de `media/videos/9/` y sus filas 13 y
14, y el usuario de prueba 9.

## Pendientes / limitaciones conocidas para revisar más adelante

- **Park: prototipo v1 agregado (`analyze_park_video.py`), separado de
  `segment_turns`/`detect_asymmetry`/etc. porque un salto no genera la
  secuencia de giros alternados que esa lógica espera.** Detecta 3 patrones
  a partir de las mismas métricas por frame de `analyze_ski_video.py`
  (centro de masa, escala de torso, inclinación de tronco):
  `salto_detectado` (pico brusco de elevación de caderas/hombros que sube y
  vuelve a bajar, vs. el vaivén lateral gradual de un giro),
  `aterrizaje_inestable` (desplazamiento brusco de centro de masa después
  del pico) y `posible_caida` (tronco cerca de la horizontal después de un
  aterrizaje). El tercer patrón distingue explícitamente una caída real de
  una pérdida de tracking de MediaPipe: si la ventana posterior al
  aterrizaje tiene una proporción alta de frames sin pose válida, se reporta
  aparte en `insufficient_data_events` y **nunca** como `posible_caida` —
  mismo principio que la nota de encuadre de más arriba (frames faltantes no
  son evidencia de nada, son ausencia de datos).

  Es explícitamente un **prototipo sin calibrar**: con 4 videos de
  referencia no hay forma de ajustar umbrales con rigor. El
  `confidence_score` en este modo tiene un tope duro (25/100, ver
  `PARK_PROTOTYPE_MAX_CONFIDENCE`) sea cual sea la cantidad de datos, y el
  JSON de salida incluye `"prototype_notice"` marcando esto explícitamente.

  **Resultado de la corrida de validación contra `park1-4.mp4`:**

  | Video | Frames válidos (8fps) | Salto detectado | Nota |
  |---|---|---|---|
  | park1 | 0/41 | — | Ver caso especial abajo |
  | park2 | 0/97 | — | Encuadre muy abierto (esquiadores a lo lejos, mismo patrón que el caso de park documentado arriba) |
  | park3 | 0/150 | — | Igual que park2 |
  | park4 | 23/109 | Sí (1) | Encuadre cercano; sin inestabilidad ni caída detectada |

  Solo `park4` tenía encuadre suficientemente cercano para trackear algo, y
  ahí la lógica funcionó end-to-end: detectó el único salto del clip sin
  falsos positivos de inestabilidad/caída. Los otros tres fallan por el
  mismo motivo ya documentado arriba (sujeto chico en el frame).
  **Corrección (2026-09-30)**: ese "sin falsos positivos" era casualidad.
  El aterrizaje se evaluaba 4,4 s después del pico por un bug de ventanas.
  Con el bug arreglado, park4 da caída e inestabilidad falsas, y por eso el
  prototipo sigue **sin conectar a producción**. Ver "Enrutamiento de park"
  más arriba.

  **Caso especial — park1 (revisado manualmente frame a frame):** el video
  sí contiene un salto con una caída real y visible (aterrizaje con el
  cuerpo en el piso, esquís separados), pero el pipeline no detectó pose en
  ningún frame muestreado a 8fps. Subiendo el muestreo a 15fps se rescatan
  21/81 frames, pero siguen siendo demasiado discontinuos (gaps grandes
  entre frames válidos) como para que `find_jumps` arme la señal de
  elevación — la ventana de pico/baseline asume frames aproximadamente
  contiguos (mismo supuesto que ya usa `segment_turns` para giros), y con
  gaps grandes esa ventana deja de tener sentido en tiempo real aunque sí
  lo tenga en índice de lista. Conclusión: la combinación de rotación rápida
  del cuerpo durante el truco (motion blur) + encuadre no siempre cercano
  rompe el tracking justo en el momento más importante (el aterrizaje). Esto
  es una ilustración concreta de por qué `insufficient_data_events` existe
  como categoría separada: acá ni siquiera llegamos a esa categoría, porque
  la falta de datos es tan severa que no se detecta el salto en absoluto, no
  solo el aterrizaje. Pendiente para cuando haya más videos: si esto se
  repite, evaluar si vale la pena rehacer las ventanas de `find_jumps`
  sobre timestamps reales en vez de posición en la lista de frames válidos,
  para tolerar mejor los gaps.
- **Snowboard: prototipo v1 agregado (`analyze_snowboard_video.py`), separado
  de `analyze_ski_video.py` (no una modificación de ese archivo).**
  *** SIN VALIDAR CONTRA NINGÚN VIDEO REAL DE SNOWBOARD — basado únicamente
  en referencia técnica documentada. No usar para dar feedback real a un
  usuario hasta conseguir videos de prueba. ***

  Se separa de ski porque la mecánica es fundamentalmente distinta, no un
  ajuste de umbrales: el rider viaja de costado a la dirección de
  desplazamiento (no de frente como en ski), y los giros no son simétricos
  izquierda/derecha sino **toe-side** (peso sobre los dedos) y **heel-side**
  (peso sobre el talón) — mecánicamente distintos a propósito. Referencia
  técnica validada por el fundador (instructor certificado): en toe-side el
  peso arranca en el pie delantero sobre los dedos y se centra en el apex,
  con las rodillas siguiendo la dirección de los dedos; en heel-side el peso
  arranca todavía adelantado y se traslada al pie trasero y el talón al
  completar el giro, con hombros/cabeza apuntando a la dirección de
  descenso y torso relativamente calmo. Que haya diferencias de ejecución
  entre toe-side y heel-side en el mismo rider **no es un error en sí
  mismo** — por eso el módulo nunca compara un tipo contra el otro.

  Reutiliza de `analyze_ski_video.py` solo lo que es geometría genérica y no
  depende de orientación corporal ni de simetría de giros: extracción de
  pose, `compute_frame_metrics` (centro de masa / escala de torso) y
  `detect_balance_loss` **tal cual, sin cambios** — es portable porque solo
  mide saltos bruscos del centro de masa entre frames, no depende de hacia
  dónde mira el cuerpo. También reutiliza `INCONSISTENCY_CV_THRESHOLDS` (es
  un coeficiente de variación adimensional, portable igual).

  La segmentación de giros usa un proxy nuevo en vez del cruce por cero de
  `trunk_lean` que usa ski: el cambio de orientación cadera-hombro
  (`hip_vec + shoulder_vec`, plano x-y) respecto a la dirección de
  desplazamiento del centro de masa entre frames consecutivos
  (`compute_edge_orientation_series`). Como el rider viaja de costado, ese
  ángulo tiene un offset base esperable de ~90° en postura neutra (en vez de
  ~0° como el `trunk_lean` de ski), así que en vez de comparar contra cero
  se le resta un baseline móvil ancho (`compute_edge_deviation`) — mismo
  truco que usa `find_jumps` en `analyze_park_video.py` para aislar el pico
  de un salto del nivel de piso de la elevación. Los cruces de signo de esa
  desviación segmentan los giros (`segment_edge_turns`), igual mecanismo que
  `segment_turns` de ski pero sobre esta señal.

  **Caveat más fuerte que el de izquierda/derecha en ski**: la etiqueta
  `toe_side`/`heel_side` asignada a cada signo es una convención arbitraria
  de este prototipo (positivo = `toe_side`), no una detección real de qué
  borde está cargado — sin un video real filmado con stance y encuadre
  conocidos no hay forma de confirmar la correspondencia. Lo que sí es
  válido es que ambos signos alternan de forma consistente dentro del mismo
  video, así que sirve para separar "giros del mismo tipo entre sí" para el
  chequeo de inconsistencia, aunque la etiqueta en sí no esté confirmada.

  Patrones detectados: `perdida_de_balance` (reusado de ski, sin cambios) e
  `inconsistencia_entre_giros` **por separado para `toe_side` y `heel_side`**
  (nunca cruzado — comparar un tipo contra el otro no tiene sentido, ver
  arriba). El `confidence_score` tiene un tope duro de **15/100**
  (`SNOWBOARD_PROTOTYPE_MAX_CONFIDENCE`), más bajo que el de park (25/100)
  porque ahí al menos hay 4 videos reales de referencia (`park1-4.mp4`) y acá
  no hay ninguno todavía. El JSON de salida incluye `"prototype_notice"` con
  el disclaimer completo.

  **Validación**: no hay ningún video real de snowboard en el repo todavía,
  así que se validó con una secuencia sintética de keypoints (rider
  simulado viajando a velocidad constante, con la línea cadera-hombro
  rotando en seno alrededor de la perpendicular a la dirección de
  desplazamiento, más un salto brusco de centro de masa inyectado a
  propósito). El pipeline completo corrió sin excepciones: segmentó 13
  giros alternando `toe_side`/`heel_side` como se esperaba de la señal
  simulada, `detect_balance_loss` disparó sobre el salto de centro de masa
  inyectado, y ambos chequeos de inconsistencia (`toe_side` y `heel_side`
  por separado) se ejecutaron y devolvieron severidad "baja" sobre la
  variación sintética. Esto confirma que la lógica corre end-to-end sin
  errores estructurales — **no confirma que el resultado tenga sentido
  biomecánico real**, eso requiere video real (mismo criterio que se usó al
  validar carving/powder/moguls/freeride más arriba, pero un escalón más
  débil: ahí al menos había videos reales, aunque sin el caso positivo
  específico).

  **No conectado al flujo real todavía**: el pipeline async
  (`analysis_job.py`) y el campo `sport_type=snowboard` de `VideoUpload`
  siguen sin tocarse — a propósito, hasta tener al menos un video real de
  snowboard para probar este módulo contra él.
- **terrain_tag**: falta un campo para el tipo de terreno/pista (pista
  groomed vs fuera de pista, por ejemplo). Pendiente definir si aporta algo
  a las reglas heurísticas o si es solo metadata informativa.
