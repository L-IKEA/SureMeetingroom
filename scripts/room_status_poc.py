"""Meeting Room Data Normalization and Status Calculation POC Script.

Fetches 5F room data and daily reservations from Groupware API,
normalizes data into Room & Reservation models, and outputs room status.
Strictly omits personal data (user names, titles).
"""

import getpass
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

# Add project src to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.groupware.client import (
    GroupwareAPIError,
    GroupwareAuthError,
    GroupwareClient,
    GroupwareNetworkError,
)
from meeting_room_bot.models import Reservation, Room
from meeting_room_bot.services import RoomStatusService

SEOUL_TZ = timezone(timedelta(hours=9))


def parse_rooms_from_api(item_res: dict, asset_id: int = 50) -> List[Room]:
    """Parse Item API response dictionary into Room model instances."""
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

    rooms = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        try:
            room = Room.from_api_dict(item, asset_id=asset_id)
            rooms.append(room)
        except Exception:
            continue

    return rooms


def parse_reservations_by_room(daily_res: dict) -> Dict[int, List[Reservation]]:
    """Parse Daily API response and group Reservation models by room ID."""
    reservations_by_room: Dict[int, List[Reservation]] = defaultdict(list)

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

        # Check if entry is a room container holding reservations
        room_id = (
            entry.get("itemId")
            or entry.get("id")
            or entry.get("assetItemId")
        )
        res_list = (
            entry.get("reservations")
            or entry.get("items")
            or entry.get("schedules")
        )

        if isinstance(res_list, list) and room_id is not None:
            for r_dict in res_list:
                if isinstance(r_dict, dict):
                    try:
                        res = Reservation.from_api_dict(r_dict, room_id=int(room_id))
                        reservations_by_room[int(room_id)].append(res)
                    except Exception:
                        continue
        elif room_id is not None:
            # Single reservation entry
            try:
                res = Reservation.from_api_dict(entry, room_id=int(room_id))
                reservations_by_room[int(room_id)].append(res)
            except Exception:
                continue

    return reservations_by_room


def main():
    username = input("Username: ").strip()
    if not username:
        print("[FAIL] Username cannot be empty.")
        sys.exit(1)

    password = getpass.getpass("Password: ")
    if not password:
        print("[FAIL] Password cannot be empty.")
        sys.exit(1)

    print()
    client = GroupwareClient()

    try:
        login_success = client.login(username, password)
    except GroupwareAuthError:
        print("Groupware authentication failed")
        sys.exit(1)
    except Exception as e:
        print(f"Login failed: {e}")
        sys.exit(1)

    if not login_success:
        print("Groupware authentication failed")
        sys.exit(1)

    # Fetch 5F Item and Daily data
    asset_id = 50
    try:
        item_res = client.get_items(asset_id=asset_id)
        daily_res = client.get_daily_reservations(asset_id=asset_id)
    except GroupwareAuthError:
        print("Groupware authentication failed")
        sys.exit(1)
    except Exception as e:
        print(f"API query failed: {e}")
        sys.exit(1)

    rooms = parse_rooms_from_api(item_res, asset_id=asset_id)
    reservations_by_room = parse_reservations_by_room(daily_res)

    now = datetime.now(SEOUL_TZ)
    print("=== 5F Meeting Rooms ===")
    print(f"Checked at: {now.strftime('%Y-%m-%d %H:%M')}")
    print()

    for room in rooms:
        res_list = reservations_by_room.get(room.id, [])
        status_info = RoomStatusService.calculate_status(room, res_list, now=now)

        if status_info.is_occupied:
            print(f"🔴 {room.name}")
            print("   현재 사용 중")
            if status_info.available_from:
                print(f"   {status_info.available_from.strftime('%H:%M')}부터 사용 가능")
        else:
            print(f"🟢 {room.name}")
            print("   현재 비어 있음")
            if status_info.next_reservation_start:
                print(f"   다음 예약: {status_info.next_reservation_start.strftime('%H:%M')}")
            else:
                print("   오늘 추가 예약 없음")
        print()


if __name__ == "__main__":
    main()
