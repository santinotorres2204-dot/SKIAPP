# Debug report — video16_malo_corto

- Video: `C:/Users/santi/ski-app/backend/media/videos/1/1783043e34d74c4dafd21f4f81eb1dfe.mp4`
- Disciplina: `carving`
- Frames muestreados: 518 | válidos: 9 (1.7%) | fps efectivo: 7.5
- Giros detectados: 1
- Filtro de actividad válida: descarta 0 frames iniciales (arranca en t=1.87s) → quedan 1 giros / 9 frames para los patrones
- **confidence_score: 5**

## Patrones

| Patrón | Disparó | Severidad | Detalle |
|---|---|---|---|
| `asimetria_izq_der` | No | — | reason=insuficientes giros (izq=0, der=1) |
| `rotacion_excesiva_tren_superior` | No | — | mean=10.43, std=8.12, proportion_over_baja=0.333, sustained_proportion_required=0.35 |
| `inconsistencia_entre_giros` | No | — | reason=insuficientes giros (1) |
| `perdida_de_balance` | No | — |  |
| `peso_hacia_atras` | No | — | applicable=True |

## Giros

| # | dirección | inicio | fin | frames | max\|lean\| |
|---|---|---|---|---|---|
| 1 | derecha | 00:02.27 | 00:15.21 | 6 | 44.5 |

## Frames guardados (0)
