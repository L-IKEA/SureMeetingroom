"""Interactive Terminal Menu POC for Meeting Room Queries.

Acts purely as a UI layer calling MeetingRoomService.
Does not contain direct business logic or raw API handling.
"""

import getpass
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional

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
from meeting_room_bot.services import MeetingRoomService

SEOUL_TZ = timezone(timedelta(hours=9))


def handle_get_now(service: MeetingRoomService, assets: List[Asset]):
    """Menu 1: 지금 빈 회의실."""
    print()
    print("=== 위치 선택 ===")
    print("0. 전체 위치")
    for idx, asset in enumerate(assets, 1):
        print(f"{idx}. {asset.name}")
    print()

    sel = input("선택 (콤마로 다중 선택 가능, 예: 1,2 또는 0=전체): ").strip()
    target_ids: Optional[List[int]] = None

    if sel and sel != "0":
        parts = [p.strip() for p in sel.split(",") if p.strip()]
        selected_ids = []
        for p in parts:
            try:
                idx = int(p)
                if 1 <= idx <= len(assets):
                    selected_ids.append(assets[idx - 1].id)
            except ValueError:
                continue
        if selected_ids:
            target_ids = selected_ids

    results = service.get_available_rooms_now(asset_ids=target_ids)

    print()
    print("=== 현재 빈 회의실 ===")
    print()

    if not results:
        print("현재 비어 있는 회의실이 없습니다.")
        return

    # Group results by asset
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


def handle_get_at(service: MeetingRoomService, assets: List[Asset]):
    """Menu 2: 언제 빈 회의실."""
    print()
    print("=== 시간대별 빈 회의실 조회 ===")
    now_seoul = datetime.now(SEOUL_TZ)

    date_str = input("날짜 [YYYY-MM-DD, Enter=오늘]: ").strip()
    if not date_str:
        base_date = now_seoul.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        try:
            base_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=SEOUL_TZ)
        except ValueError:
            print("[ERROR] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).")
            return

    time_str = input("시작시간 [HH:MM]: ").strip()
    try:
        t = datetime.strptime(time_str, "%H:%M")
        start_hour, start_min = t.hour, t.minute
    except ValueError:
        print("[ERROR] 시간 형식이 올바르지 않습니다 (HH:MM).")
        return

    print()
    print("사용시간:")
    print("1. 30분  2. 60분  3. 90분  4. 120분")
    dur_str = input("선택 (분 단위 직접 입력 가능): ").strip()
    dur_map = {"1": 30, "2": 60, "3": 90, "4": 120}

    if dur_str in dur_map:
        duration_mins = dur_map[dur_str]
    else:
        try:
            duration_mins = int(dur_str)
            if duration_mins <= 0:
                print("[ERROR] 사용시간은 0보다 커야 합니다.")
                return
        except ValueError:
            print("[ERROR] 올바른 수치를 입력해주세요.")
            return

    print()
    print("위치 선택:")
    print("0. 전체 위치")
    for idx, asset in enumerate(assets, 1):
        print(f"{idx}. {asset.name}")

    loc_str = input("선택: ").strip()
    target_ids: Optional[List[int]] = None
    if loc_str and loc_str != "0":
        try:
            idx = int(loc_str)
            if 1 <= idx <= len(assets):
                target_ids = [assets[idx - 1].id]
        except ValueError:
            pass

    req_start = base_date.replace(hour=start_hour, minute=start_min, second=0, microsecond=0)
    req_end = req_start + timedelta(minutes=duration_mins)

    results = service.get_available_rooms_at(target_ids, req_start, req_end)

    print()
    print("=== 해당 시간대 사용 가능한 회의실 ===")
    print(f"조회 시간: {req_start.strftime('%Y-%m-%d %H:%M')} ~ {req_end.strftime('%H:%M')}")
    print()

    for item in results:
        asset = item["asset"]
        avail_rooms = item["available_rooms"]
        unavail_rooms = item["unavailable_rooms"]

        print(f"[{asset.name}]")
        if avail_rooms:
            for r in avail_rooms:
                print(f"🟢 {r.name}")
        else:
            print("  (사용 가능한 회의실 없음)")

        if unavail_rooms:
            print("  사용 불가:")
            for r in unavail_rooms:
                print(f"  🔴 {r.name}")
        print()


