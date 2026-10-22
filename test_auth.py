"""
Unit tests for proxy-header authentication and project roles.

Tests server/utils/auth.py: settings parsing, roles file parsing, role
resolution, route -> permission mapping, and AuthMiddleware end-to-end via
FastAPI's TestClient.
"""

import tempfile
import unittest
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from server.utils.auth import (
    ROLE_ADMIN,
    ROLE_DEVELOPER,
    ROLE_NONE,
    ROLE_VIEWER,
    WS_CLOSE_FORBIDDEN,
    WS_CLOSE_UNAUTHORIZED,
    AuthMiddleware,
    AuthUser,
    RoleConfigStore,
    get_request_user,
    load_auth_settings,
    parse_role_config,
    project_role,
    required_permission,
)

ROLES_YAML = """
version: 1
default_role: none
admins:
  users: [Alice]
  groups: [autoforge-admins]
projects:
  "*":
    viewer:
      groups: [staff]
  my-app:
    developer:
      users: [bob]
"""


class TestSettings(unittest.TestCase):
    def test_defaults_disabled(self):
        s = load_auth_settings({})
        assert s.enabled is False
        assert s.user_header == "x-forwarded-user"
        assert s.groups_header == "x-forwarded-groups"
        assert len(s.trusted_proxies) == 2
        assert s.trust_any_proxy is False

    def test_header_mode(self):
        s = load_auth_settings({
            "AUTOFORGE_AUTH_MODE": "HEADER",
            "AUTOFORGE_AUTH_USER_HEADER": "X-authentik-username",
            "AUTOFORGE_AUTH_TRUSTED_PROXIES": "10.0.0.0/8, *, bogus",
            "AUTOFORGE_AUTH_PROXY_SECRET": "s3cret",
        })
        assert s.enabled is True
        assert s.user_header == "x-authentik-username"
        assert s.trust_any_proxy is True
        assert len(s.trusted_proxies) == 1
        assert s.proxy_secret == "s3cret"

    def test_invalid_mode_raises(self):
        with self.assertRaises(ValueError):
            load_auth_settings({"AUTOFORGE_AUTH_MODE": "oidc"})


class TestRoleConfig(unittest.TestCase):
    def setUp(self):
        import yaml
        self.config = parse_role_config(yaml.safe_load(ROLES_YAML))

    def test_admin_by_user_case_insensitive(self):
        assert project_role(AuthUser("alice"), "anything", self.config) == ROLE_ADMIN

    def test_admin_by_group(self):
        assert project_role(AuthUser("x", ("Autoforge-Admins",)), "my-app", self.config) == ROLE_ADMIN

    def test_wildcard_and_project_roles(self):
        assert project_role(AuthUser("carol", ("staff",)), "other", self.config) == ROLE_VIEWER
        assert project_role(AuthUser("bob"), "my-app", self.config) == ROLE_DEVELOPER
        assert project_role(AuthUser("bob"), "other", self.config) == ROLE_NONE
        # Highest matching role wins
        assert project_role(AuthUser("bob", ("staff",)), "my-app", self.config) == ROLE_DEVELOPER

    def test_default_role(self):
        config = parse_role_config({"default_role": "viewer"})
        assert project_role(AuthUser("anyone"), "p", config) == ROLE_VIEWER

    def test_invalid_configs(self):
        for bad in (
            {"default_role": "admin"},
            {"projects": {"p": {"owner": {"users": ["x"]}}}},
            {"projects": {"p": {"viewer": {"users": "x", "groups": 5}}}},
            ["not", "a", "mapping"],
        ):
            with self.assertRaises(ValueError):
                parse_role_config(bad)

    def test_example_config_is_valid(self):
        import yaml
        example = Path(__file__).parent / "examples" / "auth.yaml"
        config = parse_role_config(yaml.safe_load(example.read_text()))
        assert project_role(AuthUser("bob@example.com"), "my-app", config) == ROLE_DEVELOPER

    def test_store_fails_closed_on_invalid_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "auth.yaml"
            store = RoleConfigStore(path)
            assert store.get().admins.users == frozenset()  # missing file
            path.write_text("default_role: superuser\n")
            assert store.get().default_role == ROLE_NONE


