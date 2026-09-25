# Revisión — `asimetria_izq_der` (sprint "confiabilidad de carving", punto 3)

**No se cambió `detect_asymmetry()` en este sprint** (instrucción explícita: "no
cambiarlo agresivamente todavía"). Este documento agrega el diagnóstico pedido y una
recomendación para decidir en un sprint aparte — con evidencia, no solo intuición.

## Estado después de los puntos 1 y 2 (importante antes de leer lo demás)

Video17 pasó de estar a **5.7%** del umbral "baja" (auditoría original, con el arranque
cerca del lift todavía contaminando el cálculo) a estar a **26.2%** (`gap_to_baja=0.0314`
sobre un umbral de 0.12) una vez aplicado el filtro de actividad del punto 2 — sin tocar
nada de la lógica de asimetría en sí. Buena parte de la urgencia que motivó este punto 3
ya se resolvió como efecto colateral de arreglar el punto 2.

## Diagnóstico extra agregado (instrumentación, no cambia el resultado)

`instrument_video.py` ahora reporta, para `asimetria_izq_der`: `diff_knee_pct` y
`diff_lean_pct` por separado (antes solo se veía el máximo de los dos), `cv_lean_left`/
`cv_lean_right` (variabilidad dentro de cada lado), y **`persistence_first_half`/
`persistence_second_half`** — la asimetría medida por separado en la primera y segunda
mitad de los giros, en orden temporal.

## Resultado en los 3 videos con suficientes giros por lado

| Video | ¿Dispara? | n_izq / n_der | diff (agregado) | 1ra mitad | 2da mitad |
|---|---|---|---|---|---|
| video17 (sólido) | No | 11 / 12 | 0.089 | 0.217 | **0.366** |
| video1 (mixto) | No | 3 / 5 | 0.089 | 0.188 | **0.541** |
| video2 (errores conocidos) | **Sí, alta** | **2 / 3** | 0.779 | 0.018 | **0.423** |

## Hallazgo 1 — la diferencia NO es estable en ninguno de los 3 videos

En los tres casos la asimetría de la segunda mitad es notablemente mayor que la de la
primera — en video2 la diferencia casi no existe en la primera mitad (0.018, prácticamente
cero) y se dispara en la segunda (0.423). El valor agregado de todo el video esconde esto
por completo. Con solo 3 videos no alcanza para afirmar que esto sea un patrón general
(¿fatiga? ¿la sesión se vuelve más dinámica con el tiempo? ¿es ruido con pocos giros?) —
pero en ninguno de los 3 casos la asimetría se ve "estable", que es justo lo que el
criterio propuesto por el sprint pide exigir.

## Hallazgo 2 — el disparo "alta" de video2 descansa en muy poca evidencia

`n_left=2, n_right=3` — apenas por encima del mínimo (`MIN_TURNS_FOR_ASYMMETRY=2`). El
77.9% de diferencia viene de `knee_flex`, no de `trunk_lean` (que da un 6.6%, mucho más
moderado) — con 2 giros de un lado, un solo giro atípico puede mover el promedio
enormemente. Esto no significa que la asimetría de video2 sea falsa (es un video con
errores conocidos, y el founder puede tener contexto real de que ese esquiador
efectivamente asimetriza) — significa que, tal como está calculado hoy, **no hay forma
de distinguir desde los datos solos** si es una asimetría real y consistente o el
resultado de tener muy pocos giros de un lado.

## Evaluación del criterio propuesto ("diferencia suficiente + suficientes giros + diferencia estable")

Con la evidencia de arriba, el criterio conceptual parece bien encaminado — los tres
componentes atacan un problema real y medido:
- **Diferencia suficiente**: ya existe (el threshold actual).
- **Suficientes giros**: `MIN_TURNS_FOR_ASYMMETRY=2` es bajo — video2 dispara "alta"
  con el mínimo absoluto. Subir este mínimo (ej. a 5) es un cambio acotado y fácil de
  justificar con lo medido acá.
- **Diferencia estable**: ninguno de los 3 videos la tiene, incluido el que hoy dispara
  "alta" — agregar este requisito cambiaría el resultado de video2, que es justo el caso
  que usamos como referencia de "esto sí tiene que seguir marcando".

## Por qué no lo implemento ahora (además de la instrucción explícita)

Agregar el requisito de estabilidad **downgradearía la severidad de video2** — el único
caso positivo confirmado que tenemos. Antes de tocar eso hace falta algo que este sprint
no tiene: confirmación de dominio (¿el founder puede confirmar si la asimetría de ese
esquiador es efectivamente un patrón sostenido de toda la sesión, o se concentra en un
tramo puntual?). Cambiarlo sin esa confirmación arriesga exactamente lo que pide evitar
el criterio de éxito general del sprint: "no perder problemas reales" a cambio de menos
falsos positivos.

## Recomendación para el próximo sprint (no implementada)

1. Subir `MIN_TURNS_FOR_ASYMMETRY` de 2 a un valor mayor (candidato: 5) — cambio acotado,
   bien justificado por el caso de video2 (2 vs 3 giros es insuficiente para una
   severidad "alta").
2. Evaluar agregar un chequeo de persistencia (ej. dividir en mitades o en una ventana
   móvil, como el diagnóstico ya agregado) como **requisito adicional para severidad
   "alta"/"media"** específicamente, no necesariamente para "baja" — permitiendo que una
   asimetría chica y estable siga contando como señal preliminar suave, mientras que una
   severidad fuerte exige evidencia más sólida.
3. Antes de aplicar cualquiera de los dos, confirmar con el founder si la asimetría
   conocida de video2 es consistente durante toda la sesión o concentrada en un tramo —
   esa respuesta determina si el requisito de estabilidad es correcto o si suprimiría un
   problema real.
