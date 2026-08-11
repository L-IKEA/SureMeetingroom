"""Reservation model definition and parsing logic."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

SEOUL_TZ = timezone(timedelta(hours=9))


def parse_to_seoul_datetime(val: Any) -> datetime:
    """Convert input string/timestamp/datetime to Asia/Seoul timezone-aware datetime."""
    if isinstance(val, datetime):
        dt = val
    elif isinstance(val, (int, float)):
        if val > 1e11:  # Timestamp in milliseconds
            val = val / 1000.0
        dt = datetime.fromtimestamp(val, tz=SEOUL_TZ)
    elif isinstance(val, str):
        val = val.strip()
        if val.endswith("Z"):
            val = val[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(val)
        except ValueError:
            try:
                dt = datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                dt = datetime.strptime(val, "%Y-%m-%d %H:%M")
    else:
        raise ValueError(f"Unsupported datetime value type: {type(val)}")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=SEOUL_TZ)
    else:
        dt = dt.astimezone(SEOUL_TZ)

    return dt


@dataclass
class Reservation:
    """Represents a meeting room reservation.

    Personal information (user name, meeting title, etc.) is strictly omitted.
    """

    id: int
    room_id: int
    start_time: datetime
    end_time: datetime

    def __post_init__(self):
        """Ensure datetimes are timezone-aware Asia/Seoul datetimes."""
        self.start_time = parse_to_seoul_datetime(self.start_time)
        self.end_time = parse_to_seoul_datetime(self.end_time)

    @classmethod
    def from_api_dict(cls, res_dict: Dict[str, Any], room_id: int) -> "Reservation":
        """Construct Reservation model from API dict, dropping all sensitive user info."""
        res_id = (
            res_dict.get("id")
            or res_dict.get("reservationId")
            or res_dict.get("seq")
            or 0
        )

        start_val = (
            res_dict.get("startTime")
            or res_dict.get("startDate")
            or res_dict.get("start")
            or res_dict.get("startDatetime")
            or res_dict.get("fromDate")
        )
        end_val = (
            res_dict.get("endTime")
            or res_dict.get("endDate")
            or res_dict.get("end")
            or res_dict.get("endDatetime")
            or res_dict.get("toDate")
        )

        if not start_val or not end_val:
            raise ValueError(f"Reservation dictionary missing start/end time: {res_dict.keys()}")

        start_dt = parse_to_seoul_datetime(start_val)
        end_dt = parse_to_seoul_datetime(end_val)

        return cls(
            id=int(res_id),
            room_id=int(room_id),
            start_time=start_dt,
            end_time=end_dt,
        )
