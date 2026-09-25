# Debug report — video1_carving_bueno

- Video: `C:/Users/santi/ski-app/backend/media/videos/1/39f865208d164135be348a94310a3a3e.mp4`
- Disciplina: `carving`
- Frames muestreados: 118 | válidos: 95 (80.5%) | fps efectivo: 7.48
- Giros detectados: 8
- Filtro de actividad válida: descarta 2 frames iniciales (arranca en t=1.47s) → quedan 8 giros / 93 frames para los patrones
- **confidence_score: 64**

## Patrones

| Patrón | Disparó | Severidad | Detalle |
|---|---|---|---|
| `asimetria_izq_der` | No | — | value=0.0889, diff_knee_pct=8.89, diff_lean_pct=5.8, n_left=3, n_right=5, std_lean_left=9.17, std_lean_right=9.95, cv_lean_left=0.3006, cv_lean_right=0.3078, persistence_first_half=0.1877, persistence_second_half=0.5413, gap_to_baja=0.0311 |
| `rotacion_excesiva_tren_superior` | No | — | mean=9.02, std=23.36, proportion_over_baja=0.108, sustained_proportion_required=0.35 |
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

## Frames guardados (0)
