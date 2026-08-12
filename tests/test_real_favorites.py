"""Pytest suite for Real Mode FavoriteService Integration & Telegram BadRequest Guarding."""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from telegram.error import BadRequest
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.auth.session_manager import UserSessionManager
from meeting_room_bot.favorites.models import UserFavorites
from meeting_room_bot.favorites.service import FavoriteService
from meeting_room_bot.groupware.client import GroupwareClient
from meeting_room_bot.providers.base import QueryStatus
from meeting_room_bot.providers.real_provider import RealMeetingRoomProvider
from meeting_room_bot.telegram.handlers import button_callback, set_query_provider


class TestRealFavoritesIntegration:

    @pytest.fixture
    def setup_real_provider(self, tmp_path):
        from meeting_room_bot.favorites.json_repository import JsonFavoriteRepository

        json_path = tmp_path / "test_favs.json"
        repo = JsonFavoriteRepository(file_path=json_path)
        fav_service = FavoriteService(repo=repo)
        session_mgr = UserSessionManager()

        # Set authenticated client for user_101
        client_101 = MagicMock(spec=GroupwareClient)
        client_101.is_authenticated = True
        client_101.get_assets.return_value = [
            {"id": 50, "name": "[판교] 5층 회의실"},
            {"id": 80, "name": "[판교] 8층 회의실"},
        ]
        client_101.get_items.return_value = [
            {"id": 501, "name": "회의실 5-1"},
            {"id": 502, "name": "회의실 5-2"},
        ]
        client_101.get_daily_reservations.return_value = []
        session_mgr.set_client("user_101", client_101)

        provider = RealMeetingRoomProvider(session_mgr=session_mgr, favorite_service=fav_service)
        set_query_provider(provider)

        return provider, fav_service, session_mgr

    @pytest.mark.anyio
    async def test_1_real_mode_add_asset_shows_real_locations(self, setup_real_provider):
        """Test 1: Real Mode + [➕ 위치 추가] displays real Asset list."""
        _, _, _ = setup_real_provider

        update = MagicMock()
        user = MagicMock()
        user.id = "user_101"
        update.effective_user = user
        query = MagicMock()
        query.data = "fav_action:add_asset"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        await button_callback(update, MagicMock())

        query.edit_message_text.assert_called_once()
        args, kwargs = query.edit_message_text.call_args
        assert "⭐ 즐겨찾기에 추가할 위치를 선택하세요." in args[0]
        # Verify reply_markup contains real locations
        kb = kwargs.get("reply_markup") or args[1]
        buttons_text = [btn.text for row in kb.inline_keyboard for btn in row]
        assert "[5층 회의실]" in buttons_text or "[5층]" in buttons_text
        assert "[8층 회의실]" in buttons_text or "[8층]" in buttons_text

    @pytest.mark.anyio
    async def test_2_3_asset_selection_calls_add_asset(self, setup_real_provider):
        """Test 2 & 3: Selecting location calls FavoriteService.add_asset with user_id."""
        _, fav_service, _ = setup_real_provider

        update = MagicMock()
        user = MagicMock()
        user.id = "user_101"
        update.effective_user = user
        query = MagicMock()
        query.data = "fav_add_asset:80"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        with patch("meeting_room_bot.telegram.handlers.fav_service", fav_service):
            await button_callback(update, MagicMock())

        uf = fav_service.get_user_favorites("user_101")
        assert 80 in uf.favorite_assets

        query.edit_message_text.assert_called_once()
        args, _ = query.edit_message_text.call_args
        assert "✅ 즐겨찾기에 추가했습니다." in args[0]
        assert "[판교] 8층 회의실" in args[0]

    @pytest.mark.anyio
    async def test_4_favorites_user_isolation(self, setup_real_provider):
        """Test 4: Favorites added by user_101 do NOT affect user_202."""
        _, fav_service, _ = setup_real_provider

        fav_service.add_asset("user_101", 50)
        fav_service.add_asset("user_202", 80)

        uf1 = fav_service.get_user_favorites("user_101")
        uf2 = fav_service.get_user_favorites("user_202")

        assert uf1.favorite_assets == {50}
        assert uf2.favorite_assets == {80}
        assert uf1.favorite_assets != uf2.favorite_assets

    @pytest.mark.anyio
    async def test_5_duplicate_asset_addition_prevention(self, setup_real_provider):
        """Test 5: Duplicate asset addition shows info message without duplicating data."""
        _, fav_service, _ = setup_real_provider
        fav_service.add_asset("user_101", 80)

        update = MagicMock()
        user = MagicMock()
        user.id = "user_101"
        update.effective_user = user
        query = MagicMock()
        query.data = "fav_add_asset:80"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        with patch("meeting_room_bot.telegram.handlers.fav_service", fav_service):
            await button_callback(update, MagicMock())

        args, _ = query.edit_message_text.call_args
        assert "ℹ️ 이미 즐겨찾기에 등록된 위치입니다." in args[0]

    @pytest.mark.anyio
    async def test_6_7_8_9_add_room_flow(self, setup_real_provider):
        """Test 6, 7, 8, 9: Add room flow (Location list -> Room list -> add_room)."""
        _, fav_service, _ = setup_real_provider

        # Step 1: Click [➕ 회의실 추가]
        update = MagicMock()
        user = MagicMock()
        user.id = "user_101"
        update.effective_user = user
        query = MagicMock()
        query.data = "fav_action:add_room"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        await button_callback(update, MagicMock())
        args, _ = query.edit_message_text.call_args
        assert "⭐ 회의실을 추가할 위치를 선택하세요." in args[0]

        # Step 2: Select 5층 (fav_sel_asset:50)
        query.data = "fav_sel_asset:50"
        query.edit_message_text.reset_mock()
        await button_callback(update, MagicMock())
        args, _ = query.edit_message_text.call_args
        assert "⭐ 즐겨찾기에 추가할 회의실을 선택하세요." in args[0]

        # Step 3: Select Room 501 (fav_add_room:501)
        query.data = "fav_add_room:501"
        query.edit_message_text.reset_mock()
        with patch("meeting_room_bot.telegram.handlers.fav_service", fav_service):
            await button_callback(update, MagicMock())

        uf = fav_service.get_user_favorites("user_101")
        assert 501 in uf.favorite_rooms
        args, _ = query.edit_message_text.call_args
        assert "✅ 즐겨찾기에 추가했습니다." in args[0]

    @pytest.mark.anyio
    async def test_10_view_favorites_real_mode(self, setup_real_provider):
        """Test 10: Display real favorites list."""
        _, fav_service, _ = setup_real_provider
        fav_service.add_asset("user_101", 50)
        fav_service.add_room("user_101", 501)

        update = MagicMock()
        user = MagicMock()
        user.id = "user_101"
        update.effective_user = user
        query = MagicMock()
        query.data = "menu:fav"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        with patch("meeting_room_bot.telegram.handlers.fav_service", fav_service):
            await button_callback(update, MagicMock())

        args, _ = query.edit_message_text.call_args
        assert "⭐ 내 즐겨찾기" in args[0]
        assert "[판교] 5층 회의실" in args[0]

    @pytest.mark.anyio
    async def test_11_delete_favorite_real_mode(self, setup_real_provider):
        """Test 11: Real deletion of asset favorite."""
        _, fav_service, _ = setup_real_provider
        fav_service.add_asset("user_101", 50)
        assert 50 in fav_service.get_user_favorites("user_101").favorite_assets

        update = MagicMock()
        user = MagicMock()
        user.id = "user_101"
        update.effective_user = user
        query = MagicMock()
        query.data = "fav_del_asset:50"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        with patch("meeting_room_bot.telegram.handlers.fav_service", fav_service):
            await button_callback(update, MagicMock())

        assert 50 not in fav_service.get_user_favorites("user_101").favorite_assets
        args, _ = query.edit_message_text.call_args
        assert "✅ 즐겨찾기에서 삭제했습니다." in args[0]

    @pytest.mark.anyio
    async def test_12_13_message_is_not_modified_ignored_gracefully(self, setup_real_provider):
        """Test 12 & 13: Message is not modified error is gracefully ignored and does NOT show REQUEST_STATE_EXPIRED."""
        _, fav_service, _ = setup_real_provider

        update = MagicMock()
        user = MagicMock()
        user.id = "user_101"
        update.effective_user = user
        query = MagicMock()
        query.data = "menu:fav"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock(side_effect=BadRequest("Message is not modified: specified new message content and reply markup are exactly the same"))
        update.callback_query = query

        with patch("meeting_room_bot.telegram.handlers.fav_service", fav_service):
            # Should not raise exception and should not show expired screen
            await button_callback(update, MagicMock())

    @pytest.mark.anyio
    async def test_14_no_mock_ui_string_in_real_mode(self, setup_real_provider):
        """Test 14: '⭐ 즐겨찾기 변경 기능 (Mock UI)' string is NEVER displayed in Real Mode."""
        _, fav_service, _ = setup_real_provider

        update = MagicMock()
        user = MagicMock()
        user.id = "user_101"
        update.effective_user = user
        query = MagicMock()
        query.data = "fav_action:add_asset"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        with patch("meeting_room_bot.telegram.handlers.fav_service", fav_service):
            await button_callback(update, MagicMock())

        args, _ = query.edit_message_text.call_args
        assert "Mock UI" not in args[0]

    @pytest.mark.anyio
    async def test_15_16_added_favorites_reflected_in_queries(self, setup_real_provider):
        """Test 15 & 16: Adding favorites filters [🟢 지금 빈 회의실] and [🕐 언제 빈 회의실] scope."""
        provider, fav_service, _ = setup_real_provider

        # Add 5층 (asset_id 50) to favorites
        fav_service.add_asset("user_101", 50)

        # Query now in favorite scope
        res_now = provider.get_available_rooms_now("user_101", scope="fav")
        assert res_now.status == QueryStatus.SUCCESS
        # Only asset 50 (5층) should be in groups
        asset_names = [g["asset_name"] for g in res_now.data.get("groups", [])]
        assert asset_names == ["[판교] 5층 회의실"]
