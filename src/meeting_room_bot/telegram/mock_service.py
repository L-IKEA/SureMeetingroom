"""Telegram adapter re-export for mock meeting room service (Backward Compatibility)."""

from meeting_room_bot.providers.mock_data import (
    MockMeetingRoomData,
    MockTelegramService,
)

__all__ = ["MockMeetingRoomData", "MockTelegramService"]
