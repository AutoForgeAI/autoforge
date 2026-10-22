"""
Tests for the optional OIDC authentication and role system (server/auth/).

Run with: python -m pytest test_auth.py
"""

import os
import tempfile
import time
import unittest
from pathlib import Path
from typing import Any
from unittest import mock
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.auth import oidc as oidc_module
from server.auth.config import AuthSettings, load_auth_settings, reset_auth_settings
from server.auth.middleware import (
    WS_CLOSE_FORBIDDEN,
    WS_CLOSE_UNAUTHORIZED,
    AuthMiddleware,
    can_read_project,
    is_same_origin_request,
)
from server.auth.policy import Access, required_access
from server.auth.roles import Role, parse_roles_config
from server.auth.session import LOGIN_STATE_COOKIE, SESSION_COOKIE, AuthUser, get_session_store
from server.routers.auth import _safe_next
from server.routers.auth import router as auth_router

ISSUER = "https://idp.example.com/realms/test"
CLIENT_ID = "autoforge"

ROLES_YAML = """
version: 1
admins:
  users: [Admin@Example.com]
  groups: [autoforge-admins]
default_role: none
projects:
  "*":
    readonly:
      groups: [viewers]
  my-app:
    developer:
      users: [dev@example.com]
  "team-*":
    developer:
      groups: [team-devs]
"""


class TestSettings(unittest.TestCase):
    def test_disabled_by_default(self):
        settings = load_auth_settings({})
        assert settings.enabled is False

    def test_invalid_mode_rejected(self):
        with self.assertRaises(RuntimeError):
            load_auth_settings({"AUTOFORGE_AUTH_MODE": "basic"})

    def test_oidc_requires_issuer_and_client(self):
        with self.assertRaises(RuntimeError):
            load_auth_settings({"AUTOFORGE_AUTH_MODE": "oidc", "AUTOFORGE_OIDC_ISSUER": ISSUER})

    def test_oidc_settings_parsed(self):
        settings = load_auth_settings({
            "AUTOFORGE_AUTH_MODE": "OIDC",
            "AUTOFORGE_OIDC_ISSUER": ISSUER + "/",
            "AUTOFORGE_OIDC_CLIENT_ID": CLIENT_ID,
            "AUTOFORGE_OIDC_GROUP_CLAIMS": "groups, app_roles",
            "AUTOFORGE_SESSION_TTL_HOURS": "2",
            "AUTOFORGE_AUTH_TRUSTED_ORIGINS": "http://localhost:5173/",
        })
        assert settings.enabled
        assert settings.issuer == ISSUER
        assert settings.group_claims == ("groups", "app_roles")
        assert settings.session_ttl_seconds == 7200
        assert settings.trusted_origins == ("http://localhost:5173",)


