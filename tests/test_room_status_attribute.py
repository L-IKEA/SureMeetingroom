"""Pytest suite for Task 8 RealProvider RoomStatus Attribute & available_from Fix."""

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.auth.session_manager import UserSessionManager
from meeting_room_bot.favorites.service import FavoriteService
from meeting_room_bot.groupware.client import GroupwareClient
from meeting_room_bot.models import Asset, Reservation, Room
from meeting_room_bot.providers.base import QueryStatus
from meeting_room_bot.providers.real_provider import RealMeetingRoomProvider
from meeting_room_bot.services.room_status_service import RoomStatus, RoomStatusService

SEOUL_TZ = timezone(timedelta(hours=9))


class TestRoomStatusAttributeFix:

    @pytest.fixture
    def provider_setup(self):
        session_mgr = UserSessionManager()
        fav_service = MagicMock(spec=FavoriteService)
        provider = RealMeetingRoomProvider(session_mgr=session_mgr, favorite_service=fav_service)

        client = MagicMock(spec=GroupwareClient)
        client.is_authenticated = True
        session_mgr.set_client("user_status", client)

        return provider, client

    def test_1_occupied_room_status_uses_available_from(self, provider_setup):
        """Test 1: Occupied RoomStatus uses current_reservation_end and formats note correctly."""
        provider, client = provider_setup

        asset = Asset(id=50, name="5층 회의실", raw_name="5층 회의실")
        room = Room(id=501, asset_id=50, name="회의실 5-1", capacity=6, raw_name="회의실 5-1")
        st_end = datetime(2026, 8, 11, 17, 0, tzinfo=SEOUL_TZ)
        room_st = RoomStatus(
            room=room,
            status="OCCUPIED",
            current_reservation_end=st_end,
            available_from=st_end,
            next_reservation_start=None,
        )

        client.get_assets.return_value = [{"id": 50, "name": "[판교] 5층 회의실"}]
        client.get_items.return_value = [{"id": 501, "name": "회의실 5-1"}]
        client.get_daily_reservations.return_value = [
            {
                "itemId": 501,
                "assetId": 50,
                "itemName": "회의실 5-1",
                "start": "2026-08-11T14:00:00+09:00",
                "end": "2026-08-11T17:00:00+09:00",
                "empName": "홍길동",
                "title": "회의",
            }
        ]

        with patch("meeting_room_bot.services.meeting_room_service.RoomStatusService.calculate_status", return_value=room_st):
            res = provider.get_location_status("user_status", asset_id=50)

        assert res.status == QueryStatus.SUCCESS
        rooms = res.data["rooms"]
        assert len(rooms) == 1
        assert rooms[0]["status"] == "🔴 사용 중"
        assert "현재 예약: 17:00 종료" in rooms[0]["note"]
        assert "이후 예약 없음" in rooms[0]["note"]

    def test_2_3_available_room_status_formatting(self, provider_setup):
        """Test 2 & 3: Available RoomStatus uses next_reservation_start or '오늘 추가 예약 없음'."""
        provider, client = provider_setup

        room = Room(id=502, asset_id=50, name="회의실 5-2", capacity=8, raw_name="회의실 5-2")
        next_start = datetime(2026, 8, 11, 15, 30, tzinfo=SEOUL_TZ)
        st_next = RoomStatus(room=room, status="AVAILABLE", next_reservation_start=next_start)
        st_none = RoomStatus(room=room, status="AVAILABLE", next_reservation_start=None)

        client.get_assets.return_value = [{"id": 50, "name": "[판교] 5층 회의실"}]
        client.get_items.return_value = [{"id": 502, "name": "회의실 5-2"}]
        client.get_daily_reservations.return_value = []

        # With next reservation
        with patch("meeting_room_bot.services.meeting_room_service.RoomStatusService.calculate_status", return_value=st_next):
            res1 = provider.get_location_status("user_status", asset_id=50)
        assert res1.data["rooms"][0]["status"] == "🟢 사용 가능"
        assert res1.data["rooms"][0]["note"] == "15:30부터 예약"

        # Without next reservation
        with patch("meeting_room_bot.services.meeting_room_service.RoomStatusService.calculate_status", return_value=st_none):
            res2 = provider.get_location_status("user_status", asset_id=50)
        assert res2.data["rooms"][0]["status"] == "🟢 사용 가능"
        assert res2.data["rooms"][0]["note"] == "오늘 추가 예약 없음"

    def test_4_back_to_back_reservations_available_from_calculation(self):
        """Test 4: Back-to-back reservations (14:00~15:00 and 15:00~16:00, now=14:30) calculates available_from=16:00."""
        room = Room(id=501, asset_id=50, name="회의실 5-1", capacity=6, raw_name="회의실 5-1")
        now = datetime(2026, 8, 11, 14, 30, tzinfo=SEOUL_TZ)

        res1 = Reservation(
            id=1,
            room_id=501,
            start_time=datetime(2026, 8, 11, 14, 0, tzinfo=SEOUL_TZ),
            end_time=datetime(2026, 8, 11, 15, 0, tzinfo=SEOUL_TZ),
        )
        res2 = Reservation(
            id=2,
            room_id=501,
            start_time=datetime(2026, 8, 11, 15, 0, tzinfo=SEOUL_TZ),
            end_time=datetime(2026, 8, 11, 16, 0, tzinfo=SEOUL_TZ),
        )

        st = RoomStatusService.calculate_status(room=room, reservations=[res1, res2], now=now)

        assert st.is_occupied is True
        assert st.available_from == datetime(2026, 8, 11, 16, 0, tzinfo=SEOUL_TZ)

    def test_5_room_status_has_current_reservation_end_attribute(self):
        """Test 5: Verify RoomStatus DTO has current_reservation_end attribute."""
        room = Room(id=501, asset_id=50, name="회의실 5-1", capacity=6, raw_name="회의실 5-1")
        st = RoomStatus(
            room=room,
            status="OCCUPIED",
            current_reservation_end=datetime(2026, 8, 11, 14, 0, tzinfo=SEOUL_TZ),
        )
        assert st.current_reservation_end == datetime(2026, 8, 11, 14, 0, tzinfo=SEOUL_TZ)

    def test_6_get_room_detail_executes_without_attribute_error(self, provider_setup):
        """Test 6: get_room_detail executes without attribute errors."""
        provider, client = provider_setup

        client.get_assets.return_value = [{"id": 50, "name": "[판교] 5층 회의실"}]
        client.get_items.return_value = [{"id": 501, "name": "회의실 5-1"}]
        client.get_daily_reservations.return_value = []

        res = provider.get_room_detail("user_status", asset_id=50, room_id=501)
        assert res.status == QueryStatus.SUCCESS
        assert res.data["name"] == "회의실 5-1"
