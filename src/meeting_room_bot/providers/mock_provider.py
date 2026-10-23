"""Mock implementation of MeetingRoomQueryProvider for development and UI testing."""

from datetime import datetime
from typing import Optional, Union

from meeting_room_bot.models.user_key import UserKey
from meeting_room_bot.providers.base import (
    MeetingRoomQueryProvider,
    QueryResult,
    QueryStatus,
)
from meeting_room_bot.providers.mock_data import MockMeetingRoomData


class MockMeetingRoomProvider(MeetingRoomQueryProvider):
    """Provides mock data without calling Groupware HTTP API."""

    def _resolve_uid(self, user_id: Union[UserKey, str]) -> str:
        """Resolve UserKey to qualified string 'platform:user_id', or keep raw string."""
        if isinstance(user_id, UserKey):
            return user_id.to_string()
        return str(user_id).strip()

    def check_authentication(self, user_id: Union[UserKey, str]) -> QueryResult:
        return QueryResult(status=QueryStatus.SUCCESS)

    def get_locations(self, user_id: Union[UserKey, str]) -> QueryResult:
        locations = MockMeetingRoomData.get_mock_locations()
        return QueryResult(status=QueryStatus.SUCCESS, data={"locations": locations})

    def get_available_rooms_now(self, user_id: Union[UserKey, str], scope: str = "fav") -> QueryResult:
        uid = self._resolve_uid(user_id)
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
        uid = self._resolve_uid(user_id)
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
        uid = self._resolve_uid(user_id)
        res = MockMeetingRoomData.get_mock_favorites(uid)
        return QueryResult(status=QueryStatus.SUCCESS, data=res)

    def get_timeline(
        self,
        user_id: Union[UserKey, str],
        asset_id: Optional[int] = None,
        target_date: Optional[datetime] = None,
    ) -> QueryResult:
        uid = self._resolve_uid(user_id)
        res = MockMeetingRoomData.get_mock_timeline_data(
            asset_id=asset_id,
            user_key=uid,
            target_date=target_date,
        )
        return QueryResult(status=QueryStatus.SUCCESS, data=res)
