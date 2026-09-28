# Decisión — `asimetria_izq_der`: evidencia suficiente, no solo threshold

Sprint de seguimiento a "confiabilidad de carving" (implementa la recomendación dejada
pendiente en `asymmetry-review.md`, punto 3). Pedido explícito: exigir 3 condiciones
combinadas antes de marcar el patrón — (1) diferencia porcentual suficiente (ya existía),
(2) sample size mínimo por lado, (3) persistencia/estabilidad en el tiempo — y medir cada
una por separado contra el dataset de referencia antes de fijar un mínimo concreto, mismo
principio que el sprint anterior ("no cambiar el threshold hasta que deje de dispararse").

## Condición 2 — sample size mínimo por lado

Script: `asymmetry_condition_analysis.py`. Método: leave-one-out sobre los giros reales de
cada video — se saca un giro a la vez y se mide cuánto se mueve el `diff` agregado.

| Video | n_izq/n_der | diff agregado | leave-one-out: delta máximo al sacar 1 giro |
|---|---|---|---|
| video17 (sólido) | 11/12 | 0.089 | **0.037** |
| video1 (mixto) | 3/5 | 0.089 | 0.358 |
| video2 (errores conocidos) | 2/3 | 0.779 | 0.558 |
| video16 (casi sin datos) | 0/1 | — (no computable) | — |

Con 2-3 giros de un lado, sacar **un solo giro** puede mover el diff más que el rango
completo de severidad (0.35, el umbral "alta"). Con 11-12, el mismo movimiento es un orden
de magnitud menor. No hay videos de referencia con 4-10 giros por lado para afinar el
punto exacto donde la sensibilidad deja de ser peligrosa — **`MIN_TURNS_FOR_ASYMMETRY = 5`**
(antes 2) es un piso razonado con margen sobre la zona demostrada como frágil, no un valor
calibrado con rigor estadístico completo. Mismo tipo de limitación ya documentada para los
umbrales de rotación en el sprint anterior.

## Condición 3 — persistencia: dos intentos, el primero se descarta con evidencia

### Intento 1 (descartado): exigir el umbral "baja" en las dos mitades del video

Primera implementación: partir los giros en 2 mitades temporales y exigir que el diff de
`trunk_lean` supere el umbral "baja" en **ambas**. Con los datos de video2 (1ra mitad=0.018,
2da mitad=0.423) esto separaba limpio el caso conocido... hasta que se confirmó con el
usuario que la asimetría de video2 **es un error técnico real que él conocía**. Un fix que
hace desaparecer el único caso positivo confirmado del dataset no es aceptable sin
entender antes por qué — se paró la implementación acá y se re-analizó.

**Root cause del disparo original**: el 77.9% de diferencia que hacía disparar "alta"
venía casi enteramente de `knee_flex`, y ese valor está dominado por un solo giro con
flexión de rodilla de 61.6° (vs 9-13° en los otros 4 giros de ese video) — evidencia
visual y numérica de un giro atípico puntual, no un patrón de rodilla estable. La señal de
`trunk_lean`, en cambio, mostraba algo distinto: casi simétrica en la primera mitad y
consistentemente volcada a la derecha en la segunda (sin cambiar de lado) — compatible con
una asimetría real que se acentúa con el cansancio, no con un giro raro. El chequeo de
"ambas mitades" descartaba las dos señales sin distinguir entre ellas.

### Intento 2 (adoptado): robustez a sacar el giro más influyente, por métrica

Script: `asymmetry_persistence_check_discarded_anyturn.py` (primer intento, descartado) y
`asymmetry_persistence_check_final.py` (versión adoptada). Definición operacional de "no
depende de un solo giro atípico": para cada métrica (`knee_flex`, `trunk_lean`) por
separado, se identifica el giro individual más influyente (el que más reduce o invierte la
diferencia al sacarlo) y se chequea si el lado favorecido se mantiene sin él. Solo las
métricas que sobreviven ese chequeo cuentan para decidir la severidad final.

**Primer intento probado y descartado**: exigir robustez a sacar **cualquier** giro (no
solo el más influyente) resultó demasiado estricto — hasta el `trunk_lean` de video17
(11/12 giros, la muestra más grande y menos sospechosa del dataset) fallaba ese chequeo en
algún giro puntual, porque con una diferencia chica (8.9%) cualquier perturbación menor
puede voltear cuál lado es mayor. No distinguía "frágil por poca diferencia real" de
"frágil por depender de 1 giro atípico" — se descartó por sobre-corregir.

**Resultado de la versión adoptada (leave-one-out del giro más influyente)**:

| Video | `knee_flex` sobrevive | `trunk_lean` sobrevive |
|---|---|---|
| video17 (11/12 giros) | No (pero diff ya era chico, 4.3%, irrelevante) | **Sí** |
| video1 (3/5 giros) | No | No |
| video2 (2/3 giros) | No | **No** |

**Hallazgo importante, no anticipado**: la re-verificación giro por giro (no solo por
mitades) mostró que el `trunk_lean` de video2 **tampoco** sobrevive el chequeo más
permisivo — remover el giro individual más influyente también invierte su dirección. La
caracterización inicial por mitades había sido optimista porque agregar 2-3 giros en un
bloque diluye el ruido; mirado giro por giro, ninguna de las dos métricas de video2 es
robusta, sin importar cuál de las dos definiciones de "persistencia" se use. Esto converge
exactamente con la condición 2: **con 5 giros totales (2 izq/3 der), no hay evidencia
estadística que sobreviva ningún chequeo razonable de robustez**, más allá de cómo se
defina "estable".

