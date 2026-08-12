"""Pytest suite for Mock and Real MeetingRoomQueryProviders."""

import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.auth.session_manager import UserSessionManager
from meeting_room_bot.favorites.service import FavoriteService
from meeting_room_bot.groupware.client import GroupwareAuthError, GroupwareClient
from meeting_room_bot.models import Asset, Room
from meeting_room_bot.providers.base import QueryStatus
from meeting_room_bot.providers.mock_provider import MockMeetingRoomProvider
from meeting_room_bot.providers.real_provider import RealMeetingRoomProvider


class TestMockMeetingRoomProvider:

    def test_mock_provider_does_not_call_groupware_api(self):
        """Verify MockMeetingRoomProvider returns mock data without calling Groupware API."""
        provider = MockMeetingRoomProvider()

        res_now = provider.get_available_rooms_now("111", scope="fav")
        assert res_now.status == QueryStatus.SUCCESS
        assert len(res_now.data["groups"]) >= 1

        res_at = provider.get_available_rooms_at("111", "2026-08-11", "14:00", 60, scope="all")
        assert res_at.status == QueryStatus.SUCCESS
        assert "🟢 컨퍼런스홀 1-1" in res_at.data["available_rooms"]


class TestRealMeetingRoomProvider:

    def test_unauthenticated_user_returns_not_authenticated(self):
        """Verify user without session returns NOT_AUTHENTICATED status."""
        session_mgr = UserSessionManager()
        fav_service = MagicMock(spec=FavoriteService)
        provider = RealMeetingRoomProvider(session_mgr=session_mgr, favorite_service=fav_service)

        res = provider.get_available_rooms_now("999", scope="fav")
        assert res.status == QueryStatus.NOT_AUTHENTICATED

        res_at = provider.get_available_rooms_at("999", "2026-08-11", "14:00", 60, scope="fav")
        assert res_at.status == QueryStatus.NOT_AUTHENTICATED

        res_loc = provider.get_location_status("999", 50)
        assert res_loc.status == QueryStatus.NOT_AUTHENTICATED

    def test_auth_error_clears_session_and_returns_session_expired(self):
        """Verify 401 Auth error removes user session and returns SESSION_EXPIRED."""
        session_mgr = UserSessionManager()
        fav_service = MagicMock(spec=FavoriteService)
        provider = RealMeetingRoomProvider(session_mgr=session_mgr, favorite_service=fav_service)

        # Mock authenticated client that raises GroupwareAuthError on API call
        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.is_authenticated = True
        mock_client.get_assets.side_effect = GroupwareAuthError("401 Unauthorized")

        session_mgr.set_client("111", mock_client)
        assert session_mgr.has_session("111") is True

        res = provider.get_available_rooms_now("111", scope="all")

        # Session should be removed automatically and SESSION_EXPIRED returned
        assert res.status == QueryStatus.SESSION_EXPIRED
        assert session_mgr.has_session("111") is False

    def test_no_favorites_returns_no_favorites_status(self):
        """Verify scope='fav' returns NO_FAVORITES status when user has no favorites."""
        session_mgr = UserSessionManager()
        fav_service = MagicMock(spec=FavoriteService)
        fav_service.get_favorite_rooms.return_value = []

        provider = RealMeetingRoomProvider(session_mgr=session_mgr, favorite_service=fav_service)

        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.is_authenticated = True
        session_mgr.set_client("111", mock_client)

        res = provider.get_available_rooms_now("111", scope="fav")
        assert res.status == QueryStatus.NO_FAVORITES

    def test_real_provider_all_locations_query_does_not_restrict_to_favorites(self):
        """Verify scope='all' queries all meeting room assets regardless of favorites."""
        session_mgr = UserSessionManager()
        fav_service = MagicMock(spec=FavoriteService)

        asset_4 = Asset(id=40, name="4층 회의실", raw_name="4층 회의실")
        asset_5 = Asset(id=50, name="5층 회의실", raw_name="5층 회의실")

        # Mock client responses
        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.is_authenticated = True
        mock_client.get_assets.return_value = [
            {"id": 40, "name": "4층 회의실"},
            {"id": 50, "name": "5층 회의실"},
        ]
        mock_client.get_items.return_value = [
            {"id": 140, "name": "회의실 4-1"},
            {"id": 150, "name": "회의실 5-1"},
        ]
        mock_client.get_daily_reservations.return_value = []

        session_mgr.set_client("111", mock_client)

        provider = RealMeetingRoomProvider(session_mgr=session_mgr, favorite_service=fav_service)
        res = provider.get_available_rooms_now("111", scope="all")

        assert res.status == QueryStatus.SUCCESS
        assert len(res.data["groups"]) == 2
        asset_names = [g["asset_name"] for g in res.data["groups"]]
        assert "4층 회의실" in asset_names
        assert "5층 회의실" in asset_names

    def test_asset_id_passed_correctly_for_location_status(self):
        """Verify specific location asset_id (e.g. 80) is passed directly to client."""
        session_mgr = UserSessionManager()
        fav_service = MagicMock(spec=FavoriteService)

        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.is_authenticated = True
        mock_client.get_assets.return_value = [{"id": 80, "name": "8층 회의실"}]
        mock_client.get_items.return_value = [{"id": 180, "name": "회의실 8-1"}]
        mock_client.get_daily_reservations.return_value = []

        session_mgr.set_client("111", mock_client)

        provider = RealMeetingRoomProvider(session_mgr=session_mgr, favorite_service=fav_service)
        res = provider.get_location_status("111", 80)

        assert res.status == QueryStatus.SUCCESS
        mock_client.get_items.assert_called_with(80)
        assert res.data["asset_name"] == "8층 회의실"
