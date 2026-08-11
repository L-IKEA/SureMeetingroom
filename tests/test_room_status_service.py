"""Pytest suite for RoomStatusService and models."""

from datetime import datetime, timedelta, timezone
import pytest

from meeting_room_bot.models import Reservation, Room
from meeting_room_bot.services import RoomStatusService

SEOUL_TZ = timezone(timedelta(hours=9))


@pytest.fixture
def sample_room():
    return Room(
        id=130,
        asset_id=50,
        name="회의실 5-1",
        capacity=6,
        raw_name="회의실 5-1(6인 / TV)",
    )


def make_dt(hour: int, minute: int, day: int = 11) -> datetime:
    """Helper to create Asia/Seoul timezone-aware datetime."""
    return datetime(2026, 8, day, hour, minute, tzinfo=SEOUL_TZ)


class TestRoomModelParsing:

    def test_room_name_parsing_success(self):
        """Test regex extraction of room name and capacity."""
        name, capacity = Room.parse_raw_name("회의실 5-1(6인 / TV)")
        assert name == "회의실 5-1"
        assert capacity == 6

        name2, capacity2 = Room.parse_raw_name("보안룸 회의실 5-4(8인 / TV, 화상)")
        assert name2 == "보안룸 회의실 5-4"
        assert capacity2 == 8

        name3, capacity3 = Room.parse_raw_name("소회의실(4인)")
        assert name3 == "소회의실"
        assert capacity3 == 4

    def test_room_name_parsing_fallback(self):
        """Test fallback when raw_name does not fit standard pattern."""
        name, capacity = Room.parse_raw_name("회의실 A")
        assert name == "회의실 A"
        assert capacity is None

    def test_from_api_dict(self):
        """Test Room.from_api_dict construction."""
        item = {"id": 130, "name": "회의실 5-1(6인 / TV)"}
        room = Room.from_api_dict(item, asset_id=50)
        assert room.id == 130
        assert room.asset_id == 50
        assert room.name == "회의실 5-1"
        assert room.capacity == 6
        assert room.raw_name == "회의실 5-1(6인 / TV)"


class TestReservationSecurity:

    def test_reservation_omits_sensitive_data(self):
        """Verify Reservation model drops all personal information."""
        res_dict = {
            "id": 101,
            "itemId": 130,
            "startTime": "2026-08-11T10:00:00+09:00",
            "endTime": "2026-08-11T11:00:00+09:00",
            "userName": "홍길동",
            "title": "비밀 경영 회의",
            "company": "슈어소프트테크",
        }
        res = Reservation.from_api_dict(res_dict, room_id=130)
        assert res.id == 101
        assert res.room_id == 130
        assert not hasattr(res, "userName")
        assert not hasattr(res, "title")
        assert not hasattr(res, "company")


class TestRoomStatusService:

    def test_no_reservations(self, sample_room):
        """1. Room with zero reservations -> AVAILABLE, next_reservation_start is None."""
        now = make_dt(10, 0)
        status = RoomStatusService.calculate_status(sample_room, [], now=now)

        assert status.is_available
        assert not status.is_occupied
        assert status.next_reservation_start is None
        assert status.available_from is None

    def test_currently_occupied(self, sample_room):
        """2. Currently occupied -> OCCUPIED, available_from set to end of reservation."""
        now = make_dt(10, 0)
        res = Reservation(
            id=1,
            room_id=sample_room.id,
            start_time=make_dt(9, 30),
            end_time=make_dt(10, 30),
        )

        status = RoomStatusService.calculate_status(sample_room, [res], now=now)

        assert status.is_occupied
        assert status.available_from == make_dt(10, 30)
        assert status.next_reservation_start is None

    def test_available_with_future_reservation(self, sample_room):
        """3. Currently available with future reservation -> AVAILABLE, next_reservation_start set."""
        now = make_dt(10, 0)
        res = Reservation(
            id=1,
            room_id=sample_room.id,
            start_time=make_dt(14, 0),
            end_time=make_dt(15, 0),
        )

        status = RoomStatusService.calculate_status(sample_room, [res], now=now)

        assert status.is_available
        assert status.next_reservation_start == make_dt(14, 0)

    def test_right_after_reservation_end(self, sample_room):
        """4. Right at end_time boundary -> AVAILABLE."""
        res = Reservation(
            id=1,
            room_id=sample_room.id,
            start_time=make_dt(9, 30),
            end_time=make_dt(10, 30),
        )
        now = make_dt(10, 30)

        status = RoomStatusService.calculate_status(sample_room, [res], now=now)

        assert status.is_available

    def test_consecutive_reservations(self, sample_room):
        """5. Consecutive reservations (09:30~10:30 & 10:30~11:00) at 10:00 -> available_from is 11:00."""
        now = make_dt(10, 0)
        res1 = Reservation(
            id=1,
            room_id=sample_room.id,
            start_time=make_dt(9, 30),
            end_time=make_dt(10, 30),
        )
        res2 = Reservation(
            id=2,
            room_id=sample_room.id,
            start_time=make_dt(10, 30),
            end_time=make_dt(11, 0),
        )

        status = RoomStatusService.calculate_status(
            sample_room, [res1, res2], now=now
        )

        assert status.is_occupied
        assert status.available_from == make_dt(11, 0)

    def test_unsorted_reservations_input(self, sample_room):
        """6. Multiple reservations provided out of chronological order."""
        now = make_dt(10, 0)
        res_later = Reservation(
            id=2,
            room_id=sample_room.id,
            start_time=make_dt(14, 0),
            end_time=make_dt(15, 0),
        )
        res_earlier = Reservation(
            id=1,
            room_id=sample_room.id,
            start_time=make_dt(11, 0),
            end_time=make_dt(12, 0),
        )

        # Pass out-of-order list
        status = RoomStatusService.calculate_status(
            sample_room, [res_later, res_earlier], now=now
        )

        assert status.is_available
        assert status.next_reservation_start == make_dt(11, 0)

    def test_timezone_aware_datetime_handling(self, sample_room):
        """7. Naive datetime parameter throws ValueError."""
        naive_now = datetime(2026, 8, 11, 10, 0)  # No tzinfo

        with pytest.raises(ValueError, match="timezone-aware"):
            RoomStatusService.calculate_status(sample_room, [], now=naive_now)
