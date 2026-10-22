"""
Authentication & Role-Based Access Control
==========================================

Optional auth layer for exposing the UI on a LAN or behind a reverse proxy.

Two ways to identify users:

* ``header`` - trust the identity headers set by an authenticating reverse
  proxy ("forward auth"), which is how Authentik's proxy outpost,
  oauth2-proxy (Entra ID, Google, GitHub, Keycloak, ...), Authelia, Pomerium
  and Cloudflare Access all work. The proxy handles login/SSO.
* ``oidc`` - AutoForge signs users in itself with an OpenID Connect provider
  (Entra ID, Authentik, Keycloak, ...) and keeps a server-side session,
  so no proxy is needed (see ``server/utils/oidc.py``).

Either way AutoForge maps the user and their groups onto roles defined in a
YAML file and enforces them on every HTTP request and WebSocket handshake.

Disabled by default (``AUTOFORGE_AUTH_MODE`` unset/``none``): behaviour is
exactly as before.

Environment variables:

* ``AUTOFORGE_AUTH_MODE`` - ``none`` (default), ``header`` or ``oidc``.
* ``AUTOFORGE_AUTH_USER_HEADER`` - header carrying the username
  (default ``X-Forwarded-User``; Authentik: ``X-authentik-username``).
* ``AUTOFORGE_AUTH_GROUPS_HEADER`` - header carrying the user's groups,
  separated by ``,`` or ``|`` (default ``X-Forwarded-Groups``;
  Authentik: ``X-authentik-groups``).
* ``AUTOFORGE_AUTH_TRUSTED_PROXIES`` - comma-separated IPs/CIDRs allowed to
  send identity headers (default ``127.0.0.1,::1``). ``*`` disables the IP
  check (only sensible together with a proxy secret).
* ``AUTOFORGE_AUTH_PROXY_SECRET`` - optional shared secret the proxy must send
  in ``X-AutoForge-Proxy-Secret``.
* ``AUTOFORGE_AUTH_CONFIG`` - path to the roles file
  (default ``~/.autoforge/auth.yaml``). Reloaded automatically when it changes.

OIDC mode only:

* ``AUTOFORGE_OIDC_ISSUER`` / ``AUTOFORGE_OIDC_CLIENT_ID`` - required.
* ``AUTOFORGE_OIDC_CLIENT_SECRET`` - optional (public client; PKCE is always used).
* ``AUTOFORGE_OIDC_REDIRECT_URI`` - optional, defaults to ``<request base>/api/auth/callback``
  (set it when behind a proxy that changes the scheme/host).
* ``AUTOFORGE_OIDC_SCOPES`` - default ``openid profile email``.
* ``AUTOFORGE_OIDC_GROUPS_CLAIM`` - comma-separated claims holding group/role
  names (default ``groups,roles``: Authentik groups, Entra ID app roles).
* ``AUTOFORGE_SESSION_TTL_HOURS`` - session lifetime (default 12).
* ``AUTOFORGE_COOKIE_SECURE`` - ``auto`` (default: when served over https), ``true`` or ``false``.

In OIDC mode, users match ``users:`` entries by ``preferred_username``,
``email`` or ``sub``.

Roles (lowest to highest): ``none`` < ``viewer`` < ``developer`` < ``admin``.

* ``viewer``    - read-only access to a project (GET requests, live updates).
* ``developer`` - full control of a project (agent, features, terminal,
  dev server, chats, schedules, prompts).
* ``admin``     - everything, including global settings, the server
  filesystem browser and creating/deleting projects.
"""

from __future__ import annotations

import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import time
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass, field
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

import yaml

from .oidc import OIDCClient, OIDCConfig

logger = logging.getLogger(__name__)

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

ROLE_NONE = "none"
ROLE_VIEWER = "viewer"
ROLE_DEVELOPER = "developer"
ROLE_ADMIN = "admin"

ROLE_LEVELS: dict[str, int] = {
    ROLE_NONE: 0,
    ROLE_VIEWER: 1,
    ROLE_DEVELOPER: 2,
    ROLE_ADMIN: 3,
}

# Roles assignable per project (admin is global-only)
PROJECT_ROLES = (ROLE_VIEWER, ROLE_DEVELOPER)

PROXY_SECRET_HEADER = "x-autoforge-proxy-secret"

SESSION_COOKIE = "autoforge_session"
LOGIN_PATH = "/api/auth/login"

