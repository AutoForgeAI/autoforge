"""
Authentication & Authorization
==============================

Optional OpenID Connect (OIDC) login with a small role system for the web UI.

Disabled by default: with ``AUTOFORGE_AUTH_MODE`` unset (or ``none``) the
server behaves exactly as before. With ``AUTOFORGE_AUTH_MODE=oidc`` every API
and WebSocket request must carry a valid session, obtained by signing in with
any standards-compliant OIDC provider (Microsoft Entra ID, Authentik,
Keycloak, Google, ...).

Roles:

* ``admin`` - global: everything, including creating/deleting projects,
  global settings and the server filesystem browser.
* ``developer`` - per project: read and change the project (start agents,
  edit features, terminal, dev server, ...).
* ``readonly`` - per project: view the project only.

Role assignments live in ``~/.autoforge/auth.yaml`` (see
``examples/auth.yaml``) and are re-read whenever the file changes.
"""

from .config import AuthSettings, get_auth_settings, reset_auth_settings
from .middleware import AuthMiddleware
from .roles import Role, RolesConfig, get_roles_config
from .session import AuthUser, get_session_store

__all__ = [
    "AuthMiddleware",
    "AuthSettings",
    "AuthUser",
    "Role",
    "RolesConfig",
    "get_auth_settings",
    "get_roles_config",
    "get_session_store",
    "reset_auth_settings",
]