class TestPolicy(unittest.TestCase):
    def check(self, method: str, path: str, access: Access, project: str | None = None):
        req = required_access(method, path)
        assert (req.access, req.project) == (access, project), f"{method} {path} -> {req}"

    def test_public_routes(self):
        self.check("GET", "/", Access.PUBLIC)
        self.check("GET", "/assets/index.js", Access.PUBLIC)
        self.check("GET", "/api/health", Access.PUBLIC)
        self.check("GET", "/api/auth/login", Access.PUBLIC)
        self.check("POST", "/api/auth/logout", Access.PUBLIC)

    def test_project_routes(self):
        self.check("GET", "/api/projects", Access.AUTHENTICATED)
        self.check("POST", "/api/projects", Access.ADMIN)
        self.check("GET", "/api/projects/app", Access.READ, "app")
        self.check("DELETE", "/api/projects/app", Access.ADMIN, "app")
        self.check("GET", "/api/projects/app/features", Access.READ, "app")
        self.check("POST", "/api/projects/app/features", Access.WRITE, "app")
        self.check("PATCH", "/api/projects/app/features/3", Access.WRITE, "app")
        self.check("GET", "/api/projects/app/agent/status", Access.READ, "app")
        self.check("POST", "/api/projects/app/agent/start", Access.WRITE, "app")
        self.check("POST", "/api/projects/app/reset", Access.WRITE, "app")
        self.check("PUT", "/api/projects/app/prompts", Access.WRITE, "app")
        self.check("GET", "/ws/projects/app", Access.READ, "app")

    def test_interactive_routes_need_write(self):
        self.check("GET", "/api/terminal/app", Access.WRITE, "app")
        self.check("GET", "/api/terminal/ws/app/t1", Access.WRITE, "app")
        self.check("GET", "/api/spec/ws/app", Access.WRITE, "app")
        self.check("GET", "/api/expand/ws/app", Access.WRITE, "app")
        self.check("GET", "/api/assistant/ws/app", Access.WRITE, "app")
        self.check("GET", "/api/assistant/conversations/app", Access.READ, "app")

    def test_global_routes(self):
        self.check("GET", "/api/settings", Access.AUTHENTICATED)
        self.check("PATCH", "/api/settings", Access.ADMIN)
        self.check("GET", "/api/filesystem/list", Access.ADMIN)
        self.check("POST", "/api/scaffold/run", Access.ADMIN)
        self.check("GET", "/api/spec/sessions", Access.ADMIN)

    def test_unknown_api_routes_default_to_admin(self):
        self.check("GET", "/api/something-new", Access.ADMIN)
        self.check("GET", "/ws/other", Access.ADMIN)


class TestRoles(unittest.TestCase):
    def setUp(self):
        self.roles = parse_roles_config(__import__("yaml").safe_load(ROLES_YAML))

    def test_admin_by_user_case_insensitive(self):
        user = AuthUser(sub="1", email="admin@example.com")
        assert self.roles.is_admin(user)
        assert self.roles.role_for(user, "anything") == Role.DEVELOPER

    def test_admin_by_group(self):
        assert self.roles.is_admin(AuthUser(sub="1", groups=("autoforge-admins",)))

    def test_project_roles(self):
        dev = AuthUser(sub="2", email="dev@example.com", groups=("viewers",))
        assert self.roles.role_for(dev, "my-app") == Role.DEVELOPER
        assert self.roles.role_for(dev, "other") == Role.READONLY
        assert not self.roles.is_admin(dev)

    def test_glob_patterns(self):
        user = AuthUser(sub="3", groups=("team-devs",))
        assert self.roles.role_for(user, "team-alpha") == Role.DEVELOPER
        assert self.roles.role_for(user, "my-app") == Role.NONE

    def test_default_role(self):
        roles = parse_roles_config({"default_role": "readonly"})
        assert roles.role_for(AuthUser(sub="x"), "p") == Role.READONLY

    def test_invalid_role_rejected(self):
        with self.assertRaises(ValueError):
            parse_roles_config({"projects": {"p": {"owner": {"users": ["a"]}}}})


class TestOrigin(unittest.TestCase):
    def test_same_origin(self):
        assert is_same_origin_request(None, "host:8888")
        assert is_same_origin_request("http://host:8888", "host:8888")
        assert is_same_origin_request("https://af.example.com", "af.example.com")
        assert is_same_origin_request("https://af.example.com", "af.example.com:443")

    def test_other_port_rejected(self):
        """A generated app's dev server on the same host must not drive the API."""
        assert not is_same_origin_request("http://host:3000", "host:8888")
        assert not is_same_origin_request("http://evil.com", "host:8888")
        assert not is_same_origin_request("null", "host:8888")

    def test_trusted_origin(self):
        assert is_same_origin_request("http://localhost:5173", "127.0.0.1:8888", ("http://localhost:5173",))


