"""Mock implementation of MeetingRoomQueryProvider for development and UI testing."""

from typing import Union

from meeting_room_bot.models.user_key import UserKey
from meeting_room_bot.providers.base import (
    MeetingRoomQueryProvider,
    QueryResult,
    QueryStatus,
)
from meeting_room_bot.providers.mock_data import MockMeetingRoomData


class MockMeetingRoomProvider(MeetingRoomQueryProvider):
    """Provides mock data without calling Groupware HTTP API."""

    def check_authentication(self, user_id: Union[UserKey, str]) -> QueryResult:
        return QueryResult(status=QueryStatus.SUCCESS)

    def get_locations(self, user_id: Union[UserKey, str]) -> QueryResult:
        locations = MockMeetingRoomData.get_mock_locations()
        return QueryResult(status=QueryStatus.SUCCESS, data={"locations": locations})

    def get_available_rooms_now(self, user_id: Union[UserKey, str], scope: str = "fav") -> QueryResult:
        uid = user_id.platform_user_id if isinstance(user_id, UserKey) else str(user_id)
        if scope in ("fav", "favorites") and not MockMeetingRoomData.has_favorites(uid):
            return QueryResult(status=QueryStatus.NO_FAVORITES)

        res = MockMeetingRoomData.get_mock_available_rooms_now(scope=scope, user_id=uid)
        return QueryResult(status=QueryStatus.SUCCESS, data=res)

    def get_available_rooms_at(
        self,
        user_id: Union[UserKey, str],
        date_str: str,
        start_time: str,
        duration: int,
        scope: str = "fav",
    ) -> QueryResult:
        uid = user_id.platform_user_id if isinstance(user_id, UserKey) else str(user_id)
        if scope in ("fav", "favorites") and not MockMeetingRoomData.has_favorites(uid):
            return QueryResult(status=QueryStatus.NO_FAVORITES)

        res = MockMeetingRoomData.get_mock_available_rooms_at(
            date_str=date_str,
            start_time=start_time,
            duration=duration,
            scope=scope,
            user_id=uid,
        )
        return QueryResult(status=QueryStatus.SUCCESS, data=res)

    def get_location_status(self, user_id: Union[UserKey, str], asset_id: int) -> QueryResult:
        res = MockMeetingRoomData.get_mock_location_status(asset_id)
        return QueryResult(status=QueryStatus.SUCCESS, data=res)

    def get_room_detail(self, user_id: Union[UserKey, str], asset_id: int, room_id: int) -> QueryResult:
        res = MockMeetingRoomData.get_mock_room_detail(asset_id, room_id)
        if not res:
            return QueryResult(
                status=QueryStatus.GROUPWARE_API_ERROR,
                error_message="Room detail not found",
            )
        return QueryResult(status=QueryStatus.SUCCESS, data=res)

    def get_favorites(self, user_id: Union[UserKey, str]) -> QueryResult:
        uid = user_id.platform_user_id if isinstance(user_id, UserKey) else str(user_id)
        res = MockMeetingRoomData.get_mock_favorites(uid)
        return QueryResult(status=QueryStatus.SUCCESS, data=res)