WS_CLOSE_UNAUTHORIZED = 4401
WS_CLOSE_FORBIDDEN = 4403

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

DEFAULT_CONFIG_PATH = Path.home() / ".autoforge" / "auth.yaml"


# ============================================================================
# Settings
# ============================================================================

@dataclass(frozen=True)
class AuthSettings:
    """Auth settings loaded from environment variables."""

    mode: str = "none"
    user_header: str = "x-forwarded-user"
    groups_header: str = "x-forwarded-groups"
    trusted_proxies: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...] = ()
    trust_any_proxy: bool = False
    proxy_secret: str | None = None
    config_path: Path = DEFAULT_CONFIG_PATH
    # OIDC mode
    oidc: OIDCConfig | None = None
    oidc_redirect_uri: str | None = None
    session_ttl_seconds: int = 12 * 3600
    cookie_secure: bool | None = None  # None = secure when the request is https

    @property
    def enabled(self) -> bool:
        return self.mode in ("header", "oidc")


def _parse_networks(value: str) -> tuple[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...], bool]:
    networks = []
    trust_any = False
    for raw in value.split(","):
        item = raw.strip()
        if not item:
            continue
        if item == "*":
            trust_any = True
            continue
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid AUTOFORGE_AUTH_TRUSTED_PROXIES entry: %r", item)
    return tuple(networks), trust_any


def load_auth_settings(env: MutableMapping[str, str] | None = None) -> AuthSettings:
    """Build AuthSettings from environment variables."""
    env = os.environ if env is None else env

    mode = env.get("AUTOFORGE_AUTH_MODE", "none").strip().lower() or "none"
    if mode not in ("none", "header", "oidc"):
        raise ValueError(f"Invalid AUTOFORGE_AUTH_MODE {mode!r} (expected 'none', 'header' or 'oidc')")

    networks, trust_any = _parse_networks(env.get("AUTOFORGE_AUTH_TRUSTED_PROXIES", "127.0.0.1,::1"))
    config_path = env.get("AUTOFORGE_AUTH_CONFIG")

    oidc: OIDCConfig | None = None
    ttl_seconds = 12 * 3600
    cookie_secure: bool | None = None
    if mode == "oidc":
        issuer = env.get("AUTOFORGE_OIDC_ISSUER", "").strip().rstrip("/")
        client_id = env.get("AUTOFORGE_OIDC_CLIENT_ID", "").strip()
        missing = [n for n, v in (("AUTOFORGE_OIDC_ISSUER", issuer), ("AUTOFORGE_OIDC_CLIENT_ID", client_id)) if not v]
        if missing:
            raise ValueError(f"AUTOFORGE_AUTH_MODE=oidc requires {', '.join(missing)}")
        claims = env.get("AUTOFORGE_OIDC_GROUPS_CLAIM", "groups,roles")
        oidc = OIDCConfig(
            issuer=issuer,
            client_id=client_id,
            client_secret=env.get("AUTOFORGE_OIDC_CLIENT_SECRET") or None,
            scopes=env.get("AUTOFORGE_OIDC_SCOPES", "").strip() or "openid profile email",
            roles_claims=tuple(c.strip() for c in claims.split(",") if c.strip()),
        )
        try:
            ttl_hours = float(env.get("AUTOFORGE_SESSION_TTL_HOURS", "12") or "12")
        except ValueError:
            raise ValueError("AUTOFORGE_SESSION_TTL_HOURS must be a number")
        if ttl_hours <= 0:
            raise ValueError("AUTOFORGE_SESSION_TTL_HOURS must be positive")
        ttl_seconds = int(ttl_hours * 3600)
        secure = env.get("AUTOFORGE_COOKIE_SECURE", "auto").strip().lower()
        cookie_secure = None if secure in ("", "auto") else secure in ("1", "true", "yes")

    return AuthSettings(
        mode=mode,
        user_header=env.get("AUTOFORGE_AUTH_USER_HEADER", "X-Forwarded-User").strip().lower(),
        groups_header=env.get("AUTOFORGE_AUTH_GROUPS_HEADER", "X-Forwarded-Groups").strip().lower(),
        trusted_proxies=networks,
        trust_any_proxy=trust_any,
        proxy_secret=env.get("AUTOFORGE_AUTH_PROXY_SECRET") or None,
        config_path=Path(config_path).expanduser() if config_path else DEFAULT_CONFIG_PATH,
        oidc=oidc,
        oidc_redirect_uri=env.get("AUTOFORGE_OIDC_REDIRECT_URI") or None,
        session_ttl_seconds=ttl_seconds,
        cookie_secure=cookie_secure,
    )


