"""Pytest suite for Telegram Bot UI components, keyboards, states, and Mock service."""

import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.telegram.keyboards import (
    main_menu_keyboard,
    no_favorites_guidance_keyboard,
    result_now_keyboard,
    result_when_keyboard,
    when_date_keyboard,
    when_duration_keyboard,
    when_time_keyboard,
    where_location_keyboard,
    where_room_keyboard,
)
from meeting_room_bot.telegram.mock_service import MockTelegramService
from meeting_room_bot.telegram.states import UserStateManager


class TestTelegramKeyboards:

    def test_main_menu_keyboard_layout(self):
        """Verify main menu keyboard buttons and 1-column vertical layout."""
        kb = main_menu_keyboard()
        inline_kb = kb.inline_keyboard

        assert len(inline_kb) == 4
        assert inline_kb[0][0].text == "🟢 지금 빈 회의실"
        assert inline_kb[0][0].callback_data == "menu:now"
        assert inline_kb[1][0].text == "🕐 언제 빈 회의실"
        assert inline_kb[1][0].callback_data == "menu:when"
        assert inline_kb[2][0].text == "🏢 어디 빈 회의실"
        assert inline_kb[2][0].callback_data == "menu:where"
        assert inline_kb[3][0].text == "⭐ 즐겨찾기 관리"
        assert inline_kb[3][0].callback_data == "menu:fav"

    def test_when_date_keyboard(self):
        """Verify date selection keyboard."""
        kb = when_date_keyboard()
        inline_kb = kb.inline_keyboard

        assert inline_kb[0][0].callback_data == "date:today"
        assert inline_kb[0][1].callback_data == "date:tomorrow"

    def test_when_time_keyboard_grid(self):
        """Verify 3-column grid arrangement of time buttons."""
        kb = when_time_keyboard()
        inline_kb = kb.inline_keyboard

        assert len(inline_kb) == 7
        assert len(inline_kb[0]) == 3
        assert inline_kb[0][0].text == "09:00"
        assert inline_kb[0][0].callback_data == "time:0900"
        assert inline_kb[5][2].text == "17:30"
        assert inline_kb[5][2].callback_data == "time:1730"

    def test_when_duration_keyboard(self):
        """Verify duration selection keyboard."""
        kb = when_duration_keyboard()
        inline_kb = kb.inline_keyboard

        assert inline_kb[0][0].callback_data == "dur:30"
        assert inline_kb[0][1].callback_data == "dur:60"
        assert inline_kb[1][0].callback_data == "dur:90"
        assert inline_kb[1][1].callback_data == "dur:120"

    def test_result_keyboard_layout(self):
        """Verify result screen keyboards have Row 1: 2 buttons, Row 2: 1 button (Home)."""
        # 1. Result When - Favorites scope
        kb_when_fav = result_when_keyboard(scope="fav")
        inline_when_fav = kb_when_fav.inline_keyboard
        assert len(inline_when_fav) == 2
        assert len(inline_when_fav[0]) == 2
        assert inline_when_fav[0][0].text == "🌐 전체 위치로 조회"
        assert inline_when_fav[0][1].text == "🔄 조건 다시 선택"
        assert len(inline_when_fav[1]) == 1
        assert inline_when_fav[1][0].text == "🏠 처음으로"

        # 2. Result When - All scope
        kb_when_all = result_when_keyboard(scope="all")
        inline_when_all = kb_when_all.inline_keyboard
        assert len(inline_when_all) == 2
        assert len(inline_when_all[0]) == 2
        assert inline_when_all[0][0].text == "⭐ 즐겨찾기 기준"
        assert inline_when_all[0][1].text == "🔄 조건 다시 선택"
        assert len(inline_when_all[1]) == 1
        assert inline_when_all[1][0].text == "🏠 처음으로"

        # 3. Result Now - Favorites scope
        kb_now_fav = result_now_keyboard(scope="fav")
        inline_now_fav = kb_now_fav.inline_keyboard
        assert len(inline_now_fav) == 2
        assert len(inline_now_fav[0]) == 2
        assert inline_now_fav[0][0].text == "🌐 전체 위치로 조회"
        assert inline_now_fav[0][1].text == "🔄 새로고침"
        assert len(inline_now_fav[1]) == 1
        assert inline_now_fav[1][0].text == "🏠 처음으로"

    def test_unpaginated_2column_where_location_keyboard(self):
        """Verify '어디 빈 회의실' keyboard has NO Next/Previous buttons and 2-column grid."""
        locations = MockTelegramService.get_mock_locations()
        kb = where_location_keyboard(locations)
        inline_kb = kb.inline_keyboard

        all_button_texts = [btn.text for row in inline_kb for btn in row]

        # 1. No Next or Previous buttons
        assert not any("다음" in txt for txt in all_button_texts)
        assert not any("이전" in txt for txt in all_button_texts)

        # 2. All locations included
        assert len(locations) == 13

        # 3. 2-column layout check
        # 13 items -> 6 rows of 2 buttons + 1 row of 1 button + 1 home row = 8 rows
        assert len(inline_kb) == 8
        assert len(inline_kb[0]) == 2
        assert len(inline_kb[5]) == 2
        assert len(inline_kb[6]) == 1  # Odd 13th item
        assert inline_kb[7][0].text == "🏠 처음으로"

        # 4. callback_data asset_id check
        assert inline_kb[0][0].callback_data == "asset:10"
        assert inline_kb[3][1].callback_data == "asset:80"


