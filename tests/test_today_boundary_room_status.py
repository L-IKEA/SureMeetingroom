"""Pytest suite for Task 8 Today Date Boundary Defense in RoomStatusService."""

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.models import Room
from meeting_room_bot.models.reservation import Reservation
from meeting_room_bot.services.room_status_service import RoomStatusService

SEOUL_TZ = timezone(timedelta(hours=9))


def dt(day: int, hour: int, minute: int) -> datetime:
    return datetime(2026, 8, day, hour, minute, tzinfo=SEOUL_TZ)


class TestTodayBoundaryRoomStatus:

    @pytest.fixture
    def room(self):
        return Room(id=502, asset_id=50, name="회의실 5-2", capacity=8, raw_name="회의실 5-2")

    @pytest.fixture
    def now_1300(self):
        return dt(11, 13, 0)

    @pytest.fixture
    def now_1700(self):
        return dt(11, 17, 0)

    def test_case_1_tomorrow_reservation_ignored_when_today_future_exists(self, room, now_1300):
        """Case 1: 08/11 09~10, 08/11 14~15, 08/12 09~10 at 13:00 -> next = 08/11 14:00."""
        r1 = Reservation(id=1, room_id=502, start_time=dt(11, 9, 0), end_time=dt(11, 10, 0))
        r2 = Reservation(id=2, room_id=502, start_time=dt(11, 14, 0), end_time=dt(11, 15, 0))
        r3 = Reservation(id=3, room_id=502, start_time=dt(12, 9, 0), end_time=dt(12, 10, 0))

        st = RoomStatusService.calculate_status(room, [r1, r2, r3], now=now_1300)

        assert st.is_available is True
        assert st.next_reservation_start == dt(11, 14, 0)

    def test_case_2_tomorrow_reservation_ignored_when_today_all_past(self, room, now_1300):
        """Case 2: 08/11 09~10, 08/11 11~12, 08/12 09~10 at 13:00 -> next = None."""
        r1 = Reservation(id=1, room_id=502, start_time=dt(11, 9, 0), end_time=dt(11, 10, 0))
        r2 = Reservation(id=2, room_id=502, start_time=dt(11, 11, 0), end_time=dt(11, 12, 0))
        r3 = Reservation(id=3, room_id=502, start_time=dt(12, 9, 0), end_time=dt(12, 10, 0))

        st = RoomStatusService.calculate_status(room, [r1, r2, r3], now=now_1300)

        assert st.is_available is True
        assert st.next_reservation_start is None

    def test_case_3_only_tomorrow_reservation_at_1700(self, room, now_1700):
        """Case 3: 08/12 09~10 at 17:00 -> AVAILABLE, next = None."""
        r1 = Reservation(id=1, room_id=502, start_time=dt(12, 9, 0), end_time=dt(12, 10, 0))

        st = RoomStatusService.calculate_status(room, [r1], now=now_1700)

        assert st.is_available is True
        assert st.next_reservation_start is None

    def test_case_4_occupied_with_tomorrow_reservation_only(self, room, now_1300):
        """Case 4: 08/11 12:30~14:00, 08/12 09~10 at 13:00 -> OCCUPIED, current_end=14:00, next=None, available_from=14:00."""
        r1 = Reservation(id=1, room_id=502, start_time=dt(11, 12, 30), end_time=dt(11, 14, 0))
        r2 = Reservation(id=2, room_id=502, start_time=dt(12, 9, 0), end_time=dt(12, 10, 0))

        st = RoomStatusService.calculate_status(room, [r1, r2], now=now_1300)

        assert st.is_occupied is True
        assert st.current_reservation_end == dt(11, 14, 0)
        assert st.next_reservation_start is None
        assert st.available_from == dt(11, 14, 0)

    def test_case_5_occupied_with_today_next_and_tomorrow_reservation(self, room, now_1300):
        """Case 5: 08/11 12:30~14:00, 08/11 15~16, 08/12 09~10 at 13:00 -> current_end=14:00, next=15:00, available_from=14:00."""
        r1 = Reservation(id=1, room_id=502, start_time=dt(11, 12, 30), end_time=dt(11, 14, 0))
        r2 = Reservation(id=2, room_id=502, start_time=dt(11, 15, 0), end_time=dt(11, 16, 0))
        r3 = Reservation(id=3, room_id=502, start_time=dt(12, 9, 0), end_time=dt(12, 10, 0))

        st = RoomStatusService.calculate_status(room, [r1, r2, r3], now=now_1300)

        assert st.is_occupied is True
        assert st.current_reservation_end == dt(11, 14, 0)
        assert st.next_reservation_start == dt(11, 15, 0)
        assert st.available_from == dt(11, 14, 0)

    def test_case_6_occupied_back_to_back_and_tomorrow_reservation(self, room, now_1300):
        """Case 6: 08/11 12:30~14:00, 08/11 14~15, 08/12 09~10 at 13:00 -> current_end=14:00, next=14:00, available_from=15:00."""
        r1 = Reservation(id=1, room_id=502, start_time=dt(11, 12, 30), end_time=dt(11, 14, 0))
        r2 = Reservation(id=2, room_id=502, start_time=dt(11, 14, 0), end_time=dt(11, 15, 0))
        r3 = Reservation(id=3, room_id=502, start_time=dt(12, 9, 0), end_time=dt(12, 10, 0))

        st = RoomStatusService.calculate_status(room, [r1, r2, r3], now=now_1300)

        assert st.is_occupied is True
        assert st.current_reservation_end == dt(11, 14, 0)
        assert st.next_reservation_start == dt(11, 14, 0)
        assert st.available_from == dt(11, 15, 0)

    def test_case_7_multiple_tomorrow_reservations_returns_no_next_reservation(self, room, now_1700):
        """Case 7: Multiple reservations only on tomorrow -> AVAILABLE, next = None."""
        r1 = Reservation(id=1, room_id=502, start_time=dt(12, 9, 0), end_time=dt(12, 10, 0))
        r2 = Reservation(id=2, room_id=502, start_time=dt(12, 14, 0), end_time=dt(12, 15, 0))

        st = RoomStatusService.calculate_status(room, [r1, r2], now=now_1700)

        assert st.is_available is True
        assert st.next_reservation_start is None
