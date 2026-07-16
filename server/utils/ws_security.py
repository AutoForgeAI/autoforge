"""
WebSocket Origin Validation
===========================

Starlette's ``@app.middleware("http")`` decorator only runs for HTTP requests,
so the ``require_localhost`` guard in ``server/main.py`` never sees WebSocket
handshakes. Browsers also do not enforce same-origin policy on WebSocket
connections, which left every WS endpoint (including the interactive PTY
terminal) open to cross-site WebSocket hijacking (CSWSH): any malicious web
page the user visited could open ``ws://127.0.0.1:8888/api/terminal/ws/...``
and drive a shell (CWE-306).

This module provides a pure-ASGI middleware that validates the ``Origin``
header on every WebSocket handshake before the route handler runs. Handshakes
from disallowed origins are rejected with close code 4403 and never reach the
application, so no PTY/session is ever created.

Non-browser clients (CLI tools, native apps) do not send an ``Origin`` header
and are allowed through: the CSWSH threat model is browser-only, and raw
socket access is governed by the localhost bind / ``AUTOFORGE_ALLOW_REMOTE``.
"""

import logging
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ASGI type aliases (kept loose to avoid a hard dependency on starlette.types)
Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

# WebSocket close code used when rejecting a disallowed origin.
# 4000-4999 is the range reserved for application-specific codes.
WS_CLOSE_FORBIDDEN = 4403

_LOCALHOST_HOSTNAMES = frozenset({"localhost", "127.0.0.1", "::1"})


def _hostname_from_origin(origin: str) -> str | None:
    """Extract the lowercase hostname from an Origin header value."""
    try:
        return urlparse(origin).hostname
    except ValueError:
        return None


def _hostname_from_host(host: str) -> str | None:
    """Extract the lowercase hostname from a Host header value (strips port)."""
    try:
        # Prefix with // so urlparse treats the value as a netloc
        # (handles bracketed IPv6 literals like [::1]:8888).
        return urlparse(f"//{host}").hostname
    except ValueError:
        return None


def is_allowed_ws_origin(origin: str | None, allow_remote: bool, host: str | None = None) -> bool:
    """Decide whether a WebSocket handshake with the given Origin is allowed.

    Rules:

    * No ``Origin`` header (non-browser client such as a CLI or native app):
      allowed. CSWSH is a browser-only threat, and non-browser network access
      is already gated by the localhost bind / AUTOFORGE_ALLOW_REMOTE opt-in.
    * Origin hostname is a localhost variant (``localhost``, ``127.0.0.1``,
      ``::1``): allowed regardless of scheme or port. This covers the Vite
      dev server (5173) and the production server (8888).
    * ``allow_remote`` is True: additionally allow origins whose hostname
      matches the host the browser connected to (the ``Host`` header), so the
      remotely-served UI keeps working while foreign pages are still rejected.
    * Everything else: rejected.

    Args:
        origin: Value of the Origin header, or None if absent.
        allow_remote: Whether AUTOFORGE_ALLOW_REMOTE is enabled.
        host: Value of the Host header (used only when allow_remote is True).

    Returns:
        True if the handshake should proceed, False if it must be rejected.
    """
    if not origin:
        return True

    hostname = _hostname_from_origin(origin)
    if not hostname:
        return False

    if hostname in _LOCALHOST_HOSTNAMES:
        return True

    if allow_remote and host:
        host_name = _hostname_from_host(host)
        return host_name is not None and hostname == host_name

    return False


class WebSocketOriginMiddleware:
    """Pure-ASGI middleware that rejects WS handshakes from disallowed origins.

    Implemented as raw ASGI (not ``@app.middleware("http")``) because
    Starlette's http middleware decorator is never invoked for scope type
    ``websocket`` -- which is exactly the gap that left the WS endpoints
    unprotected. HTTP and lifespan scopes pass through untouched.
    """

    def __init__(self, app: Any, allow_remote: bool = False) -> None:
        self.app = app
        self.allow_remote = allow_remote

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "websocket":
            await self.app(scope, receive, send)
            return

        origin: str | None = None
        host: str | None = None
        for name, value in scope.get("headers", []):
            if name == b"origin":
                origin = value.decode("latin-1")
            elif name == b"host":
                host = value.decode("latin-1")

        if not is_allowed_ws_origin(origin, self.allow_remote, host):
            logger.warning(
                "Rejected WebSocket handshake from disallowed origin %r (path=%s)",
                origin,
                scope.get("path"),
            )
            # Refuse the handshake without ever accepting: consume the
            # connect event, then close. The route handler never runs,
            # so no terminal/chat session is created.
            message = await receive()
            if message["type"] == "websocket.connect":
                await send({"type": "websocket.close", "code": WS_CLOSE_FORBIDDEN})
            return

        await self.app(scope, receive, send)
