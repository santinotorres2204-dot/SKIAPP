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

## Pendientes / limitaciones conocidas para revisar más adelante

- **Park necesita lógica de análisis distinta a la de giros.** El pipeline
  actual (`segment_turns`, `detect_asymmetry`, `detect_inconsistency`) está
  calibrado para disciplinas con giros alternados (carving, freeride,
  all_mountain). Un salto de park no genera esa secuencia de giros, así que
  aunque la pose se trackee perfectamente esos patrones no van a disparar.
  Falta definir qué "patrones de screening" tienen sentido para park (ej.
  detección de caída al aterrizar, simetría en el take-off) antes de poder
  dar un análisis útil para esa disciplina.
- **terrain_tag**: falta un campo para el tipo de terreno/pista (pista
  groomed vs fuera de pista, por ejemplo). Pendiente definir si aporta algo
  a las reglas heurísticas o si es solo metadata informativa.
- **ski vs snowboard**: el pipeline asume postura de ski (flexión de
  rodilla, giros alternados izquierda/derecha de cara a la pendiente).
  Snowboard tiene una biomecánica distinta (postura lateral, "giros" de
  canto), no evaluado ni calibrado todavía.
