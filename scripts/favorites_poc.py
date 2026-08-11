"""Favorites management and availability POC script."""

import getpass
import sys
from pathlib import Path
from typing import List

# Add project src to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.favorites import FavoriteService, JsonFavoriteRepository
from meeting_room_bot.groupware.client import GroupwareAuthError, GroupwareClient
from meeting_room_bot.models import Asset
from meeting_room_bot.services import MeetingRoomService


def handle_show_favorites(user_id: str, fav_service: FavoriteService, meeting_service: MeetingRoomService):
    """1. 내 즐겨찾기 보기."""
    uf = fav_service.get_user_favorites(user_id)

    print()
    print(f"⭐ [{user_id}] 님의 즐겨찾기")
    print()

    if uf.is_empty():
        print("등록된 즐겨찾기가 없습니다.")
        return

    meeting_assets = meeting_service.get_meeting_assets()
    asset_dict = {a.id: a for a in meeting_assets}

    print("위치 (Asset):")
    if uf.favorite_assets:
        for aid in sorted(uf.favorite_assets):
            asset = asset_dict.get(aid)
            name = asset.name if asset else f"Asset {aid}"
            print(f"- {name} (ID: {aid})")
    else:
        print("- (없음)")

    print()
    print("회의실 (Room):")
    if uf.favorite_rooms:
        for rid in sorted(uf.favorite_rooms):
            # Attempt to resolve room name across meeting assets
            found_name = f"Room {rid}"
            for asset in meeting_assets:
                try:
                    from meeting_room_bot.services.meeting_room_service import _parse_rooms
                    item_res = meeting_service.client.get_items(asset.id)
                    rooms = _parse_rooms(item_res, asset.id)
                    target_r = next((r for r in rooms if r.id == rid), None)
                    if target_r:
                        found_name = f"{asset.name} > {target_r.name}"
                        break
                except Exception:
                    continue
            print(f"- {found_name} (ID: {rid})")
    else:
        print("- (없음)")


def handle_add_asset(user_id: str, fav_service: FavoriteService, meeting_service: MeetingRoomService):
    """2. 위치 즐겨찾기 추가."""
    assets = meeting_service.get_meeting_assets()
    print()
    print("=== 위치 목록 ===")
    for idx, asset in enumerate(assets, 1):
        print(f"{idx}. {asset.name}")
    print()

    sel = input("추가할 위치 번호를 선택하세요: ").strip()
    try:
        idx = int(sel)
        if 1 <= idx <= len(assets):
            selected = assets[idx - 1]
            added = fav_service.add_asset(user_id, selected.id)
            if added:
                print(f"[OK] '{selected.name}' 위치가 즐겨찾기에 추가되었습니다.")
            else:
                print(f"[INFO] '{selected.name}' 위치는 이미 즐겨찾기에 있습니다.")
        else:
            print("[ERROR] 올바른 번호를 입력하세요.")
    except ValueError:
        print("[ERROR] 숫자를 입력하세요.")


def handle_add_room(user_id: str, fav_service: FavoriteService, meeting_service: MeetingRoomService):
    """3. 회의실 즐겨찾기 추가."""
    assets = meeting_service.get_meeting_assets()
    print()
    print("=== 위치 선택 ===")
    for idx, asset in enumerate(assets, 1):
        print(f"{idx}. {asset.name}")
    print()

    sel = input("위치를 선택하세요: ").strip()
    try:
        idx = int(sel)
        if not (1 <= idx <= len(assets)):
            print("[ERROR] 올바른 번호를 입력하세요.")
            return
        selected_asset = assets[idx - 1]
    except ValueError:
        print("[ERROR] 숫자를 입력하세요.")
        return

    from meeting_room_bot.services.meeting_room_service import _parse_rooms
    item_res = meeting_service.client.get_items(selected_asset.id)
    rooms = _parse_rooms(item_res, selected_asset.id)

    print()
    print(f"=== {selected_asset.name} 회의실 목록 ===")
    for r_idx, room in enumerate(rooms, 1):
        print(f"{r_idx}. {room.name}")
    print()

    r_sel = input("추가할 회의실 번호를 선택하세요: ").strip()
    try:
        r_idx = int(r_sel)
        if 1 <= r_idx <= len(rooms):
            target_room = rooms[r_idx - 1]
            added = fav_service.add_room(user_id, target_room.id)
            if added:
                print(f"[OK] '{target_room.name}' 회의실이 즐겨찾기에 추가되었습니다.")
            else:
                print(f"[INFO] '{target_room.name}' 회의실은 이미 즐겨찾기에 있습니다.")
        else:
            print("[ERROR] 올바른 번호를 입력하세요.")
    except ValueError:
        print("[ERROR] 숫자를 입력하세요.")


