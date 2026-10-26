"""Reservation model definition and parsing logic."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Union

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


def _get_property_content(res_dict: Dict[str, Any], attribute_id: Union[int, str]) -> Optional[str]:
    """Safely extract content string from properties array by attributeId (e.g. 50=title, 51=reserver)."""
    properties = res_dict.get("properties")
    if not isinstance(properties, list):
        return None
    target_id_str = str(attribute_id).strip()
    for prop in properties:
        if not isinstance(prop, dict):
            continue
        attr_id = prop.get("attributeId")
        if attr_id is not None and str(attr_id).strip() == target_id_str:
            content = prop.get("content")
            if content is not None:
                content_str = str(content).strip()
                if content_str:
                    return content_str
    return None


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
    use_anonym: bool = False

    def __post_init__(self):
        """Ensure datetimes are timezone-aware Asia/Seoul datetimes."""
        self.start_time = parse_to_seoul_datetime(self.start_time)
        self.end_time = parse_to_seoul_datetime(self.end_time)

    @classmethod
    def from_api_dict(cls, res_dict: Dict[str, Any], room_id: Optional[int] = None) -> "Reservation":
        """Construct Reservation model from API dict."""
        res_id = (
            res_dict.get("id")
            or res_dict.get("reservationId")
            or res_dict.get("seq")
            or 0
        )

        resolved_room_id = (
            room_id
            or res_dict.get("itemId")
            or res_dict.get("roomId")
            or res_dict.get("assetItemId")
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

        # 1. Anonymity check: useAnonym
        use_anonym_val = res_dict.get("useAnonym")
        is_anonym = False
        if isinstance(use_anonym_val, bool):
            is_anonym = use_anonym_val
        elif isinstance(use_anonym_val, str):
            is_anonym = use_anonym_val.strip().lower() in ("true", "1", "yes")

        if is_anonym:
            reserver_name = "비공개"
            meeting_title = "비공개"
        else:
            # 2. Reserver Name mapping
            # Priority 1 (authoritative): res_dict["user"]["name"]
            reserver_name = None
            user_obj = res_dict.get("user")
            if isinstance(user_obj, dict):
                uname = user_obj.get("name")
                if uname is not None and str(uname).strip():
                    reserver_name = str(uname).strip()

            # Fallback 1: properties array attributeId == 51
            if not reserver_name:
                prop_reserver = _get_property_content(res_dict, 51)
                if prop_reserver:
                    reserver_name = prop_reserver

            # Fallback 2: legacy/compatibility fields
            if not reserver_name:
                legacy_reserver = (
                    res_dict.get("userName")
                    or res_dict.get("empName")
                    or res_dict.get("reserverName")
                    or res_dict.get("registerName")
                    or res_dict.get("writer")
                )
                if legacy_reserver is not None and str(legacy_reserver).strip():
                    reserver_name = str(legacy_reserver).strip()

            # 3. Meeting Title mapping
            # Priority 1 (authoritative): properties array attributeId == 50
            meeting_title = _get_property_content(res_dict, 50)

            # Fallback: legacy/compatibility fields
            if not meeting_title:
                legacy_title = (
                    res_dict.get("title")
                    or res_dict.get("subject")
                    or res_dict.get("meetingTitle")
                    or res_dict.get("scheduleTitle")
                )
                if legacy_title is not None and str(legacy_title).strip():
                    meeting_title = str(legacy_title).strip()

        return cls(
            id=int(res_id),
            room_id=int(resolved_room_id),
            start_time=start_dt,
            end_time=end_dt,
            reserver_name=str(reserver_name).strip() if reserver_name else None,
            meeting_title=str(meeting_title).strip() if meeting_title else None,
            use_anonym=is_anonym,
        )