## Consecuencia aceptada: falso negativo conocido en video2

Con las 2 condiciones nuevas implementadas, `asimetria_izq_der` **deja de dispararse en
video2** — el único caso del dataset con una asimetría real confirmada por el usuario
(video propio, error técnico conocido). Esto se decidió **con el usuario, explícitamente**,
después de mostrarle que ninguna definición rigurosa de persistencia recupera el caso con
solo 5 giros: no es un defecto de diseño, es una limitación de datos (el video es
demasiado corto para que un chequeo automático lo confirme con confianza).

**Mitigación implementada** (decisión explícita del usuario): en vez de que el video quede
en silencio total sobre la asimetría, se agrega `asymmetry_note` — un campo nuevo en el
JSON de salida (y prependido al `summary`, mismo mecanismo que `discipline_note` en
`analysis_job.py`) que dice explícitamente "no hay suficientes giros de cada lado para
evaluar la asimetría con confianza", en vez de dejar que el silencio se lea como "sin
problema". Se dispara cuando cualquiera de los dos lados tiene menos de
`MIN_TURNS_FOR_ASYMMETRY` (5) giros.

## Implementación

`analyze_ski_video.py`:
- `MIN_TURNS_FOR_ASYMMETRY = 5` (antes 2).
- `_rel_diff`, `_metric_side_means`, `_metric_robust_to_outlier_turn`: helpers nuevos,
  reusados también por `instrument_video.py` (no se reimplementa la lógica en el reporte
  de debug).
- `detect_asymmetry`: ahora calcula `knee_diff`/`lean_diff` con su robustez cada uno, arma
  `diff` como el máximo **entre las métricas robustas únicamente** (una métrica no robusta
  no cuenta aunque su valor sea más grande), y solo entonces evalúa severidad.
- `build_asymmetry_note`: nueva función, llamada desde `analyze_video()`, agrega
  `asymmetry_note` al resultado.

`backend/app/analysis_job.py`: antepone `asymmetry_note` al `summary` persistido, mismo
mecanismo ya usado para `discipline_note` (sin migración nueva, mismo criterio que ya
estaba documentado ahí).

`instrument_video.py`: el diagnóstico de `asimetria_izq_der` ahora reusa
`_metric_robust_to_outlier_turn` de producción en vez de reimplementar el cálculo de
mitades (que ya no existe), y reporta `knee_diff`/`lean_diff`/robustez de cada uno, más el
motivo exacto de no-disparo en el mismo orden que evalúa `detect_asymmetry`. Se agregó
`MIN_TURNS_FOR_ASYMMETRY_DIAGNOSTIC = 2`, deliberadamente más bajo que el umbral de
producción, para seguir viendo los números de diagnóstico en videos que ya no alcanzan el
mínimo de producción (video1, video2) — sin esto, el reporte de debug se quedaría mudo
justo en los casos más interesantes de revisar.

## Resultado en los 4 videos del dataset (before/after)

| Video | Antes | Después | ¿Cambió? |
|---|---|---|---|
| video17 (sólido) | sin asimetría | sin asimetría | No — ya no disparaba, sigue sin disparar |
| video1 (mixto) | sin asimetría | sin asimetría + `asymmetry_note` (3/5 giros, insuficiente) | Parcial — mismo resultado, pero ahora explícito que no se pudo evaluar con confianza |
| video2 (errores conocidos) | `asimetria_izq_der` **alta** | sin asimetría + `asymmetry_note` (2/3 giros, insuficiente) | **Sí** — deja de marcar un error real conocido, mitigado con la nota explícita |
| video16 (casi sin datos) | sin asimetría | sin asimetría + `asymmetry_note` (0/1 giros, insuficiente) | Parcial — mismo resultado, ahora explícito |

`confidence_score` no cambia en ningún video (no depende de qué patrones disparan).

**Marca manual, punto 6 del sprint anterior ("no considerar exitoso solo porque aparecen
menos errores"):**
- video17: **igual** (ningún cambio de comportamiento).
- video1: **igual** (mismo resultado, ahora con contexto explícito).
- video2: **incierto, con riesgo real y reconocido** — no es "mejoró" (se pierde un
  patrón confirmado como real) ni "empeoró" en el sentido de agregar ruido; es un
  trade-off consciente y documentado: se exige más evidencia de la que este video en
  particular puede dar, y se comunica esa limitación en vez de fallar en silencio.
- video16: **igual** (mismo resultado, ahora con contexto explícito).

## Por qué no se resolvió "agresivamente" en ninguna dirección

No se relajaron las condiciones para forzar que video2 siguiera disparando (eso hubiera
sido ajustar el criterio para que el caso conocido "no deje de dispararse", exactamente lo
que el sprint anterior pidió evitar). Tampoco se ignoró el hallazgo de que el fix pierde un
caso real: se lo llevó al usuario con evidencia completa (tabla de leave-one-out por
métrica, no una intuición) y se decidió en conjunto aceptar el trade-off con mitigación
explícita, no en silencio. Queda documentado como limitación conocida, mismo criterio que
"no hay caso positivo confirmado de rotación excesiva" en el sprint anterior — es una
limitación del dataset (necesita un video con más giros por lado y una asimetría real
confirmada para validar mejor esta lógica), no una falla de diseño a resolver ahora.
