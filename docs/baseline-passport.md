# Baseline — Sprint Passport (perfil de usuario)

Estado de referencia antes de tocar `/passport/{id}`. Capturado el 2026-09-24 sobre `master` (commit `2d12b58`, ya con el sprint de Hero cerrado), usuario de prueba `id=1` (Santino — es el usuario con más datos cargados de los dos que existen en la base: tiene viajes, videos, trick cards, ski card, achievements, planes de entrenamiento, physical assessment y season review; el único que le falta son Freeride Runs, y ningún usuario existente tiene datos ahí — la captura documenta ese estado vacío tal cual está, sin inventar datos).

## Capturas

Todas en `docs/baseline-passport/`. Nota técnica: las versiones "full" están capturadas con una neutralización puntual de `background-attachment:fixed` en `body` (solo para la captura, no toca el sitio real) — sin eso, la captura full-page de Playwright corta el contenido y lo reemplaza por una franja en blanco a partir de cierta altura (mismo artefacto ya documentado en `docs/hero-sprint-cierre.md` para la home, pero ahí no hacía falta corregirlo porque no afectaba la comparación; acá sí hacía falta porque se necesita ver el contenido real).

### Mobile (390px)
- `passport-mobile-viewport.png` — primer fold, tal como carga la página (acordeones cerrados).
- `passport-mobile-closed-full.png` — página completa con todos los acordeones cerrados (lista de secciones).
- `passport-mobile-open-full.png` — página completa con **todos** los acordeones abiertos (Historial de viajes, Mis videos, Trick Cards, Freeride Runs, Ski Card, Achievements, Planes de entrenamiento, Physical Assessment, Season Review) — el estado real de todo el contenido.

### Desktop (1440px)
- `passport-desktop-viewport.png` — primer fold.
- `passport-desktop-closed-full.png` — página completa, acordeones cerrados.
- `passport-desktop-open-full.png` — página completa, todos los acordeones abiertos.

## Ski Card — foco especial de este sprint

Hoy la Ski Card es una tabla dentro de uno de los acordeones (`Disciplina | Rating | Confidence score | Verificado por coach`), alimentada por el modelo `SkiRating` (mismo dato que ya se resume arriba, en la franja oscura del hero, como "Rating principal"). Se va a rediseñar como una carta vertical tipo "carta de jugador" — foto/avatar arriba como elemento protagonista, rating general destacado, disciplinas como stats secundarios debajo.

Puntos a resolver en Fase 1 (no ahora): no existe ningún asset de avatar/silueta genérica en `static/images/` todavía — el resto del sitio usa SVGs inline para íconos (ver `feature-card--sign` en la home), así que probablemente el placeholder de foto siga ese mismo patrón en vez de sumar un archivo de imagen nuevo, pero es una decisión de Fase 1, no algo ya resuelto acá.

## Restricciones para este sprint

1. **NO TOCAR**: home ("/"), register, admin, ni ninguna otra pantalla — solo Passport (`/passport/{id}`).
2. **NO TOCAR** backend, base de datos, ni endpoints — 100% frontend.
3. **NO cambiar** la paleta base ni la tipografía.
4. **NO migrar** a React, **no WebGL**.
5. **NO romper** el fix de `overflow-x: clip` ni el sistema `.reveal` existente.
6. **Mantener consistencia** con el patrón ya establecido en el Hero de la home (capas de profundidad, uso acotado del naranja, tokens de contraste `--on-dark-secondary`) — este sprint debe sentirse como continuación del mismo sistema, no algo nuevo.
7. **Mobile-first**, no romper ningún breakpoint responsive ya existente.
8. **Ski Card**: rediseño 100% de layout/composición visual sobre el dato que ya existe (`SkiRating` — mismo dato que hoy alimenta la tabla del acordeón y el resumen del hero). Usar una imagen genérica o ícono/silueta ya disponible como placeholder de foto — **NO** agregar upload de foto propia del usuario (requiere backend nuevo, fuera de alcance).
9. **NO incluir** ningún mecanismo de compartir la Ski Card ni de comparación/competencia con otros usuarios — es una funcionalidad social aparte, a diseñar por separado más adelante.

No hay diseño ni implementación todavía — este documento es solo el punto de partida.
