"""
Auth Router
===========

Exposes the current user's identity and roles so the UI can hide controls
the user is not allowed to use. Enforcement happens in AuthMiddleware.

In OIDC mode it also implements the login flow (login -> identity provider
-> callback -> session cookie) and logout.
"""

import html
import logging
import sys

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from ..schemas import AuthInfo
from ..services.chat_constants import ROOT_DIR
from ..utils import auth
from ..utils.oidc import OIDCClient, OIDCError, safe_next_path

# Ensure root is on sys.path for registry import
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

router = APIRouter(prefix="/api/auth", tags=["auth"])

logger = logging.getLogger(__name__)


@router.get("/me", response_model=AuthInfo)
async def get_current_user(request: Request) -> AuthInfo:
    """Return the authenticated user and their effective roles."""
    settings = auth.get_settings()
    if not settings.enabled:
        return AuthInfo(enabled=False, is_admin=True, default_role=auth.ROLE_ADMIN)

    user = auth.get_request_user(request)
    if user is None:
        # Signed out (OIDC mode); unreachable in header mode. Fail closed.
        return AuthInfo(enabled=True, mode=settings.mode, is_admin=False, default_role=auth.ROLE_NONE)

    from registry import list_registered_projects

    config = auth.get_role_config()
    admin = auth.is_admin(user, config)
    projects = {
        name: auth.project_role(user, name, config)
        for name in list_registered_projects()
    }
    return AuthInfo(
        enabled=True,
        mode=settings.mode,
        user=user.name,
        display_name=user.display_name,
        groups=list(user.groups),
        is_admin=admin,
        default_role=auth.ROLE_ADMIN if admin else config.default_role,
        projects={name: role for name, role in projects.items() if role != auth.ROLE_NONE},
    )


# ============================================================================
# OIDC login flow (AUTOFORGE_AUTH_MODE=oidc)
# ============================================================================

def _require_oidc() -> tuple[auth.AuthSettings, OIDCClient, auth.SessionStore]:
    settings = auth.get_settings()
    client = auth.get_oidc_client()
    sessions = auth.get_sessions()
    if settings.mode != "oidc" or client is None or sessions is None:
        raise HTTPException(status_code=404, detail="OIDC login is not enabled")
    return settings, client, sessions


def _login_error(message: str, status_code: int = 400) -> HTMLResponse:
    body = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Sign-in failed</title></head>"
        "<body style='font-family:sans-serif;max-width:32rem;margin:4rem auto'>"
        f"<h1>Sign-in failed</h1><p>{html.escape(message)}</p>"
        f"<p><a href='{auth.LOGIN_PATH}'>Try again</a></p></body></html>"
    )
    return HTMLResponse(body, status_code=status_code)


@router.get("/login")
async def login(request: Request, next: str = Query(default="/")):
    """Redirect the browser to the identity provider."""
    settings, client, _ = _require_oidc()
    redirect_uri = settings.oidc_redirect_uri or str(request.url_for("auth_callback"))
    try:
        url = await client.authorization_url(redirect_uri, safe_next_path(next))
    except OIDCError as e:
        return _login_error(str(e), status_code=502)
    return RedirectResponse(url, status_code=302)


@router.get("/callback", name="auth_callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    """Finish the login: verify the ID token and start a session."""
    settings, client, sessions = _require_oidc()
    if error:
        return _login_error(error_description or error)
    if not code or not state:
        return _login_error("Missing authorization code")

    try:
        claims, next_path = await client.complete_login(code, state)
    except OIDCError as e:
        return _login_error(str(e))

    assert settings.oidc is not None  # guaranteed by _require_oidc
    user = auth.user_from_claims(claims, settings.oidc.roles_claims)
    logger.info("User signed in: %s (groups: %s)", user.name, ", ".join(user.groups) or "-")

    secure = settings.cookie_secure if settings.cookie_secure is not None else request.url.scheme == "https"
    response = RedirectResponse(next_path, status_code=302)
    response.set_cookie(
        auth.SESSION_COOKIE,
        sessions.create(user),
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=secure,
        path="/",
    )
    return response


@router.post("/logout")
async def logout(request: Request):
    """End the session; returns the provider's logout URL when it has one."""
    _, client, sessions = _require_oidc()
    sessions.delete(request.cookies.get(auth.SESSION_COOKIE))
    end_session_url = await client.end_session_url(str(request.base_url))
    response = JSONResponse({"logged_out": True, "end_session_url": end_session_url})
    response.delete_cookie(auth.SESSION_COOKIE, path="/")
    return response
