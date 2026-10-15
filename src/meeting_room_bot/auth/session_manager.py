"""User Session Manager for isolated per-user Groupware HTTP sessions."""

import logging
from typing import Dict, List, Optional, Union

from meeting_room_bot.groupware.client import GroupwareClient
from meeting_room_bot.models.user_key import UserKey

logger = logging.getLogger(__name__)


class UserSessionManager:
    """Manages isolated GroupwareClient HTTP sessions keyed by generic UserKey or legacy user_id.

    Transition Compatibility Notice:
    - UserKey is the primary channel identity model.
    - Support for plain `str` and `Union[UserKey, str]` is a Transition Compatibility Layer
      for backward compatibility with v0.1 tests and existing session data.
    - Platform adapters must explicitly pass UserKey (e.g. UserKey("telegram", ...), UserKey("kakao", ...)).
      New adapters must not rely on raw str fallbacks.
    """

    def __init__(self):
        # Map storage_key: str -> GroupwareClient
        self._sessions: Dict[str, GroupwareClient] = {}

    def _lookup_keys(self, user: Union[UserKey, str]) -> List[str]:
        """Generate candidate keys for lookup to support backward compatibility."""
        keys = []
        if isinstance(user, UserKey):
            keys.append(user.to_string())
            if user.platform == "telegram":
                keys.append(user.platform_user_id)
        else:
            raw = str(user).strip()
            keys.append(raw)
            if ":" not in raw:
                keys.append(f"telegram:{raw}")
            else:
                parts = raw.split(":", 1)
                if parts[0] == "telegram":
                    keys.append(parts[1])
        return keys

    def has_session(self, user: Union[UserKey, str]) -> bool:
        """Check if an active Groupware session exists for user."""
        client = self.get_client(user)
        return client is not None and client.is_authenticated

    def get_client(self, user: Union[UserKey, str]) -> Optional[GroupwareClient]:
        """Retrieve GroupwareClient for a specific user if session exists."""
        for k in self._lookup_keys(user):
            client = self._sessions.get(k)
            if client is not None:
                return client
        return None

    def set_client(self, user: Union[UserKey, str], client: GroupwareClient):
        """Register or update GroupwareClient session for a specific user."""
        if not isinstance(client, GroupwareClient):
            raise TypeError("client must be an instance of GroupwareClient")

        storage_key = user.to_string() if isinstance(user, UserKey) else str(user).strip()
        self._sessions[storage_key] = client
        # Log event WITHOUT logging cookie secrets or passwords
        logger.info(f"[UserSessionManager] Registered Groupware session for user: {storage_key}")

    def remove_session(self, user: Union[UserKey, str]):
        """Remove Groupware session for a specific user."""
        for k in self._lookup_keys(user):
            if k in self._sessions:
                del self._sessions[k]
                logger.info(f"[UserSessionManager] Removed Groupware session for user key: {k}")

    def clear_expired_session(self, user: Union[UserKey, str]):
        """Alias for removing an expired or 401 unauthenticated session."""
        self.remove_session(user)

    def clear_all_sessions(self):
        """Clear all active user sessions (useful for tests or shutdown)."""
        self._sessions.clear()


# Global UserSessionManager instance for system use
session_manager = UserSessionManager()
