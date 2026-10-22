"""
Auth Router
===========

OIDC login/logout and "who am I" endpoints. All routes here are public in
the access policy; they work (and report ``enabled: false``) when auth is off.
"""

import html
import logging
import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from ..auth.config import AuthSettings, get_auth_settings
from ..auth.middleware import get_cookie
from ..auth.oidc import OIDCError, generate_pkce_pair, get_oidc_client, user_from_claims
from ..auth.roles import get_roles_config
from ..auth.session import LOGIN_STATE_COOKIE, LOGIN_TTL_SECONDS, SESSION_COOKIE, PendingLogin, get_session_store
from ..schemas import AuthMeResponse, AuthUserInfo, LogoutResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _require_enabled() -> AuthSettings:
    settings = get_auth_settings()
    if not settings.enabled:
        raise HTTPException(status_code=404, detail="Authentication is not enabled")
    return settings


def _safe_next(next_path: str | None) -> str:
    """Only allow same-site relative redirects after login (no open redirect)."""
    if not next_path or not next_path.startswith("/") or next_path.startswith("//") or "\\" in next_path:
        return "/"
    return next_path


def _redirect_uri(request: Request, settings: AuthSettings) -> str:
    return settings.redirect_uri or str(request.url_for("auth_callback"))


def _cookie_secure(request: Request, settings: AuthSettings, redirect_uri: str = "") -> bool:
    if settings.cookie_secure is not None:
        return settings.cookie_secure
    return request.url.scheme == "https" or redirect_uri.startswith("https://")


def _error_page(message: str, status_code: int = 400) -> HTMLResponse:
    body = (
        "<!doctype html><html><head><meta charset='utf-8'><title>Sign-in failed</title></head>"
        "<body style='font-family:system-ui,sans-serif;max-width:40rem;margin:4rem auto;padding:0 1rem'>"
        f"<h1>Sign-in failed</h1><p>{html.escape(message)}</p>"
        "<p><a href='/api/auth/login'>Try again</a></p></body></html>"
    )
    return HTMLResponse(body, status_code=status_code)


@router.get("/me", response_model=AuthMeResponse)
async def me(request: Request):
    """Return the auth status of the caller and their role on each project."""
    settings = get_auth_settings()
    if not settings.enabled:
        return AuthMeResponse(enabled=False, authenticated=False)

    session = get_session_store().get(get_cookie(request.scope, SESSION_COOKIE))
    if session is None:
        return AuthMeResponse(enabled=True, authenticated=False, provider_name=settings.provider_name)

    from registry import list_registered_projects

    user = session.user
    roles = get_roles_config(settings.roles_file)
    project_roles = {name: roles.role_for(user, name).label for name in list_registered_projects()}

    return AuthMeResponse(
        enabled=True,
        authenticated=True,
        provider_name=settings.provider_name,
        user=AuthUserInfo(
            sub=user.sub,
            name=user.display_name,
            email=user.email or None,
            username=user.username or None,
            groups=list(user.groups),
        ),
        is_admin=roles.is_admin(user),
        project_roles=project_roles,
    )


@router.get("/login")
async def login(request: Request, next: str | None = None):
    """Start the OIDC authorization code flow."""
    settings = _require_enabled()
    client = get_oidc_client(settings)

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    verifier, challenge = generate_pkce_pair()
    redirect_uri = _redirect_uri(request, settings)

    try:
        url = await client.authorization_url(redirect_uri, state, nonce, challenge)
    except OIDCError as e:
        logger.error("OIDC login failed: %s", e)
        return _error_page(f"The identity provider is unavailable: {e}", status_code=502)

    get_session_store().add_pending(
        state, PendingLogin(nonce=nonce, code_verifier=verifier, redirect_uri=redirect_uri, next_path=_safe_next(next))
    )
    response = RedirectResponse(url, status_code=302)
    # Binds the login to this browser so a forged callback cannot log the
    # victim into the attacker's account (login CSRF).
    response.set_cookie(
        LOGIN_STATE_COOKIE, state, max_age=LOGIN_TTL_SECONDS, httponly=True, samesite="lax",
        secure=_cookie_secure(request, settings, redirect_uri), path="/api/auth",
    )
    return response


@router.get("/callback", name="auth_callback")
async def callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    """Handle the redirect back from the identity provider."""
    settings = _require_enabled()
    store = get_session_store()

    if error:
        return _error_page(f"{error}: {error_description or 'the identity provider rejected the request'}")
    if not code or not state:
        return _error_page("Missing code or state parameter.")

    browser_state = get_cookie(request.scope, LOGIN_STATE_COOKIE) or ""
    pending = store.pop_pending(state)
    if pending is None or not secrets.compare_digest(browser_state, state):
        return _error_page("This sign-in link has expired or was not started from this browser.")

    client = get_oidc_client(settings)
    try:
        tokens = await client.exchange_code(code, pending.code_verifier, pending.redirect_uri)
        claims = await client.validate_id_token(tokens["id_token"], pending.nonce)
        if not any(claim in claims for claim in settings.group_claims):
            # Some providers only expose groups via userinfo.
            extra = await client.userinfo(str(tokens.get("access_token", "")))
            if extra.get("sub") == claims["sub"]:
                claims = {**extra, **claims}
    except OIDCError as e:
        logger.warning("OIDC callback failed: %s", e)
        return _error_page(str(e))

    user = user_from_claims(claims, settings.group_claims)
    sid = store.create(user, settings.session_ttl_seconds, id_token=str(tokens["id_token"]))
    logger.info("User %s signed in (groups: %s)", user.display_name, ", ".join(user.groups) or "-")

    response = RedirectResponse(pending.next_path, status_code=302)
    response.set_cookie(
        SESSION_COOKIE, sid, max_age=settings.session_ttl_seconds, httponly=True, samesite="lax",
        secure=_cookie_secure(request, settings, pending.redirect_uri), path="/",
    )
    response.delete_cookie(LOGIN_STATE_COOKIE, path="/api/auth")
    return response


@router.post("/logout", response_model=LogoutResponse)
async def logout(request: Request, response: Response):
    """End the session. Returns the provider's logout URL when it has one."""
    settings = get_auth_settings()
    session = get_session_store().delete(get_cookie(request.scope, SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")

    logout_url = None
    if settings.enabled and session is not None:
        home = str(request.base_url)
        logout_url = await get_oidc_client(settings).end_session_url(session.id_token, home)
    return LogoutResponse(logout_url=logout_url)
