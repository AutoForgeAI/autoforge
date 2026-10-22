"""
Role assignments (``~/.autoforge/auth.yaml``).

Example::

    version: 1
    # Full access to everything: create/delete projects, global settings,
    # the server filesystem browser, and developer on every project.
    admins:
      users: [alice@example.com]
      groups: [autoforge-admins]

    # Role every signed-in user gets on projects not granted below:
    # none (default) | readonly | developer
    default_role: none

    projects:
      "*":                       # glob patterns match project names
        readonly:
          groups: [engineering]
      my-app:
        developer:
          users: [bob@example.com]
          groups: [my-app-devs]

Users are matched (case-insensitively) on their ``email``,
``preferred_username`` or ``sub`` claim; groups on the claims listed in
``AUTOFORGE_OIDC_GROUP_CLAIMS`` (Entra ID app roles / group object IDs,
Authentik group names, ...). A user's role on a project is the highest role
granted by any matching entry.
"""

import fnmatch
import logging
import threading
from dataclasses import dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any

import yaml

from .session import AuthUser

logger = logging.getLogger(__name__)


class Role(IntEnum):
    """Per-project role. Ordered so that a higher value grants more."""

    NONE = 0
    READONLY = 1
    DEVELOPER = 2

    @property
    def label(self) -> str:
        return self.name.lower()

    @classmethod
    def parse(cls, value: Any) -> "Role":
        text = str(value).strip().lower().replace("-", "").replace("_", "")
        aliases = {
            "none": cls.NONE,
            "readonly": cls.READONLY,
            "read": cls.READONLY,
            "viewer": cls.READONLY,
            "developer": cls.DEVELOPER,
            "dev": cls.DEVELOPER,
            "write": cls.DEVELOPER,
        }
        if text not in aliases:
            raise ValueError(f"Unknown role {value!r}; expected none, readonly or developer")
        return aliases[text]


@dataclass(frozen=True)
class Subjects:
    """A set of users and groups an assignment applies to."""

    users: frozenset[str] = frozenset()
    groups: frozenset[str] = frozenset()

    def matches(self, user: AuthUser) -> bool:
        if self.users and self.users & user.identifiers():
            return True
        return bool(self.groups and self.groups & set(user.groups))


@dataclass(frozen=True)
class ProjectGrant:
    pattern: str
    role: Role
    subjects: Subjects


@dataclass(frozen=True)
class RolesConfig:
    admins: Subjects = field(default_factory=Subjects)
    default_role: Role = Role.NONE
    grants: tuple[ProjectGrant, ...] = ()

    def is_admin(self, user: AuthUser) -> bool:
        return self.admins.matches(user)

    def role_for(self, user: AuthUser, project: str) -> Role:
        """Effective role of ``user`` on ``project``."""
        if self.is_admin(user):
            return Role.DEVELOPER
        role = self.default_role
        for grant in self.grants:
            if grant.role > role and fnmatch.fnmatchcase(project, grant.pattern) and grant.subjects.matches(user):
                role = grant.role
        return role


def _parse_subjects(raw: Any, where: str) -> Subjects:
    if raw is None:
        return Subjects()
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: expected a mapping with 'users' and/or 'groups'")

    def _names(key: str, casefold: bool) -> frozenset[str]:
        values = raw.get(key) or []
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            raise ValueError(f"{where}.{key}: expected a list")
        return frozenset(str(v).strip().lower() if casefold else str(v).strip() for v in values if str(v).strip())

    return Subjects(users=_names("users", casefold=True), groups=_names("groups", casefold=False))


def parse_roles_config(data: Any) -> RolesConfig:
    """Validate and convert the parsed YAML document into a RolesConfig."""
    if data is None:
        return RolesConfig()
    if not isinstance(data, dict):
        raise ValueError("auth config must be a mapping")

    admins = _parse_subjects(data.get("admins"), "admins")
    default_role = Role.parse(data.get("default_role", "none"))

    grants: list[ProjectGrant] = []
    projects = data.get("projects") or {}
    if not isinstance(projects, dict):
        raise ValueError("projects: expected a mapping of project name/pattern to roles")
    for pattern, roles in projects.items():
        if not isinstance(roles, dict):
            raise ValueError(f"projects.{pattern}: expected a mapping of role to users/groups")
        for role_name, subjects in roles.items():
            role = Role.parse(role_name)
            grants.append(ProjectGrant(str(pattern), role, _parse_subjects(subjects, f"projects.{pattern}.{role_name}")))

    return RolesConfig(admins=admins, default_role=default_role, grants=tuple(grants))


class _RolesFileCache:
    """Loads the roles file and reloads it when its mtime changes.

    An unreadable or invalid file yields an empty config (nobody has access)
    rather than keeping stale grants, so mistakes fail closed.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._path: Path | None = None
        self._mtime: float | None = None
        self._config = RolesConfig()

    def get(self, path: Path) -> RolesConfig:
        try:
            mtime: float | None = path.stat().st_mtime
        except OSError:
            mtime = None

        with self._lock:
            if path == self._path and mtime == self._mtime:
                return self._config
            self._path, self._mtime = path, mtime
            if mtime is None:
                logger.warning("Auth roles file %s not found; no user has access until it is created", path)
                self._config = RolesConfig()
                return self._config
            try:
                self._config = parse_roles_config(yaml.safe_load(path.read_text(encoding="utf-8")))
                logger.info("Loaded auth roles from %s", path)
            except (OSError, ValueError, yaml.YAMLError) as e:
                logger.error("Invalid auth roles file %s: %s; denying access until fixed", path, e)
                self._config = RolesConfig()
            return self._config


_cache = _RolesFileCache()


def default_roles_path() -> Path:
    from registry import get_config_dir

    return get_config_dir() / "auth.yaml"


def get_roles_config(path: Path | None = None) -> RolesConfig:
    """Return the current role assignments, reloading the file if it changed."""
    return _cache.get(path or default_roles_path())
