# Debug report — video2_errores_conocidos

- Video: `C:/Users/santi/ski-app/backend/media/videos/1/12eb1401de9b4c27b1d63712a46fdcd3.mp4`
- Disciplina: `carving`
- Frames muestreados: 84 | válidos: 37 (44.0%) | fps efectivo: 7.52
- Giros detectados: 5
- Filtro de actividad válida: descarta 1 frames iniciales (arranca en t=5.45s) → quedan 5 giros / 36 frames para los patrones
- **confidence_score: 37**

## Patrones

| Patrón | Disparó | Severidad | Detalle |
|---|---|---|---|
| `asimetria_izq_der` | No | — | reason=sample size insuficiente para produccion (izq=2, der=3, minimo=5), value=0.7791, knee_diff=0.7791, knee_diff_robust=False, lean_diff=0.0664, lean_diff_robust=False, n_left=2, n_right=3, min_turns_required=5 |
| `rotacion_excesiva_tren_superior` | No | — | mean=4.13, std=10.05, proportion_over_baja=0.056, sustained_proportion_required=0.35 |
| `inconsistencia_entre_giros` | Sí | baja | cv=0.2545, n_turns=5 |
| `perdida_de_balance` | Sí | media |  |
| `peso_hacia_atras` | No | — | applicable=True |

## Giros

| # | dirección | inicio | fin | frames | max\|lean\| |
|---|---|---|---|---|---|
| 1 | derecha | 00:05.45 | 00:05.99 | 5 | 27.8 |
| 2 | izquierda | 00:06.25 | 00:07.32 | 9 | 30.0 |
| 3 | derecha | 00:07.58 | 00:08.91 | 9 | 24.5 |
| 4 | izquierda | 00:09.31 | 00:09.84 | 5 | 12.5 |
| 5 | derecha | 00:10.64 | 00:11.04 | 3 | 24.2 |

## Frames guardados (0)
