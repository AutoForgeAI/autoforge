"""
OIDC Client
===========

Minimal OpenID Connect Authorization Code flow (with PKCE) used by
``AUTOFORGE_AUTH_MODE=oidc`` so AutoForge can sign users in directly with
Microsoft Entra ID, Authentik, Keycloak, ... without a reverse proxy.
ID tokens are verified against the provider's JWKS (signature, issuer,
audience, expiry and nonce).

This module only knows about OIDC; mapping claims to an AutoForge user and
roles happens in ``server/utils/auth.py``.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

logger = logging.getLogger(__name__)

# Signing algorithms we accept for ID tokens ("none" is never accepted)
_ASYMMETRIC_ALGS = ("RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512", "EdDSA")
_HMAC_ALGS = ("HS256", "HS384", "HS512")

_DISCOVERY_TTL = 3600
_PENDING_TTL = 600
_MAX_PENDING = 1000
_HTTP_TIMEOUT = 10.0


@dataclass(frozen=True)
class OIDCConfig:
    issuer: str
    client_id: str
    client_secret: str | None = None
    scopes: str = "openid profile email"
    # Claims that may hold group / role names (checked in order)
    roles_claims: tuple[str, ...] = ("groups", "roles")


class OIDCError(Exception):
    """Login failed; the message is safe to show to the user."""


@dataclass
class PendingLogin:
    nonce: str
    code_verifier: str
    next_path: str
    redirect_uri: str
    created: float


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def safe_next_path(value: str | None) -> str:
    """Only allow same-origin relative redirects after login (no open redirect)."""
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/"
    return value


class OIDCClient:
    def __init__(self, settings: OIDCConfig, http: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._http = http
        self._metadata: dict[str, Any] | None = None
        self._metadata_fetched = 0.0
        self._jwks: jwt.PyJWKSet | None = None
        self._pending: dict[str, PendingLogin] = {}

    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=_HTTP_TIMEOUT)
        return self._http

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    # ------------------------------------------------------------------
    # Provider metadata
    # ------------------------------------------------------------------

    async def metadata(self) -> dict[str, Any]:
        if self._metadata is None or time.time() - self._metadata_fetched > _DISCOVERY_TTL:
            url = f"{self.settings.issuer}/.well-known/openid-configuration"
            try:
                resp = await self._client().get(url)
                resp.raise_for_status()
                data = resp.json()
            except (httpx.HTTPError, ValueError) as e:
                logger.error("OIDC discovery failed for %s: %s", url, e)
                raise OIDCError("Identity provider is unreachable")
            for key in ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri"):
                if not data.get(key):
                    raise OIDCError(f"Identity provider metadata is missing '{key}'")
            self._metadata = data
            self._metadata_fetched = time.time()
            self._jwks = None
        return self._metadata

    async def _signing_key(self, kid: str | None) -> jwt.PyJWK:
        for attempt in range(2):
            if self._jwks is None or attempt == 1:
                meta = await self.metadata()
                try:
                    resp = await self._client().get(meta["jwks_uri"])
                    resp.raise_for_status()
                    self._jwks = jwt.PyJWKSet.from_dict(resp.json())
                except (httpx.HTTPError, ValueError, jwt.PyJWTError) as e:
                    logger.error("Failed to fetch OIDC JWKS: %s", e)
                    raise OIDCError("Could not load identity provider signing keys")
            keys = self._jwks.keys
            if kid is None and len(keys) == 1:
                return keys[0]
            for key in keys:
                if key.key_id == kid:
                    return key
            # Unknown kid: the provider may have rotated keys, refetch once
        raise OIDCError("ID token was signed with an unknown key")

    # ------------------------------------------------------------------
    # Authorization Code flow
    # ------------------------------------------------------------------

    def _prune_pending(self) -> None:
        now = time.time()
        for state in [s for s, p in self._pending.items() if now - p.created > _PENDING_TTL]:
            del self._pending[state]
        # Bound memory: unauthenticated clients can start logins freely
        while len(self._pending) >= _MAX_PENDING:
            self._pending.pop(next(iter(self._pending)))

    async def authorization_url(self, redirect_uri: str, next_path: str) -> str:
        meta = await self.metadata()
        self._prune_pending()

        state = secrets.token_urlsafe(32)
        pending = PendingLogin(
            nonce=secrets.token_urlsafe(32),
            code_verifier=secrets.token_urlsafe(64),
            next_path=safe_next_path(next_path),
            redirect_uri=redirect_uri,
            created=time.time(),
        )
        self._pending[state] = pending

        params = {
            "response_type": "code",
            "client_id": self.settings.client_id,
            "redirect_uri": redirect_uri,
            "scope": self.settings.scopes,
            "state": state,
            "nonce": pending.nonce,
            "code_challenge": _pkce_challenge(pending.code_verifier),
            "code_challenge_method": "S256",
        }
        sep = "&" if "?" in meta["authorization_endpoint"] else "?"
        return f"{meta['authorization_endpoint']}{sep}{urlencode(params)}"

    async def complete_login(self, code: str, state: str) -> tuple[dict[str, Any], str]:
        """Exchange the authorization code; return the ID token claims and the post-login path.

        When the ID token carries none of the configured group claims, claims
        from the userinfo endpoint are merged in (ID token claims win).
        """
        pending = self._pending.pop(state, None)
        if pending is None or time.time() - pending.created > _PENDING_TTL:
            raise OIDCError("Login session expired or invalid, please try again")

        meta = await self.metadata()
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": pending.redirect_uri,
            "client_id": self.settings.client_id,
            "code_verifier": pending.code_verifier,
        }
        if self.settings.client_secret:
            data["client_secret"] = self.settings.client_secret

        try:
            resp = await self._client().post(meta["token_endpoint"], data=data)
        except httpx.HTTPError as e:
            logger.error("OIDC token request failed: %s", e)
            raise OIDCError("Identity provider is unreachable")
        if resp.status_code != 200:
            logger.warning("OIDC token endpoint returned %s: %s", resp.status_code, resp.text[:500])
            raise OIDCError("Identity provider rejected the login")

        try:
            tokens = resp.json()
        except ValueError:
            raise OIDCError("Identity provider returned an invalid token response")
        id_token = tokens.get("id_token")
        if not id_token:
            raise OIDCError("Identity provider did not return an ID token (is the 'openid' scope set?)")

        claims = await self.verify_id_token(id_token, pending.nonce)

        # Some providers only expose groups via the userinfo endpoint
        access_token = tokens.get("access_token")
        if access_token and meta.get("userinfo_endpoint") and not self._has_role_claim(claims):
            claims = {**(await self._userinfo(meta["userinfo_endpoint"], access_token, claims["sub"])), **claims}

        return claims, pending.next_path

    async def verify_id_token(self, id_token: str, nonce: str) -> dict[str, Any]:
        meta = await self.metadata()
        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.PyJWTError:
            raise OIDCError("Malformed ID token")

        alg = header.get("alg")
        if alg in _HMAC_ALGS and self.settings.client_secret:
            key: Any = self.settings.client_secret
        elif alg in _ASYMMETRIC_ALGS:
            key = await self._signing_key(header.get("kid"))
        else:
            raise OIDCError(f"Unsupported ID token algorithm: {alg}")

        try:
            claims: dict[str, Any] = jwt.decode(
                id_token,
                key,
                algorithms=[alg],
                audience=self.settings.client_id,
                issuer=meta["issuer"],
                leeway=60,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
        except jwt.PyJWTError as e:
            logger.warning("ID token validation failed: %s", e)
            raise OIDCError("ID token validation failed")

        if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
            raise OIDCError("ID token nonce mismatch")
        return claims

    async def _userinfo(self, url: str, access_token: str, sub: str) -> dict[str, Any]:
        try:
            resp = await self._client().get(url, headers={"Authorization": f"Bearer {access_token}"})
            resp.raise_for_status()
            info = resp.json()
        except (httpx.HTTPError, ValueError) as e:
            logger.warning("OIDC userinfo request failed (continuing with ID token claims): %s", e)
            return {}
        # The userinfo response must be about the same subject
        if not isinstance(info, dict) or info.get("sub") != sub:
            return {}
        return info

    def _has_role_claim(self, claims: dict[str, Any]) -> bool:
        return any(c in claims for c in self.settings.roles_claims)

    async def end_session_url(self, post_logout_redirect_uri: str) -> str | None:
        try:
            meta = await self.metadata()
        except OIDCError:
            return None
        endpoint = meta.get("end_session_endpoint")
        if not endpoint:
            return None
        params = {"client_id": self.settings.client_id, "post_logout_redirect_uri": post_logout_redirect_uri}
        sep = "&" if "?" in endpoint else "?"
        return f"{endpoint}{sep}{urlencode(params)}"
