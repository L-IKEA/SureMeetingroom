"""Pytest suite for Task 8 Localhost Account Linking POC Fix."""

import logging
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.account_link.app import create_app
from meeting_room_bot.account_link.token_service import token_service
from meeting_room_bot.auth.session_manager import UserSessionManager
from meeting_room_bot.favorites.service import FavoriteService
from meeting_room_bot.groupware.client import GroupwareClient
from meeting_room_bot.providers.base import QueryStatus
from meeting_room_bot.providers.real_provider import RealMeetingRoomProvider
from meeting_room_bot.telegram.handlers import handle_unauthenticated_or_expired, set_query_provider
from meeting_room_bot.telegram.keyboards import (
    is_localhost_url,
    session_expired_keyboard,
    unauthenticated_keyboard,
)


class TestLocalhostAccountLinking:

    def test_1_is_localhost_url_detection(self):
        """Test 1: Verify is_localhost_url detects localhost & 127.0.0.1 URLs."""
        assert is_localhost_url("http://localhost:8000") is True
        assert is_localhost_url("http://127.0.0.1:8000") is True
        assert is_localhost_url("http://localhost") is True
        assert is_localhost_url("https://my-domain.com") is False

    def test_2_localhost_url_does_not_create_telegram_url_button(self):
        """Test 2: Localhost URL (or link_url=None) does NOT add url parameter to InlineKeyboardButton."""
        kb = unauthenticated_keyboard(link_url=None)
        buttons = kb.inline_keyboard

        # Ensure no button has a url attribute
        for row in buttons:
            for btn in row:
                assert getattr(btn, "url", None) is None

    def test_3_https_url_creates_telegram_url_button(self):
        """Test 3: Production HTTPS URL creates InlineKeyboardButton with url parameter."""
        url = "https://company-link.com/link/secure_token_abc"
        kb = unauthenticated_keyboard(link_url=url)
        buttons = kb.inline_keyboard

        # First row should have url parameter
        assert buttons[0][0].url is not None
        assert buttons[0][0].url == url

    @pytest.mark.anyio
    async def test_4_dev_mode_prints_token_url_to_console_log(self, caplog):
        """Test 4: DEV mode outputs [DEV] console log with PC browser link URL."""
        with patch.dict(os.environ, {"ACCOUNT_LINK_BASE_URL": "http://localhost:8000"}):
            query = MagicMock()
            query.edit_message_text = AsyncMock()

            with caplog.at_level(logging.INFO):
                await handle_unauthenticated_or_expired(query, QueryStatus.NOT_AUTHENTICATED, user_id="dev_user_123")

            assert "[DEV] Account linking required for user_id: dev_user_123" in caplog.text
            assert "http://localhost:8000/link/" in caplog.text

            # Check Telegram message text mentions local dev mode
            args, _ = query.edit_message_text.call_args
            assert "현재 로컬 개발 모드입니다." in args[0]
            assert "PC 브라우저에서 계정 연결을 진행해주세요." in args[0]

    def test_5_shared_session_manager_binds_session_for_real_provider(self):
        """Test 5: Shared UserSessionManager binds session from FastAPI to RealMeetingRoomProvider."""
        session_mgr = UserSessionManager()
        fav_service = MagicMock(spec=FavoriteService)
        provider = RealMeetingRoomProvider(session_mgr=session_mgr, favorite_service=fav_service)

        user_id = "user_shared_99"

        # Initially unauthenticated
        assert provider.check_authentication(user_id).status == QueryStatus.NOT_AUTHENTICATED

        # Perform login via FastAPI endpoint (mocking Groupware login)
        app = create_app()
        client_app = TestClient(app)
        token = token_service.create_token(user_id, ttl_seconds=600)

        def mock_login(self, username, password):
            self._is_authenticated = True
            return True

        with patch("meeting_room_bot.account_link.app.session_manager", session_mgr):
            with patch.object(GroupwareClient, "login", side_effect=mock_login, autospec=True):
                res = client_app.post(f"/link/{token}", data={"username": "user", "password": "pw"})
                assert res.status_code == 200

        # Now session is available in shared session_mgr for RealProvider
        assert session_mgr.has_session(user_id) is True
        assert provider.check_authentication(user_id).status == QueryStatus.SUCCESS

    def test_6_httpx_logger_masked(self):
        """Test 6: httpx logger is set to WARNING level to suppress bot token leakage."""
        import meeting_room_bot.telegram.bot  # noqa: F401
        httpx_logger = logging.getLogger("httpx")
        assert httpx_logger.level >= logging.WARNING