def _build_app(settings: AuthSettings) -> FastAPI:
    app = FastAPI()
    app.add_middleware(AuthMiddleware, settings=settings)
    app.include_router(auth_router)

    @app.get("/api/projects")
    async def projects(request: Request):
        return [p for p in ("my-app", "other", "secret") if can_read_project(request.scope, p)]

    @app.get("/api/projects/{name}/features")
    async def list_features(name: str):
        return {"project": name}

    @app.post("/api/projects/{name}/features")
    async def create_feature(name: str):
        return {"created": name}

    @app.get("/api/filesystem/list")
    async def fs_list():
        return []

    @app.websocket("/ws/projects/{name}")
    async def project_ws(websocket: WebSocket, name: str):
        await websocket.accept()
        await websocket.send_json({"project": name})
        await websocket.close()

    @app.websocket("/api/terminal/ws/{name}/{tid}")
    async def terminal_ws(websocket: WebSocket, name: str, tid: str):
        await websocket.accept()
        await websocket.close()

    @app.get("/")
    async def index():
        return {"ui": True}

    return app


class AuthAppTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        roles_file = Path(self.tmp.name) / "auth.yaml"
        roles_file.write_text(ROLES_YAML, encoding="utf-8")
        self.settings = AuthSettings(
            mode="oidc", issuer=ISSUER, client_id=CLIENT_ID, client_secret="s3cret",
            roles_file=roles_file, cookie_secure=False,
        )
        reset_auth_settings(self.settings)
        get_session_store().clear()
        self.client = TestClient(_build_app(self.settings), base_url="http://testserver")

    def tearDown(self):
        reset_auth_settings(None)
        get_session_store().clear()
        self.tmp.cleanup()

    def login_as(self, user: AuthUser) -> None:
        sid = get_session_store().create(user, ttl_seconds=3600)
        self.client.cookies.set(SESSION_COOKIE, sid)


class TestMiddleware(AuthAppTestCase):
    def test_disabled_auth_is_noop(self):
        client = TestClient(_build_app(AuthSettings()))
        assert client.get("/api/projects/x/features").status_code == 200
        assert client.post("/api/projects/x/features").status_code == 200

    def test_unauthenticated(self):
        assert self.client.get("/").status_code == 200
        response = self.client.get("/api/projects/my-app/features")
        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication required"

    def test_unknown_session_rejected(self):
        self.client.cookies.set(SESSION_COOKIE, "forged")
        assert self.client.get("/api/projects/my-app/features").status_code == 401

    def test_expired_session_rejected(self):
        sid = get_session_store().create(AuthUser(sub="x", email="dev@example.com"), ttl_seconds=3600)
        get_session_store()._sessions[sid].expires_at = time.time() - 1
        self.client.cookies.set(SESSION_COOKIE, sid)
        assert self.client.get("/api/projects/my-app/features").status_code == 401

    def test_readonly_user(self):
        self.login_as(AuthUser(sub="v", groups=("viewers",)))
        assert self.client.get("/api/projects/other/features").status_code == 200
        assert self.client.post("/api/projects/other/features").status_code == 403
        assert self.client.get("/api/filesystem/list").status_code == 403

    def test_developer_user(self):
        self.login_as(AuthUser(sub="d", email="dev@example.com"))
        assert self.client.post("/api/projects/my-app/features").status_code == 200
        assert self.client.get("/api/projects/other/features").status_code == 403

    def test_admin_user(self):
        self.login_as(AuthUser(sub="a", groups=("autoforge-admins",)))
        assert self.client.post("/api/projects/secret/features").status_code == 200
        assert self.client.get("/api/filesystem/list").status_code == 200

    def test_project_list_filtered(self):
        self.login_as(AuthUser(sub="d", email="dev@example.com"))
        assert self.client.get("/api/projects").json() == ["my-app"]

    def test_roles_file_reloaded(self):
        user = AuthUser(sub="n", email="new@example.com")
        self.login_as(user)
        assert self.client.get("/api/projects/secret/features").status_code == 403
        roles_file = self.settings.roles_file
        assert roles_file is not None
        roles_file.write_text("projects:\n  secret:\n    readonly:\n      users: [new@example.com]\n")
        future = time.time() + 5
        os.utime(roles_file, (future, future))
        assert self.client.get("/api/projects/secret/features").status_code == 200

    def test_invalid_roles_file_fails_closed(self):
        roles_file = self.settings.roles_file
        assert roles_file is not None
        roles_file.write_text("projects: [not, a, mapping]\n")
        future = time.time() + 10
        os.utime(roles_file, (future, future))
        self.login_as(AuthUser(sub="d", email="dev@example.com"))
        assert self.client.get("/api/projects/my-app/features").status_code == 403

    def test_cross_origin_post_rejected(self):
        self.login_as(AuthUser(sub="d", email="dev@example.com"))
        evil = self.client.post("/api/projects/my-app/features", headers={"Origin": "http://testserver:3000"})
        assert evil.status_code == 403
        same = self.client.post("/api/projects/my-app/features", headers={"Origin": "http://testserver"})
        assert same.status_code == 200

    def test_websocket_requires_session(self):
        with self.assertRaises(WebSocketDisconnect) as ctx:
            with self.client.websocket_connect("/ws/projects/my-app"):
                pass
        assert ctx.exception.code == WS_CLOSE_UNAUTHORIZED

    def test_websocket_read_allowed_for_readonly(self):
        self.login_as(AuthUser(sub="v", groups=("viewers",)))
        with self.client.websocket_connect("/ws/projects/other") as ws:
            assert ws.receive_json() == {"project": "other"}

    def test_terminal_websocket_forbidden_for_readonly(self):
        self.login_as(AuthUser(sub="v", groups=("viewers",)))
        with self.assertRaises(WebSocketDisconnect) as ctx:
            with self.client.websocket_connect("/api/terminal/ws/other/t1"):
                pass
        assert ctx.exception.code == WS_CLOSE_FORBIDDEN

    def test_cross_origin_websocket_rejected(self):
        self.login_as(AuthUser(sub="d", email="dev@example.com"))
        with self.assertRaises(WebSocketDisconnect) as ctx:
            with self.client.websocket_connect("/ws/projects/my-app", headers={"Origin": "http://testserver:3000"}):
                pass
        assert ctx.exception.code == WS_CLOSE_FORBIDDEN


