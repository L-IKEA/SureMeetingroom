"""Reservation model definition and parsing logic."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

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

    Personal information (user name, meeting title) is preserved for presentation layer if present.
    """

    id: int
    room_id: int
    start_time: datetime
    end_time: datetime
    reserver_name: Optional[str] = None
    meeting_title: Optional[str] = None

    def __post_init__(self):
        """Ensure datetimes are timezone-aware Asia/Seoul datetimes."""
        self.start_time = parse_to_seoul_datetime(self.start_time)
        self.end_time = parse_to_seoul_datetime(self.end_time)

    @classmethod
    def from_api_dict(cls, res_dict: Dict[str, Any], room_id: int) -> "Reservation":
        """Construct Reservation model from API dict."""
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

        # Map reserver name and meeting title from actual Groupware API fields if present
        reserver_name = (
            res_dict.get("userName")
            or res_dict.get("empName")
            or res_dict.get("reserverName")
            or res_dict.get("registerName")
            or res_dict.get("writer")
        )
        meeting_title = (
            res_dict.get("title")
            or res_dict.get("subject")
            or res_dict.get("meetingTitle")
            or res_dict.get("scheduleTitle")
        )

        return cls(
            id=int(res_id),
            room_id=int(room_id),
            start_time=start_dt,
            end_time=end_dt,
            reserver_name=str(reserver_name).strip() if reserver_name else None,
            meeting_title=str(meeting_title).strip() if meeting_title else None,
        )
