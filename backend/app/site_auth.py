"""Contrasena compartida para todo el sitio (HTTP Basic Auth).

Proteccion minima para una beta cerrada: no hay cuentas ni sesiones todavia,
asi que sin esto cualquiera con la URL ve el admin y el passport de todos.
NO separa usuarios entre si -- quien tiene la clave ve todo.

Middleware ASGI puro (no BaseHTTPMiddleware) para no meterse con el cuerpo
de las subidas de video. Va por fuera de los mounts, asi cubre tambien
/static y /media.
"""

from __future__ import annotations

import base64
import binascii
import json
import secrets
from pathlib import Path

from starlette.types import ASGIApp, Receive, Scope, Send

# Health checks de Railway y recursos que el navegador pide SIN credenciales:
# el manifest (<link rel="manifest"> sin crossorigin="use-credentials") y los
# iconos que referencia, mas el service worker y el apple-touch-icon. Si
# quedan detras del 401, se rompe la instalacion de la PWA. Ninguno expone
# datos de usuarios.
_ALWAYS_PUBLIC = {
    "/health",
    "/health/db",
    "/sw.js",
    "/static/manifest.json",
    "/static/images/apple-touch-icon.png",
}


def public_paths(manifest_path: Path) -> frozenset[str]:
    """Rutas sin auth: las fijas mas los iconos declarados en el manifest
    (asi un icono nuevo no queda bloqueado por olvido)."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    icons = {icon["src"] for icon in manifest.get("icons", []) if icon.get("src", "").startswith("/")}
    return frozenset(_ALWAYS_PUBLIC | icons)


class SiteBasicAuthMiddleware:
    def __init__(self, app: ASGIApp, *, password: str, username: str = "", public: frozenset[str] = frozenset()) -> None:
        self.app = app
        self._password = password.encode()
        self._username = username.encode()
        self._public = public

    def _authorized(self, scope: Scope) -> bool:
        header = next((v for k, v in scope.get("headers", []) if k == b"authorization"), None)
        if header is None or not header[:6].lower() == b"basic ":
            return False
        try:
            decoded = base64.b64decode(header[6:].strip(), validate=True)
        except (binascii.Error, ValueError):
            return False
        user, sep, password = decoded.partition(b":")
        if not sep:
            return False
        # compare_digest siempre, aunque el usuario no se valide, para no
        # filtrar por tiempo de respuesta.
        password_ok = secrets.compare_digest(password, self._password)
        user_ok = secrets.compare_digest(user, self._username) if self._username else True
        return password_ok and user_ok

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket") or scope["path"] in self._public or self._authorized(scope):
            await self.app(scope, receive, send)
            return

        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return

        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"www-authenticate", b'Basic realm="Ski App", charset="UTF-8"'),
                    (b"content-type", b"text/plain; charset=utf-8"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": "Se necesita la contraseña del sitio.".encode()})
