"""Pytest suite for MeetingRoomService."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.groupware.client import GroupwareClient
from meeting_room_bot.models import Asset, Reservation, Room
from meeting_room_bot.services.meeting_room_service import MeetingRoomService

SEOUL_TZ = timezone(timedelta(hours=9))


def make_dt(hour: int, minute: int, day: int = 11) -> datetime:
    return datetime(2026, 8, day, hour, minute, tzinfo=SEOUL_TZ)


@pytest.fixture
def mock_client():
    client = MagicMock(spec=GroupwareClient)
    # Mock get_assets response
    client.get_assets.return_value = {
        "code": "200",
        "data": [
            {"id": 50, "name": "[판교] 5층 회의실"},
            {"id": 60, "name": "[판교] 6층 프로젝트룸"},
            {"id": 10, "name": "법인차량 A"},  # Should be excluded by exclude filter
        ],
    }

    # Mock get_items response for asset 50
    def mock_get_items(asset_id):
        if asset_id == 50:
            return {
                "code": "200",
                "data": [
                    {"id": 130, "name": "회의실 5-1(6인 / TV)"},
                    {"id": 131, "name": "회의실 5-2(6인 / TV)"},
                ],
            }
        elif asset_id == 60:
            return {
                "code": "200",
                "data": [
                    {"id": 140, "name": "프로젝트룸 6-1(10인)"},
                ],
            }
        return {"code": "200", "data": []}

    client.get_items.side_effect = mock_get_items

    # Mock get_daily_reservations response
    def mock_get_daily(asset_id, date_str=None):
        if asset_id == 50:
            return {
                "code": "200",
                "data": [
                    {
                        "id": 130,
                        "reservations": [
                            {
                                "id": 1,
                                "startTime": "2026-08-11T09:30:00+09:00",
                                "endTime": "2026-08-11T10:30:00+09:00",
                                "userName": "홍길동",
                                "title": "비밀회의",
                            }
                        ],
                    },
                    {
                        "id": 131,
                        "reservations": [
                            {
                                "id": 2,
                                "startTime": "2026-08-11T14:00:00+09:00",
                                "endTime": "2026-08-11T15:00:00+09:00",
                            }
                        ],
                    },
                ],
            }
        elif asset_id == 60:
            return {"code": "200", "data": []}  # 0 reservations
        return {"code": "200", "data": []}

    client.get_daily_reservations.side_effect = mock_get_daily

    return client


class TestMeetingRoomService:

    def test_get_meeting_assets_excludes_non_meeting_spaces(self, mock_client):
        """Verify get_meeting_assets excludes vehicle assets."""
        service = MeetingRoomService(mock_client)
        assets = service.get_meeting_assets()

        assert len(assets) == 2
        asset_ids = [a.id for a in assets]
        assert 50 in asset_ids
        assert 60 in asset_ids
        assert 10 not in asset_ids  # 法인차량 excluded

    def test_get_available_rooms_now(self, mock_client):
        """Verify get_available_rooms_now returns available rooms and excludes occupied ones."""
        service = MeetingRoomService(mock_client)
        now = make_dt(10, 0)  # Room 130 is occupied (09:30~10:30), Room 131 is available

        avail_now = service.get_available_rooms_now(asset_ids=[50], now=now)

        assert len(avail_now) == 1
        item = avail_now[0]
        assert item["room"].id == 131
        assert item["next_reservation_start"] == make_dt(14, 0)

    def test_get_available_rooms_now_multi_asset(self, mock_client):
        """Verify get_available_rooms_now works across multiple assets simultaneously."""
        service = MeetingRoomService(mock_client)
        now = make_dt(10, 0)

        # Query all meeting assets (asset 50 and asset 60)
        avail_now = service.get_available_rooms_now(asset_ids=None, now=now)

        # Asset 50 -> Room 131 available. Asset 60 -> Room 140 available.
        room_ids = [item["room"].id for item in avail_now]
        assert 131 in room_ids
        assert 140 in room_ids
        assert 130 not in room_ids

    def test_get_available_rooms_at(self, mock_client):
        """Verify get_available_rooms_at for specific time slot."""
        service = MeetingRoomService(mock_client)
        req_start = make_dt(14, 0)
        req_end = make_dt(15, 0)

        results = service.get_available_rooms_at(asset_ids=[50], start_time=req_start, end_time=req_end)

        assert len(results) == 1
        asset_res = results[0]
        avail_ids = [r.id for r in asset_res["available_rooms"]]
        unavail_ids = [r.id for r in asset_res["unavailable_rooms"]]

        # Room 131 has reservation 14:00~15:00 -> unavailable
        # Room 130 has reservation 09:30~10:30 -> available
        assert 130 in avail_ids
        assert 131 in unavail_ids

    def test_get_location_status(self, mock_client):
        """Verify get_location_status returns status of all rooms in an asset."""
        service = MeetingRoomService(mock_client)
        now = make_dt(10, 0)

        loc_status = service.get_location_status(asset_id=50, now=now)

        assert loc_status["asset"].id == 50
        statuses = loc_status["room_statuses"]
        assert len(statuses) == 2

        status_130 = next(s for s in statuses if s.room.id == 130)
        status_131 = next(s for s in statuses if s.room.id == 131)

        assert status_130.is_occupied
        assert status_130.available_from == make_dt(10, 30)

        assert status_131.is_available
        assert status_131.next_reservation_start == make_dt(14, 0)

    def test_get_room_detail_privacy_check(self, mock_client):
        """Verify get_room_detail returns reservation time slots without exposing personal info."""
        service = MeetingRoomService(mock_client)
        now = make_dt(10, 0)

        detail = service.get_room_detail(asset_id=50, room_id=130, now=now)

        assert detail["asset"].id == 50
        assert detail["room"].id == 130
        assert detail["status"].is_occupied

        slots = detail["reservation_slots"]
        assert len(slots) == 1
        assert slots[0] == (make_dt(9, 30), make_dt(10, 30))

        # Check privacy: dictionary keys must not contain user info
        assert "userName" not in detail
        assert "title" not in detail
        assert "company" not in detail

    def test_get_room_detail_zero_reservations(self, mock_client):
        """Verify get_room_detail for room with 0 reservations."""
        service = MeetingRoomService(mock_client)
        now = make_dt(10, 0)

        detail = service.get_room_detail(asset_id=60, room_id=140, now=now)

        assert detail["room"].id == 140
        assert detail["status"].is_available
        assert len(detail["reservation_slots"]) == 0
