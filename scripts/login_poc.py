"""Groupware Login & Query Proof of Concept (POC) Script.

Executes Groupware login and tests Asset, Item, and Daily APIs using requests.Session.
Strictly adheres to security guidelines (no credentials or cookies printed).
"""

import getpass
import sys
from pathlib import Path

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


def parse_rooms(items_data):
    """Extract room list from item API response."""
    rooms = []
    # Candidate lists in response JSON
    raw_list = []
    if isinstance(items_data, dict):
        for key in ["data", "items", "list", "result", "content"]:
            val = items_data.get(key)
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
        if not raw_list and isinstance(items_data.get("data"), list):
            raw_list = items_data["data"]
    elif isinstance(items_data, list):
        raw_list = items_data

    for item in raw_list:
        if not isinstance(item, dict):
            continue
        room_id = item.get("id") or item.get("itemId") or item.get("assetItemId")
        room_name = item.get("name") or item.get("itemName") or item.get("title") or item.get("assetItemName")
        if room_id is not None and room_name is not None:
            rooms.append((room_id, room_name))

    return rooms


def count_reservations(daily_data):
    """Count total reservation items received without exposing sensitive details."""
    count = 0
    raw_items = []
    if isinstance(daily_data, dict):
        for key in ["data", "items", "reservations", "list", "result"]:
            val = daily_data.get(key)
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
    elif isinstance(daily_data, list):
        raw_items = daily_data

    for entry in raw_items:
        if isinstance(entry, dict):
            # If entry contains a sub-list of reservations/items
            res_list = entry.get("reservations") or entry.get("items") or entry.get("schedules")
            if isinstance(res_list, list):
                count += len(res_list)
            else:
                count += 1
        else:
            count += 1

    return count


def main():
    print("=== Groupware Login POC ===")
    print()

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

    # 1. Login
    try:
        login_success = client.login(username, password)
    except GroupwareAuthError:
        print("Groupware authentication failed")
        sys.exit(1)
    except GroupwareNetworkError as e:
        print(f"Network error during login: {e}")
        sys.exit(1)
    except (GroupwareAPIError, Exception) as e:
        print(f"Login failed: {e}")
        sys.exit(1)

    if not login_success:
        print("Groupware authentication failed")
        sys.exit(1)

    cookie_status = "AVAILABLE" if client.has_gosso_cookie() else "UNAVAILABLE"

    # 2. Asset API
    try:
        asset_res = client.get_assets()
        asset_status = "SUCCESS"
    except GroupwareAuthError:
        print("Groupware authentication failed")
        sys.exit(1)
    except Exception as e:
        asset_status = f"FAILED ({e})"
        asset_res = {}

    # 3. 5F Item API (asset_id = 50)
    try:
        item_res = client.get_items(asset_id=50)
        item_status = "SUCCESS"
    except GroupwareAuthError:
        print("Groupware authentication failed")
        sys.exit(1)
    except Exception as e:
        item_status = f"FAILED ({e})"
        item_res = {}

    # 4. 5F Daily Reservations API (asset_id = 50)
    try:
        daily_res = client.get_daily_reservations(asset_id=50)
        daily_status = "SUCCESS"
    except GroupwareAuthError:
        print("Groupware authentication failed")
        sys.exit(1)
    except Exception as e:
        daily_status = f"FAILED ({e})"
        daily_res = {}

    # Format Output
    print(f"Login: SUCCESS")
    print(f"Session Cookie: {cookie_status}")
    print()
    print(f"Asset API: {asset_status}")
    print(f"Item API: {item_status}")
    print(f"Daily API: {daily_status}")
    print()

    rooms = parse_rooms(item_res)
    print("5F rooms:")
    if rooms:
        for room_id, room_name in rooms:
            print(f"- ID {room_id} : {room_name}")
    else:
        print("- (No rooms found or raw structure format)")

    print()
    res_count = count_reservations(daily_res)
    print(f"Reservations received: {res_count}")


if __name__ == "__main__":
    main()
