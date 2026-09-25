# Comparación before/after — sprint "confiabilidad de carving"

Dataset: 4 videos de carving ya existentes en la base (`docs/baseline-passport.md`-style,
mismo criterio de mantener el mismo set durante todo el sprint). "Antes" = comportamiento
de producción previo a este sprint (capturado en `debug_reports/baseline/` para
video17, y directamente desde la base de datos para 1/2/16 — resultados ya guardados por
el pipeline real, no re-derivados). "Después" = `debug_reports/after_activity_filter/`
(rotación arreglada + filtro de actividad aplicado, los dos cambios de código de este
sprint).

## video17_influencer — esquiador técnicamente sólido

| | Antes | Después |
|---|---|---|
| Giros detectados | 27 | 27 (23 cuentan para los patrones tras el filtro) |
| confidence_score | 97 | 93 |
| Patrones | `rotacion_excesiva_tren_superior` (baja), `inconsistencia_entre_giros` (baja) | **(ninguno)** |

**Motivo de cada cambio**: rotación — geometría (x,z) reemplazada por (x,y), el outlier
que la disparaba tenía landmarks mal ubicados (confirmado visualmente en la auditoría).
Inconsistencia — dejó de dispararse al excluir los 4 giros del arranque cerca del lift
del cálculo de varianza entre giros (esos 4 giros de baja intensidad eran justamente los
que inflaban la varianza).

**Marca manual: MEJORÓ.** Coincide con la técnica visualmente sólida del video — ya no
hay ningún patrón contaminado por ruido de landmark o por actividad no relevante.

## video1_carving_bueno — carving mixto, más giros

| | Antes | Después |
|---|---|---|
| Giros detectados | 8 | 8 (8 válidos, el filtro descartó solo 2 frames iniciales sin actividad real que filtrar) |
| confidence_score | 64 | 64 |
| Patrones | `perdida_de_balance` (baja), `inconsistencia_entre_giros` (baja) | `perdida_de_balance` (baja), `inconsistencia_entre_giros` (baja) |

**Marca manual: IGUAL.** Sin cambios — este video no tenía ni el problema de rotación ni
un tramo de arranque significativo que filtrar. Confirma que los dos fixes son
quirúrgicos, no efectos colaterales sobre videos sin el problema original.

## video2_errores_conocidos — con errores reales conocidos

| | Antes | Después |
|---|---|---|
| Giros detectados | 5 | 5 (5 válidos, filtro descartó 1 frame) |
| confidence_score | 38 | 37 |
| Patrones | `asimetria_izq_der` (**alta**), `perdida_de_balance` (media), `inconsistencia_entre_giros` (baja) | `asimetria_izq_der` (**alta**), `perdida_de_balance` (media), `inconsistencia_entre_giros` (baja) |

**Marca manual: IGUAL.** Los 3 patrones conocidos siguen exactamente igual — **este es el
resultado más importante de todo el sprint en términos de "no rompimos nada"**: el video
con problemas reales confirmados sigue marcándolos con la misma severidad, pese a los dos
cambios de lógica. (Nota aparte, documentada en `asymmetry-review.md`: la asimetría "alta"
de este video descansa en solo 2 vs 3 giros — se deja señalado para el próximo sprint, no
se tocó acá.)

## video16_malo_corto — video corto/difícil, casi sin datos

| | Antes | Después |
|---|---|---|
| Giros detectados | 1 | 1 (1 válido, filtro no descartó nada) |
| confidence_score | 5 | 5 |
| Patrones | (ninguno — confianza insuficiente) | (ninguno) |

**Marca manual: IGUAL.** Ya era un caso degenerado (muy pocos frames válidos); ninguno de
los dos fixes tenía margen para cambiar algo acá, y efectivamente no cambió nada.

## Resumen

| Video | Mejoró | Igual | Empeoró | Incierto |
|---|---|---|---|---|
| video17 (sólido) | ✅ | | | |
| video1 (mixto) | | ✅ | | |
| video2 (errores conocidos) | | ✅ | | |
| video16 (malo/corto) | | ✅ | | |

**Ningún video empeoró.** El único cambio de comportamiento ocurrió exactamente en el
video que motivó la auditoría original, y fue en la dirección esperada (menos ruido, sin
perder los patrones reales de los otros 3 videos). Esto satisface el criterio explícito
del sprint de no medir éxito solo por "menos errores aparecen" — se verificó
específicamente que el video con problemas reales conocidos los siga señalando.
