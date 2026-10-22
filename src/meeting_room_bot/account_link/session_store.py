"""In-memory session stores for Account Linking and Web Authentication.

Phase 2.2 Pilot Architecture:
- Single-process in-memory stores protected with threading locks.
- LinkSession: short-lived (default 300s), holds pre-login UserKey and CSRF token during login flow.
- WebSession: authenticated user session (default 86400s) used for /timeline and web UI access.
- Note: Server restart clears in-memory sessions, requiring users to re-authenticate.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import secrets
import threading
from typing import Dict, List, Optional

from meeting_room_bot.models.user_key import UserKey

logger = logging.getLogger(__name__)

LINK_SESSION_COOKIE_NAME = "meetingroom_link_session"
WEB_SESSION_COOKIE_NAME = "meetingroom_web_session"


@dataclass
class LinkSession:
    """Pre-authentication link session holding UserKey and CSRF token during login flow."""

    session_id: str
    user_key: UserKey
    csrf_token: str
    created_at: datetime
    expires_at: datetime


@dataclass
class WebSession:
    """Authenticated web session created after successful login, used for /timeline."""

    session_id: str
    user_key: UserKey
    created_at: datetime
    expires_at: datetime


class LinkSessionStore:
    """In-memory store for pre-login link sessions."""

    def __init__(self, default_ttl_seconds: int = 300):
        self._default_ttl = default_ttl_seconds
        self._sessions: Dict[str, LinkSession] = {}
        self._lock = threading.Lock()

    def cleanup_expired(self) -> int:
        """Purge expired link sessions from storage."""
        now = datetime.now(timezone.utc)
        with self._lock:
            expired = [sid for sid, s in self._sessions.items() if now > s.expires_at]
            for sid in expired:
                del self._sessions[sid]
            return len(expired)

    def create_link_session(self, user_key: UserKey, ttl_seconds: Optional[int] = None) -> LinkSession:
        """Create and store a new LinkSession with cryptographically strong opaque IDs."""
        self.cleanup_expired()
        session_id = secrets.token_urlsafe(32)
        csrf_token = secrets.token_hex(32)
        created_at = datetime.now(timezone.utc)
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expires_at = created_at + timedelta(seconds=ttl)
        session = LinkSession(
            session_id=session_id,
            user_key=user_key,
            csrf_token=csrf_token,
            created_at=created_at,
            expires_at=expires_at,
        )
        with self._lock:
            self._sessions[session_id] = session
        logger.info(f"[LinkSessionStore] Created link session for user_key: {user_key.to_string()}")
        return session

    def get_link_session(self, session_id: str) -> Optional[LinkSession]:
        """Retrieve valid, unexpired LinkSession by session_id."""
        if not session_id:
            return None
        now = datetime.now(timezone.utc)
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            if now > session.expires_at:
                del self._sessions[session_id]
                return None
            return session

    def consume_link_session(self, session_id: str) -> Optional[LinkSession]:
        """Consume and delete a LinkSession (one-time exchange upon login attempt)."""
        if not session_id:
            return None
        now = datetime.now(timezone.utc)
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if not session:
                return None
            if now > session.expires_at:
                return None
            return session

    def clear(self):
        """Clear all stored sessions (useful for tests)."""
        with self._lock:
            self._sessions.clear()


class WebSessionStore:
    """In-memory store for authenticated web sessions."""

    def __init__(self, default_ttl_seconds: int = 86400):
        self._default_ttl = default_ttl_seconds
        self._sessions: Dict[str, WebSession] = {}
        self._lock = threading.Lock()

    def cleanup_expired(self) -> int:
        """Purge expired web sessions from storage."""
        now = datetime.now(timezone.utc)
        with self._lock:
            expired = [sid for sid, s in self._sessions.items() if now > s.expires_at]
            for sid in expired:
                del self._sessions[sid]
            return len(expired)

    def create_web_session(self, user_key: UserKey, ttl_seconds: Optional[int] = None) -> WebSession:
        """Create and store an authenticated WebSession for user_key."""
        self.cleanup_expired()
        session_id = secrets.token_urlsafe(32)
        created_at = datetime.now(timezone.utc)
        ttl = ttl_seconds if ttl_seconds is not None else self._default_ttl
        expires_at = created_at + timedelta(seconds=ttl)
        session = WebSession(
            session_id=session_id,
            user_key=user_key,
            created_at=created_at,
            expires_at=expires_at,
        )
        with self._lock:
            # Clean up old web sessions for same user
            old_sids = [sid for sid, s in self._sessions.items() if s.user_key == user_key]
            for sid in old_sids:
                del self._sessions[sid]
            self._sessions[session_id] = session
        logger.info(f"[WebSessionStore] Created web session for user_key: {user_key.to_string()}")
        return session

    def get_web_session(self, session_id: str) -> Optional[WebSession]:
        """Retrieve valid, unexpired WebSession by session_id."""
        if not session_id:
            return None
        now = datetime.now(timezone.utc)
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return None
            if now > session.expires_at:
                del self._sessions[session_id]
                return None
            return session

    def remove_web_session(self, session_id: str) -> Optional[WebSession]:
        """Remove WebSession by session_id."""
        if not session_id:
            return None
        with self._lock:
            return self._sessions.pop(session_id, None)

    def remove_user_sessions(self, user_key: UserKey) -> int:
        """Remove all active WebSessions for a specific UserKey."""
        with self._lock:
            target_sids = [sid for sid, s in self._sessions.items() if s.user_key == user_key]
            for sid in target_sids:
                del self._sessions[sid]
            return len(target_sids)

    def clear(self):
        """Clear all stored web sessions (useful for tests)."""
        with self._lock:
            self._sessions.clear()


# Global singletons
link_session_store = LinkSessionStore()
web_session_store = WebSessionStore()
