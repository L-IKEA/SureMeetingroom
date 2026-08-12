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
    current_reservation_end: Optional[datetime] = None
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

        # Define today's date boundaries in Asia/Seoul
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        # Normalize all reservation datetimes to Asia/Seoul
        normalized_res: List[Reservation] = []
        for r in reservations:
            st = r.start_time if r.start_time.tzinfo else r.start_time.replace(tzinfo=SEOUL_TZ)
            st = st.astimezone(SEOUL_TZ)
            et = r.end_time if r.end_time.tzinfo else r.end_time.replace(tzinfo=SEOUL_TZ)
            et = et.astimezone(SEOUL_TZ)
            normalized_res.append(
                Reservation(id=r.id, room_id=r.room_id, start_time=st, end_time=et)
            )

        # Filter reservations overlapping with today: r.end_time > day_start and r.start_time < day_end
        today_res = [
            r for r in normalized_res
            if r.end_time > day_start and r.start_time < day_end
        ]

        # Sort reservations by start_time
        sorted_res = sorted(today_res, key=lambda r: r.start_time)

        # Find all active reservations where start_time <= now < end_time
        active_reservations = [
            r for r in sorted_res if r.start_time <= now < r.end_time
        ]

        if active_reservations:
            # Status: OCCUPIED
            current_active = active_reservations[0]
            current_end = current_active.end_time

            # Next reservation today: earliest reservation starting strictly after now and before day_end excluding current_active
            next_reservations = [
                r for r in sorted_res
                if r.id != current_active.id and now < r.start_time < day_end
            ]
            next_start = min((r.start_time for r in next_reservations), default=None)

            # Calculate final available_from considering consecutive back-to-back reservations
            end_cursor = current_end
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
                current_reservation_end=current_end,
                next_reservation_start=next_start,
            )

        else:
            # Status: AVAILABLE
            # Find the earliest reservation starting strictly after now and before day_end (today only!)
            future_reservations = [
                r for r in sorted_res if now < r.start_time < day_end
            ]
            next_start = min((r.start_time for r in future_reservations), default=None)

            return RoomStatus(
                room=room,
                status="AVAILABLE",
                available_from=None,
                current_reservation_end=None,
                next_reservation_start=next_start,
            )
