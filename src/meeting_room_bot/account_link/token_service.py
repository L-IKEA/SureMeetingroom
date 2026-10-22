"""Token Service for one-time short-lived Account Linking tokens."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets
from typing import Dict, Optional, Union

from meeting_room_bot.models.user_key import UserKey


@dataclass
class TokenData:
    """Dataclass holding token metadata."""

    token: str
    user_id: str
    created_at: datetime
    expires_at: datetime
    is_used: bool = False


class AccountLinkTokenService:
    """Manages secure, short-lived, one-time Account Linking tokens.

    Transition Compatibility Notice:
    - UserKey is serialized into 'platform:user_id' for tokens.
    - Plain str is accepted during v0.2 transition period for v0.1 test backward compatibility.
    """

    def __init__(self, default_ttl_seconds: Optional[int] = None, default_ttl: Optional[int] = None):
        import os
        ttl = default_ttl_seconds if default_ttl_seconds is not None else default_ttl
        if ttl is not None:
            self.default_ttl = ttl
        else:
            self.default_ttl = int(os.environ.get("ACCOUNT_LINK_TOKEN_TTL", "600"))
        self._tokens: Dict[str, TokenData] = {}

    def cleanup_expired_tokens(self) -> int:
        """Remove all expired or already used tokens from storage. Return count of removed tokens."""
        now = datetime.now(timezone.utc)
        to_remove = [k for k, v in self._tokens.items() if v.is_used or now > v.expires_at]
        for k in to_remove:
            self._tokens.pop(k, None)
        return len(to_remove)

    def create_token(self, user_id: Union[UserKey, str], ttl_seconds: Optional[int] = None) -> str:
        """Create a new one-time token for a user. Cleans up expired and replaces previous user tokens."""
        # 1. Housekeeping: remove expired tokens
        self.cleanup_expired_tokens()

        # 2. Invalidate / remove any existing active tokens for the same user
        uid_str = user_id.to_string() if isinstance(user_id, UserKey) else str(user_id)
        existing_tokens = [k for k, v in self._tokens.items() if v.user_id == uid_str]
        for k in existing_tokens:
            self._tokens.pop(k, None)

        # 3. Issue new token
        token = secrets.token_urlsafe(32)
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl

        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=ttl)

        data = TokenData(
            token=token,
            user_id=uid_str,
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
        """Validate and consume token (mark as used and safely remove from active tokens). Return user_id or None."""
        user_id = self.validate_token(token)
        if user_id is None:
            return None

        # Burn-on-use and cleanup entry
        tdata = self._tokens.pop(token, None)
        if tdata:
            tdata.is_used = True
        return user_id

    def revoke_token(self, token: str):
        """Revoke a token immediately."""
        self._tokens.pop(token, None)

    def clear_all(self):
        """Clear all active tokens (for testing)."""
        self._tokens.clear()


# Global token service instance
token_service = AccountLinkTokenService()
