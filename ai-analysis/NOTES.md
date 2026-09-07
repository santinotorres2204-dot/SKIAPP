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
- **terrain_tag**: falta un campo para el tipo de terreno/pista (pista
  groomed vs fuera de pista, por ejemplo). Pendiente definir si aporta algo
  a las reglas heurísticas o si es solo metadata informativa.
- **ski vs snowboard**: el pipeline asume postura de ski (flexión de
  rodilla, giros alternados izquierda/derecha de cara a la pendiente).
  Snowboard tiene una biomecánica distinta (postura lateral, "giros" de
  canto), no evaluado ni calibrado todavía.