class TestRequiredPermission(unittest.TestCase):
    def check(self, scope_type, method, path, role, project):
        req = required_permission(scope_type, method, path)
        assert (req.role, req.project) == (role, project), (path, req)

    def test_project_reads_and_writes(self):
        self.check("http", "GET", "/api/projects/app", ROLE_VIEWER, "app")
        self.check("http", "GET", "/api/projects/app/features", ROLE_VIEWER, "app")
        self.check("http", "POST", "/api/projects/app/agent/start", ROLE_DEVELOPER, "app")
        self.check("http", "PATCH", "/api/projects/app/features/3", ROLE_DEVELOPER, "app")
        self.check("http", "DELETE", "/api/projects/app/schedules/1", ROLE_DEVELOPER, "app")
        self.check("http", "DELETE", "/api/projects/app", ROLE_ADMIN, None)
        self.check("http", "GET", "/api/spec/status/app", ROLE_VIEWER, "app")
        self.check("http", "GET", "/api/assistant/conversations/app/4", ROLE_VIEWER, "app")
        self.check("http", "POST", "/api/assistant/conversations/app", ROLE_DEVELOPER, "app")

    def test_terminal_always_developer(self):
        self.check("http", "GET", "/api/terminal/app", ROLE_DEVELOPER, "app")
        self.check("websocket", "GET", "/api/terminal/ws/app/t1", ROLE_DEVELOPER, "app")

    def test_websockets(self):
        self.check("websocket", "GET", "/ws/projects/app", ROLE_VIEWER, "app")
        self.check("websocket", "GET", "/api/assistant/ws/app", ROLE_DEVELOPER, "app")
        self.check("websocket", "GET", "/api/spec/ws/app", ROLE_DEVELOPER, "app")
        self.check("websocket", "GET", "/api/expand/ws/app", ROLE_DEVELOPER, "app")

    def test_global_routes(self):
        self.check("http", "GET", "/api/projects", ROLE_NONE, None)
        self.check("http", "GET", "/api/settings", ROLE_NONE, None)
        self.check("http", "GET", "/", ROLE_NONE, None)
        self.check("http", "POST", "/api/projects", ROLE_ADMIN, None)
        self.check("http", "PATCH", "/api/settings", ROLE_ADMIN, None)
        self.check("http", "GET", "/api/filesystem/list", ROLE_ADMIN, None)
        self.check("http", "POST", "/api/scaffold/run", ROLE_ADMIN, None)
        self.check("http", "GET", "/api/assistant/sessions", ROLE_ADMIN, None)


def _make_client(env, roles_yaml=ROLES_YAML, client_host="127.0.0.1"):
    tmp = tempfile.TemporaryDirectory()
    path = Path(tmp.name) / "auth.yaml"
    path.write_text(roles_yaml)
    settings = load_auth_settings({"AUTOFORGE_AUTH_MODE": "header", "AUTOFORGE_AUTH_CONFIG": str(path), **env})

    app = FastAPI()

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    @app.get("/api/whoami")
    async def whoami(request: Request):
        user = get_request_user(request)
        return {"user": user.name if user else None, "groups": list(user.groups) if user else []}

    @app.get("/api/projects/{name}/features")
    async def features(name: str):
        return {"project": name}

    @app.post("/api/projects/{name}/agent/start")
    async def start(name: str):
        return {"started": name}

    @app.patch("/api/settings")
    async def settings_patch():
        return {"ok": True}

    @app.websocket("/ws/projects/{name}")
    async def ws(websocket: WebSocket, name: str):
        await websocket.accept()
        await websocket.send_text(name)
        await websocket.close()

    app.add_middleware(AuthMiddleware, settings=settings, store=RoleConfigStore(path))
    client = TestClient(app, client=(client_host, 50000))
    client._tmp = tmp  # keep tempdir alive
    return client