# ============================================================================
# Role configuration
# ============================================================================

@dataclass(frozen=True)
class Principals:
    """A set of users and groups (stored lowercase)."""

    users: frozenset[str] = frozenset()
    groups: frozenset[str] = frozenset()

    def matches(self, user: AuthUser) -> bool:
        if any(n.lower() in self.users for n in (user.name, *user.aliases)):
            return True
        return any(g.lower() in self.groups for g in user.groups)


@dataclass(frozen=True)
class RoleConfig:
    """Parsed roles file."""

    default_role: str = ROLE_NONE
    admins: Principals = Principals()
    # project name ("*" = all projects) -> role -> principals
    projects: dict[str, dict[str, Principals]] = field(default_factory=dict)


def _parse_principals(raw: Any, where: str) -> Principals:
    if raw is None:
        return Principals()
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: expected a mapping with 'users' and/or 'groups'")

    def _names(key: str) -> frozenset[str]:
        values = raw.get(key) or []
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            raise ValueError(f"{where}.{key}: expected a list")
        return frozenset(str(v).strip().lower() for v in values if str(v).strip())

    return Principals(users=_names("users"), groups=_names("groups"))


def parse_role_config(data: Any) -> RoleConfig:
    """Validate and parse the roles YAML document."""
    if data is None:
        return RoleConfig()
    if not isinstance(data, dict):
        raise ValueError("auth config must be a mapping")

    default_role = str(data.get("default_role", ROLE_NONE)).strip().lower()
    if default_role not in (ROLE_NONE, *PROJECT_ROLES):
        raise ValueError(f"default_role must be one of none, viewer, developer (got {default_role!r})")

    admins = _parse_principals(data.get("admins"), "admins")

    projects: dict[str, dict[str, Principals]] = {}
    raw_projects = data.get("projects") or {}
    if not isinstance(raw_projects, dict):
        raise ValueError("projects: expected a mapping of project name -> roles")
    for project, roles in raw_projects.items():
        if not isinstance(roles, dict):
            raise ValueError(f"projects.{project}: expected a mapping of role -> principals")
        parsed: dict[str, Principals] = {}
        for role, principals in roles.items():
            role_name = str(role).strip().lower()
            if role_name not in PROJECT_ROLES:
                raise ValueError(
                    f"projects.{project}: unknown role {role!r} (expected viewer or developer)"
                )
            parsed[role_name] = _parse_principals(principals, f"projects.{project}.{role_name}")
        projects[str(project)] = parsed

    return RoleConfig(default_role=default_role, admins=admins, projects=projects)


class RoleConfigStore:
    """Loads the roles file and reloads it when its mtime changes.

    An invalid or missing file results in an empty config (nobody has access
    except via ``default_role: none`` -> no access), i.e. fail closed.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self._mtime: float | None = None
        self._config = RoleConfig()
        self._warned_missing = False

    def get(self) -> RoleConfig:
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            if not self._warned_missing:
                logger.warning("Auth roles file %s not found; no user has access", self.path)
                self._warned_missing = True
            self._mtime = None
            self._config = RoleConfig()
            return self._config

        if mtime != self._mtime:
            self._mtime = mtime
            self._warned_missing = False
            try:
                with open(self.path, encoding="utf-8") as f:
                    self._config = parse_role_config(yaml.safe_load(f))
                logger.info("Loaded auth roles from %s", self.path)
            except (OSError, ValueError, yaml.YAMLError) as e:
                logger.error("Invalid auth roles file %s: %s (denying all access)", self.path, e)
                self._config = RoleConfig()
        return self._config


# ============================================================================
# Users and role resolution
# ============================================================================

@dataclass(frozen=True)
class AuthUser:
    """An authenticated user (from proxy headers or an OIDC login)."""

    name: str
    groups: tuple[str, ...] = ()
    # Other identifiers that ``users:`` entries may match (OIDC: email, sub)
    aliases: tuple[str, ...] = ()
    display_name: str | None = None


def user_from_claims(claims: dict[str, Any], groups_claims: tuple[str, ...]) -> AuthUser:
    """Build an AuthUser from OIDC ID token / userinfo claims."""
    sub = str(claims["sub"])
    email = claims.get("email")
    username = claims.get("preferred_username") or claims.get("upn") or email or sub

    groups: list[str] = []
    for claim in groups_claims:
        value = claims.get(claim)
        if isinstance(value, str):
            groups.append(value)
        elif isinstance(value, list):
            groups.extend(str(v) for v in value if isinstance(v, (str, int)))

    aliases = tuple(dict.fromkeys(str(a) for a in (email, sub) if a and a != username))
    return AuthUser(
        name=str(username),
        groups=tuple(dict.fromkeys(groups)),
        aliases=aliases,
        display_name=claims.get("name"),
    )


class SessionStore:
    """In-memory OIDC sessions keyed by an opaque random cookie value.

    Server-side so logout revokes immediately; a restart signs everyone out.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._sessions: dict[str, tuple[AuthUser, float]] = {}

    def create(self, user: AuthUser) -> str:
        now = time.time()
        for token in [t for t, (_, exp) in self._sessions.items() if exp < now]:
            del self._sessions[token]
        token = secrets.token_urlsafe(32)
        self._sessions[token] = (user, now + self.ttl_seconds)
        return token

    def get(self, token: str | None) -> AuthUser | None:
        if not token:
            return None
        entry = self._sessions.get(token)
        if entry is None:
            return None
        user, expires = entry
        if expires < time.time():
            self._sessions.pop(token, None)
            return None
        return user

    def delete(self, token: str | None) -> None:
        if token:
            self._sessions.pop(token, None)


