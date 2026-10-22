"""
Server-side session storage.

Sessions are kept in memory and identified by a random, unguessable cookie
value. Keeping them server-side means logout truly revokes a session and the
cookie stays small no matter how many groups the identity provider returns.
Sessions do not survive a server restart; users simply sign in again.
"""

import secrets
import threading
import time
from dataclasses import dataclass, field

SESSION_COOKIE = "autoforge_session"
LOGIN_STATE_COOKIE = "autoforge_login_state"

# Pending logins (between redirect to the provider and the callback).
LOGIN_TTL_SECONDS = 600


@dataclass(frozen=True)
class AuthUser:
    """Identity of a signed-in user, taken from the OIDC claims."""

    sub: str
    email: str = ""
    username: str = ""
    name: str = ""
    groups: tuple[str, ...] = ()

    @property
    def display_name(self) -> str:
        return self.name or self.email or self.username or self.sub

    def identifiers(self) -> set[str]:
        """Lower-cased values a roles file may use to refer to this user."""
        return {v.lower() for v in (self.sub, self.email, self.username) if v}


@dataclass
class Session:
    user: AuthUser
    expires_at: float
    id_token: str = ""


@dataclass
class PendingLogin:
    nonce: str
    code_verifier: str
    redirect_uri: str
    next_path: str
    expires_at: float = field(default_factory=lambda: time.time() + LOGIN_TTL_SECONDS)


class SessionStore:
    """Thread-safe in-memory store for sessions and pending logins."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, Session] = {}
        self._pending: dict[str, PendingLogin] = {}

    def _prune(self, now: float) -> None:
        for sid in [k for k, s in self._sessions.items() if s.expires_at <= now]:
            del self._sessions[sid]
        for state in [k for k, p in self._pending.items() if p.expires_at <= now]:
            del self._pending[state]

    def create(self, user: AuthUser, ttl_seconds: int, id_token: str = "") -> str:
        sid = secrets.token_urlsafe(32)
        now = time.time()
        with self._lock:
            self._prune(now)
            self._sessions[sid] = Session(user=user, expires_at=now + ttl_seconds, id_token=id_token)
        return sid

    def get(self, sid: str | None) -> Session | None:
        if not sid:
            return None
        now = time.time()
        with self._lock:
            session = self._sessions.get(sid)
            if session is None:
                return None
            if session.expires_at <= now:
                del self._sessions[sid]
                return None
            return session

    def delete(self, sid: str | None) -> Session | None:
        if not sid:
            return None
        with self._lock:
            return self._sessions.pop(sid, None)

    def add_pending(self, state: str, pending: PendingLogin) -> None:
        with self._lock:
            self._prune(time.time())
            self._pending[state] = pending

    def pop_pending(self, state: str) -> PendingLogin | None:
        """Consume a pending login (single use)."""
        with self._lock:
            pending = self._pending.pop(state, None)
        if pending is None or pending.expires_at <= time.time():
            return None
        return pending

    def clear(self) -> None:
        with self._lock:
            self._sessions.clear()
            self._pending.clear()


_store = SessionStore()


def get_session_store() -> SessionStore:
    return _store
