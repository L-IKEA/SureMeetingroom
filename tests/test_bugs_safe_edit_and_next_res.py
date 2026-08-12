"""Pytest suite for Task 8 BUG 1 (safe_edit_message_text TypeError) & BUG 2 (Next reservation calculation)."""

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest
from telegram.error import BadRequest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.models import Room
from meeting_room_bot.models.reservation import Reservation
from meeting_room_bot.providers.real_provider import RealMeetingRoomProvider
from meeting_room_bot.services.room_status_service import RoomStatusService
from meeting_room_bot.telegram.handlers import safe_edit_message_text

SEOUL_TZ = timezone(timedelta(hours=9))


class TestBugFixes:

    def test_case_1_past_reservations_only_results_in_no_next_reservation(self):
        """CASE 1: Reservations 09:00~10:00 & 15:00~16:00, now 16:30 -> AVAILABLE, next_reservation_start = None."""
        room = Room(id=502, asset_id=50, name="회의실 5-2", capacity=8, raw_name="회의실 5-2")
        now = datetime(2026, 8, 11, 16, 30, tzinfo=SEOUL_TZ)

        res1 = Reservation(id=1, room_id=502, start_time=datetime(2026, 8, 11, 9, 0, tzinfo=SEOUL_TZ), end_time=datetime(2026, 8, 11, 10, 0, tzinfo=SEOUL_TZ))
        res2 = Reservation(id=2, room_id=502, start_time=datetime(2026, 8, 11, 15, 0, tzinfo=SEOUL_TZ), end_time=datetime(2026, 8, 11, 16, 0, tzinfo=SEOUL_TZ))

        st = RoomStatusService.calculate_status(room, [res1, res2], now=now)
        assert st.is_available is True
        assert st.next_reservation_start is None

    def test_case_2_past_and_future_reservations_selects_earliest_future(self):
        """CASE 2: Reservations 09:00~10:00, 15:00~16:00, 17:30~18:00, now 16:30 -> AVAILABLE, next_reservation_start = 17:30."""
        room = Room(id=502, asset_id=50, name="회의실 5-2", capacity=8, raw_name="회의실 5-2")
        now = datetime(2026, 8, 11, 16, 30, tzinfo=SEOUL_TZ)

        res1 = Reservation(id=1, room_id=502, start_time=datetime(2026, 8, 11, 9, 0, tzinfo=SEOUL_TZ), end_time=datetime(2026, 8, 11, 10, 0, tzinfo=SEOUL_TZ))
        res2 = Reservation(id=2, room_id=502, start_time=datetime(2026, 8, 11, 15, 0, tzinfo=SEOUL_TZ), end_time=datetime(2026, 8, 11, 16, 0, tzinfo=SEOUL_TZ))
        res3 = Reservation(id=3, room_id=502, start_time=datetime(2026, 8, 11, 17, 30, tzinfo=SEOUL_TZ), end_time=datetime(2026, 8, 11, 18, 0, tzinfo=SEOUL_TZ))

        st = RoomStatusService.calculate_status(room, [res1, res2, res3], now=now)
        assert st.is_available is True
        assert st.next_reservation_start == datetime(2026, 8, 11, 17, 30, tzinfo=SEOUL_TZ)

    def test_case_3_active_single_reservation_occupied(self):
        """CASE 3: Reservation 15:00~17:00, now 16:30 -> OCCUPIED, available_from = 17:00."""
        room = Room(id=502, asset_id=50, name="회의실 5-2", capacity=8, raw_name="회의실 5-2")
        now = datetime(2026, 8, 11, 16, 30, tzinfo=SEOUL_TZ)

        res = Reservation(id=1, room_id=502, start_time=datetime(2026, 8, 11, 15, 0, tzinfo=SEOUL_TZ), end_time=datetime(2026, 8, 11, 17, 0, tzinfo=SEOUL_TZ))

        st = RoomStatusService.calculate_status(room, [res], now=now)
        assert st.is_occupied is True
        assert st.available_from == datetime(2026, 8, 11, 17, 0, tzinfo=SEOUL_TZ)

    def test_case_4_active_back_to_back_reservations_occupied(self):
        """CASE 4: Reservations 15:00~17:00 & 17:00~18:00, now 16:30 -> OCCUPIED, available_from = 18:00."""
        room = Room(id=502, asset_id=50, name="회의실 5-2", capacity=8, raw_name="회의실 5-2")
        now = datetime(2026, 8, 11, 16, 30, tzinfo=SEOUL_TZ)

        res1 = Reservation(id=1, room_id=502, start_time=datetime(2026, 8, 11, 15, 0, tzinfo=SEOUL_TZ), end_time=datetime(2026, 8, 11, 17, 0, tzinfo=SEOUL_TZ))
        res2 = Reservation(id=2, room_id=502, start_time=datetime(2026, 8, 11, 17, 0, tzinfo=SEOUL_TZ), end_time=datetime(2026, 8, 11, 18, 0, tzinfo=SEOUL_TZ))

        st = RoomStatusService.calculate_status(room, [res1, res2], now=now)
        assert st.is_occupied is True
        assert st.available_from == datetime(2026, 8, 11, 18, 0, tzinfo=SEOUL_TZ)

    def test_case_5_exact_start_time_match_is_occupied(self):
        """CASE 5: Reservation 16:30~17:00, now 16:30 -> OCCUPIED."""
        room = Room(id=502, asset_id=50, name="회의실 5-2", capacity=8, raw_name="회의실 5-2")
        now = datetime(2026, 8, 11, 16, 30, tzinfo=SEOUL_TZ)

        res = Reservation(id=1, room_id=502, start_time=datetime(2026, 8, 11, 16, 30, tzinfo=SEOUL_TZ), end_time=datetime(2026, 8, 11, 17, 0, tzinfo=SEOUL_TZ))

        st = RoomStatusService.calculate_status(room, [res], now=now)
        assert st.is_occupied is True

    def test_case_6_telegram_note_formatting_for_past_only(self):
        """CASE 6: Reservation 09:00~10:00, now 16:30 -> Note is '오늘 추가 예약 없음'."""
        room = Room(id=502, asset_id=50, name="회의실 5-2", capacity=8, raw_name="회의실 5-2")
        now = datetime(2026, 8, 11, 16, 30, tzinfo=SEOUL_TZ)
        res = Reservation(id=1, room_id=502, start_time=datetime(2026, 8, 11, 9, 0, tzinfo=SEOUL_TZ), end_time=datetime(2026, 8, 11, 10, 0, tzinfo=SEOUL_TZ))

        st = RoomStatusService.calculate_status(room, [res], now=now)

        # Format note like real_provider.py
        if st.is_available:
            note = f"{st.next_reservation_start.strftime('%H:%M')}부터 예약" if st.next_reservation_start else "오늘 추가 예약 없음"
        else:
            note = f"{st.available_from.strftime('%H:%M')}부터 사용 가능" if st.available_from else "현재 사용 중"

        assert note == "오늘 추가 예약 없음"

    def test_case_7_shuffled_reservation_input_order(self):
        """CASE 7: Shuffled input order produces deterministic earliest future reservation."""
        room = Room(id=502, asset_id=50, name="회의실 5-2", capacity=8, raw_name="회의실 5-2")
        now = datetime(2026, 8, 11, 16, 30, tzinfo=SEOUL_TZ)

        res_future_late = Reservation(id=3, room_id=502, start_time=datetime(2026, 8, 11, 19, 0, tzinfo=SEOUL_TZ), end_time=datetime(2026, 8, 11, 20, 0, tzinfo=SEOUL_TZ))
        res_past = Reservation(id=1, room_id=502, start_time=datetime(2026, 8, 11, 9, 0, tzinfo=SEOUL_TZ), end_time=datetime(2026, 8, 11, 10, 0, tzinfo=SEOUL_TZ))
        res_future_early = Reservation(id=2, room_id=502, start_time=datetime(2026, 8, 11, 17, 30, tzinfo=SEOUL_TZ), end_time=datetime(2026, 8, 11, 18, 0, tzinfo=SEOUL_TZ))

        # Pass in shuffled order
        shuffled = [res_future_late, res_past, res_future_early]
        st = RoomStatusService.calculate_status(room, shuffled, now=now)

        assert st.is_available is True
        assert st.next_reservation_start == datetime(2026, 8, 11, 17, 30, tzinfo=SEOUL_TZ)

    @pytest.mark.anyio
    async def test_safe_edit_message_text_helper_behavior(self):
        """Test safe_edit_message_text helper parameter passing & exception handling."""
        query = MagicMock()
        query.edit_message_text = AsyncMock()

        # 1. Normal call with query, text, reply_markup
        await safe_edit_message_text(query, text="Test Message", reply_markup="keyboard_mock")
        query.edit_message_text.assert_called_once_with("Test Message", reply_markup="keyboard_mock")

        # 2. Message is not modified exception -> caught silently (no-op)
        query.edit_message_text.side_effect = BadRequest("Message is not modified: specified new message content...")
        await safe_edit_message_text(query, text="Same Message")

        # 3. Other BadRequest exception -> re-raised
        query.edit_message_text.side_effect = BadRequest("Chat not found")
        with pytest.raises(BadRequest, match="Chat not found"):
            await safe_edit_message_text(query, text="Test Message")