def session_token(headers: dict[str, str]) -> str | None:
    """Extract the session cookie value from lowercase request headers."""
    raw = headers.get("cookie")
    if not raw:
        return None
    cookie: SimpleCookie = SimpleCookie()
    try:
        cookie.load(raw)
    except Exception:
        return None
    morsel = cookie.get(SESSION_COOKIE)
    return morsel.value if morsel is not None and morsel.value else None


def is_admin(user: AuthUser, config: RoleConfig) -> bool:
    return config.admins.matches(user)


def project_role(user: AuthUser, project: str, config: RoleConfig) -> str:
    """Return the effective role of ``user`` on ``project``."""
    if is_admin(user, config):
        return ROLE_ADMIN

    best = config.default_role
    for key in ("*", project):
        for role, principals in config.projects.get(key, {}).items():
            if ROLE_LEVELS[role] > ROLE_LEVELS[best] and principals.matches(user):
                best = role
    return best


def has_role(actual: str, required: str) -> bool:
    return ROLE_LEVELS[actual] >= ROLE_LEVELS[required]


# ============================================================================
# Route -> required permission
# ============================================================================

# Patterns extracting the project name from project-scoped routes.
# Order matters: more specific patterns first.
_PROJECT_PATTERNS = [
    re.compile(r"^/api/projects/(?P<project>[^/]+)(?:/|$)"),
    re.compile(r"^/api/terminal/ws/(?P<project>[^/]+)(?:/|$)"),
    re.compile(r"^/api/terminal/(?P<project>[^/]+)(?:/|$)"),
    re.compile(r"^/api/assistant/(?:conversations|sessions|ws)/(?P<project>[^/]+)(?:/|$)"),
    re.compile(r"^/api/spec/(?:sessions|status|ws)/(?P<project>[^/]+)(?:/|$)"),
    re.compile(r"^/api/expand/(?:sessions|ws)/(?P<project>[^/]+)(?:/|$)"),
    re.compile(r"^/ws/projects/(?P<project>[^/]+)(?:/|$)"),
]

# Global routes restricted to admins regardless of method.
_ADMIN_ONLY_PREFIXES = (
    "/api/filesystem",
    "/api/scaffold",
    "/api/assistant/sessions",
    "/api/spec/sessions",
    "/api/expand/sessions",
)

# Routes reachable without authentication (e.g. proxy health checks).
_PUBLIC_PATHS = frozenset({"/api/health"})

# Additionally public in OIDC mode: the login flow itself, and /me so the UI
# can tell "signed out" apart from "no access".
_OIDC_PUBLIC_PATHS = frozenset({"/api/auth/login", "/api/auth/callback", "/api/auth/logout", "/api/auth/me"})


@dataclass(frozen=True)
class Requirement:
    """Permission needed for a request: a project role, or a global one."""

    role: str
    project: str | None = None


