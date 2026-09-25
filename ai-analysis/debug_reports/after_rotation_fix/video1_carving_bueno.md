# Debug report — video1_carving_bueno

- Video: `C:/Users/santi/ski-app/backend/media/videos/1/39f865208d164135be348a94310a3a3e.mp4`
- Disciplina: `carving`
- Frames muestreados: 118 | válidos: 95 (80.5%) | fps efectivo: 7.48
- Giros detectados: 8
- **confidence_score: 64**

## Patrones

| Patrón | Disparó | Severidad | Detalle |
|---|---|---|---|
| `asimetria_izq_der` | No | — | value=0.0889, n_left=3, n_right=5, std_lean_left=9.17, std_lean_right=9.95, gap_to_baja=0.0311 |
| `rotacion_excesiva_tren_superior` | No | — | mean=9.04, std=23.12, proportion_over_baja=0.105, sustained_proportion_required=0.35 |
| `inconsistencia_entre_giros` | Sí | baja | cv=0.254, n_turns=8 |
| `perdida_de_balance` | Sí | baja |  |
| `peso_hacia_atras` | No | — | applicable=True |

## Giros

| # | dirección | inicio | fin | frames | max\|lean\| |
|---|---|---|---|---|---|
| 1 | derecha | 00:01.47 | 00:03.21 | 10 | 55.6 |
| 2 | izquierda | 00:03.34 | 00:04.68 | 11 | 43.2 |
| 3 | derecha | 00:04.95 | 00:06.02 | 9 | 33.2 |
| 4 | izquierda | 00:06.55 | 00:07.75 | 10 | 49.9 |
| 5 | derecha | 00:08.02 | 00:10.70 | 15 | 72.3 |
| 6 | derecha | 00:11.50 | 00:13.24 | 13 | 41.5 |
| 7 | izquierda | 00:13.37 | 00:14.30 | 8 | 33.7 |
| 8 | derecha | 00:14.57 | 00:15.64 | 9 | 45.6 |

## Frames guardados (10)

- `debug_reports\after_rotation_fix\frames\video1_carving_bueno\giro01_pico_derecha.jpg`
- `debug_reports\after_rotation_fix\frames\video1_carving_bueno\giro02_pico_izquierda.jpg`
- `debug_reports\after_rotation_fix\frames\video1_carving_bueno\giro03_pico_derecha.jpg`
- `debug_reports\after_rotation_fix\frames\video1_carving_bueno\giro04_pico_izquierda.jpg`
- `debug_reports\after_rotation_fix\frames\video1_carving_bueno\giro05_pico_derecha.jpg`
- `debug_reports\after_rotation_fix\frames\video1_carving_bueno\giro06_pico_derecha.jpg`
- `debug_reports\after_rotation_fix\frames\video1_carving_bueno\giro07_pico_izquierda.jpg`
- `debug_reports\after_rotation_fix\frames\video1_carving_bueno\giro08_pico_derecha.jpg`
- `debug_reports\after_rotation_fix\frames\video1_carving_bueno\rotacion_extremo.jpg`
- `debug_reports\after_rotation_fix\frames\video1_carving_bueno\peso_atras_extremo.jpg`