"""
Authentication / authorization ASGI middleware.

Implemented as raw ASGI (like ``server/utils/ws_security.py``) so that it
guards WebSocket handshakes as well as HTTP requests: Starlette's
``@app.middleware("http")`` never runs for WebSockets.
"""

import json
import logging
from collections.abc import Awaitable, Callable, MutableMapping
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import urlparse

from .config import AuthSettings, get_auth_settings
from .policy import SAFE_METHODS, Access, required_access
from .roles import Role, RolesConfig, get_roles_config
from .session import SESSION_COOKIE, AuthUser, get_session_store

logger = logging.getLogger(__name__)

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_FORBIDDEN = 4403

_DEFAULT_PORTS = {"http": "80", "https": "443", "ws": "80", "wss": "443"}


def get_cookie(scope: Scope, name: str) -> str | None:
    for header, value in scope.get("headers", []):
        if header == b"cookie":
            cookie: SimpleCookie = SimpleCookie()
            try:
                cookie.load(value.decode("latin-1"))
            except Exception:
                continue
            if name in cookie:
                return cookie[name].value
    return None


def _header(scope: Scope, name: bytes) -> str | None:
    for header, value in scope.get("headers", []):
        if header == name:
            return str(value.decode("latin-1"))
    return None


def _normalize_netloc(scheme: str, netloc: str) -> str:
    netloc = netloc.lower()
    default = _DEFAULT_PORTS.get(scheme)
    if default and netloc.endswith(f":{default}"):
        netloc = netloc[: -len(default) - 1]
    return netloc


def is_same_origin_request(origin: str | None, host: str | None, trusted_origins: tuple[str, ...] = ()) -> bool:
    """Check a browser ``Origin`` against the server the request was sent to.

    Unlike the hostname-only WebSocket check, this compares host *and port*:
    generated apps' dev servers run on the same machine (same site, so the
    session cookie is sent) and must not be able to drive the API.
    Requests without an Origin header (non-browser clients) pass.
    """
    if not origin:
        return True
    origin = origin.rstrip("/").lower()
    if origin in trusted_origins:
        return True
    if not host:
        return False
    try:
        parsed = urlparse(origin)
    except ValueError:
        return False
    if not parsed.scheme or not parsed.netloc:
        return False
    return _normalize_netloc(parsed.scheme, parsed.netloc) == _normalize_netloc(
        "https" if parsed.scheme in ("https", "wss") else "http", host
    )


def has_access(user: AuthUser, roles: RolesConfig, access: Access, project: str | None) -> bool:
    if access in (Access.PUBLIC, Access.AUTHENTICATED):
        return True
    if roles.is_admin(user):
        return True
    if access == Access.ADMIN or project is None:
        return False
    role = roles.role_for(user, project)
    if access == Access.READ:
        return role >= Role.READONLY
    return role >= Role.DEVELOPER


class AuthMiddleware:
    """Require a valid session and the right role for API/WebSocket routes.

    A no-op when auth is disabled. On success the signed-in user is exposed
    to handlers as ``request.state.auth_user``.
    """

    def __init__(self, app: Any, settings: AuthSettings | None = None) -> None:
        self.app = app
        self._settings = settings

    @property
    def settings(self) -> AuthSettings:
        return self._settings or get_auth_settings()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        settings = self.settings
        if scope["type"] not in ("http", "websocket") or not settings.enabled:
            await self.app(scope, receive, send)
            return

        is_ws = scope["type"] == "websocket"
        method = "GET" if is_ws else str(scope.get("method", "GET")).upper()
        path = scope.get("path", "")

        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return

        requirement = required_access(method, path)
        if requirement.access == Access.PUBLIC:
            await self.app(scope, receive, send)
            return

        # CSRF / cross-origin protection for anything that changes state.
        if is_ws or method not in SAFE_METHODS:
            origin = _header(scope, b"origin")
            if not is_same_origin_request(origin, _header(scope, b"host"), settings.trusted_origins):
                logger.warning("Rejected cross-origin %s %s from origin %r", method, path, origin)
                await self._deny(scope, receive, send, 403, "Cross-origin request rejected")
                return

        session = get_session_store().get(get_cookie(scope, SESSION_COOKIE))
        if session is None:
            await self._deny(scope, receive, send, 401, "Authentication required")
            return

        user = session.user
        roles = get_roles_config(settings.roles_file)
        if not has_access(user, roles, requirement.access, requirement.project):
            logger.info(
                "Denied %s %s for %s (needs %s on %s)",
                method, path, user.display_name, requirement.access.value, requirement.project or "-",
            )
            await self._deny(scope, receive, send, 403, "You do not have permission to do this")
            return

        scope.setdefault("state", {})["auth_user"] = user
        await self.app(scope, receive, send)

    @staticmethod
    async def _deny(scope: Scope, receive: Receive, send: Send, status: int, detail: str) -> None:
        if scope["type"] == "websocket":
            message = await receive()
            if message["type"] == "websocket.connect":
                code = WS_CLOSE_UNAUTHORIZED if status == 401 else WS_CLOSE_FORBIDDEN
                await send({"type": "websocket.close", "code": code})
            return

        body = json.dumps({"detail": detail}).encode()
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": body})


def can_read_project(scope: Scope, project: str) -> bool:
    """Whether the request's user may see ``project`` (always True with auth off).

    For handlers that return data about several projects (e.g. the project
    list), where the path-based policy cannot decide on its own.
    """
    settings = get_auth_settings()
    if not settings.enabled:
        return True
    user = scope.get("state", {}).get("auth_user")
    if user is None:
        return False
    return has_access(user, get_roles_config(settings.roles_file), Access.READ, project)
