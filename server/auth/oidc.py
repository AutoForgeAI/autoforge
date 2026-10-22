"""
Minimal OpenID Connect relying party (authorization code flow + PKCE).

Works with any provider that publishes ``/.well-known/openid-configuration``,
for example:

* Microsoft Entra ID: ``https://login.microsoftonline.com/<tenant-id>/v2.0``
* Authentik: ``https://authentik.example.com/application/o/<app-slug>/``
* Keycloak: ``https://keycloak.example.com/realms/<realm>``
"""

import asyncio
import base64
import hashlib
import logging
import secrets
import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

from .config import AuthSettings
from .session import AuthUser

logger = logging.getLogger(__name__)

_DISCOVERY_TTL_SECONDS = 3600
_HTTP_TIMEOUT = 15.0
_ASYMMETRIC_ALGS = ["RS256", "RS384", "RS512", "PS256", "PS384", "PS512", "ES256", "ES384", "ES512"]
_SYMMETRIC_ALGS = ["HS256", "HS384", "HS512"]


class OIDCError(Exception):
    """Raised when any step of the OIDC flow fails."""


def generate_pkce_pair() -> tuple[str, str]:
    """Return ``(code_verifier, code_challenge)`` for the S256 method."""
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


class OIDCClient:
    def __init__(self, settings: AuthSettings) -> None:
        self.settings = settings
        self._metadata: dict[str, Any] | None = None
        self._metadata_fetched_at = 0.0
        self._jwk_client: jwt.PyJWKClient | None = None
        self._lock = asyncio.Lock()

    async def metadata(self) -> dict[str, Any]:
        """Fetch (and cache) the provider's discovery document."""
        async with self._lock:
            if self._metadata and time.time() - self._metadata_fetched_at < _DISCOVERY_TTL_SECONDS:
                return self._metadata
            url = f"{self.settings.issuer}/.well-known/openid-configuration"
            try:
                async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    data: dict[str, Any] = response.json()
            except (httpx.HTTPError, ValueError) as e:
                raise OIDCError(f"Could not load OIDC discovery document from {url}: {e}") from e
            if not isinstance(data, dict):
                raise OIDCError("OIDC discovery document is not a JSON object")

            for key in ("issuer", "authorization_endpoint", "token_endpoint", "jwks_uri"):
                if not data.get(key):
                    raise OIDCError(f"OIDC discovery document is missing '{key}'")
            if str(data["issuer"]).rstrip("/") != self.settings.issuer:
                raise OIDCError(
                    f"Issuer mismatch: configured {self.settings.issuer!r}, provider says {data['issuer']!r}"
                )

            if self._metadata is None or self._metadata.get("jwks_uri") != data["jwks_uri"]:
                self._jwk_client = jwt.PyJWKClient(data["jwks_uri"], cache_keys=True, timeout=int(_HTTP_TIMEOUT))
            self._metadata = data
            self._metadata_fetched_at = time.time()
            return data

    async def authorization_url(self, redirect_uri: str, state: str, nonce: str, code_challenge: str) -> str:
        meta = await self.metadata()
        params = {
            "response_type": "code",
            "client_id": self.settings.client_id,
            "redirect_uri": redirect_uri,
            "scope": self.settings.scopes,
            "state": state,
            "nonce": nonce,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
        separator = "&" if "?" in meta["authorization_endpoint"] else "?"
        return f"{meta['authorization_endpoint']}{separator}{urlencode(params)}"

    async def end_session_url(self, id_token: str, post_logout_redirect_uri: str) -> str | None:
        """RP-initiated logout URL, if the provider supports it."""
        try:
            meta = await self.metadata()
        except OIDCError:
            return None
        endpoint = meta.get("end_session_endpoint")
        if not endpoint:
            return None
        params = {"client_id": self.settings.client_id, "post_logout_redirect_uri": post_logout_redirect_uri}
        if id_token:
            params["id_token_hint"] = id_token
        separator = "&" if "?" in endpoint else "?"
        return f"{endpoint}{separator}{urlencode(params)}"

    async def exchange_code(self, code: str, code_verifier: str, redirect_uri: str) -> dict[str, Any]:
        meta = await self.metadata()
        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.settings.client_id,
            "code_verifier": code_verifier,
        }
        if self.settings.client_secret:
            form["client_secret"] = self.settings.client_secret
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                response = await client.post(meta["token_endpoint"], data=form, headers={"Accept": "application/json"})
        except httpx.HTTPError as e:
            raise OIDCError(f"Token request failed: {e}") from e
        if response.status_code != 200:
            raise OIDCError(f"Token endpoint returned HTTP {response.status_code}: {response.text[:300]}")
        try:
            tokens: dict[str, Any] = response.json()
        except ValueError as e:
            raise OIDCError("Token endpoint returned invalid JSON") from e
        if not tokens.get("id_token"):
            raise OIDCError("Token response did not include an id_token (is the 'openid' scope enabled?)")
        return tokens

    async def validate_id_token(self, id_token: str, nonce: str) -> dict[str, Any]:
        """Verify the ID token signature and standard claims."""
        await self.metadata()
        try:
            header = jwt.get_unverified_header(id_token)
        except jwt.PyJWTError as e:
            raise OIDCError(f"Malformed id_token: {e}") from e

        alg = header.get("alg", "")
        key: Any
        if alg in _SYMMETRIC_ALGS:
            # e.g. Authentik without a signing key: HMAC with the client secret
            if not self.settings.client_secret:
                raise OIDCError(f"id_token uses {alg} but no client secret is configured")
            key, algorithms = self.settings.client_secret, _SYMMETRIC_ALGS
        elif alg in _ASYMMETRIC_ALGS:
            assert self._jwk_client is not None  # set by metadata()
            try:
                key = (await asyncio.to_thread(self._jwk_client.get_signing_key_from_jwt, id_token)).key
            except jwt.PyJWTError as e:
                raise OIDCError(f"Could not fetch id_token signing key: {e}") from e
            algorithms = _ASYMMETRIC_ALGS
        else:
            raise OIDCError(f"Unsupported id_token algorithm {alg!r}")

        try:
            claims: dict[str, Any] = jwt.decode(
                id_token,
                key=key,
                algorithms=algorithms,
                audience=self.settings.client_id,
                leeway=60,
                options={"require": ["exp", "iat", "sub", "iss"]},
            )
        except jwt.PyJWTError as e:
            raise OIDCError(f"Invalid id_token: {e}") from e

        # Compared manually because some providers (Authentik) put a trailing
        # slash in "iss" while the configured issuer is stored without one.
        if str(claims["iss"]).rstrip("/") != self.settings.issuer:
            raise OIDCError("Invalid id_token: issuer mismatch")
        if not secrets.compare_digest(str(claims.get("nonce", "")), nonce):
            raise OIDCError("Invalid id_token: nonce mismatch")
        return claims

    async def userinfo(self, access_token: str) -> dict[str, Any]:
        """Fetch extra claims (e.g. groups) from the userinfo endpoint. Best effort."""
        try:
            meta = await self.metadata()
        except OIDCError:
            return {}
        endpoint = meta.get("userinfo_endpoint")
        if not endpoint or not access_token:
            return {}
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
                response = await client.get(endpoint, headers={"Authorization": f"Bearer {access_token}"})
            if response.status_code != 200:
                return {}
            data = response.json()
            return data if isinstance(data, dict) else {}
        except (httpx.HTTPError, ValueError):
            logger.debug("userinfo request failed", exc_info=True)
            return {}


def user_from_claims(claims: dict[str, Any], group_claims: tuple[str, ...]) -> AuthUser:
    """Build an AuthUser from ID token (and userinfo) claims."""
    groups: list[str] = []
    for claim in group_claims:
        value = claims.get(claim)
        if isinstance(value, str):
            value = [value]
        if isinstance(value, list):
            groups.extend(str(v) for v in value if str(v) and str(v) not in groups)

    return AuthUser(
        sub=str(claims["sub"]),
        email=str(claims.get("email") or ""),
        username=str(claims.get("preferred_username") or claims.get("upn") or ""),
        name=str(claims.get("name") or ""),
        groups=tuple(groups),
    )


_client: OIDCClient | None = None


def get_oidc_client(settings: AuthSettings) -> OIDCClient:
    global _client
    if _client is None or _client.settings != settings:
        _client = OIDCClient(settings)
    return _client
