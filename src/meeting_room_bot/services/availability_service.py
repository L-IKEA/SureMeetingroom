"""Availability calculation service for specific time slots."""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple

from meeting_room_bot.models.reservation import Reservation
from meeting_room_bot.models.room import Room

SEOUL_TZ = timezone(timedelta(hours=9))


class AvailabilityService:
    """Service to compute room availability for specified time intervals."""

    @staticmethod
    def _validate_datetime(dt: datetime, name: str) -> datetime:
        """Ensure datetime is timezone-aware Asia/Seoul datetime."""
        if not isinstance(dt, datetime):
            raise TypeError(f"{name} must be a datetime object")
        if dt.tzinfo is None:
            raise ValueError(f"{name} must be timezone-aware (Asia/Seoul)")
        return dt.astimezone(SEOUL_TZ)

    @classmethod
    def is_available(
        cls,
        room: Room,
        reservations: List[Reservation],
        start_time: datetime,
        end_time: datetime,
    ) -> bool:
        """Check if a room is available for the given start_time to end_time slot.

        Conflict condition: reservation.start_time < requested_end AND reservation.end_time > requested_start
        """
        req_start = cls._validate_datetime(start_time, "start_time")
        req_end = cls._validate_datetime(end_time, "end_time")

        if req_start >= req_end:
            raise ValueError("start_time must be strictly earlier than end_time")

        # Unsorted inputs must be handled safely
        sorted_res = sorted(reservations, key=lambda r: r.start_time)

        for res in sorted_res:
            res_start = cls._validate_datetime(res.start_time, "reservation.start_time")
            res_end = cls._validate_datetime(res.end_time, "reservation.end_time")

            # Check conflict condition
            if res_start < req_end and res_end > req_start:
                return False

        return True

    @classmethod
    def find_available_rooms(
        cls,
        rooms: List[Room],
        reservations_by_room: Dict[int, List[Reservation]],
        start_time: datetime,
        end_time: datetime,
    ) -> Tuple[List[Room], List[Room]]:
        """Filter rooms into available and unavailable for the requested time slot.

        Returns tuple: (available_rooms, unavailable_rooms)
        """
        available_rooms: List[Room] = []
        unavailable_rooms: List[Room] = []

        for room in rooms:
            res_list = reservations_by_room.get(room.id, [])
            if cls.is_available(room, res_list, start_time, end_time):
                available_rooms.append(room)
            else:
                unavailable_rooms.append(room)

        return available_rooms, unavailable_rooms