def handle_get_location(service: MeetingRoomService, assets: List[Asset]):
    """Menu 3: 어디 빈 회의실 (위치별 전체 회의실 상태 & 상세)."""
    print()
    print("=== 위치 선택 ===")
    for idx, asset in enumerate(assets, 1):
        print(f"{idx}. {asset.name}")
    print()

    sel = input("선택: ").strip()
    try:
        idx = int(sel)
        if not (1 <= idx <= len(assets)):
            print("[ERROR] 올바른 번호를 선택해주세요.")
            return
        selected_asset = assets[idx - 1]
    except ValueError:
        print("[ERROR] 숫자를 입력해 주세요.")
        return

    location_data = service.get_location_status(selected_asset.id)
    room_statuses = location_data["room_statuses"]

    print()
    print(f"=== {selected_asset.name} ===")
    print()

    for idx, st in enumerate(room_statuses, 1):
        room = st.room
        if st.is_occupied:
            print(f"[{idx}] 🔴 {room.name}")
            print("    현재 사용 중")
            if st.available_from:
                print(f"    {st.available_from.strftime('%H:%M')}부터 사용 가능")
        else:
            print(f"[{idx}] 🟢 {room.name}")
            print("    현재 비어 있음")
            if st.next_reservation_start:
                print(f"    {st.next_reservation_start.strftime('%H:%M')}부터 예약")
            else:
                print("    오늘 추가 예약 없음")
        print()

    detail_sel = input("회의실 상세 정보를 볼 번호를 선택하세요 (Enter=메인 메뉴로): ").strip()
    if detail_sel:
        try:
            r_idx = int(detail_sel)
            if 1 <= r_idx <= len(room_statuses):
                target_room = room_statuses[r_idx - 1].room
                detail = service.get_room_detail(selected_asset.id, target_room.id)

                print()
                print(f"--- {target_room.name} 상세 정보 ---")
                print(f"위치: {selected_asset.name}")
                print(f"정원: {target_room.capacity or '미지정'}인")
                print(f"현재 상태: {'사용 중' if detail['status'].is_occupied else '비어 있음'}")
                print()
                print("오늘 예약 일정:")
                slots = detail["reservation_slots"]
                if slots:
                    for s_start, s_end in slots:
                        print(f"- {s_start.strftime('%H:%M')} ~ {s_end.strftime('%H:%M')}")
                else:
                    print("- 예약 없음")
                print()
        except ValueError:
            pass


def main():
    print("=== Groupware Meeting Room Query Bot ===")
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

    service = MeetingRoomService(client)

    try:
        assets = service.get_meeting_assets()
    except Exception as e:
        print(f"위치 목록을 가져오지 못했습니다: {e}")
        sys.exit(1)

    while True:
        print()
        print("==========================================")
        print("1. 지금 빈 회의실")
        print("2. 언제 빈 회의실")
        print("3. 어디 빈 회의실")
        print("0. 종료")
        print("==========================================")

        choice = input("메뉴 선택: ").strip()

        if choice == "1":
            try:
                handle_get_now(service, assets)
            except Exception as e:
                print(f"[오류] 지금 빈 회의실 조회 실패: {e}")
        elif choice == "2":
            try:
                handle_get_at(service, assets)
            except Exception as e:
                print(f"[오류] 시간대별 회의실 조회 실패: {e}")
        elif choice == "3":
            try:
                handle_get_location(service, assets)
            except Exception as e:
                print(f"[오류] 어디 빈 회의실 조회 실패: {e}")
        elif choice == "0":
            print("프로그램을 종료합니다.")
            break
        else:
            print("잘못된 메뉴 선택입니다.")


if __name__ == "__main__":
    main()
