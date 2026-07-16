"""
Unit tests for WebSocket Origin validation (CSWSH protection).

Tests is_allowed_ws_origin() and WebSocketOriginMiddleware from
server/utils/ws_security.py.
"""

import asyncio
import unittest

from server.utils.ws_security import (
    WS_CLOSE_FORBIDDEN,
    WebSocketOriginMiddleware,
    is_allowed_ws_origin,
)


class TestIsAllowedWsOrigin(unittest.TestCase):
    """Tests for is_allowed_ws_origin()."""

    def test_missing_origin_allowed(self):
        """Non-browser clients send no Origin header and must be allowed."""
        assert is_allowed_ws_origin(None, False) is True
        assert is_allowed_ws_origin("", False) is True
        assert is_allowed_ws_origin(None, True) is True

    def test_localhost_origins_allowed(self):
        """Localhost variants are allowed regardless of scheme or port."""
        assert is_allowed_ws_origin("http://localhost:5173", False) is True
        assert is_allowed_ws_origin("http://localhost:8888", False) is True
        assert is_allowed_ws_origin("http://127.0.0.1:8888", False) is True
        assert is_allowed_ws_origin("https://127.0.0.1", False) is True
        assert is_allowed_ws_origin("http://[::1]:8888", False) is True

    def test_foreign_origins_rejected(self):
        """Non-localhost origins are rejected in the default (local) mode."""
        assert is_allowed_ws_origin("http://evil.com", False) is False
        assert is_allowed_ws_origin("https://evil.com:8888", False) is False
        assert is_allowed_ws_origin("http://localhost.evil.com", False) is False
        assert is_allowed_ws_origin("http://192.168.1.50:8888", False) is False

    def test_garbage_origin_rejected(self):
        """Origins without a parseable hostname are rejected."""
        assert is_allowed_ws_origin("null", False) is False
        assert is_allowed_ws_origin("not a url", False) is False

    def test_remote_mode_host_match_allowed(self):
        """In remote mode, origins matching the connected Host are allowed."""
        assert is_allowed_ws_origin("http://192.168.1.50:8888", True, host="192.168.1.50:8888") is True
        assert is_allowed_ws_origin("http://myserver:8888", True, host="myserver:8888") is True
        # Localhost still allowed too
        assert is_allowed_ws_origin("http://localhost:5173", True, host="192.168.1.50:8888") is True

    def test_remote_mode_foreign_origin_rejected(self):
        """In remote mode, origins not matching the Host are still rejected."""
        assert is_allowed_ws_origin("http://evil.com", True, host="192.168.1.50:8888") is False
        assert is_allowed_ws_origin("http://evil.com", True, host=None) is False


class _FakeApp:
    """Minimal downstream ASGI app that records whether it was called."""

    def __init__(self):
        self.called = False

    async def __call__(self, scope, receive, send):
        self.called = True


def _run_ws_handshake(middleware, headers):
    """Drive a websocket scope through the middleware; return sent messages."""
    sent = []

    async def receive():
        return {"type": "websocket.connect"}

    async def send(message):
        sent.append(message)

    scope = {"type": "websocket", "path": "/api/terminal/ws/proj/term", "headers": headers}
    asyncio.run(middleware(scope, receive, send))
    return sent


class TestWebSocketOriginMiddleware(unittest.TestCase):
    """Tests for the ASGI middleware behavior."""

    def test_http_scope_passes_through(self):
        """HTTP requests are never touched by this middleware."""
        app = _FakeApp()
        middleware = WebSocketOriginMiddleware(app, allow_remote=False)
        asyncio.run(middleware({"type": "http", "headers": []}, None, None))
        assert app.called is True

    def test_allowed_origin_reaches_app(self):
        """Localhost-origin handshakes reach the route handler."""
        app = _FakeApp()
        middleware = WebSocketOriginMiddleware(app, allow_remote=False)
        sent = _run_ws_handshake(middleware, [(b"origin", b"http://localhost:8888")])
        assert app.called is True
        assert sent == []

    def test_missing_origin_reaches_app(self):
        """Handshakes without an Origin header (non-browser) reach the app."""
        app = _FakeApp()
        middleware = WebSocketOriginMiddleware(app, allow_remote=False)
        _run_ws_handshake(middleware, [])
        assert app.called is True

    def test_foreign_origin_rejected_before_app(self):
        """Cross-site handshakes are closed with 4403 and never reach the app."""
        app = _FakeApp()
        middleware = WebSocketOriginMiddleware(app, allow_remote=False)
        sent = _run_ws_handshake(middleware, [(b"origin", b"http://evil.com")])
        assert app.called is False
        assert sent == [{"type": "websocket.close", "code": WS_CLOSE_FORBIDDEN}]


if __name__ == "__main__":
    unittest.main()
