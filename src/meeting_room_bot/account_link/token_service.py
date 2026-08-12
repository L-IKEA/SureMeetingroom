"""Token Service for one-time short-lived Account Linking tokens."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets
from typing import Dict, Optional


@dataclass
class TokenData:
    """Dataclass holding token metadata."""

    token: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    is_used: bool = False


class AccountLinkTokenService:
    """Manages secure, short-lived, one-time Account Linking tokens."""

    def __init__(self, default_ttl_seconds: int = 600):
        self.default_ttl = default_ttl_seconds
        self._tokens: Dict[str, TokenData] = {}

    def create_token(self, user_id: str, ttl_seconds: Optional[int] = None) -> str:
        """Create a new one-time token for a Telegram user_id."""
        token = secrets.token_urlsafe(32)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl

        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=ttl)

        data = TokenData(
            token=token,
            user_id=str(user_id),
            created_at=now,
            expires_at=expires,
            is_used=False,
        )
        self._tokens[token] = data
        return token

    def validate_token(self, token: str) -> Optional[str]:
        """Validate if token exists, is unexpired, and has not been used. Return user_id or None."""
        if not token or token not in self._tokens:
            return None

        tdata = self._tokens[token]
        now = datetime.now(timezone.utc)

        if tdata.is_used:
            return None

        if now > tdata.expires_at:
            return None

        return tdata.user_id

    def consume_token(self, token: str) -> Optional[str]:
        """Validate and consume token (mark as used). Return user_id or None."""
        user_id = self.validate_token(token)
        if user_id is None:
            return None

        self._tokens[token].is_used = True
        return user_id

    def revoke_token(self, token: str):
        """Revoke a token immediately."""
        if token in self._tokens:
            self._tokens[token].is_used = True

    def clear_all(self):
        """Clear all active tokens (for testing)."""
        self._tokens.clear()


# Global token service instance
token_service = AccountLinkTokenService()