class TestUserStateIsolation:

    def test_per_user_state_isolation(self):
        """Verify states for User A and User B do not mix."""
        mgr = UserStateManager()
        mgr.update_state("1001", date="2026-08-11", duration=90)
        mgr.update_state("2002", date="2026-08-12", duration=30)

        state_a = mgr.get_state("1001")
        state_b = mgr.get_state("2002")

        assert state_a["date"] == "2026-08-11"
        assert state_a["duration"] == 90

        assert state_b["date"] == "2026-08-12"
        assert state_b["duration"] == 30

    def test_state_reset(self):
        """Verify resetting state returns default state."""
        mgr = UserStateManager()
        mgr.update_state("1001", date="2026-08-15")
        mgr.reset_state("1001")

        state = mgr.get_state("1001")
        assert state["date"] == "today"


class TestMockTelegramService:

    def test_has_favorites_check(self):
        """Verify has_favorites returns True for default user and False for no_fav_user."""
        assert MockTelegramService.has_favorites("12345") is True
        assert MockTelegramService.has_favorites("no_fav_user") is False
        assert MockTelegramService.has_favorites("empty") is False

    def test_mock_locations_returns_all_data(self):
        """Verify MockTelegramService location dataset contains all 13 locations with short labels."""
        locations = MockTelegramService.get_mock_locations()
        assert len(locations) == 13
        assert locations[0]["short_label"] == "1층 컨퍼런스홀"
        assert locations[9]["short_label"] == "10층"
        assert locations[12]["short_label"] == "대전 회의실"

    def test_when_available_rooms_scope_differentiation(self):
        """Verify '언제 빈 회의실' returns different rooms for 'fav' vs 'all' scope while retaining time."""
        # 1. Favorites scope query
        res_fav = MockTelegramService.get_mock_available_rooms_at(
            date_str="2026-08-11", start_time="12:00", duration=30, scope="fav"
        )
        assert res_fav["start_time"] == "12:00"
        assert res_fav["end_time"] == "12:30"
        assert len(res_fav["available_rooms"]) == 3
        assert "🟢 회의실 5-2" in res_fav["available_rooms"]
        assert "🟢 컨퍼런스홀 1-1" not in res_fav["available_rooms"]

        # 2. All locations scope query with SAME time conditions
        res_all = MockTelegramService.get_mock_available_rooms_at(
            date_str="2026-08-11", start_time="12:00", duration=30, scope="all"
        )
        assert res_all["start_time"] == "12:00"
        assert res_all["end_time"] == "12:30"
        assert len(res_all["available_rooms"]) > len(res_fav["available_rooms"])
        assert "🟢 컨퍼런스홀 1-1" in res_all["available_rooms"]
        assert "🟢 회의실 4-1" in res_all["available_rooms"]

        # 3. Switching back to 'fav' restores favorites scope
        res_fav_back = MockTelegramService.get_mock_available_rooms_at(
            date_str="2026-08-11", start_time="12:00", duration=30, scope="fav"
        )
        assert res_fav_back["available_rooms"] == res_fav["available_rooms"]

    def test_mock_location_status_distinct_per_asset(self):
        """Verify location status returns specific rooms per floor (5F, 7F, 8F) and not duplicate lists."""
        status_5F = MockTelegramService.get_mock_location_status(50)
        status_7F = MockTelegramService.get_mock_location_status(70)
        status_8F = MockTelegramService.get_mock_location_status(80)

        assert status_5F["asset_name"] == "[판교] 5층 회의실"
        assert status_7F["asset_name"] == "[판교] 7층 회의실"
        assert status_8F["asset_name"] == "[판교] 8층 회의실"

        rooms_5F = [r["name"] for r in status_5F["rooms"]]
        rooms_7F = [r["name"] for r in status_7F["rooms"]]
        rooms_8F = [r["name"] for r in status_8F["rooms"]]

        # Check 5F rooms
        assert any("5-1" in r for r in rooms_5F)
        assert not any("7-1" in r for r in rooms_5F)
        assert not any("8-1" in r for r in rooms_5F)

        # Check 7F rooms
        assert any("7-1" in r for r in rooms_7F)
        assert not any("5-1" in r for r in rooms_7F)

        # Check 8F rooms
        assert any("8-1" in r for r in rooms_8F)
        assert not any("5-1" in r for r in rooms_8F)

        # Ensure distinct room lists across different assets
        assert rooms_5F != rooms_7F
        assert rooms_5F != rooms_8F
        assert rooms_7F != rooms_8F

    def test_mock_room_detail_specific_to_floor(self):
        """Verify 8F room selection returns 8F room detail."""
        detail = MockTelegramService.get_mock_room_detail(80, 180)
        assert detail is not None
        assert detail["name"] == "회의실 8-1"
        assert detail["asset_id"] == 80

    def test_non_existent_asset_id_handling(self):
        """Verify handling of non-existent asset_id."""
        status = MockTelegramService.get_mock_location_status(999)
        assert status["asset_id"] == 999
        assert status["rooms"] == []

    def test_non_existent_room_id_handling(self):
        """Verify handling of non-existent room_id."""
        detail = MockTelegramService.get_mock_room_detail(50, 999)
        assert detail is None
