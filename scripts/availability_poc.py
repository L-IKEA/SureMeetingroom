"""Interactive POC script to search available meeting rooms for a specific time slot."""

import getpass
import sys
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
)
from meeting_room_bot.models import Asset, Reservation, Room
from meeting_room_bot.services import AvailabilityService
from list_assets_poc import parse_meeting_assets
from room_status_poc import parse_reservations_by_room, parse_rooms_from_api

SEOUL_TZ = timezone(timedelta(hours=9))


def prompt_location(meeting_assets: List[Asset]) -> Asset:
    """Prompt user to select a location/floor from available assets."""
    print("Select location:")
    print()
    for idx, asset in enumerate(meeting_assets, 1):
        print(f"{idx}. {asset.name}")
    print()

    sel_str = input("Select: ").strip()
    try:
        idx = int(sel_str)
        if 1 <= idx <= len(meeting_assets):
            return meeting_assets[idx - 1]
        print(f"[ERROR] Invalid choice. Please enter a number between 1 and {len(meeting_assets)}.")
        sys.exit(1)
    except ValueError:
        print("[ERROR] Invalid choice. Please enter a valid integer.")
        sys.exit(1)


def prompt_date() -> datetime:
    """Prompt user for date (YYYY-MM-DD or Enter for today)."""
    now_seoul = datetime.now(SEOUL_TZ)
    date_str = input("Date [YYYY-MM-DD, Enter=today]: ").strip()

    if not date_str:
        return now_seoul.replace(hour=0, minute=0, second=0, microsecond=0)

    try:
        parsed_dt = datetime.strptime(date_str, "%Y-%m-%d")
        return parsed_dt.replace(tzinfo=SEOUL_TZ)
    except ValueError:
        print("[ERROR] Invalid date format. Please use YYYY-MM-DD (e.g. 2026-08-11).")
        sys.exit(1)


def prompt_start_time() -> tuple[int, int]:
    """Prompt user for start time (HH:MM)."""
    time_str = input("Start time [HH:MM]: ").strip()
    try:
        t = datetime.strptime(time_str, "%H:%M")
        return t.hour, t.minute
    except ValueError:
        print("[ERROR] Invalid time format. Please use HH:MM (e.g. 14:00).")
        sys.exit(1)


def prompt_duration_minutes() -> int:
    """Prompt user for duration in minutes."""
    print()
    print("Duration:")
    print("1. 30 minutes")
    print("2. 60 minutes")
    print("3. 90 minutes")
    print("4. 120 minutes")
    print()

    dur_str = input("Select: ").strip()
    dur_map = {"1": 30, "2": 60, "3": 90, "4": 120}

    if dur_str in dur_map:
        return dur_map[dur_str]

    # Check if user entered raw number of minutes (e.g. 45)
    try:
        mins = int(dur_str)
        if mins <= 0:
            print("[ERROR] Duration must be greater than 0 minutes.")
            sys.exit(1)
        return mins
    except ValueError:
        print("[ERROR] Invalid duration selection. Please select 1-4 or enter minutes.")
        sys.exit(1)


def main():
    print("=== Meeting Room Availability POC ===")
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

    try:
        if not client.login(username, password):
            print("Groupware authentication failed")
            sys.exit(1)
    except GroupwareAuthError:
        print("Groupware authentication failed")
        sys.exit(1)
    except Exception as e:
        print(f"Login failed: {e}")
        sys.exit(1)

    try:
        assets_res = client.get_assets()
    except GroupwareAuthError:
        print("Groupware authentication failed")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to fetch locations: {e}")
        sys.exit(1)

    meeting_assets = parse_meeting_assets(assets_res)
    if not meeting_assets:
        print("[ERROR] No meeting room locations found.")
        sys.exit(1)

    selected_asset = prompt_location(meeting_assets)
    base_date = prompt_date()
    start_hour, start_min = prompt_start_time()
    duration_mins = prompt_duration_minutes()

    requested_start = base_date.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
    requested_end = requested_start + timedelta(minutes=duration_mins)

    # Date string for daily API (YYYY-MM-DDT00:00:00.000+09:00)
    date_api_str = requested_start.strftime("%Y-%m-%dT00:00:00.000+09:00")

    try:
        item_res = client.get_items(asset_id=selected_asset.id)
        daily_res = client.get_daily_reservations(asset_id=selected_asset.id, date_str=date_api_str)
    except GroupwareAuthError:
        print("Groupware authentication failed")
        sys.exit(1)
    except Exception as e:
        print(f"API query failed: {e}")
        sys.exit(1)

    rooms = parse_rooms_from_api(item_res, asset_id=selected_asset.id)
    reservations_by_room = parse_reservations_by_room(daily_res)

    available_rooms, unavailable_rooms = AvailabilityService.find_available_rooms(
        rooms, reservations_by_room, requested_start, requested_end
    )

    print()
    print("=== Available Rooms ===")
    print()
    print(selected_asset.name)
    print(
        f"{requested_start.strftime('%Y-%m-%d %H:%M')} ~ {requested_end.strftime('%H:%M')}"
    )
    print()

    if available_rooms:
        for room in available_rooms:
            print(f"🟢 {room.name}")
    else:
        print("(No available rooms for this time slot)")

    print()
    print("Unavailable:")
    if unavailable_rooms:
        for room in unavailable_rooms:
            print(f"🔴 {room.name}")
    else:
        print("(None)")


if __name__ == "__main__":
    main()
