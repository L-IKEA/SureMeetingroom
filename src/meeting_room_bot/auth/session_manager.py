"""User Session Manager for isolated per-user Groupware HTTP sessions."""

import logging
from typing import Dict, Optional
from meeting_room_bot.groupware.client import GroupwareClient

logger = logging.getLogger(__name__)


class UserSessionManager:
    """Manages isolated GroupwareClient HTTP sessions keyed by generic user_id."""

    def __init__(self):
        # Map user_id: str -> GroupwareClient
        self._sessions: Dict[str, GroupwareClient] = {}

    def has_session(self, user_id: str) -> bool:
        """Check if an active Groupware session exists for user_id."""
        key = str(user_id)
        client = self._sessions.get(key)
        return client is not None and client.is_authenticated

    def get_client(self, user_id: str) -> Optional[GroupwareClient]:
        """Retrieve GroupwareClient for a specific user_id if session exists."""
        key = str(user_id)
        return self._sessions.get(key)

    def set_client(self, user_id: str, client: GroupwareClient):
        """Register or update GroupwareClient session for a specific user_id."""
        key = str(user_id)
        if not isinstance(client, GroupwareClient):
            raise TypeError("client must be an instance of GroupwareClient")
        self._sessions[key] = client
        # Log event WITHOUT logging cookie secrets or passwords
        logger.info(f"[UserSessionManager] Registered Groupware session for user_id: {key}")

    def remove_session(self, user_id: str):
        """Remove Groupware session for a specific user_id."""
        key = str(user_id)
        if key in self._sessions:
            del self._sessions[key]
            logger.info(f"[UserSessionManager] Removed Groupware session for user_id: {key}")

    def clear_expired_session(self, user_id: str):
        """Alias for removing an expired or 401 unauthenticated session."""
        self.remove_session(user_id)

    def clear_all_sessions(self):
        """Clear all active user sessions (useful for tests or shutdown)."""
        self._sessions.clear()


# Global UserSessionManager instance for system use
session_manager = UserSessionManager()
