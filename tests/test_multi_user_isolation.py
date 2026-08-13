"""Pytest suite for Task 9 Multi-User Isolation, Navigation, and UI Error Regressions."""

from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.auth.session_manager import UserSessionManager
from meeting_room_bot.favorites.json_repository import JsonFavoriteRepository
from meeting_room_bot.favorites.service import FavoriteService
from meeting_room_bot.groupware.client import GroupwareClient
from meeting_room_bot.providers.real_provider import RealMeetingRoomProvider
from meeting_room_bot.telegram.handlers import button_callback, set_query_provider, user_state_mgr

SEOUL_TZ = timezone(timedelta(hours=9))


def dt(day: int, hour: int, minute: int) -> datetime:
    return datetime(2026, 8, day, hour, minute, tzinfo=SEOUL_TZ)


class TestMultiUserIsolationAndRegression:

    @pytest.fixture
    def setup_multi_user_env(self, tmp_path):
        fav_repo = JsonFavoriteRepository(file_path=str(tmp_path / "fav_test.json"))
        fav_service = FavoriteService(repo=fav_repo)
        session_mgr = UserSessionManager()

        # User A Client
        client_a = MagicMock(spec=GroupwareClient)
        client_a.is_authenticated = True
        client_a.get_assets.return_value = [{"id": 50, "name": "[판교] 5층 회의실"}]
        session_mgr.set_client("user_A", client_a)

        # User B Client
        client_b = MagicMock(spec=GroupwareClient)
        client_b.is_authenticated = True
        client_b.get_assets.return_value = [{"id": 80, "name": "[판교] 8층 회의실"}]
        session_mgr.set_client("user_B", client_b)

        provider = RealMeetingRoomProvider(session_mgr=session_mgr, favorite_service=fav_service)
        set_query_provider(provider)

        return session_mgr, fav_service, provider

    def test_1_user_session_and_favorites_isolation(self, setup_multi_user_env):
        """User A and User B sessions and favorites are completely isolated."""
        session_mgr, fav_service, provider = setup_multi_user_env

        # Add favorites for User A
        fav_service.add_asset("user_A", 50)
        fav_service.add_room("user_A", 501)

        # Add favorites for User B
        fav_service.add_asset("user_B", 80)

        fav_a = fav_service.get_user_favorites("user_A")
        fav_b = fav_service.get_user_favorites("user_B")

        assert 50 in fav_a.favorite_assets
        assert 501 in fav_a.favorite_rooms

        assert 80 in fav_b.favorite_assets
        assert len(fav_b.favorite_rooms) == 0

        # Session removal for User A does not affect User B
        session_mgr.remove_session("user_A")
        assert session_mgr.has_session("user_A") is False
        assert session_mgr.has_session("user_B") is True

    @pytest.mark.anyio
    async def test_2_navigation_flow_repeated_home_and_menus(self, setup_multi_user_env):
        """Navigating /start -> when -> home -> where -> home -> now -> home without state loss errors."""
        _, _, _ = setup_multi_user_env

        update = MagicMock()
        user = MagicMock()
        user.id = "user_B"
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
    async def test_3_real_mode_ui_does_not_contain_mock_ui_text(self, setup_multi_user_env):
        """In Real Mode, user interface text NEVER renders 'Mock UI'."""
        _, _, _ = setup_multi_user_env

        update = MagicMock()
        user = MagicMock()
        user.id = "user_B"
        update.effective_user = user
        query = MagicMock()
        query.data = "menu:fav"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        await button_callback(update, MagicMock())

        args, _ = query.edit_message_text.call_args
        assert "Mock UI" not in args[0]
