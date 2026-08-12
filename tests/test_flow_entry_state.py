"""Pytest suite for Task 8 Flow Entry Point State Initialization & Exception Guarding."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.auth.session_manager import UserSessionManager
from meeting_room_bot.favorites.service import FavoriteService
from meeting_room_bot.groupware.client import GroupwareClient
from meeting_room_bot.providers.real_provider import RealMeetingRoomProvider
from meeting_room_bot.telegram.handlers import button_callback, set_query_provider, user_state_mgr


class TestFlowEntryState:

    @pytest.fixture
    def setup_real_provider(self):
        fav_service = MagicMock(spec=FavoriteService)
        session_mgr = UserSessionManager()

        client_101 = MagicMock(spec=GroupwareClient)
        client_101.is_authenticated = True
        client_101.get_assets.return_value = [
            {"id": 50, "name": "[판교] 5층 회의실"},
            {"id": 80, "name": "[판교] 8층 회의실"},
        ]
        session_mgr.set_client("user_101", client_101)

        provider = RealMeetingRoomProvider(session_mgr=session_mgr, favorite_service=fav_service)
        set_query_provider(provider)

        return provider, fav_service, session_mgr

    @pytest.mark.anyio
    async def test_1_8_menu_when_with_empty_user_data(self, setup_real_provider):
        """Test 1 & 8: menu:when with completely empty user_data displays time selection screen (NOT REQUEST_STATE_EXPIRED)."""
        _, _, _ = setup_real_provider
        user_state_mgr.reset_state("user_101")

        update = MagicMock()
        user = MagicMock()
        user.id = "user_101"
        update.effective_user = user
        query = MagicMock()
        query.data = "menu:when"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        await button_callback(update, MagicMock())

        query.edit_message_text.assert_called_once()
        args, _ = query.edit_message_text.call_args
        assert "시작 시간을 선택하세요." in args[0]
        assert "요청 상태가 만료되었습니다" not in args[0]

    @pytest.mark.anyio
    async def test_2_9_10_menu_where_with_empty_user_data(self, setup_real_provider):
        """Test 2, 9, 10: menu:where with empty user_data queries real Groupware assets (NOT REQUEST_STATE_EXPIRED)."""
        _, _, _ = setup_real_provider
        user_state_mgr.reset_state("user_101")

        update = MagicMock()
        user = MagicMock()
        user.id = "user_101"
        update.effective_user = user
        query = MagicMock()
        query.data = "menu:where"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        await button_callback(update, MagicMock())

        query.edit_message_text.assert_called_once()
        args, kwargs = query.edit_message_text.call_args
        assert "어디 빈 회의실 - 위치 선택:" in args[0]
        assert "요청 상태가 만료되었습니다" not in args[0]

        # Verify buttons contain real assets
        kb = kwargs.get("reply_markup") or args[1]
        buttons_text = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "[5층 회의실]" in buttons_text or "[5층]" in buttons_text
        assert "[8층 회의실]" in buttons_text or "[8층]" in buttons_text

    @pytest.mark.anyio
    async def test_3_start_then_menu_when(self, setup_real_provider):
        """Test 3: /start followed by menu:when succeeds cleanly."""
        _, _, _ = setup_real_provider
        user_state_mgr.reset_state("user_101")

        update = MagicMock()
        user = MagicMock()
        user.id = "user_101"
        update.effective_user = user
        query = MagicMock()
        query.data = "menu:when"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        await button_callback(update, MagicMock())

        args, _ = query.edit_message_text.call_args
        assert "시작 시간을 선택하세요." in args[0]

    @pytest.mark.anyio
    async def test_4_start_then_menu_where(self, setup_real_provider):
        """Test 4: /start followed by menu:where succeeds cleanly."""
        _, _, _ = setup_real_provider
        user_state_mgr.reset_state("user_101")

        update = MagicMock()
        user = MagicMock()
        user.id = "user_101"
        update.effective_user = user
        query = MagicMock()
        query.data = "menu:where"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        await button_callback(update, MagicMock())

        args, _ = query.edit_message_text.call_args
        assert "어디 빈 회의실 - 위치 선택:" in args[0]

    @pytest.mark.anyio
    async def test_5_6_home_then_menu_when_and_where(self, setup_real_provider):
        """Test 5 & 6: nav:home followed by menu:when and menu:where succeeds cleanly."""
        _, _, _ = setup_real_provider

        update = MagicMock()
        user = MagicMock()
        user.id = "user_101"
        update.effective_user = user
        query = MagicMock()
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        # 1. nav:home
        query.data = "nav:home"
        await button_callback(update, MagicMock())
        args, _ = query.edit_message_text.call_args
        assert "회의실 도우미" in args[0]

        # 2. menu:when
        query.data = "menu:when"
        query.edit_message_text.reset_mock()
        await button_callback(update, MagicMock())
        args, _ = query.edit_message_text.call_args
        assert "시작 시간을 선택하세요." in args[0]

        # 3. nav:home
        query.data = "nav:home"
        query.edit_message_text.reset_mock()
        await button_callback(update, MagicMock())

        # 4. menu:where
        query.data = "menu:where"
        query.edit_message_text.reset_mock()
        await button_callback(update, MagicMock())
        args, _ = query.edit_message_text.call_args
        assert "어디 빈 회의실 - 위치 선택:" in args[0]

    @pytest.mark.anyio
    async def test_7_dur_callback_without_time_triggers_request_state_expired(self, setup_real_provider):
        """Test 7: dur:60 callback without prior time in state triggers REQUEST_STATE_EXPIRED."""
        _, _, _ = setup_real_provider
        user_state_mgr.reset_state("user_101")
        state = user_state_mgr.get_state("user_101")
        state.pop("time", None)

        update = MagicMock()
        user = MagicMock()
        user.id = "user_101"
        update.effective_user = user
        query = MagicMock()
        query.data = "dur:60"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        await button_callback(update, MagicMock())

        args, _ = query.edit_message_text.call_args
        assert "⚠️ 요청 상태가 만료되었습니다." in args[0]
