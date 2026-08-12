"""Pytest suite for Task 8 Precise RoomStatus calculation at 13:00 now."""

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


def dt(hour: int, minute: int) -> datetime:
    return datetime(2026, 8, 11, hour, minute, tzinfo=SEOUL_TZ)


class TestPreciseRoomStatusCalculation:

    @pytest.fixture
    def room(self):
        return Room(id=502, asset_id=50, name="회의실 5-2", capacity=8, raw_name="회의실 5-2")

    @pytest.fixture
    def now_1300(self):
        return dt(13, 0)

    def test_case_1_available_with_future_reservation(self, room, now_1300):
        """Case 1: 09:00~10:00, 14:00~15:00 at 13:00 -> AVAILABLE, next = 14:00."""
        r1 = Reservation(id=1, room_id=502, start_time=dt(9, 0), end_time=dt(10, 0))
        r2 = Reservation(id=2, room_id=502, start_time=dt(14, 0), end_time=dt(15, 0))

        st = RoomStatusService.calculate_status(room, [r1, r2], now=now_1300)

        assert st.is_available is True
        assert st.next_reservation_start == dt(14, 0)
        assert st.current_reservation_end is None
        assert st.available_from is None

    def test_case_2_available_with_past_reservations_only(self, room, now_1300):
        """Case 2: 09:00~10:00, 11:00~12:00 at 13:00 -> AVAILABLE, next = None."""
        r1 = Reservation(id=1, room_id=502, start_time=dt(9, 0), end_time=dt(10, 0))
        r2 = Reservation(id=2, room_id=502, start_time=dt(11, 0), end_time=dt(12, 0))

        st = RoomStatusService.calculate_status(room, [r1, r2], now=now_1300)

        assert st.is_available is True
        assert st.next_reservation_start is None
        assert st.current_reservation_end is None
        assert st.available_from is None

    def test_case_3_occupied_with_next_reservation(self, room, now_1300):
        """Case 3: 12:30~14:00, 15:00~16:00 at 13:00 -> OCCUPIED, current_end=14:00, next=15:00, available_from=14:00."""
        r1 = Reservation(id=1, room_id=502, start_time=dt(12, 30), end_time=dt(14, 0))
        r2 = Reservation(id=2, room_id=502, start_time=dt(15, 0), end_time=dt(16, 0))

        st = RoomStatusService.calculate_status(room, [r1, r2], now=now_1300)

        assert st.is_occupied is True
        assert st.current_reservation_end == dt(14, 0)
        assert st.next_reservation_start == dt(15, 0)
        assert st.available_from == dt(14, 0)

    def test_case_4_occupied_without_next_reservation(self, room, now_1300):
        """Case 4: 12:30~14:00 at 13:00 -> OCCUPIED, current_end=14:00, next=None, available_from=14:00."""
        r1 = Reservation(id=1, room_id=502, start_time=dt(12, 30), end_time=dt(14, 0))

        st = RoomStatusService.calculate_status(room, [r1], now=now_1300)

        assert st.is_occupied is True
        assert st.current_reservation_end == dt(14, 0)
        assert st.next_reservation_start is None
        assert st.available_from == dt(14, 0)

    def test_case_5_occupied_with_back_to_back_consecutive_reservations(self, room, now_1300):
        """Case 5: 12:30~14:00, 14:00~15:00 at 13:00 -> OCCUPIED, current_end=14:00, next=14:00, available_from=15:00."""
        r1 = Reservation(id=1, room_id=502, start_time=dt(12, 30), end_time=dt(14, 0))
        r2 = Reservation(id=2, room_id=502, start_time=dt(14, 0), end_time=dt(15, 0))

        st = RoomStatusService.calculate_status(room, [r1, r2], now=now_1300)

        assert st.is_occupied is True
        assert st.current_reservation_end == dt(14, 0)
        assert st.next_reservation_start == dt(14, 0)
        assert st.available_from == dt(15, 0)

    def test_case_6_multiple_past_and_future_reservations(self, room, now_1300):
        """Case 6: 09:00~10:00, 11:00~12:00, 14:00~15:00, 17:00~18:00 at 13:00 -> AVAILABLE, next=14:00."""
        r1 = Reservation(id=1, room_id=502, start_time=dt(9, 0), end_time=dt(10, 0))
        r2 = Reservation(id=2, room_id=502, start_time=dt(11, 0), end_time=dt(12, 0))
        r3 = Reservation(id=3, room_id=502, start_time=dt(14, 0), end_time=dt(15, 0))
        r4 = Reservation(id=4, room_id=502, start_time=dt(17, 0), end_time=dt(18, 0))

        st = RoomStatusService.calculate_status(room, [r1, r2, r3, r4], now=now_1300)

        assert st.is_available is True
        assert st.next_reservation_start == dt(14, 0)

    def test_case_7_shuffled_input_order_deterministic(self, room, now_1300):
        """Case 7: Shuffled input order yields identical deterministic output."""
        r1 = Reservation(id=1, room_id=502, start_time=dt(9, 0), end_time=dt(10, 0))
        r2 = Reservation(id=2, room_id=502, start_time=dt(11, 0), end_time=dt(12, 0))
        r3 = Reservation(id=3, room_id=502, start_time=dt(14, 0), end_time=dt(15, 0))
        r4 = Reservation(id=4, room_id=502, start_time=dt(17, 0), end_time=dt(18, 0))

        shuffled = [r3, r1, r4, r2]
        st = RoomStatusService.calculate_status(room, shuffled, now=now_1300)

        assert st.is_available is True
        assert st.next_reservation_start == dt(14, 0)
