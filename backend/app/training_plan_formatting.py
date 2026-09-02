from __future__ import annotations

import re

# Coincide con las lineas de encabezado de bloque que pide prompt_builder.py
# ("Bloque 1 -- Fuerza unilateral (...)") en el prompt que se copia a una IA.
_BLOCK_HEADING_RE = re.compile(r"^bloque\s+\d+\b", re.IGNORECASE)


def parse_training_plan_blocks(content: str) -> list[dict]:
    """Divide el texto libre de un training plan en bloques con titulo +
    lista de items, a partir de las lineas 'Bloque N -- ...'.

    Es un parseo heuristico sobre texto libre pegado a mano por el coach --
    si el contenido no sigue ese formato, todo cae en un unico bloque sin
    titulo (mejor que nada, nunca un error).
    """
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.strip() for line in normalized.split("\n")]
    lines = [line for line in lines if line]

    # "lines", no "items": un dict con clave "items" choca con el metodo
    # dict.items() cuando Jinja resuelve el atributo (bloque.items devuelve
    # el metodo, no la lista) -- costo real, no cosmetico.
    blocks: list[dict] = [{"title": None, "lines": []}]
    for line in lines:
        if _BLOCK_HEADING_RE.match(line):
            blocks.append({"title": line, "lines": []})
        else:
            blocks[-1]["lines"].append(line)

    return [b for b in blocks if b["title"] or b["lines"]]