def handle_remove_asset(user_id: str, fav_service: FavoriteService, meeting_service: MeetingRoomService):
    """4. 위치 즐겨찾기 삭제."""
    uf = fav_service.get_user_favorites(user_id)
    if not uf.favorite_assets:
        print("[INFO] 삭제할 위치 즐겨찾기가 없습니다.")
        return

    meeting_assets = meeting_service.get_meeting_assets()
    asset_dict = {a.id: a for a in meeting_assets}

    fav_list = sorted(list(uf.favorite_assets))
    print()
    print("=== 위치 즐겨찾기 목록 ===")
    for idx, aid in enumerate(fav_list, 1):
        asset = asset_dict.get(aid)
        name = asset.name if asset else f"Asset {aid}"
        print(f"{idx}. {name}")
    print()

    sel = input("삭제할 번호를 선택하세요: ").strip()
    try:
        idx = int(sel)
        if 1 <= idx <= len(fav_list):
            target_aid = fav_list[idx - 1]
            fav_service.remove_asset(user_id, target_aid)
            print("[OK] 위치 즐겨찾기가 삭제되었습니다.")
        else:
            print("[ERROR] 올바른 번호를 입력하세요.")
    except ValueError:
        print("[ERROR] 숫자를 입력하세요.")


def handle_remove_room(user_id: str, fav_service: FavoriteService, meeting_service: MeetingRoomService):
    """5. 회의실 즐겨찾기 삭제."""
    uf = fav_service.get_user_favorites(user_id)
    if not uf.favorite_rooms:
        print("[INFO] 삭제할 회의실 즐겨찾기가 없습니다.")
        return

    fav_list = sorted(list(uf.favorite_rooms))
    print()
    print("=== 회의실 즐겨찾기 목록 ===")
    for idx, rid in enumerate(fav_list, 1):
        print(f"{idx}. Room ID {rid}")
    print()

    sel = input("삭제할 번호를 선택하세요: ").strip()
    try:
        idx = int(sel)
        if 1 <= idx <= len(fav_list):
            target_rid = fav_list[idx - 1]
            fav_service.remove_room(user_id, target_rid)
            print("[OK] 회의실 즐겨찾기가 삭제되었습니다.")
        else:
            print("[ERROR] 올바른 번호를 입력하세요.")
    except ValueError:
        print("[ERROR] 숫자를 입력하세요.")


def handle_favorite_rooms_now(user_id: str, fav_service: FavoriteService, meeting_service: MeetingRoomService):
    """6. 즐겨찾기 기준 현재 빈 회의실."""
    results = meeting_service.get_available_favorite_rooms_now(user_id, fav_service)

    print()
    print(f"=== [{user_id}] 즐겨찾기 기준 현재 빈 회의실 ===")
    print()

    if not results:
        uf = fav_service.get_user_favorites(user_id)
        if uf.is_empty():
            print("등록된 즐겨찾기가 없습니다.")
        else:
            print("현재 비어 있는 즐겨찾기 회의실이 없습니다.")
        return

    # Group by asset
    grouped: dict[str, list] = {}
    for item in results:
        asset_name = item["asset"].name
        grouped.setdefault(asset_name, []).append(item)

    for asset_name, items in grouped.items():
        print(f"[{asset_name}]")
        print()
        for item in items:
            room = item["room"]
            next_start = item["next_reservation_start"]
            print(f"🟢 {room.name}")
            if next_start:
                print(f"   {next_start.strftime('%H:%M')}부터 예약")
            else:
                print("   오늘 추가 예약 없음")
            print()


def main():
    print("=== Meeting Room Favorites POC ===")
    print()

    username = input("Groupware Username: ").strip()
    if not username:
        print("[FAIL] Username cannot be empty.")
        sys.exit(1)

    password = getpass.getpass("Groupware Password: ")
    if not password:
        print("[FAIL] Password cannot be empty.")
        sys.exit(1)

    current_user_id = input("User ID [default: local-user]: ").strip() or "local-user"

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

    meeting_service = MeetingRoomService(client)
    repo = JsonFavoriteRepository("data/favorites.json")
    fav_service = FavoriteService(repo=repo, meeting_room_service=meeting_service)

    while True:
        print()
        print(f"==========================================")
        print(f" 현재 사용자: [{current_user_id}]")
        print(f"==========================================")
        print("1. 내 즐겨찾기 보기")
        print("2. 위치 즐겨찾기 추가")
        print("3. 회의실 즐겨찾기 추가")
        print("4. 위치 즐겨찾기 삭제")
        print("5. 회의실 즐겨찾기 삭제")
        print("6. 즐겨찾기 기준 현재 빈 회의실")
        print("7. 다른 사용자 테스트")
        print("0. 종료")
        print("==========================================")

        choice = input("선택: ").strip()

        if choice == "1":
            handle_show_favorites(current_user_id, fav_service, meeting_service)
        elif choice == "2":
            handle_add_asset(current_user_id, fav_service, meeting_service)
        elif choice == "3":
            handle_add_room(current_user_id, fav_service, meeting_service)
        elif choice == "4":
            handle_remove_asset(current_user_id, fav_service, meeting_service)
        elif choice == "5":
            handle_remove_room(current_user_id, fav_service, meeting_service)
        elif choice == "6":
            handle_favorite_rooms_now(current_user_id, fav_service, meeting_service)
        elif choice == "7":
            new_user = input("새 User ID 입력: ").strip()
            if new_user:
                current_user_id = new_user
                print(f"[OK] 사용자가 [{current_user_id}] (으)로 변경되었습니다.")
        elif choice == "0":
            print("프로그램을 종료합니다.")
            break
        else:
            print("잘못된 선택입니다.")


if __name__ == "__main__":
    main()
