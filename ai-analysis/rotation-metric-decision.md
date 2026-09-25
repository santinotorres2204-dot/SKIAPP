# Decisión — `rotacion_excesiva_tren_superior` (sprint "confiabilidad de carving", punto 1)

Script de comparación: `rotation_metric_comparison.py`. Datos crudos por video en
`rotation_comparisons/*.json`. Este documento es el registro de la decisión, no solo el
resultado final — el pedido explícito fue "primero hay que saber si la métrica nueva
representa mejor lo que vemos", así que documento la comparación completa antes de la
elección.

## Problema (de `audit-carving-video.md`)

`rotation_diff` se calculaba con `arctan2(vec[2], vec[0])` — plano (x, z) de MediaPipe,
donde z es profundidad relativa. Se disparaba (severidad "baja") con la media de todo
el video en 26.02°, arrastrada por outliers de hasta 152.5°. Evidencia visual: el frame
del outlier extremo tenía el esqueleto dibujado claramente mal ubicado (no correspondía
a la postura real de la foto).

## Candidatos comparados

| | Geometría | Qué mide realmente |
|---|---|---|
| **A — actual** | `arctan2(z, x)` | Intento de rotación axial 3D, sobre la coordenada menos confiable de MediaPipe |
| **B — XY simple** | `arctan2(y, x)` | Diferencial de inclinación entre línea de hombros y línea de cadera, en el plano de la imagen |
| **C — XY relativo a dirección de desplazamiento** | ángulo de cada línea respecto al vector de movimiento del centro de masa entre frames | Mismo principio que ya usa `analyze_snowboard_video.py` (`compute_edge_orientation_series`) para su proxy de orientación de canto |

**Caveat explícito de B y C** (no es gratis dejar Z): una torsión real del tronco
alrededor de su eje vertical es, por definición, invisible en 2D puro sin profundidad.
Lo que B/C miden es un proxy relacionado (diferencial de inclinación), no rotación
axial en sentido estricto — más ruda, pero anclada en coordenadas confiables.

## Resultado — video 17 (el "influencer", técnica sólida, 238 frames válidos)

| Candidato | mean | std | median | max | % frames > 20° |
|---|---|---|---|---|---|
| A (Z, actual) | 26.02° | 23.69° | 20.22° | **152.45°** | 50.8% |
| B (XY simple) | **5.22°** | 7.83° | 3.22° | 87.77° | 3.4% |
| C (XY dir. desplazamiento) | 5.23° | 7.84° | 3.21° | 87.77° | 3.4% |

**B y C dan resultados prácticamente idénticos** (diferencia de centésimas). C agrega
complejidad real (necesita el frame anterior, manejar el caso sin desplazamiento
significativo — 1 frame de 238 sin señal en este video) sin ninguna ganancia medible
sobre B en este dataset. Se descarta C por ahora, no porque esté mal sino porque no se
justifica la complejidad extra todavía — queda documentado como alternativa válida si
en el futuro aparece un caso donde B falle y C no.

**Validación visual del top outlier de B** (idx99, t=00:13.98s, 87.8°,
`rotation_comparisons/xy_outlier_idx99_t13.98s.jpg`): a diferencia del outlier de A, acá
el esqueleto se ve razonablemente bien ubicado — el esquiador está en una flexión
profunda con separación real de hombros/cadera visible (contra-rotación, un elemento
técnico legítimo del carving dinámico). El valor puede seguir estando algo inflado por
foreshortening de cámara, pero ya no hay evidencia de landmark roto como en A.

## Suavizado temporal (ventana 5 frames, misma que ya usa `trunk_lean`)

| Candidato | mean sin suavizar | mean suavizado |
|---|---|---|
| A | 26.02° | 14.23° (ya no dispararía con el umbral viejo) |
| B | 5.22° | 3.16° |

El suavizado por sí solo también "arregla" el falso positivo de A — pero es tapar el
síntoma (promediar el ruido) sin sacar la fuente (seguir dependiendo de Z). Se decidió
**no** adoptar suavizado temporal como parte de la solución: la exigencia de sostenido
(ver abajo) ya cumple el mismo rol de "no dejar que 1-2 frames ruidosos disparen el
patrón" sin además diluir eventos reales rápidos (cambios de canto), y es una
transformación menos sobre la señal.

## Agregación: de "promedio de todo el video" a "sostenido" (mismo criterio que `peso_hacia_atras`)

