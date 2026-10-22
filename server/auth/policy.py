"""
Route access policy.

Maps an HTTP method + path (or WebSocket path) to the access level required
to use it. Keeping the whole policy in one table makes it easy to audit, and
anything not listed under ``/api`` or ``/ws`` requires admin (deny by
default), so a new router cannot accidentally become readable by everyone.
"""

import re
from dataclasses import dataclass
from enum import Enum

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class Access(Enum):
    PUBLIC = "public"            # no session needed (login flow, health, static UI)
    AUTHENTICATED = "authenticated"  # any signed-in user
    READ = "read"                # readonly or developer on the project
    WRITE = "write"              # developer on the project
    ADMIN = "admin"              # global admin


@dataclass(frozen=True)
class Requirement:
    access: Access
    project: str | None = None


# Shorthands for the rule table: (read access, write access)
_READ_WRITE = (Access.READ, Access.WRITE)
_WRITE_ONLY = (Access.WRITE, Access.WRITE)
_ADMIN_ONLY = (Access.ADMIN, Access.ADMIN)

_P = r"(?P<project>[^/]+)"

# (pattern, (access for safe methods, access for other methods)).
# First match wins. ``project`` group names the project the rule is scoped to.
_RULES: list[tuple[re.Pattern[str], tuple[Access, Access]]] = [
    (re.compile(p), access)
    for p, access in [
        # Auth endpoints and health check are public
        (r"^/api/auth(/.*)?$", (Access.PUBLIC, Access.PUBLIC)),
        (r"^/api/health$", (Access.PUBLIC, Access.PUBLIC)),
        # Global, non-project endpoints
        (r"^/api/setup/status$", (Access.AUTHENTICATED, Access.ADMIN)),
        (r"^/api/settings(/.*)?$", (Access.AUTHENTICATED, Access.ADMIN)),
        # The project list is filtered per user inside the router
        (r"^/api/projects/?$", (Access.AUTHENTICATED, Access.ADMIN)),
        (r"^/api/filesystem(/.*)?$", _ADMIN_ONLY),
        (r"^/api/scaffold(/.*)?$", _ADMIN_ONLY),
        # Project resources
        (rf"^/api/projects/{_P}/?$", (Access.READ, Access.ADMIN)),  # GET detail / DELETE project
        (rf"^/api/projects/{_P}/(prompts|stats|settings|reset)/?$", _READ_WRITE),
        (rf"^/api/projects/{_P}/(agent|features|schedules|devserver)(/.*)?$", _READ_WRITE),
        (rf"^/ws/projects/{_P}$", (Access.READ, Access.READ)),
        # Interactive sessions that run Claude or a shell require developer
        (rf"^/api/terminal/ws/{_P}/[^/]+$", _WRITE_ONLY),
        (rf"^/api/terminal/{_P}(/.*)?$", _WRITE_ONLY),
        (rf"^/api/spec/ws/{_P}$", _WRITE_ONLY),
        (rf"^/api/spec/(sessions|status)/{_P}$", _READ_WRITE),
        (rf"^/api/expand/ws/{_P}$", _WRITE_ONLY),
        (rf"^/api/expand/sessions/{_P}$", _READ_WRITE),
        # The assistant can create features, so chatting requires developer
        (rf"^/api/assistant/ws/{_P}$", _WRITE_ONLY),
        (rf"^/api/assistant/sessions/{_P}$", _READ_WRITE),
        (rf"^/api/assistant/conversations/{_P}(/.*)?$", _READ_WRITE),
    ]
]


def required_access(method: str, path: str) -> Requirement:
    """Return the access needed for ``method`` on ``path``.

    WebSocket handshakes should pass ``"GET"`` as the method.
    """
    if not (path == "/api" or path.startswith("/api/") or path == "/ws" or path.startswith("/ws/")):
        # Static UI assets and SPA routes: the login page must load.
        return Requirement(Access.PUBLIC)

    safe = method.upper() in SAFE_METHODS
    for pattern, (read_access, write_access) in _RULES:
        match = pattern.match(path)
        if match:
            project = match.groupdict().get("project")
            return Requirement(read_access if safe else write_access, project)

    return Requirement(Access.ADMIN)
