"""
Tests for the built-in OIDC login (AUTOFORGE_AUTH_MODE=oidc).

Uses a fake identity provider (httpx.MockTransport + a real RSA key) so the
full login flow, ID token verification, sessions and role enforcement are
exercised without network access.

Run with: python -m pytest test_auth_oidc.py
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.routers.auth import router as auth_router
from server.utils import auth
from server.utils.oidc import OIDCClient, OIDCConfig, OIDCError, safe_next_path

ISSUER = "https://idp.example.com"
CLIENT_ID = "autoforge"

ROLES_YAML = """
default_role: none
admins:
  groups: [autoforge-admins]
projects:
  "*":
    viewer:
      groups: [readers]
  alpha:
    developer:
      users: [dev@example.com]
      groups: [alpha-devs]
"""


# ============================================================================
# Fake identity provider
# ============================================================================

class FakeIdP:
    def __init__(self) -> None:
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key()))
        jwk.update({"kid": "k1", "use": "sig", "alg": "RS256"})
        self.jwks = {"keys": [jwk]}
        self.claims: dict[str, Any] = {}
        self.nonce: str | None = None
        self.token_requests: list[dict[str, str]] = []

    def sign(self, claims: dict[str, Any], kid: str = "k1") -> str:
        return jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": kid})

    def id_token(self, **overrides: Any) -> str:
        now = int(time.time())
        claims = {
            "iss": ISSUER, "aud": CLIENT_ID, "sub": "user-1", "iat": now, "exp": now + 300,
            "nonce": self.nonce, "email": "dev@example.com", "name": "Dee Dev",
            **self.claims,
        }
        claims.update(overrides)
        return self.sign(claims)

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/.well-known/openid-configuration":
            return httpx.Response(200, json={
                "issuer": ISSUER,
                "authorization_endpoint": f"{ISSUER}/authorize",
                "token_endpoint": f"{ISSUER}/token",
                "jwks_uri": f"{ISSUER}/jwks",
                "userinfo_endpoint": f"{ISSUER}/userinfo",
                "end_session_endpoint": f"{ISSUER}/logout",
            })
        if path == "/jwks":
            return httpx.Response(200, json=self.jwks)
        if path == "/token":
            form = parse_qs(request.content.decode())
            self.token_requests.append({k: v[0] for k, v in form.items()})
            if form.get("code") != ["good-code"]:
                return httpx.Response(400, json={"error": "invalid_grant"})
            return httpx.Response(200, json={"access_token": "at", "token_type": "Bearer",
                                             "id_token": self.id_token()})
        if path == "/userinfo":
            return httpx.Response(200, json={"sub": "user-1", "groups": ["from-userinfo"]})
        return httpx.Response(404)


OIDC_CONFIG = OIDCConfig(issuer=ISSUER, client_id=CLIENT_ID, client_secret="s3cret")


def make_client(idp: FakeIdP) -> OIDCClient:
    return OIDCClient(OIDC_CONFIG, http=httpx.AsyncClient(transport=httpx.MockTransport(idp.handler)))


@pytest.fixture
def idp() -> FakeIdP:
    return FakeIdP()


@pytest.fixture
def app(idp: FakeIdP, tmp_path: Path):
    roles = tmp_path / "auth.yaml"
    roles.write_text(ROLES_YAML)
    settings = auth.AuthSettings(mode="oidc", config_path=roles, oidc=OIDC_CONFIG)
    auth.configure(settings, oidc_client=make_client(idp))

    app = FastAPI()
    store = auth.get_store()
    assert store is not None
    app.add_middleware(auth.AuthMiddleware, settings=settings, store=store)
    app.include_router(auth_router)

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    @app.get("/api/projects")
    async def projects():
        return []

    @app.post("/api/projects")
    async def create_project():
        return {"created": True}

    @app.get("/api/projects/{name}/features")
    async def features(name: str):
        return {"project": name}

    @app.post("/api/projects/{name}/agent/start")
    async def start(name: str):
        return {"started": name}

    @app.websocket("/ws/projects/{name}")
    async def ws(websocket: WebSocket, name: str):
        await websocket.accept()
        await websocket.send_json({"project": name})
        await websocket.close()

    @app.get("/{path:path}")
    async def spa(path: str):
        return {"spa": path}

    yield app
    auth.configure(auth.AuthSettings())


def login(client: TestClient, idp: FakeIdP, next_path: str = "/") -> Any:
    """Run the browser login flow against the fake IdP."""
    resp = client.get("/api/auth/login", params={"next": next_path}, follow_redirects=False)
    assert resp.status_code == 302, resp.text
    params = parse_qs(urlparse(resp.headers["location"]).query)
    idp.nonce = params["nonce"][0]
    return client.get("/api/auth/callback", params={"code": "good-code", "state": params["state"][0]},
                      follow_redirects=False)


# ============================================================================
# Settings & helpers
# ============================================================================

class TestSettings:
    def test_oidc_requires_issuer_and_client(self):
        with pytest.raises(ValueError, match="AUTOFORGE_OIDC_ISSUER"):
            auth.load_auth_settings({"AUTOFORGE_AUTH_MODE": "oidc", "AUTOFORGE_OIDC_CLIENT_ID": "x"})

    def test_oidc_settings_parsed(self):
        settings = auth.load_auth_settings({
            "AUTOFORGE_AUTH_MODE": "oidc",
            "AUTOFORGE_OIDC_ISSUER": "https://login.example.com/tenant/v2.0/",
            "AUTOFORGE_OIDC_CLIENT_ID": "cid",
            "AUTOFORGE_OIDC_GROUPS_CLAIM": "roles",
            "AUTOFORGE_SESSION_TTL_HOURS": "2",
            "AUTOFORGE_COOKIE_SECURE": "true",
        })
        assert settings.enabled and settings.mode == "oidc"
        assert settings.oidc is not None
        assert settings.oidc.issuer == "https://login.example.com/tenant/v2.0"
        assert settings.oidc.roles_claims == ("roles",)
        assert settings.oidc.client_secret is None
        assert settings.session_ttl_seconds == 7200
        assert settings.cookie_secure is True

    def test_invalid_ttl(self):
        with pytest.raises(ValueError):
            auth.load_auth_settings({"AUTOFORGE_AUTH_MODE": "oidc", "AUTOFORGE_OIDC_ISSUER": "https://i",
                                     "AUTOFORGE_OIDC_CLIENT_ID": "c", "AUTOFORGE_SESSION_TTL_HOURS": "-1"})

    def test_safe_next_path(self):
        assert safe_next_path("/#/projects") == "/#/projects"
        assert safe_next_path("//evil.com") == "/"
        assert safe_next_path("https://evil.com") == "/"
        assert safe_next_path("/\\evil.com") == "/"
        assert safe_next_path(None) == "/"

    def test_user_from_claims(self):
        user = auth.user_from_claims(
            {"sub": "s1", "email": "a@x.com", "preferred_username": "alice", "name": "Alice",
             "groups": ["g1"], "roles": ["r1", "g1"]},
            ("groups", "roles"),
        )
        assert user.name == "alice"
        assert user.groups == ("g1", "r1")
        assert user.aliases == ("a@x.com", "s1")
        assert user.display_name == "Alice"

    def test_users_entries_match_email_alias(self):
        config = auth.parse_role_config({"projects": {"p": {"developer": {"users": ["A@X.com"]}}}})
        user = auth.AuthUser(name="alice", aliases=("a@x.com",))
        assert auth.project_role(user, "p", config) == auth.ROLE_DEVELOPER


# ============================================================================
# Login flow & enforcement
# ============================================================================

class TestLoginFlow:
    def test_signed_out(self, app):
        client = TestClient(app)
        assert client.get("/api/health").status_code == 200

        # API: 401 with a login URL for the UI
        resp = client.get("/api/projects")
        assert resp.status_code == 401
        assert resp.json()["login_url"] == "/api/auth/login"

        # Page navigation: redirected through the login, keeping the target
        resp = client.get("/some/page", params={"x": "1"}, follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/api/auth/login?next=%2Fsome%2Fpage%3Fx%3D1"

        me = client.get("/api/auth/me").json()
        assert me["enabled"] is True and me["mode"] == "oidc" and me["user"] is None

        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/ws/projects/alpha") as ws:
                ws.receive_json()
        assert exc.value.code == auth.WS_CLOSE_UNAUTHORIZED

    def test_full_login_flow(self, app, idp):
        client = TestClient(app)
        resp = login(client, idp, next_path="/#/alpha")
        assert resp.status_code == 302
        assert resp.headers["location"] == "/#/alpha"
        cookie = resp.headers["set-cookie"]
        assert auth.SESSION_COOKIE in cookie and "HttpOnly" in cookie and "samesite=lax" in cookie.lower()

        token_req = idp.token_requests[-1]
        assert token_req["code_verifier"] and token_req["client_secret"] == "s3cret"

        me = client.get("/api/auth/me").json()
        assert me["user"] == "dev@example.com"
        assert me["display_name"] == "Dee Dev"
        assert me["is_admin"] is False

    def test_role_enforcement(self, app, idp):
        client = TestClient(app)
        login(client, idp)  # dev@example.com: developer on alpha only

        assert client.get("/api/projects").status_code == 200
        assert client.get("/api/projects/alpha/features").status_code == 200
        assert client.post("/api/projects/alpha/agent/start").status_code == 200
        assert client.get("/api/projects/beta/features").status_code == 403
        assert client.post("/api/projects/beta/agent/start").status_code == 403
        assert client.post("/api/projects").status_code == 403

        with client.websocket_connect("/ws/projects/alpha") as ws:
            assert ws.receive_json() == {"project": "alpha"}

    def test_viewer_via_group_claim(self, app, idp):
        idp.claims = {"email": "someone@example.com", "groups": ["readers"]}
        client = TestClient(app)
        login(client, idp)
        assert client.get("/api/projects/beta/features").status_code == 200
        resp = client.post("/api/projects/beta/agent/start")
        assert resp.status_code == 403
        assert "developer" in resp.json()["detail"]

    def test_admin_via_app_role(self, app, idp):
        # Entra ID app roles arrive in the "roles" claim
        idp.claims = {"email": "boss@example.com", "roles": ["autoforge-admins"]}
        client = TestClient(app)
        login(client, idp)
        assert client.post("/api/projects").status_code == 200
        assert client.post("/api/projects/beta/agent/start").status_code == 200

    def test_groups_from_userinfo(self, app, idp):
        client = TestClient(app)
        login(client, idp)
        assert client.get("/api/auth/me").json()["groups"] == ["from-userinfo"]

    def test_cross_site_write_rejected(self, app, idp):
        client = TestClient(app)
        login(client, idp)
        resp = client.post("/api/projects/alpha/agent/start", headers={"origin": "https://evil.example"})
        assert resp.status_code == 403

    def test_logout_revokes_session(self, app, idp):
        client = TestClient(app)
        login(client, idp)
        assert client.get("/api/projects").status_code == 200
        resp = client.post("/api/auth/logout")
        assert resp.json()["end_session_url"].startswith(f"{ISSUER}/logout?")
        assert client.get("/api/projects").status_code == 401

    def test_forged_cookie_rejected(self, app):
        client = TestClient(app)
        client.cookies.set(auth.SESSION_COOKIE, "not-a-real-session")
        assert client.get("/api/projects").status_code == 401

    def test_state_is_single_use(self, app, idp):
        client = TestClient(app)
        resp = client.get("/api/auth/login", follow_redirects=False)
        params = parse_qs(urlparse(resp.headers["location"]).query)
        idp.nonce = params["nonce"][0]
        state = params["state"][0]
        ok = client.get("/api/auth/callback", params={"code": "good-code", "state": state}, follow_redirects=False)
        assert ok.status_code == 302
        replay = client.get("/api/auth/callback", params={"code": "good-code", "state": state},
                            follow_redirects=False)
        assert replay.status_code == 400

    def test_open_redirect_blocked(self, app, idp):
        client = TestClient(app)
        assert login(client, idp, next_path="//evil.example").headers["location"] == "/"

    def test_idp_error_is_escaped(self, app):
        client = TestClient(app)
        resp = client.get("/api/auth/callback", params={"error": "access_denied", "error_description": "<b>no</b>"})
        assert resp.status_code == 400
        assert "&lt;b&gt;no&lt;/b&gt;" in resp.text

    def test_login_404_when_not_oidc(self):
        auth.configure(auth.AuthSettings())
        app = FastAPI()
        app.include_router(auth_router)
        assert TestClient(app).get("/api/auth/login").status_code == 404


# ============================================================================
# ID token validation
# ============================================================================

class TestIdTokenValidation:
    def verify(self, idp: FakeIdP, token: str, nonce: str = "n") -> dict[str, Any]:
        async def run() -> dict[str, Any]:
            client = make_client(idp)
            try:
                return await client.verify_id_token(token, nonce)
            finally:
                await client.aclose()
        return asyncio.run(run())

    def test_valid_token(self, idp):
        idp.nonce = "n"
        assert self.verify(idp, idp.id_token())["sub"] == "user-1"

    @pytest.mark.parametrize("overrides", [
        {"aud": "someone-else"},
        {"iss": "https://evil.example"},
        {"exp": int(time.time()) - 3600},
        {"nonce": "wrong"},
    ])
    def test_invalid_claims_rejected(self, idp, overrides):
        idp.nonce = "n"
        with pytest.raises(OIDCError):
            self.verify(idp, idp.id_token(**overrides))

    def test_wrong_signing_key_rejected(self, idp):
        other = FakeIdP()
        other.nonce = "n"
        with pytest.raises(OIDCError):
            self.verify(idp, other.id_token())

    def test_unsigned_token_rejected(self, idp):
        now = int(time.time())
        token = jwt.encode({"iss": ISSUER, "aud": CLIENT_ID, "sub": "x", "iat": now, "exp": now + 60,
                            "nonce": "n"}, None, algorithm="none")
        with pytest.raises(OIDCError):
            self.verify(idp, token)

    def test_unknown_kid_rejected(self, idp):
        now = int(time.time())
        token = idp.sign({"iss": ISSUER, "aud": CLIENT_ID, "sub": "x", "iat": now, "exp": now + 60,
                          "nonce": "n"}, kid="rotated-away")
        with pytest.raises(OIDCError):
            self.verify(idp, token)
