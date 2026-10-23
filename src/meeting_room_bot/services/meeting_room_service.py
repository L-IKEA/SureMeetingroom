"""High-level Integrated Application Service for Meeting Room Querying."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional, Tuple, Union

from meeting_room_bot.config import get_config
from meeting_room_bot.groupware.client import GroupwareClient
from meeting_room_bot.models import Asset, Reservation, Room, UserKey
from meeting_room_bot.services.availability_service import AvailabilityService
from meeting_room_bot.services.room_status_service import RoomStatus, RoomStatusService

logger = logging.getLogger(__name__)
SEOUL_TZ = timezone(timedelta(hours=9))


def _parse_assets(assets_res: Any) -> List[Asset]:
    """Parse Asset API response into list of Asset objects."""
    raw_list = []
    if isinstance(assets_res, dict):
        for key in ["data", "assets", "items", "list", "result", "content"]:
            val = assets_res.get(key)
            if isinstance(val, list):
                raw_list = val
                break
            elif isinstance(val, dict):
                for subkey in ["list", "assets", "content"]:
                    if isinstance(val.get(subkey), list):
                        raw_list = val.get(subkey)
                        break
                if raw_list:
                    break
    elif isinstance(assets_res, list):
        raw_list = assets_res

    assets: List[Asset] = []
    for item in raw_list:
        if isinstance(item, dict):
            try:
                assets.append(Asset.from_api_dict(item))
            except Exception:
                continue
    return assets


def _parse_rooms(item_res: Any, asset_id: int) -> List[Room]:
    """Parse Item API response into list of Room objects."""
    raw_list = []
    if isinstance(item_res, dict):
        for key in ["data", "items", "list", "result", "content"]:
            val = item_res.get(key)
            if isinstance(val, list):
                raw_list = val
                break
            elif isinstance(val, dict):
                for subkey in ["list", "items", "content"]:
                    if isinstance(val.get(subkey), list):
                        raw_list = val.get(subkey)
                        break
                if raw_list:
                    break
    elif isinstance(item_res, list):
        raw_list = item_res

    rooms: List[Room] = []
    for item in raw_list:
        if isinstance(item, dict):
            try:
                rooms.append(Room.from_api_dict(item, asset_id=asset_id))
            except Exception:
                continue
    return rooms


def _parse_reservations_by_room(daily_res: Any) -> Dict[int, List[Reservation]]:
    """Parse Daily API response and group Reservation objects by room ID."""
    res_map: Dict[int, List[Reservation]] = defaultdict(list)
    raw_items = []

    if isinstance(daily_res, dict):
        for key in ["data", "items", "reservations", "list", "result"]:
            val = daily_res.get(key)
            if isinstance(val, list):
                raw_items = val
                break
            elif isinstance(val, dict):
                for subkey in ["list", "items", "reservations"]:
                    if isinstance(val.get(subkey), list):
                        raw_items = val.get(subkey)
                        break
                if raw_items:
                    break
    elif isinstance(daily_res, list):
        raw_items = daily_res

    for entry in raw_items:
        if not isinstance(entry, dict):
            continue
        room_id = entry.get("itemId") or entry.get("id") or entry.get("assetItemId")
        res_list = entry.get("reservations") or entry.get("items") or entry.get("schedules")

        if isinstance(res_list, list) and room_id is not None:
            for r_dict in res_list:
                if isinstance(r_dict, dict):
                    try:
                        res = Reservation.from_api_dict(r_dict, room_id=int(room_id))
                        res_map[int(room_id)].append(res)
                    except Exception:
                        continue
        elif room_id is not None:
            try:
                res = Reservation.from_api_dict(entry, room_id=int(room_id))
                res_map[int(room_id)].append(res)
            except Exception:
                continue

    return res_map


class MeetingRoomService:
    """High-level Application Service integrating meeting room queries."""

    def __init__(self, client: GroupwareClient):
        self.client = client

    def get_meeting_assets(self) -> List[Asset]:
        """Fetch all meeting space assets (filtered by exclude policy)."""
        assets_res = self.client.get_assets()
        all_assets = _parse_assets(assets_res)
        return [a for a in all_assets if a.is_meeting_space()]

    def _resolve_asset_ids(self, asset_ids: Optional[List[int]]) -> List[Asset]:
        """Resolve asset_ids into Asset objects. If asset_ids is None, fetch all meeting assets."""
        all_meeting_assets = self.get_meeting_assets()
        if asset_ids is None:
            return all_meeting_assets
        target_set = set(asset_ids)
        return [a for a in all_meeting_assets if a.id in target_set]

    def get_available_rooms_now(
        self,
        asset_ids: Optional[List[int]] = None,
        now: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Feature 1: Find all currently available meeting rooms across specified assets.

        Returns list of dicts:
        [
            {
                "asset": Asset,
                "room": Room,
                "status": RoomStatus,
                "next_reservation_start": Optional[datetime]
            },
            ...
        ]
        """
        if now is None:
            now = datetime.now(SEOUL_TZ)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=SEOUL_TZ)
        else:
            now = now.astimezone(SEOUL_TZ)

        target_assets = self._resolve_asset_ids(asset_ids)
        date_str = now.strftime("%Y-%m-%dT00:00:00.000+09:00")

        results: List[Dict[str, Any]] = []

        for asset in target_assets:
            item_res = self.client.get_items(asset.id)
            daily_res = self.client.get_daily_reservations(asset.id, date_str=date_str)

            rooms = _parse_rooms(item_res, asset.id)
            res_map = _parse_reservations_by_room(daily_res)

            for room in rooms:
                reservations = res_map.get(room.id, [])
                status_info = RoomStatusService.calculate_status(room, reservations, now=now)

                if status_info.is_available:
                    results.append({
                        "asset": asset,
                        "room": room,
                        "status": status_info,
                        "next_reservation_start": status_info.next_reservation_start,
                    })

        return results

    def get_available_rooms_at(
        self,
        asset_ids: Optional[List[int]],
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict[str, Any]]:
        """Feature 2: Find meeting rooms available for specified time slot [start_time, end_time).

        Returns list of dicts per asset:
        [
            {
                "asset": Asset,
                "available_rooms": List[Room],
                "unavailable_rooms": List[Room]
            },
            ...
        ]
        """
        target_assets = self._resolve_asset_ids(asset_ids)
        date_str = start_time.strftime("%Y-%m-%dT00:00:00.000+09:00")

        results: List[Dict[str, Any]] = []

        for asset in target_assets:
            item_res = self.client.get_items(asset.id)
            daily_res = self.client.get_daily_reservations(asset.id, date_str=date_str)

            rooms = _parse_rooms(item_res, asset.id)
            res_map = _parse_reservations_by_room(daily_res)

            avail, unavail = AvailabilityService.find_available_rooms(
                rooms, res_map, start_time, end_time
            )

            results.append({
                "asset": asset,
                "available_rooms": avail,
                "unavailable_rooms": unavail,
            })

        return results

    def get_location_status(
        self,
        asset_id: int,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Feature 3: Return current status of all rooms for a specific asset location.

        Returns dict:
        {
            "asset": Asset,
            "room_statuses": List[RoomStatus]
        }
        """
        if now is None:
            now = datetime.now(SEOUL_TZ)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=SEOUL_TZ)
        else:
            now = now.astimezone(SEOUL_TZ)

        all_assets = self.get_meeting_assets()
        asset = next((a for a in all_assets if a.id == asset_id), None)
        if asset is None:
            # Fallback if not found in list
            asset = Asset(id=asset_id, name=f"Asset {asset_id}", raw_name=f"Asset {asset_id}")

        date_str = now.strftime("%Y-%m-%dT00:00:00.000+09:00")
        item_res = self.client.get_items(asset_id)
        daily_res = self.client.get_daily_reservations(asset_id, date_str=date_str)

        rooms = _parse_rooms(item_res, asset_id)
        res_map = _parse_reservations_by_room(daily_res)

        statuses: List[RoomStatus] = []
        for room in rooms:
            reservations = res_map.get(room.id, [])
            status_info = RoomStatusService.calculate_status(room, reservations, now=now)
            statuses.append(status_info)

        return {
            "asset": asset,
            "room_statuses": statuses,
        }

    def get_room_detail(
        self,
        asset_id: int,
        room_id: int,
        date: Optional[datetime] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Feature 4: Return detail status and reservation time intervals for a single room.

        Personal information (user name, title, company) is strictly excluded.

        Returns dict:
        {
            "asset": Asset,
            "room": Room,
            "status": RoomStatus,
            "reservation_slots": List[Tuple[datetime, datetime]]
        }
        """
        if now is None:
            now = datetime.now(SEOUL_TZ)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=SEOUL_TZ)

        if date is None:
            target_date = now
        elif date.tzinfo is None:
            target_date = date.replace(tzinfo=SEOUL_TZ)
        else:
            target_date = date.astimezone(SEOUL_TZ)

        date_str = target_date.strftime("%Y-%m-%dT00:00:00.000+09:00")

        all_assets = self.get_meeting_assets()
        asset = next((a for a in all_assets if a.id == asset_id), None)
        if asset is None:
            asset = Asset(id=asset_id, name=f"Asset {asset_id}", raw_name=f"Asset {asset_id}")

        item_res = self.client.get_items(asset_id)
        daily_res = self.client.get_daily_reservations(asset_id, date_str=date_str)

        rooms = _parse_rooms(item_res, asset_id)
        res_map = _parse_reservations_by_room(daily_res)

        target_room = next((r for r in rooms if r.id == room_id), None)
        if target_room is None:
            # Construct a dummy room if not present in item list
            target_room = Room(id=room_id, asset_id=asset_id, name=f"Room {room_id}", capacity=None, raw_name=f"Room {room_id}")

        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        room_reservations = res_map.get(room_id, [])
        status_info = RoomStatusService.calculate_status(target_room, room_reservations, now=now)

        # Filter reservations overlapping with target_date
        today_reservations = [
            r for r in room_reservations
            if r.end_time > day_start and r.start_time < day_end
        ]
        sorted_res = sorted(today_reservations, key=lambda r: r.start_time)
        reservation_slots = [(r.start_time, r.end_time) for r in sorted_res]

        return {
            "asset": asset,
            "room": target_room,
            "status": status_info,
            "reservation_slots": reservation_slots,
        }

    def get_available_favorite_rooms_now(
        self,
        user_id: Union[UserKey, str],
        favorite_service: Any,
        now: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """Find currently available rooms within user's favorites.

        Returns empty list [] if user has no favorites.
        """
        if now is None:
            now = datetime.now(SEOUL_TZ)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=SEOUL_TZ)
        else:
            now = now.astimezone(SEOUL_TZ)

        fav_tuples = favorite_service.get_favorite_rooms(user_id, meeting_room_service=self)
        if not fav_tuples:
            return []

        date_str = now.strftime("%Y-%m-%dT00:00:00.000+09:00")
        results: List[Dict[str, Any]] = []

        # Group favorite rooms by asset_id to avoid redundant API calls
        by_asset: Dict[int, List[Tuple[Asset, Room]]] = defaultdict(list)
        for asset, room in fav_tuples:
            by_asset[asset.id].append((asset, room))

        for asset_id, items in by_asset.items():
            asset = items[0][0]
            daily_res = self.client.get_daily_reservations(asset_id, date_str=date_str)
            res_map = _parse_reservations_by_room(daily_res)

            for _, room in items:
                reservations = res_map.get(room.id, [])
                status_info = RoomStatusService.calculate_status(room, reservations, now=now)
                if status_info.is_available:
                    results.append({
                        "asset": asset,
                        "room": room,
                        "status": status_info,
                        "next_reservation_start": status_info.next_reservation_start,
                    })

        return results

    def get_available_favorite_rooms_at(
        self,
        user_id: Union[UserKey, str],
        favorite_service: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict[str, Any]]:
        """Find rooms within user's favorites available for specified time slot [start_time, end_time).

        Returns empty list [] if user has no favorites.
        """
        fav_tuples = favorite_service.get_favorite_rooms(user_id, meeting_room_service=self)
        if not fav_tuples:
            return []

        date_str = start_time.strftime("%Y-%m-%dT00:00:00.000+09:00")
        results: List[Dict[str, Any]] = []

        by_asset: Dict[int, List[Tuple[Asset, Room]]] = defaultdict(list)
        for asset, room in fav_tuples:
            by_asset[asset.id].append((asset, room))

        for asset_id, items in by_asset.items():
            asset = items[0][0]
            rooms = [r for _, r in items]
            daily_res = self.client.get_daily_reservations(asset_id, date_str=date_str)
            res_map = _parse_reservations_by_room(daily_res)

            avail, unavail = AvailabilityService.find_available_rooms(
                rooms, res_map, start_time, end_time
            )

            results.append({
                "asset": asset,
                "available_rooms": avail,
                "unavailable_rooms": unavail,
            })

        return results

    def get_timeline_data(
        self,
        asset_id: Optional[int] = None,
        user_key: Optional[UserKey] = None,
        favorite_service: Optional[Any] = None,
        target_date: Optional[datetime] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Fetch and calculate timeline grid data for an asset location on target_date.

        Calculates:
        - List of available assets for floor selector
        - Selected asset details
        - All rooms in the asset with capacity, favorite status, and available-now status
        - Normalized reservation blocks with [left_percent, width_percent] clamped to timeline bounds
        - Asia/Seoul current time indicator position (current_time_percent)
        - Reserver name and meeting title preserved according to presentation config
        """
        config = get_config()

        if now is None:
            now = datetime.now(SEOUL_TZ)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=SEOUL_TZ)
        else:
            now = now.astimezone(SEOUL_TZ)

        if target_date is None:
            target_date = now
        elif target_date.tzinfo is None:
            target_date = target_date.replace(tzinfo=SEOUL_TZ)
        else:
            target_date = target_date.astimezone(SEOUL_TZ)

        start_hour = config.timeline_start_hour
        end_hour = config.timeline_end_hour
        if end_hour <= start_hour:
            start_hour, end_hour = 8, 20

        total_minutes = (end_hour - start_hour) * 60

        # Timeline boundary for the day in Asia/Seoul
        timeline_start = target_date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        timeline_end = target_date.replace(hour=end_hour, minute=0, second=0, microsecond=0)

        # Korean day of week
        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
        date_display = f"{target_date.year}년 {target_date.month}월 {target_date.day}일 ({weekday_names[target_date.weekday()]})"

        # Current time indicator percent if viewing today
        current_time_percent: Optional[float] = None
        if now.date() == target_date.date():
            now_offset = (now - timeline_start).total_seconds() / 60.0
            if total_minutes > 0:
                current_time_percent = max(0.0, min(100.0, (now_offset / total_minutes) * 100.0))

        all_assets = self.get_meeting_assets()
        if not all_assets:
            return {
                "date": target_date.strftime("%Y-%m-%d"),
                "date_display": date_display,
                "current_time": now.strftime("%H:%M"),
                "start_hour": start_hour,
                "end_hour": end_hour,
                "hours": list(range(start_hour, end_hour + 1)),
                "current_time_percent": round(current_time_percent, 2) if current_time_percent is not None else None,
                "assets": [],
                "selected_asset": None,
                "rooms": [],
                "total_rooms": 0,
                "available_rooms_count": 0,
            }

        # Resolve selected asset
        selected_asset = None
        if asset_id is not None:
            selected_asset = next((a for a in all_assets if a.id == asset_id), None)
        if selected_asset is None:
            selected_asset = all_assets[0]

        # Asset metadata for dropdown
        assets_data = [
            {
                "id": a.id,
                "name": a.name,
                "short_label": a.name.replace("[판교] ", "").replace("[대전] ", "").strip(),
                "selected": (a.id == selected_asset.id),
            }
            for a in all_assets
        ]

        # Fetch rooms and reservations for selected asset
        date_str = target_date.strftime("%Y-%m-%dT00:00:00.000+09:00")
        item_res = self.client.get_items(selected_asset.id)
        daily_res = self.client.get_daily_reservations(selected_asset.id, date_str=date_str)

        rooms = _parse_rooms(item_res, selected_asset.id)
        res_map = _parse_reservations_by_room(daily_res)

        # Check user favorites
        user_fav_rooms = set()
        user_fav_assets = set()
        if favorite_service and user_key:
            try:
                uf = favorite_service.get_user_favorites(user_key)
                user_fav_rooms = uf.favorite_rooms
                user_fav_assets = uf.favorite_assets
            except Exception as e:
                logger.warning(f"Failed to load favorites for timeline: {e}")

        is_asset_fav = (selected_asset.id in user_fav_assets)

        rooms_data: List[Dict[str, Any]] = []
        for room in rooms:
            is_fav = is_asset_fav or (room.id in user_fav_rooms)
            room_reservations = res_map.get(room.id, [])

            status_info = RoomStatusService.calculate_status(room, room_reservations, now=now)
            is_available_now = status_info.is_available
            if is_available_now:
                status_text = "지금 빈 회의실"
                if status_info.next_reservation_start:
                    status_text = f"지금 비어있음 ({status_info.next_reservation_start.strftime('%H:%M')} 예약)"
            else:
                end_str = status_info.current_reservation_end.strftime("%H:%M") if status_info.current_reservation_end else ""
                status_text = f"사용 중 ({end_str}까지)" if end_str else "사용 중"

            # Filter & project reservations into timeline slots
            res_blocks: List[Dict[str, Any]] = []
            for r in room_reservations:
                if r.end_time <= timeline_start or r.start_time >= timeline_end:
                    continue
                clamped_start = max(r.start_time, timeline_start)
                clamped_end = min(r.end_time, timeline_end)
                start_offset = (clamped_start - timeline_start).total_seconds() / 60.0
                duration = (clamped_end - clamped_start).total_seconds() / 60.0

                left_pct = (start_offset / total_minutes) * 100.0
                width_pct = (duration / total_minutes) * 100.0
                if width_pct < 1.0:
                    width_pct = 1.0

                reserver_name = r.reserver_name if config.show_reserver_name else None
                meeting_title = r.meeting_title if config.show_meeting_title else None

                res_blocks.append({
                    "id": r.id,
                    "room_id": room.id,
                    "room_name": room.name,
                    "start_time": r.start_time.strftime("%H:%M"),
                    "end_time": r.end_time.strftime("%H:%M"),
                    "start_iso": r.start_time.isoformat(),
                    "end_iso": r.end_time.isoformat(),
                    "reserver_name": reserver_name,
                    "meeting_title": meeting_title,
                    "left_percent": round(left_pct, 2),
                    "width_percent": round(width_pct, 2),
                })

            res_blocks.sort(key=lambda b: b["start_time"])

            rooms_data.append({
                "id": room.id,
                "name": room.name,
                "capacity": room.capacity,
                "favorite": is_fav,
                "is_available_now": is_available_now,
                "status_text": status_text,
                "reservations": res_blocks,
            })

        return {
            "date": target_date.strftime("%Y-%m-%d"),
            "date_display": date_display,
            "current_time": now.strftime("%H:%M"),
            "start_hour": start_hour,
            "end_hour": end_hour,
            "hours": list(range(start_hour, end_hour + 1)),
            "current_time_percent": round(current_time_percent, 2) if current_time_percent is not None else None,
            "assets": assets_data,
            "selected_asset": {
                "id": selected_asset.id,
                "name": selected_asset.name,
                "short_label": selected_asset.name.replace("[판교] ", "").replace("[대전] ", "").strip(),
            },
            "rooms": rooms_data,
            "total_rooms": len(rooms_data),
            "available_rooms_count": sum(1 for r in rooms_data if r["is_available_now"]),
        }
