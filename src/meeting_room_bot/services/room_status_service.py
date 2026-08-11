"""Room status calculation service."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from meeting_room_bot.models.reservation import Reservation, parse_to_seoul_datetime
from meeting_room_bot.models.room import Room

SEOUL_TZ = timezone(timedelta(hours=9))


@dataclass
class RoomStatus:
    """Represents calculated status for a room at a specific datetime."""

    room: Room
    status: str  # "AVAILABLE" or "OCCUPIED"
    available_from: Optional[datetime] = None
    next_reservation_start: Optional[datetime] = None

    @property
    def is_available(self) -> bool:
        return self.status == "AVAILABLE"

    @property
    def is_occupied(self) -> bool:
        return self.status == "OCCUPIED"


class RoomStatusService:
    """Service to calculate current room availability and next reservation times."""

    @staticmethod
    def calculate_status(
        room: Room,
        reservations: List[Reservation],
        now: Optional[datetime] = None,
    ) -> RoomStatus:
        """Calculate status (AVAILABLE / OCCUPIED) for room at given datetime."""
        if now is None:
            now = datetime.now(SEOUL_TZ)
        else:
            if now.tzinfo is None:
                raise ValueError("now datetime must be timezone-aware (Asia/Seoul)")
            now = now.astimezone(SEOUL_TZ)

        # Ensure reservations are sorted by start_time
        sorted_res = sorted(reservations, key=lambda r: r.start_time)

        # Find all active reservations where start_time <= now < end_time
        active_reservations = [
            r for r in sorted_res if r.start_time <= now < r.end_time
        ]

        if active_reservations:
            # Status: OCCUPIED
            # Calculate final available_from considering consecutive reservations
            end_cursor = max(r.end_time for r in active_reservations)

            extended = True
            while extended:
                extended = False
                for r in sorted_res:
                    if r.start_time <= end_cursor < r.end_time:
                        end_cursor = r.end_time
                        extended = True

            return RoomStatus(
                room=room,
                status="OCCUPIED",
                available_from=end_cursor,
                next_reservation_start=None,
            )

        else:
            # Status: AVAILABLE
            # Find the earliest reservation starting after now
            future_reservations = [r for r in sorted_res if r.start_time > now]
            next_start = future_reservations[0].start_time if future_reservations else None

            return RoomStatus(
                room=room,
                status="AVAILABLE",
                available_from=None,
                next_reservation_start=next_start,
            )
