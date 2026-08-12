"""Pytest suite for Task 8 Room Detail target_date schedule filtering and sorting."""

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
from unittest.mock import MagicMock
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.groupware.client import GroupwareClient
from meeting_room_bot.services.meeting_room_service import MeetingRoomService

SEOUL_TZ = timezone(timedelta(hours=9))


def dt(day: int, hour: int, minute: int) -> datetime:
    return datetime(2026, 8, day, hour, minute, tzinfo=SEOUL_TZ)


class TestRoomDetailTodayFilter:

    @pytest.fixture
    def service_setup(self):
        client = MagicMock(spec=GroupwareClient)
        service = MeetingRoomService(client)
        return service, client

    def test_case_1_filters_out_tomorrow_reservation(self, service_setup):
        """Case 1: target_date 08/11 with 08/11 09:30~10:30, 08/11 10:30~14:00, 08/12 08:00~09:00 -> Only 2 slots returned."""
        service, client = service_setup
        now = dt(11, 8, 0)

        client.get_assets.return_value = [{"id": 50, "name": "5층 회의실"}]
        client.get_items.return_value = [{"id": 501, "name": "회의실 5-1"}]
        client.get_daily_reservations.return_value = [
            {"itemId": 501, "start": "2026-08-11T09:30:00+09:00", "end": "2026-08-11T10:30:00+09:00"},
            {"itemId": 501, "start": "2026-08-11T10:30:00+09:00", "end": "2026-08-11T14:00:00+09:00"},
            {"itemId": 501, "start": "2026-08-12T08:00:00+09:00", "end": "2026-08-12T09:00:00+09:00"},
        ]

        res = service.get_room_detail(asset_id=50, room_id=501, date=now, now=now)

        slots = res["reservation_slots"]
        assert len(slots) == 2
        assert slots[0] == (dt(11, 9, 30), dt(11, 10, 30))
        assert slots[1] == (dt(11, 10, 30), dt(11, 14, 0))

    def test_case_2_returns_empty_slots_when_only_tomorrow_reservation_exists(self, service_setup):
        """Case 2: target_date 08/11 with 08/12 08:00~09:00 -> Empty reservation_slots ([])."""
        service, client = service_setup
        now = dt(11, 17, 0)

        client.get_assets.return_value = [{"id": 50, "name": "5층 회의실"}]
        client.get_items.return_value = [{"id": 501, "name": "회의실 5-1"}]
        client.get_daily_reservations.return_value = [
            {"itemId": 501, "start": "2026-08-12T08:00:00+09:00", "end": "2026-08-12T09:00:00+09:00"},
        ]

        res = service.get_room_detail(asset_id=50, room_id=501, date=now, now=now)

        slots = res["reservation_slots"]
        assert len(slots) == 0

    def test_case_3_filters_both_yesterday_and_tomorrow_reservations(self, service_setup):
        """Case 3: target_date 08/11 with 08/10 15~16, 08/11 09~10, 08/12 08~09 -> Only 08/11 09~10 returned."""
        service, client = service_setup
        now = dt(11, 12, 0)

        client.get_assets.return_value = [{"id": 50, "name": "5층 회의실"}]
        client.get_items.return_value = [{"id": 501, "name": "회의실 5-1"}]
        client.get_daily_reservations.return_value = [
            {"itemId": 501, "start": "2026-08-10T15:00:00+09:00", "end": "2026-08-10T16:00:00+09:00"},
            {"itemId": 501, "start": "2026-08-11T09:00:00+09:00", "end": "2026-08-11T10:00:00+09:00"},
            {"itemId": 501, "start": "2026-08-12T08:00:00+09:00", "end": "2026-08-12T09:00:00+09:00"},
        ]

        res = service.get_room_detail(asset_id=50, room_id=501, date=now, now=now)

        slots = res["reservation_slots"]
        assert len(slots) == 1
        assert slots[0] == (dt(11, 9, 0), dt(11, 10, 0))

    def test_case_4_sorts_today_reservations_in_start_time_ascending_order(self, service_setup):
        """Case 4: Today's reservations in shuffled order returned in start_time ascending order."""
        service, client = service_setup
        now = dt(11, 7, 0)

        client.get_assets.return_value = [{"id": 50, "name": "5층 회의실"}]
        client.get_items.return_value = [{"id": 501, "name": "회의실 5-1"}]
        client.get_daily_reservations.return_value = [
            {"itemId": 501, "start": "2026-08-11T13:00:00+09:00", "end": "2026-08-11T14:00:00+09:00"},
            {"itemId": 501, "start": "2026-08-11T08:00:00+09:00", "end": "2026-08-11T09:00:00+09:00"},
            {"itemId": 501, "start": "2026-08-11T09:30:00+09:00", "end": "2026-08-11T10:30:00+09:00"},
        ]

        res = service.get_room_detail(asset_id=50, room_id=501, date=now, now=now)

        slots = res["reservation_slots"]
        assert len(slots) == 3
        assert slots[0] == (dt(11, 8, 0), dt(11, 9, 0))
        assert slots[1] == (dt(11, 9, 30), dt(11, 10, 30))
        assert slots[2] == (dt(11, 13, 0), dt(11, 14, 0))

    def test_case_5_available_status_no_remaining_today_and_tomorrow_reservation(self, service_setup):
        """Case 5: AVAILABLE status with no remaining today reservations and 08/12 08:00 reservation.
        Status: '오늘 추가 예약 없음', Slots: [].
        """
        service, client = service_setup
        now = dt(11, 17, 0)

        client.get_assets.return_value = [{"id": 50, "name": "5층 회의실"}]
        client.get_items.return_value = [{"id": 501, "name": "회의실 5-1"}]
        client.get_daily_reservations.return_value = [
            {"itemId": 501, "start": "2026-08-11T09:00:00+09:00", "end": "2026-08-11T10:00:00+09:00"},
            {"itemId": 501, "start": "2026-08-12T08:00:00+09:00", "end": "2026-08-12T09:00:00+09:00"},
        ]

        res = service.get_room_detail(asset_id=50, room_id=501, date=now, now=now)

        st = res["status"]
        assert st.is_available is True
        assert st.next_reservation_start is None

        slots = res["reservation_slots"]
        assert len(slots) == 1  # 09:00~10:00 is today's schedule
        assert slots[0] == (dt(11, 9, 0), dt(11, 10, 0))

    def test_case_6_available_status_with_today_1800_and_tomorrow_0800(self, service_setup):
        """Case 6: AVAILABLE status with today 18:00 and tomorrow 08:00.
        Status next_reservation_start: 18:00, Slots contain only today's reservations.
        """
        service, client = service_setup
        now = dt(11, 17, 0)

        client.get_assets.return_value = [{"id": 50, "name": "5층 회의실"}]
        client.get_items.return_value = [{"id": 501, "name": "회의실 5-1"}]
        client.get_daily_reservations.return_value = [
            {"itemId": 501, "start": "2026-08-11T18:00:00+09:00", "end": "2026-08-11T19:00:00+09:00"},
            {"itemId": 501, "start": "2026-08-12T08:00:00+09:00", "end": "2026-08-12T09:00:00+09:00"},
        ]

        res = service.get_room_detail(asset_id=50, room_id=501, date=now, now=now)

        st = res["status"]
        assert st.is_available is True
        assert st.next_reservation_start == dt(11, 18, 0)

        slots = res["reservation_slots"]
        assert len(slots) == 1
        assert slots[0] == (dt(11, 18, 0), dt(11, 19, 0))
