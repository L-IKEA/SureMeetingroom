"""Pytest suite for Real Mode Telegram authentication flows and state management."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.auth.session_manager import UserSessionManager
from meeting_room_bot.favorites.service import FavoriteService
from meeting_room_bot.groupware.client import GroupwareClient
from meeting_room_bot.providers.base import QueryStatus
from meeting_room_bot.providers.real_provider import RealMeetingRoomProvider
from meeting_room_bot.telegram.handlers import (
    button_callback,
    set_query_provider,
    start_command,
)
from meeting_room_bot.telegram.states import user_state_mgr


def make_mock_update(user_id: str, callback_data: str = None, message_text: str = None):
    """Construct mock Telegram Update object."""
    update = MagicMock()
    user = MagicMock()
    user.id = int(user_id)
    update.effective_user = user

    if message_text is not None:
        message = MagicMock()
        message.text = message_text
        message.reply_text = AsyncMock()
        update.message = message

    if callback_data is not None:
        query = MagicMock()
        query.data = callback_data
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

    return update


@pytest.fixture
def real_provider():
    session_mgr = UserSessionManager()
    fav_service = MagicMock(spec=FavoriteService)
    provider = RealMeetingRoomProvider(session_mgr=session_mgr, favorite_service=fav_service)
    set_query_provider(provider)
    return provider


@pytest.mark.anyio
async def test_1_real_mode_new_user_start_command_shows_main_menu(real_provider):
    """Test 1: Real Mode + new user + /start -> main menu displayed cleanly."""
    update = make_mock_update(user_id="11111", message_text="/start")
    context = MagicMock()

    await start_command(update, context)

    update.message.reply_text.assert_called_once()
    args, kwargs = update.message.reply_text.call_args
    assert "🤖 회의실 도우미" in args[0]
    assert kwargs.get("reply_markup") is not None


@pytest.mark.anyio
async def test_2_real_mode_no_session_now_menu_returns_not_authenticated(real_provider):
    """Test 2: Real Mode + session missing + '지금 빈 회의실' -> NOT_AUTHENTICATED account connect screen."""
    update = make_mock_update(user_id="22222", callback_data="menu:now")
    context = MagicMock()

    await button_callback(update, context)

    update.callback_query.edit_message_text.assert_called_once()
    args, kwargs = update.callback_query.edit_message_text.call_args
    assert "🔐 그룹웨어 계정 연결이 필요합니다." in args[0]
    assert "요청 상태가 만료되었습니다" not in args[0]


@pytest.mark.anyio
async def test_3_session_missing_does_not_show_state_expired(real_provider):
    """Test 3: Session missing -> '요청 상태가 만료되었습니다' is NEVER shown."""
    update = make_mock_update(user_id="33333", callback_data="menu:now")
    context = MagicMock()

    await button_callback(update, context)

    args, _ = update.callback_query.edit_message_text.call_args
    assert "⚠️ 요청 상태가 만료되었습니다." not in args[0]
    assert "🔐 그룹웨어 계정 연결이 필요합니다." in args[0]


@pytest.mark.anyio
async def test_4_bot_restart_empty_user_data_start_shows_main_menu(real_provider):
    """Test 4: Assuming bot restart where user_data state is empty, /start -> normal main menu."""
    user_state_mgr.reset_state("44444")
    update = make_mock_update(user_id="44444", message_text="/start")
    context = MagicMock()

    await start_command(update, context)

    args, _ = update.message.reply_text.call_args
    assert "🤖 회의실 도우미" in args[0]


@pytest.mark.anyio
async def test_5_home_button_shows_main_menu_cleanly(real_provider):
    """Test 5: Home button ([🏠 처음으로]) -> resets state and displays main menu cleanly."""
    update = make_mock_update(user_id="55555", callback_data="nav:home")
    context = MagicMock()

    await button_callback(update, context)

    args, _ = update.callback_query.edit_message_text.call_args
    assert "🤖 회의실 도우미" in args[0]
    assert "요청 상태가 만료되었습니다" not in args[0]


@pytest.mark.anyio
async def test_6_when_menu_entry_no_session_shows_account_connect(real_provider):
    """Test 6: '언제 빈 회의실' entry + session missing -> account connect screen immediately."""
    update = make_mock_update(user_id="66666", callback_data="menu:when")
    context = MagicMock()

    await button_callback(update, context)

    args, _ = update.callback_query.edit_message_text.call_args
    assert "🔐 그룹웨어 계정 연결이 필요합니다." in args[0]
    assert "시작 시간을 선택하세요" not in args[0]


@pytest.mark.anyio
async def test_7_actual_multi_step_state_loss_shows_request_state_expired(real_provider):
    """Test 7: Only when actual multi-step state is lost for authenticated user -> REQUEST_STATE_EXPIRED."""
    user_id = "77777"
    client = GroupwareClient()
    client._is_authenticated = True
    real_provider.session_mgr.set_client(user_id, client)

    # Reset state and explicitly remove 'time' to simulate multi-step state loss
    user_state_mgr.reset_state(user_id)
    state = user_state_mgr.get_state(user_id)
    state.pop("time", None)

    update = make_mock_update(user_id=user_id, callback_data="dur:60")
    context = MagicMock()

    await button_callback(update, context)

    args, _ = update.callback_query.edit_message_text.call_args
    assert "⚠️ 요청 상태가 만료되었습니다." in args[0]


@pytest.mark.anyio
async def test_8_user_a_and_user_b_state_isolation(real_provider):
    """Test 8: User A state and User B state remain strictly isolated in UserStateManager."""
    user_state_mgr.reset_state("user_a")
    user_state_mgr.reset_state("user_b")

    user_state_mgr.update_state("user_a", custom_a="VAL_A")
    user_state_mgr.update_state("user_b", custom_b="VAL_B")

    state_a = user_state_mgr.get_state("user_a")
    state_b = user_state_mgr.get_state("user_b")

    assert state_a["custom_a"] == "VAL_A"
    assert "custom_b" not in state_a

    assert state_b["custom_b"] == "VAL_B"
    assert "custom_a" not in state_b