def required_permission(scope_type: str, method: str, path: str) -> Requirement:
    """Decide what role a request needs.

    Project-scoped routes need ``viewer`` for reads and ``developer`` for
    writes. The terminal and the interactive chat sockets (assistant, spec,
    expand) always need ``developer``. Deleting a project and all non-project
    writes need ``admin``. Other non-project reads only need a logged-in user.
    """
    for pattern in _PROJECT_PATTERNS:
        m = pattern.match(path)
        if not m:
            continue
        project = m.group("project")

        if path.startswith("/api/terminal/"):
            return Requirement(ROLE_DEVELOPER, project)
        if scope_type == "websocket":
            if path.startswith("/ws/projects/"):
                return Requirement(ROLE_VIEWER, project)
            return Requirement(ROLE_DEVELOPER, project)
        if method == "DELETE" and re.fullmatch(r"/api/projects/[^/]+/?", path):
            return Requirement(ROLE_ADMIN)
        if method in SAFE_METHODS:
            return Requirement(ROLE_VIEWER, project)
        return Requirement(ROLE_DEVELOPER, project)

    if any(path == p or path.startswith(p + "/") for p in _ADMIN_ONLY_PREFIXES):
        return Requirement(ROLE_ADMIN)
    if scope_type == "websocket" or method not in SAFE_METHODS:
        return Requirement(ROLE_ADMIN)
    return Requirement(ROLE_NONE)


# ============================================================================
# Request helpers
# ============================================================================

def _client_trusted(settings: AuthSettings, client_host: str | None) -> bool:
    if settings.trust_any_proxy:
        return True
    if not client_host:
        return False
    try:
        addr = ipaddress.ip_address(client_host)
    except ValueError:
        return False
    return any(addr in net for net in settings.trusted_proxies)


def _split_groups(value: str) -> tuple[str, ...]:
    return tuple(g.strip() for g in re.split(r"[,|]", value) if g.strip())


def _hostname(value: str) -> str | None:
    try:
        return urlparse(value if "//" in value else f"//{value}").hostname
    except ValueError:
        return None


def get_request_user(request: Any) -> AuthUser | None:
    """Return the AuthUser attached by AuthMiddleware (None when auth is off)."""
    state = request.scope.get("state") or {}
    user = state.get("auth_user")
    return user if isinstance(user, AuthUser) else None


# ============================================================================
# Module-level runtime (configured from server/main.py)
# ============================================================================

_settings: AuthSettings = AuthSettings()
_store: RoleConfigStore | None = None
_oidc_client: OIDCClient | None = None
_sessions: SessionStore | None = None


def configure(settings: AuthSettings, oidc_client: OIDCClient | None = None) -> None:
    """Install settings for the running server (``oidc_client`` is for tests)."""
    global _settings, _store, _oidc_client, _sessions
    _settings = settings
    _store = RoleConfigStore(settings.config_path) if settings.enabled else None
    if settings.mode == "oidc" and settings.oidc is not None:
        _oidc_client = oidc_client or OIDCClient(settings.oidc)
        _sessions = SessionStore(settings.session_ttl_seconds)
    else:
        _oidc_client = None
        _sessions = None


def get_oidc_client() -> OIDCClient | None:
    return _oidc_client


def get_sessions() -> SessionStore | None:
    return _sessions


def get_settings() -> AuthSettings:
    return _settings


def get_store() -> RoleConfigStore | None:
    return _store


def get_role_config() -> RoleConfig:
    return _store.get() if _store is not None else RoleConfig()


def can_view_project(request: Any, project: str) -> bool:
    """True if the current request may read ``project`` (always True when auth is off)."""
    if not _settings.enabled:
        return True
    user = get_request_user(request)
    if user is None:
        return False
    return has_role(project_role(user, project, get_role_config()), ROLE_VIEWER)


# ============================================================================
# Middleware
# ============================================================================

