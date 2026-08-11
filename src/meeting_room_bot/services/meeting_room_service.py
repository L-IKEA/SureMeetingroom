"""High-level Integrated Application Service for Meeting Room Querying."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from meeting_room_bot.groupware.client import GroupwareClient
from meeting_room_bot.models import Asset, Reservation, Room
from meeting_room_bot.services.availability_service import AvailabilityService
from meeting_room_bot.services.room_status_service import RoomStatus, RoomStatusService

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

        room_reservations = res_map.get(room_id, [])
        status_info = RoomStatusService.calculate_status(target_room, room_reservations, now=now)

        sorted_res = sorted(room_reservations, key=lambda r: r.start_time)
        reservation_slots = [(r.start_time, r.end_time) for r in sorted_res]

        return {
            "asset": asset,
            "room": target_room,
            "status": status_info,
            "reservation_slots": reservation_slots,
        }

    def get_available_favorite_rooms_now(
        self,
        user_id: str,
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

        fav_tuples = favorite_service.get_favorite_rooms(user_id)
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
        user_id: str,
        favorite_service: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict[str, Any]]:
        """Find rooms within user's favorites available for specified time slot [start_time, end_time).

        Returns empty list [] if user has no favorites.
        """
        fav_tuples = favorite_service.get_favorite_rooms(user_id)
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