class TestMiddleware(unittest.TestCase):
    def test_health_is_public(self):
        client = _make_client({}, client_host="203.0.113.9")
        assert client.get("/api/health").status_code == 200

    def test_untrusted_client_rejected(self):
        client = _make_client({}, client_host="203.0.113.9")
        r = client.get("/api/whoami", headers={"X-Forwarded-User": "alice"})
        assert r.status_code == 403
        assert "trusted" in r.json()["detail"]

    def test_trusted_cidr(self):
        client = _make_client({"AUTOFORGE_AUTH_TRUSTED_PROXIES": "10.0.0.0/8"}, client_host="10.1.2.3")
        assert client.get("/api/whoami", headers={"X-Forwarded-User": "carol"}).status_code == 200

    def test_missing_user_401(self):
        client = _make_client({})
        assert client.get("/api/whoami").status_code == 401

    def test_identity_and_groups_exposed(self):
        client = _make_client({"AUTOFORGE_AUTH_GROUPS_HEADER": "X-authentik-groups"})
        r = client.get("/api/whoami", headers={"X-Forwarded-User": "carol", "X-authentik-groups": "staff|qa"})
        assert r.json() == {"user": "carol", "groups": ["staff", "qa"]}

    def test_proxy_secret(self):
        client = _make_client({"AUTOFORGE_AUTH_PROXY_SECRET": "s3cret"})
        h = {"X-Forwarded-User": "carol"}
        assert client.get("/api/whoami", headers=h).status_code == 403
        assert client.get("/api/whoami", headers={**h, "X-AutoForge-Proxy-Secret": "nope"}).status_code == 403
        assert client.get("/api/whoami", headers={**h, "X-AutoForge-Proxy-Secret": "s3cret"}).status_code == 200

    def test_project_roles_enforced(self):
        client = _make_client({})
        viewer = {"X-Forwarded-User": "carol", "X-Forwarded-Groups": "staff"}
        dev = {"X-Forwarded-User": "bob"}
        outsider = {"X-Forwarded-User": "mallory"}

        assert client.get("/api/projects/my-app/features", headers=viewer).status_code == 200
        assert client.post("/api/projects/my-app/agent/start", headers=viewer).status_code == 403
        assert client.post("/api/projects/my-app/agent/start", headers=dev).status_code == 200
        assert client.post("/api/projects/other/agent/start", headers=dev).status_code == 403
        assert client.get("/api/projects/my-app/features", headers=outsider).status_code == 403

    def test_admin_only_global_writes(self):
        client = _make_client({})
        assert client.patch("/api/settings", headers={"X-Forwarded-User": "bob"}).status_code == 403
        assert client.patch("/api/settings", headers={"X-Forwarded-User": "alice"}).status_code == 200

    def test_cross_origin_write_rejected(self):
        client = _make_client({})
        h = {"X-Forwarded-User": "alice", "Origin": "http://evil.example"}
        assert client.patch("/api/settings", headers=h).status_code == 403
        h["Origin"] = "http://testserver"
        assert client.patch("/api/settings", headers=h).status_code == 200

    def test_websocket_roles(self):
        client = _make_client({})
        with client.websocket_connect("/ws/projects/my-app", headers={"X-Forwarded-User": "bob"}) as ws:
            assert ws.receive_text() == "my-app"

        with self.assertRaises(WebSocketDisconnect) as ctx:
            with client.websocket_connect("/ws/projects/other", headers={"X-Forwarded-User": "bob"}):
                pass
        assert ctx.exception.code == WS_CLOSE_FORBIDDEN

        with self.assertRaises(WebSocketDisconnect) as ctx:
            with client.websocket_connect("/ws/projects/my-app"):
                pass
        assert ctx.exception.code == WS_CLOSE_UNAUTHORIZED


if __name__ == "__main__":
    unittest.main()
