"""Providers package for Meeting Room Queries."""

from meeting_room_bot.config import get_config
from meeting_room_bot.providers.base import (
    MeetingRoomQueryProvider,
    QueryResult,
    QueryStatus,
)
from meeting_room_bot.providers.mock_provider import MockMeetingRoomProvider
from meeting_room_bot.providers.real_provider import RealMeetingRoomProvider


def get_provider(favorite_service=None) -> MeetingRoomQueryProvider:
    """Instantiate Provider based on configuration mode (mock vs real)."""
    import os
    from meeting_room_bot.auth.session_manager import session_manager
    from meeting_room_bot.favorites.json_repository import JsonFavoriteRepository
    from meeting_room_bot.favorites.service import FavoriteService

    config = get_config()
    mode = os.environ.get("TELEGRAM_DATA_MODE", config.telegram_data_mode).strip().lower()
    if mode == "real":
        if favorite_service is None:
            favorite_service = FavoriteService(JsonFavoriteRepository())
        return RealMeetingRoomProvider(session_mgr=session_manager, favorite_service=favorite_service)
    else:
        return MockMeetingRoomProvider()


__all__ = [
    "MeetingRoomQueryProvider",
    "QueryResult",
    "QueryStatus",
    "MockMeetingRoomProvider",
    "RealMeetingRoomProvider",
    "get_provider",
]
