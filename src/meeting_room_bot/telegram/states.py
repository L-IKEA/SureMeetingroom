"""Telegram Bot Callback Constants and Per-User State Management."""

from typing import Any, Dict

# Callback Data Constants
CB_MENU_NOW = "menu:now"
CB_MENU_WHEN = "menu:when"
CB_MENU_WHERE = "menu:where"
CB_MENU_FAV = "menu:fav"

CB_NAV_HOME = "nav:home"
CB_NAV_BACK = "nav:back"

CB_SCOPE_FAV = "scope:fav"
CB_SCOPE_ALL = "scope:all"
CB_SCOPE_SELECT = "scope:select"

CB_DATE_TODAY = "date:today"
CB_DATE_TOMORROW = "date:tomorrow"

CB_TIME_PREFIX = "time:"
CB_DUR_PREFIX = "dur:"
CB_ASSET_PREFIX = "asset:"
CB_ROOM_PREFIX = "room:"
CB_PAGE_PREFIX = "page:"

CB_REFRESH_NOW = "action:refresh_now"
CB_FAV_ADD_ASSET = "fav_action:add_asset"
CB_FAV_ADD_ROOM = "fav_action:add_room"
CB_FAV_REMOVE = "fav_action:remove"


class UserStateManager:
    """Manages per-user interactive state for Telegram flows."""

    def __init__(self):
        self._states: Dict[str, Dict[str, Any]] = {}

    def get_state(self, user_id: str) -> Dict[str, Any]:
        """Get state dictionary for a specific user ID."""
        user_key = str(user_id)
        if user_key not in self._states:
            self._states[user_key] = {
                "date": "today",
                "time": "14:00",
                "duration": 60,
                "scope": "fav",
                "asset_id": 50,
                "page": 0,
                "last_menu": "home",
            }
        return self._states[user_key]

    def update_state(self, user_id: str, **kwargs) -> Dict[str, Any]:
        """Update specific state fields for a user."""
        state = self.get_state(user_id)
        state.update(kwargs)
        return state

    def reset_state(self, user_id: str):
        """Reset state for a user back to defaults."""
        user_key = str(user_id)
        if user_key in self._states:
            del self._states[user_key]


# Global state manager instance for bot handlers
user_state_mgr = UserStateManager()
