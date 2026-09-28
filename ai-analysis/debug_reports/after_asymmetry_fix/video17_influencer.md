# Debug report — video17_influencer

- Video: `C:/Users/santi/ski-app/backend/media/videos/1/04f639126caf45d89f80f3d5418b20cd.mov`
- Disciplina: `carving`
- Frames muestreados: 258 | válidos: 238 (92.2%) | fps efectivo: 8.01
- Giros detectados: 27
- Filtro de actividad válida: descarta 27 frames iniciales (arranca en t=3.37s) → quedan 23 giros / 211 frames para los patrones
- **confidence_score: 93**

## Patrones

| Patrón | Disparó | Severidad | Detalle |
|---|---|---|---|
| `asimetria_izq_der` | No | — | reason=diff robusto 0.0886 por debajo del umbral baja (0.12), value=0.0886, knee_diff=0.0429, knee_diff_robust=False, lean_diff=0.0886, lean_diff_robust=True, n_left=11, n_right=12, min_turns_required=5 |
| `rotacion_excesiva_tren_superior` | No | — | mean=5.51, std=8.22, proportion_over_baja=0.071, sustained_proportion_required=0.35 |
| `inconsistencia_entre_giros` | No | — | cv=0.2348, n_turns=23 |
| `perdida_de_balance` | No | — |  |
| `peso_hacia_atras` | No | — | applicable=True |

## Giros

| # | dirección | inicio | fin | frames | max\|lean\| |
|---|---|---|---|---|---|
| 1 | derecha | 00:00.00 | 00:01.00 | 9 | 17.6 |
| 2 | izquierda | 00:01.37 | 00:01.62 | 3 | 15.0 |
| 3 | derecha | 00:02.00 | 00:02.37 | 4 | 9.4 |
| 4 | izquierda | 00:02.75 | 00:03.12 | 4 | 8.7 |
| 5 | derecha | 00:03.37 | 00:08.86 | 32 | 45.8 |
| 6 | izquierda | 00:08.99 | 00:10.23 | 11 | 51.4 |
| 7 | derecha | 00:10.36 | 00:11.11 | 7 | 37.6 |
| 8 | izquierda | 00:11.23 | 00:12.23 | 9 | 42.9 |
| 9 | derecha | 00:12.48 | 00:12.98 | 5 | 29.5 |
| 10 | izquierda | 00:13.11 | 00:14.10 | 9 | 42.5 |
| 11 | derecha | 00:14.23 | 00:14.85 | 6 | 34.4 |
| 12 | izquierda | 00:14.98 | 00:15.85 | 8 | 43.2 |
| 13 | derecha | 00:15.98 | 00:16.72 | 6 | 46.0 |
| 14 | izquierda | 00:16.85 | 00:17.72 | 8 | 41.2 |
| 15 | derecha | 00:17.85 | 00:18.97 | 10 | 44.4 |
| 16 | izquierda | 00:19.10 | 00:19.47 | 4 | 23.9 |
| 17 | derecha | 00:19.72 | 00:20.97 | 11 | 52.5 |
| 18 | derecha | 00:21.84 | 00:22.97 | 10 | 47.4 |
| 19 | izquierda | 00:23.22 | 00:23.46 | 3 | 17.5 |
| 20 | derecha | 00:23.71 | 00:24.96 | 11 | 42.0 |
| 21 | izquierda | 00:25.09 | 00:25.71 | 6 | 32.8 |
| 22 | derecha | 00:25.96 | 00:26.96 | 6 | 36.6 |
| 23 | izquierda | 00:27.08 | 00:27.71 | 6 | 31.7 |
| 24 | derecha | 00:27.83 | 00:29.08 | 11 | 48.4 |
| 25 | izquierda | 00:29.21 | 00:29.58 | 4 | 22.8 |
| 26 | derecha | 00:29.83 | 00:30.83 | 9 | 48.1 |
| 27 | izquierda | 00:31.08 | 00:31.70 | 6 | 36.1 |

## Frames guardados (0)
