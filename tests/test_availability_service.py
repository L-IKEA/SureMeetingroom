"""Pytest suite for AvailabilityService and Asset model."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.models import Asset, Reservation, Room
from meeting_room_bot.services import AvailabilityService

SEOUL_TZ = timezone(timedelta(hours=9))


def make_dt(hour: int, minute: int, day: int = 11) -> datetime:
    """Helper to construct Asia/Seoul timezone-aware datetime."""
    return datetime(2026, 8, day, hour, minute, tzinfo=SEOUL_TZ)


@pytest.fixture
def sample_room():
    return Room(
        id=130,
        asset_id=50,
        name="회의실 5-1",
        capacity=6,
        raw_name="회의실 5-1(6인 / TV)",
    )


class TestAssetModel:

    def test_asset_is_meeting_space_filtering(self):
        """Verify asset filter includes meeting rooms and excludes vehicles, zoom, etc."""
        room_asset_1 = Asset(id=50, name="[판교] 5층 회의실", raw_name="[판교] 5층 회의실")
        room_asset_2 = Asset(id=60, name="[판교] 6층 프로젝트룸", raw_name="[판교] 6층 프로젝트룸")
        room_asset_3 = Asset(id=70, name="세미나룸", raw_name="세미나룸")

        vehicle_asset = Asset(id=10, name="법인차량 (아반떼)", raw_name="법인차량")
        zoom_asset = Asset(id=20, name="Zoom 계정 1", raw_name="Zoom 계정 1")
        pa_asset = Asset(id=30, name="PA 시스템", raw_name="PA 시스템")

        assert room_asset_1.is_meeting_space() is True
        assert room_asset_2.is_meeting_space() is True
        assert room_asset_3.is_meeting_space() is True

        assert vehicle_asset.is_meeting_space() is False
        assert zoom_asset.is_meeting_space() is False
        assert pa_asset.is_meeting_space() is False


class TestAvailabilityService:

    def test_1_no_reservations(self, sample_room):
        """1. Room with 0 reservations -> Available."""
        req_start = make_dt(14, 0)
        req_end = make_dt(15, 0)

        assert AvailabilityService.is_available(sample_room, [], req_start, req_end) is True

    def test_2_entire_requested_slot_free(self, sample_room):
        """2. Requested slot (14:00~15:00) is free with reservations at 10:00~11:00 & 16:00~17:00."""
        res1 = Reservation(id=1, room_id=130, start_time=make_dt(10, 0), end_time=make_dt(11, 0))
        res2 = Reservation(id=2, room_id=130, start_time=make_dt(16, 0), end_time=make_dt(17, 0))

        req_start = make_dt(14, 0)
        req_end = make_dt(15, 0)

        assert AvailabilityService.is_available(sample_room, [res1, res2], req_start, req_end) is True

    def test_3_request_start_equals_reservation_end(self, sample_room):
        """3. Reservation 13:00~14:00, Request 14:00~15:00 -> Available."""
        res = Reservation(id=1, room_id=130, start_time=make_dt(13, 0), end_time=make_dt(14, 0))

        req_start = make_dt(14, 0)
        req_end = make_dt(15, 0)

        assert AvailabilityService.is_available(sample_room, [res], req_start, req_end) is True

    def test_4_request_end_equals_reservation_start(self, sample_room):
        """4. Reservation 15:00~16:00, Request 14:00~15:00 -> Available."""
        res = Reservation(id=1, room_id=130, start_time=make_dt(15, 0), end_time=make_dt(16, 0))

        req_start = make_dt(14, 0)
        req_end = make_dt(15, 0)

        assert AvailabilityService.is_available(sample_room, [res], req_start, req_end) is True

    def test_5_front_overlap(self, sample_room):
        """5. Reservation 13:30~14:30, Request 14:00~15:00 -> Unavailable."""
        res = Reservation(id=1, room_id=130, start_time=make_dt(13, 30), end_time=make_dt(14, 30))

        req_start = make_dt(14, 0)
        req_end = make_dt(15, 0)

        assert AvailabilityService.is_available(sample_room, [res], req_start, req_end) is False

    def test_6_back_overlap(self, sample_room):
        """6. Reservation 14:30~15:30, Request 14:00~15:00 -> Unavailable."""
        res = Reservation(id=1, room_id=130, start_time=make_dt(14, 30), end_time=make_dt(15, 30))

        req_start = make_dt(14, 0)
        req_end = make_dt(15, 0)

        assert AvailabilityService.is_available(sample_room, [res], req_start, req_end) is False

    def test_7_enclosed_by_reservation(self, sample_room):
        """7. Reservation 13:00~16:00, Request 14:00~15:00 -> Unavailable."""
        res = Reservation(id=1, room_id=130, start_time=make_dt(13, 0), end_time=make_dt(16, 0))

        req_start = make_dt(14, 0)
        req_end = make_dt(15, 0)

        assert AvailabilityService.is_available(sample_room, [res], req_start, req_end) is False

    def test_8_reservation_inside_request(self, sample_room):
        """8. Reservation 14:15~14:45 inside Request 14:00~15:00 -> Unavailable."""
        res = Reservation(id=1, room_id=130, start_time=make_dt(14, 15), end_time=make_dt(14, 45))

        req_start = make_dt(14, 0)
        req_end = make_dt(15, 0)

        assert AvailabilityService.is_available(sample_room, [res], req_start, req_end) is False

    def test_9_multiple_reservations_one_conflict(self, sample_room):
        """9. Multiple reservations (10:00~11:00, 14:30~15:00, 16:00~17:00), Request 14:00~15:00 -> Unavailable."""
        res1 = Reservation(id=1, room_id=130, start_time=make_dt(10, 0), end_time=make_dt(11, 0))
        res2 = Reservation(id=2, room_id=130, start_time=make_dt(14, 30), end_time=make_dt(15, 0))
        res3 = Reservation(id=3, room_id=130, start_time=make_dt(16, 0), end_time=make_dt(17, 0))

        req_start = make_dt(14, 0)
        req_end = make_dt(15, 0)

        assert AvailabilityService.is_available(sample_room, [res1, res2, res3], req_start, req_end) is False

    def test_10_unsorted_reservations_input(self, sample_room):
        """10. Unsorted reservation list provided -> Handled correctly."""
        res_later = Reservation(id=2, room_id=130, start_time=make_dt(16, 0), end_time=make_dt(17, 0))
        res_conflict = Reservation(id=1, room_id=130, start_time=make_dt(14, 15), end_time=make_dt(14, 45))

        req_start = make_dt(14, 0)
        req_end = make_dt(15, 0)

        assert AvailabilityService.is_available(sample_room, [res_later, res_conflict], req_start, req_end) is False

    def test_11_timezone_aware_validation(self, sample_room):
        """11. Naive datetime raises ValueError."""
        naive_dt = datetime(2026, 8, 11, 14, 0)
        aware_dt = make_dt(15, 0)

        with pytest.raises(ValueError, match="timezone-aware"):
            AvailabilityService.is_available(sample_room, [], naive_dt, aware_dt)

        with pytest.raises(ValueError, match="timezone-aware"):
            AvailabilityService.is_available(sample_room, [], aware_dt, naive_dt)

    def test_12_multiple_rooms_returns_available_rooms_correctly(self):
        """12. find_available_rooms correctly separates available and unavailable rooms."""
        room1 = Room(id=130, asset_id=50, name="회의실 5-1", capacity=6, raw_name="회의실 5-1(6인)")
        room2 = Room(id=131, asset_id=50, name="회의실 5-2", capacity=6, raw_name="회의실 5-2(6인)")

        # room1 has conflicting reservation 14:00~15:00
        res1 = Reservation(id=1, room_id=130, start_time=make_dt(14, 0), end_time=make_dt(15, 0))
        # room2 has non-conflicting reservation 10:00~11:00
        res2 = Reservation(id=2, room_id=131, start_time=make_dt(10, 0), end_time=make_dt(11, 0))

        reservations_map = {
            130: [res1],
            131: [res2],
        }

        req_start = make_dt(14, 0)
        req_end = make_dt(15, 0)

        available, unavailable = AvailabilityService.find_available_rooms(
            [room1, room2], reservations_map, req_start, req_end
        )

        assert len(available) == 1
        assert available[0].id == 131

        assert len(unavailable) == 1
        assert unavailable[0].id == 130
