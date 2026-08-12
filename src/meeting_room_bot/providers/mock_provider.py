"""Mock implementation of MeetingRoomQueryProvider for development and UI testing."""

from meeting_room_bot.providers.base import (
    MeetingRoomQueryProvider,
    QueryResult,
    QueryStatus,
)
from meeting_room_bot.telegram.mock_service import MockTelegramService


class MockMeetingRoomProvider(MeetingRoomQueryProvider):
    """Provides mock data without calling Groupware HTTP API."""

    def check_authentication(self, user_id: str) -> QueryResult:
        return QueryResult(status=QueryStatus.SUCCESS)

    def get_locations(self, user_id: str) -> QueryResult:
        locations = MockTelegramService.get_mock_locations()
        return QueryResult(status=QueryStatus.SUCCESS, data={"locations": locations})

    def get_available_rooms_now(self, user_id: str, scope: str = "fav") -> QueryResult:
        if scope in ("fav", "favorites") and not MockTelegramService.has_favorites(user_id):
            return QueryResult(status=QueryStatus.NO_FAVORITES)

        res = MockTelegramService.get_mock_available_rooms_now(scope=scope, user_id=user_id)
        return QueryResult(status=QueryStatus.SUCCESS, data=res)

    def get_available_rooms_at(
        self,
        user_id: str,
        date_str: str,
        start_time: str,
        duration: int,
        scope: str = "fav",
    ) -> QueryResult:
        if scope in ("fav", "favorites") and not MockTelegramService.has_favorites(user_id):
            return QueryResult(status=QueryStatus.NO_FAVORITES)

        res = MockTelegramService.get_mock_available_rooms_at(
            date_str=date_str,
            start_time=start_time,
            duration=duration,
            scope=scope,
            user_id=user_id,
        )
        return QueryResult(status=QueryStatus.SUCCESS, data=res)

    def get_location_status(self, user_id: str, asset_id: int) -> QueryResult:
        res = MockTelegramService.get_mock_location_status(asset_id)
        return QueryResult(status=QueryStatus.SUCCESS, data=res)

    def get_room_detail(self, user_id: str, asset_id: int, room_id: int) -> QueryResult:
        res = MockTelegramService.get_mock_room_detail(asset_id, room_id)
        if not res:
            return QueryResult(
                status=QueryStatus.GROUPWARE_API_ERROR,
                error_message="Room detail not found",
            )
        return QueryResult(status=QueryStatus.SUCCESS, data=res)

    def get_favorites(self, user_id: str) -> QueryResult:
        res = MockTelegramService.get_mock_favorites(user_id)
        return QueryResult(status=QueryStatus.SUCCESS, data=res)
