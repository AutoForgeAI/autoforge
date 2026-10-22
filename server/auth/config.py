"""
Auth settings loaded from environment variables.

All variables are optional unless ``AUTOFORGE_AUTH_MODE=oidc``:

=================================  =============================================
``AUTOFORGE_AUTH_MODE``            ``none`` (default) or ``oidc``
``AUTOFORGE_OIDC_ISSUER``          Issuer URL (required for oidc)
``AUTOFORGE_OIDC_CLIENT_ID``       Client / application ID (required for oidc)
``AUTOFORGE_OIDC_CLIENT_SECRET``   Client secret (omit for public PKCE clients)
``AUTOFORGE_OIDC_REDIRECT_URI``    Callback URL registered with the provider,
                                   e.g. ``https://host/api/auth/callback``.
                                   Derived from the request when unset.
``AUTOFORGE_OIDC_SCOPES``          Default ``openid profile email``
``AUTOFORGE_OIDC_GROUP_CLAIMS``    Claims holding group/role names,
                                   default ``groups,roles``
``AUTOFORGE_OIDC_PROVIDER_NAME``   Label for the login button (default ``SSO``)
``AUTOFORGE_AUTH_CONFIG``          Role file, default ``~/.autoforge/auth.yaml``
``AUTOFORGE_SESSION_TTL_HOURS``    Session lifetime, default 12
``AUTOFORGE_COOKIE_SECURE``        Force the Secure cookie flag on/off
                                   (default: on when the request is HTTPS)
``AUTOFORGE_AUTH_TRUSTED_ORIGINS`` Extra browser origins allowed to make
                                   state-changing requests (comma-separated),
                                   e.g. ``http://localhost:5173`` for Vite dev
=================================  =============================================
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

AUTH_MODE_NONE = "none"
AUTH_MODE_OIDC = "oidc"


def _csv(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(",") if part.strip())


def _bool_or_none(value: str | None) -> bool | None:
    if value is None or value.strip() == "":
        return None
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class AuthSettings:
    """Immutable snapshot of the auth configuration."""

    mode: str = AUTH_MODE_NONE
    issuer: str = ""
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = ""
    scopes: str = "openid profile email"
    group_claims: tuple[str, ...] = ("groups", "roles")
    provider_name: str = "SSO"
    roles_file: Path | None = None
    session_ttl_seconds: int = 12 * 3600
    cookie_secure: bool | None = None
    trusted_origins: tuple[str, ...] = field(default_factory=tuple)

    @property
    def enabled(self) -> bool:
        return self.mode != AUTH_MODE_NONE


def load_auth_settings(env: dict[str, str] | None = None) -> AuthSettings:
    """Build settings from environment variables.

    Raises:
        RuntimeError: if the configuration is invalid. The server refuses to
            start rather than silently running without the requested auth.
    """
    env = dict(os.environ) if env is None else env
    mode = env.get("AUTOFORGE_AUTH_MODE", "").strip().lower() or AUTH_MODE_NONE

    if mode not in (AUTH_MODE_NONE, AUTH_MODE_OIDC):
        raise RuntimeError(
            f"Invalid AUTOFORGE_AUTH_MODE={mode!r}; expected 'none' or 'oidc'."
        )
    if mode == AUTH_MODE_NONE:
        return AuthSettings()

    issuer = env.get("AUTOFORGE_OIDC_ISSUER", "").strip().rstrip("/")
    client_id = env.get("AUTOFORGE_OIDC_CLIENT_ID", "").strip()
    if not issuer or not client_id:
        raise RuntimeError(
            "AUTOFORGE_AUTH_MODE=oidc requires AUTOFORGE_OIDC_ISSUER and AUTOFORGE_OIDC_CLIENT_ID."
        )

    try:
        ttl_hours = float(env.get("AUTOFORGE_SESSION_TTL_HOURS", "") or 12)
    except ValueError as e:
        raise RuntimeError("AUTOFORGE_SESSION_TTL_HOURS must be a number.") from e
    if ttl_hours <= 0:
        raise RuntimeError("AUTOFORGE_SESSION_TTL_HOURS must be positive.")

    roles_file_env = env.get("AUTOFORGE_AUTH_CONFIG", "").strip()

    return AuthSettings(
        mode=mode,
        issuer=issuer,
        client_id=client_id,
        client_secret=env.get("AUTOFORGE_OIDC_CLIENT_SECRET", "").strip(),
        redirect_uri=env.get("AUTOFORGE_OIDC_REDIRECT_URI", "").strip(),
        scopes=env.get("AUTOFORGE_OIDC_SCOPES", "").strip() or "openid profile email",
        group_claims=_csv(env.get("AUTOFORGE_OIDC_GROUP_CLAIMS", "")) or ("groups", "roles"),
        provider_name=env.get("AUTOFORGE_OIDC_PROVIDER_NAME", "").strip() or "SSO",
        roles_file=Path(roles_file_env).expanduser() if roles_file_env else None,
        session_ttl_seconds=int(ttl_hours * 3600),
        cookie_secure=_bool_or_none(env.get("AUTOFORGE_COOKIE_SECURE")),
        trusted_origins=tuple(o.rstrip("/").lower() for o in _csv(env.get("AUTOFORGE_AUTH_TRUSTED_ORIGINS", ""))),
    )


_settings: AuthSettings | None = None


def get_auth_settings() -> AuthSettings:
    """Return the process-wide auth settings (loaded once from the environment)."""
    global _settings
    if _settings is None:
        _settings = load_auth_settings()
    return _settings


def reset_auth_settings(settings: AuthSettings | None = None) -> None:
    """Replace (or clear) the cached settings. Intended for tests."""
    global _settings
    _settings = settings