El problema de fondo del formato viejo no era solo la geometría: un promedio de video
entero es frágil — unos pocos frames extremos alcanzan para arrastrarlo. Se reemplaza
por el mismo mecanismo que ya usa `detect_weight_position`: umbral por-frame +
proporción mínima sostenida (`SUSTAINED_ROTATION_PROPORTION = 0.35`, mismo valor que
`SUSTAINED_BACKWARD_PROPORTION` — no hay razón para que sean distintos, ambos existen
para el mismo propósito).

## Umbrales nuevos — por qué 15/25/35 y no otra cosa

Al cambiar la fórmula, el valor típico de la métrica bajó (media 26°→5° en el video de
referencia). Mantener los umbrales viejos (20/30/40) con la fórmula nueva haría que el
patrón prácticamente nunca dispare — no es "no tocar el threshold porque sí", es que
los umbrales viejos estaban calibrados (informalmente) para la escala de la fórmula
vieja, y esa escala cambió por diseño.

Medido en los 4 videos de carving del dataset (media de B, `% frames > 20°`):

| Video | media B | % frames > 20° |
|---|---|---|
| video17 (sólido) | 5.22° | 3.4% |
| video1 (mixto) | 9.04° | 6.3% |
| video2 (errores conocidos) | 4.05° | 5.4% |
| video16 (casi sin datos, n=9) | 10.43° | 22.2% (muestra demasiado chica para confiar) |

Ningún video del dataset tiene rotación excesiva real conocida — mismo caveat que ya
tiene `peso_hacia_atras` en `NOTES.md` (sin caso positivo confirmado para validar). Los
umbrales **15/25/35 por-frame + 35% sostenido** son un placeholder razonado (dejan
margen sobre el "piso de ruido" observado — ninguno de los 4 videos se acerca a 35% de
frames por encima de 15°, mucho menos de 25-35°) pero **sin calibrar con rigor
estadístico** — se documenta así explícitamente, no se pretende más precisión de la que
hay evidencia para sostener.

## Chequeo de generalización en los otros 3 videos (no es una confirmación completa)

Los 3 videos restantes sí tienen ruido real de Z, no solo video17: video1 tiene un pico de
100.2° (t=4.01s), video16 uno de 71.7° (t=2.40s), video2 hasta 38.4°. Pero **ninguno
cruzaba el umbral de disparo con la fórmula vieja** — la media de video completo daba
13.48°/10.93°/15.09°, todos por debajo del umbral (20°) que hacía falta para disparar.
Es decir, esos 3 videos nunca tuvieron el bug de producción, con ninguna de las dos
fórmulas.

Además, la fórmula nueva **no reduce el ruido de forma pareja**: en video1 y video2 el
pico máximo es más alto con (x,y) que con (x,z) (video1: 100.2°→156.2°; video2:
38.4°→58.7°) — solo en video16 y video17 baja. No cambia ningún resultado (ninguno se
acerca al umbral en ninguna versión), pero significa que **no hay evidencia de que la
fórmula nueva reduzca el ruido de landmarks de forma general** — solo hay evidencia de
que corrigió el caso puntual que estaba fallando (video17) sin romper los otros 3. No es
lo mismo que "el fix generaliza": es "el fix no tiene efectos colaterales conocidos".

## Decisión final

- Geometría: **B (x, y)** — reemplaza a A en `compute_frame_metrics`.
- Agregación: **sostenido** (umbral por-frame + proporción mínima 35%) — reemplaza al
  promedio de video entero en `detect_rotation_excessive`.
- Umbrales: **15/25/35°** por-frame — placeholder razonado, no calibrado.
- C y el suavizado temporal: evaluados, no adoptados — documentados como alternativas
  descartadas con su razón, no simplemente omitidos.

## Resultado en el video 17 después del cambio

`rotacion_excesiva_tren_superior` **ya no dispara** (antes: baja). El único patrón que
queda es `inconsistencia_entre_giros` (baja) — exactamente el resultado esperado por el
criterio de éxito del sprint ("no debería dispararse por un landmark evidentemente
defectuoso"). Falta todavía el punto 5 del criterio de éxito ("en videos donde
realmente haya rotación excesiva conocida, la métrica nueva debería seguir siendo capaz
de detectarla") — **no se pudo validar el caso positivo** por falta de un video de
referencia con ese problema confirmado; queda como limitación abierta, igual que ya
está documentada para `peso_hacia_atras`.