class FakeProvider:
    """In-process OIDC provider serving discovery + token endpoints."""

    def __init__(self, client_id: str = CLIENT_ID):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.client_id = client_id
        self.nonce_override: str | None = None
        self.claims: dict[str, Any] = {"sub": "user-1", "email": "dev@example.com", "name": "Dev"}
        self.last_token_request: dict[str, list[str]] = {}
        self.nonce = ""

    def id_token(self) -> str:
        now = int(time.time())
        payload = {
            "iss": ISSUER, "aud": self.client_id, "iat": now, "exp": now + 300,
            "nonce": self.nonce_override if self.nonce_override is not None else self.nonce,
            **self.claims,
        }
        return jwt.encode(payload, self.key, algorithm="RS256", headers={"kid": "k1"})

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/.well-known/openid-configuration"):
            return httpx.Response(200, json={
                "issuer": ISSUER,
                "authorization_endpoint": f"{ISSUER}/auth",
                "token_endpoint": f"{ISSUER}/token",
                "jwks_uri": f"{ISSUER}/certs",
                "end_session_endpoint": f"{ISSUER}/logout",
            })
        if request.url.path.endswith("/token"):
            self.last_token_request = parse_qs(request.content.decode())
            return httpx.Response(200, json={"id_token": self.id_token(), "access_token": "at"})
        return httpx.Response(404)


