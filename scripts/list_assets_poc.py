"""POC script to list available meeting room locations/assets."""

import getpass
import sys
from pathlib import Path
from typing import List

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
from meeting_room_bot.models import Asset


def parse_meeting_assets(assets_res: dict) -> List[Asset]:
    """Parse Asset API response and return filtered meeting room assets."""
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

    meeting_assets: List[Asset] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        try:
            asset = Asset.from_api_dict(item)
            if asset.is_meeting_space():
                meeting_assets.append(asset)
        except Exception:
            continue

    return meeting_assets


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
        print(f"Failed to fetch assets: {e}")
        sys.exit(1)

    meeting_assets = parse_meeting_assets(assets_res)

    print("=== Meeting Room Locations ===")
    print()
    if not meeting_assets:
        print("No meeting space locations found.")
    else:
        for idx, asset in enumerate(meeting_assets, 1):
            print(f"{idx}. {asset.name}")


if __name__ == "__main__":
    main()