class AuthMiddleware:
    """Pure-ASGI middleware enforcing login and roles on HTTP and WebSocket."""

    def __init__(self, app: Any, settings: AuthSettings, store: RoleConfigStore) -> None:
        self.app = app
        self.settings = settings
        self.store = store

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        scope_type = scope["type"]
        if scope_type not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        method: str = scope.get("method", "GET").upper() if scope_type == "http" else "GET"

        if path in _PUBLIC_PATHS or (scope_type == "http" and method == "OPTIONS"):
            await self.app(scope, receive, send)
            return

        headers: dict[str, str] = {}
        for name, value in scope.get("headers", []):
            headers[name.decode("latin-1").lower()] = value.decode("latin-1")

        if self.settings.mode == "oidc":
            user = await self._oidc_user(scope, receive, send, path, method, headers)
        else:
            user = await self._header_user(scope, receive, send, headers)
        if user is None:
            return  # already denied / redirected

        # CSRF: auth rides on cookies (ours or the proxy's), so reject cross-site writes.
        if scope_type == "http" and method not in SAFE_METHODS:
            origin = headers.get("origin")
            if origin and _hostname(origin) != _hostname(headers.get("host", "")):
                await self._deny(scope, receive, send, 403, "Cross-origin request rejected")
                return

        config = self.store.get()
        req = required_permission(scope_type, method, path)

        if req.role == ROLE_ADMIN:
            allowed = is_admin(user, config)
        elif req.project is not None:
            allowed = has_role(project_role(user, req.project, config), req.role)
        else:
            allowed = True

        if not allowed:
            logger.info("Denied %s %s for user %r (needs %s)", method, path, user.name, req.role)
            needed = f"'{req.role}' role on project '{req.project}'" if req.project else f"'{req.role}' role"
            await self._deny(scope, receive, send, 403, f"Forbidden: requires {needed}")
            return

        scope.setdefault("state", {})["auth_user"] = user
        await self.app(scope, receive, send)

    async def _oidc_user(
        self, scope: Scope, receive: Receive, send: Send, path: str, method: str, headers: dict[str, str],
    ) -> AuthUser | None:
        """Resolve the user from the session cookie; redirect or deny when signed out."""
        sessions = get_sessions()
        user = sessions.get(session_token(headers)) if sessions is not None else None

        if path in _OIDC_PUBLIC_PATHS:
            # Login flow and /me: pass through, exposing the user if signed in
            scope.setdefault("state", {})["auth_user"] = user
            await self.app(scope, receive, send)
            return None

        if user is not None:
            return user

        is_page = scope["type"] == "http" and method == "GET" and not path.startswith(("/api/", "/ws/"))
        if is_page:
            # Browser navigation to the SPA: send it through the login first
            target = path + (f"?{scope['query_string'].decode('latin-1')}" if scope.get("query_string") else "")
            await send({
                "type": "http.response.start",
                "status": 302,
                "headers": [
                    (b"location", f"{LOGIN_PATH}?next={quote(target, safe='')}".encode("latin-1")),
                    (b"content-length", b"0"),
                ],
            })
            await send({"type": "http.response.body", "body": b""})
            return None

        await self._deny(scope, receive, send, 401, "Not authenticated", login_url=LOGIN_PATH)
        return None

    async def _header_user(
        self, scope: Scope, receive: Receive, send: Send, headers: dict[str, str],
    ) -> AuthUser | None:
        """Resolve the user from trusted reverse-proxy headers."""
        client = scope.get("client")
        client_host = client[0] if client else None

        if not _client_trusted(self.settings, client_host):
            await self._deny(scope, receive, send, 403, (
                "Request did not come from a trusted auth proxy. Add the proxy address to "
                "AUTOFORGE_AUTH_TRUSTED_PROXIES (or configure AUTOFORGE_AUTH_PROXY_SECRET)."
            ))
            return None

        if self.settings.proxy_secret is not None:
            provided = headers.get(PROXY_SECRET_HEADER, "")
            if not hmac.compare_digest(provided.encode(), self.settings.proxy_secret.encode()):
                await self._deny(scope, receive, send, 403, "Invalid or missing proxy secret")
                return None

        username = headers.get(self.settings.user_header, "").strip()
        if not username:
            await self._deny(scope, receive, send, 401, "Not authenticated")
            return None

        return AuthUser(name=username, groups=_split_groups(headers.get(self.settings.groups_header, "")))

    @staticmethod
    async def _deny(
        scope: Scope, receive: Receive, send: Send, status: int, detail: str, login_url: str | None = None,
    ) -> None:
        if scope["type"] == "websocket":
            message = await receive()
            if message["type"] == "websocket.connect":
                code = WS_CLOSE_UNAUTHORIZED if status == 401 else WS_CLOSE_FORBIDDEN
                await send({"type": "websocket.close", "code": code})
            return

        payload: dict[str, str] = {"detail": detail}
        if login_url:
            payload["login_url"] = login_url
        body = json.dumps(payload).encode()
        await send({
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
            ],
        })
        await send({"type": "http.response.body", "body": body})