class TestOIDCFlow(AuthAppTestCase):
    def setUp(self):
        super().setUp()
        self.provider = FakeProvider()
        transport = httpx.MockTransport(self.provider.handler)
        real_client = httpx.AsyncClient

        def client_factory(*args, **kwargs):
            kwargs["transport"] = transport
            return real_client(*args, **kwargs)

        provider = self.provider

        class FakeJWKClient:
            def __init__(self, *args, **kwargs):
                pass

            def get_signing_key_from_jwt(self, token):
                return mock.Mock(key=provider.key.public_key())

        self.patches = [
            mock.patch.object(oidc_module.httpx, "AsyncClient", client_factory),
            mock.patch.object(oidc_module.jwt, "PyJWKClient", FakeJWKClient),
            mock.patch("registry.list_registered_projects", return_value={"my-app": {}, "other": {}}),
        ]
        for p in self.patches:
            p.start()
        oidc_module._client = None

    def tearDown(self):
        for p in self.patches:
            p.stop()
        oidc_module._client = None
        super().tearDown()

    def start_login(self, next_path: str = "/projects") -> dict[str, list[str]]:
        response = self.client.get("/api/auth/login", params={"next": next_path}, follow_redirects=False)
        assert response.status_code == 302, response.text
        location = urlparse(response.headers["location"])
        assert f"{location.scheme}://{location.netloc}{location.path}" == f"{ISSUER}/auth"
        params = parse_qs(location.query)
        assert params["client_id"] == [CLIENT_ID]
        assert params["code_challenge_method"] == ["S256"]
        assert params["redirect_uri"] == ["http://testserver/api/auth/callback"]
        self.provider.nonce = params["nonce"][0]
        return params

    def test_full_login_flow(self):
        assert self.client.get("/api/auth/me").json() == {
            "enabled": True, "authenticated": False, "provider_name": "SSO", "user": None,
            "is_admin": False, "project_roles": {},
        }
        params = self.start_login()

        response = self.client.get(
            "/api/auth/callback", params={"code": "abc", "state": params["state"][0]}, follow_redirects=False,
        )
        assert response.status_code == 302, response.text
        assert response.headers["location"] == "/projects"
        assert self.provider.last_token_request["code"] == ["abc"]
        assert self.provider.last_token_request["client_secret"] == ["s3cret"]
        assert self.provider.last_token_request["code_verifier"][0]

        me = self.client.get("/api/auth/me").json()
        assert me["authenticated"] is True
        assert me["user"]["email"] == "dev@example.com"
        assert me["project_roles"] == {"my-app": "developer", "other": "none"}
        assert self.client.post("/api/projects/my-app/features").status_code == 200

        logout = self.client.post("/api/auth/logout").json()
        assert logout["logout_url"].startswith(f"{ISSUER}/logout?")
        assert self.client.get("/api/projects/my-app/features").status_code == 401

    def test_state_must_match_browser_cookie(self):
        params = self.start_login()
        self.client.cookies.set(LOGIN_STATE_COOKIE, "other-state", domain="testserver.local", path="/api/auth")
        response = self.client.get(
            "/api/auth/callback", params={"code": "abc", "state": params["state"][0]}, follow_redirects=False,
        )
        assert response.status_code == 400
        assert SESSION_COOKIE not in self.client.cookies

    def test_state_single_use(self):
        params = self.start_login()
        state = params["state"][0]
        ok = self.client.get("/api/auth/callback", params={"code": "abc", "state": state}, follow_redirects=False)
        assert ok.status_code == 302
        self.client.cookies.set(LOGIN_STATE_COOKIE, state, domain="testserver.local", path="/api/auth")
        replay = self.client.get("/api/auth/callback", params={"code": "abc", "state": state})
        assert replay.status_code == 400

    def test_nonce_mismatch_rejected(self):
        params = self.start_login()
        self.provider.nonce_override = "wrong"
        response = self.client.get("/api/auth/callback", params={"code": "abc", "state": params["state"][0]})
        assert response.status_code == 400
        assert "nonce" in response.text

    def test_wrong_audience_rejected(self):
        params = self.start_login()
        self.provider.client_id = "someone-else"
        response = self.client.get("/api/auth/callback", params={"code": "abc", "state": params["state"][0]})
        assert response.status_code == 400

    def test_open_redirect_blocked(self):
        assert _safe_next("https://evil.com") == "/"
        assert _safe_next("//evil.com") == "/"
        assert _safe_next("/\\evil.com") == "/"
        assert _safe_next("/projects?x=1") == "/projects?x=1"
        assert _safe_next(None) == "/"

    def test_group_claims_from_token(self):
        self.provider.claims = {"sub": "u2", "groups": ["viewers"], "roles": "autoforge-admins"}
        user = oidc_module.user_from_claims(self.provider.claims, ("groups", "roles"))
        assert user.groups == ("viewers", "autoforge-admins")


if __name__ == "__main__":
    unittest.main()
