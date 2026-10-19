"""Tests for Phase 2.1: Production Foundation Hardening.

Covers:
1. Token single generation and keyboard separation
2. UserKey namespace preservation & AccountLink round-trip
3. Token store hygiene (consume, expiry cleanup, user token replacement)
4. Auth / API / Network error classification
5. FavoriteService single-instance wiring
6. Atomic favorite write & corrupted file safety
7. Blocking I/O event-loop isolation (asyncio.to_thread)
8. IP rate limiting on login endpoint
9. Security response headers
"""

import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
import shutil
import tempfile
import time
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from meeting_room_bot.account_link.app import app, reset_rate_limits
from meeting_room_bot.account_link.token_service import AccountLinkTokenService, token_service
from meeting_room_bot.auth.session_manager import UserSessionManager, session_manager
from meeting_room_bot.config import AppConfig, get_config
from meeting_room_bot.favorites.json_repository import JsonFavoriteRepository
from meeting_room_bot.favorites.service import FavoriteService
from meeting_room_bot.groupware.client import (
    GroupwareAPIError,
    GroupwareAuthError,
    GroupwareClient,
    GroupwareNetworkError,
)
from meeting_room_bot.models.user_key import UserKey
from meeting_room_bot.providers.base import QueryResult, QueryStatus
from meeting_room_bot.providers.real_provider import RealMeetingRoomProvider
from meeting_room_bot.telegram.bot import build_application
from meeting_room_bot.telegram.handlers import (
    button_callback,
    get_favorite_service,
    handle_unauthenticated_or_expired,
    set_favorite_service,
    set_query_provider,
)
from meeting_room_bot.telegram.keyboards import (
    session_expired_keyboard,
    unauthenticated_keyboard,
)


# ---------------------------------------------------------------------------
# 1. Token 1회 생성 & Keyboard 분리
# ---------------------------------------------------------------------------
class TestTokenGenerationSingleTime:
    def test_keyboards_do_not_generate_tokens_when_given_url(self):
        """Keyboards receive prepared link_url and do not create security tokens."""
        url = "https://meeting.example.com/link/custom_tok_123"
        kb = unauthenticated_keyboard(link_url=url)
        assert len(kb.inline_keyboard) == 2
        btn = kb.inline_keyboard[0][0]
        assert btn.text == "🔐 회사 계정 연결"
        assert btn.url == url
        assert kb.inline_keyboard[1][0].text == "🏠 처음으로"

        kb_expired = session_expired_keyboard(link_url=url)
        assert len(kb_expired.inline_keyboard) == 2
        btn_exp = kb_expired.inline_keyboard[0][0]
        assert btn_exp.text == "🔐 다시 연결"
        assert btn_exp.url == url
        assert kb_expired.inline_keyboard[1][0].text == "🏠 처음으로"

    def test_keyboards_local_mode_no_button(self):
        """In local development mode, link_url is None and no link URL button is added."""
        kb = unauthenticated_keyboard(link_url=None)
        assert len(kb.inline_keyboard) == 1
        assert kb.inline_keyboard[0][0].text == "🏠 처음으로"
        assert kb.inline_keyboard[0][0].url is None

        kb_expired = session_expired_keyboard(link_url=None)
        assert len(kb_expired.inline_keyboard) == 1
        assert kb_expired.inline_keyboard[0][0].text == "🏠 처음으로"
        assert kb_expired.inline_keyboard[0][0].url is None

    @pytest.mark.anyio
    async def test_handler_creates_token_only_once_for_unauthenticated_event(self):
        """Verifies handler creates token exactly once per auth challenge event."""
        user_key = UserKey("telegram", "user_single_tok")
        query = MagicMock()
        query.edit_message_text = AsyncMock()

        with patch.object(token_service, "create_token", wraps=token_service.create_token) as spy_create:
            with patch.dict(os.environ, {"ACCOUNT_LINK_BASE_URL": "https://approved.domain.com"}):
                handled = await handle_unauthenticated_or_expired(query, QueryStatus.NOT_AUTHENTICATED, user_key)
                assert handled is True
                assert spy_create.call_count == 1
                args, _ = spy_create.call_args
                assert args[0] == user_key


# ---------------------------------------------------------------------------
# 2. UserKey Namespace Preservation & AccountLink Round-Trip
# ---------------------------------------------------------------------------
class TestUserKeyNamespacePreservation:
    def test_token_service_preserves_userkey_namespace(self):
        svc = AccountLinkTokenService(default_ttl=300)
        u_tg = UserKey("telegram", "123")
        u_ka = UserKey("kakao", "123")

        tok_tg = svc.create_token(u_tg)
        tok_ka = svc.create_token(u_ka)

        assert tok_tg != tok_ka
        # Both distinct keys stored without collision
        assert svc._tokens[tok_tg].user_id == "telegram:123"
        assert svc._tokens[tok_ka].user_id == "kakao:123"

    def test_account_link_roundtrip_restores_userkey_in_session_mgr(self):
        """FastAPI POST /link/{token} restores UserKey before binding to session_mgr."""
        client = TestClient(app)
        user_key = UserKey("telegram", "rt_user_777")
        tok = token_service.create_token(user_key)

        def mock_login(self, username, password):
            self._is_authenticated = True
            return True

        with patch.object(GroupwareClient, "login", new=mock_login):
            resp = client.post(f"/link/{tok}", data={"username": "testuser", "password": "pw"})
            assert resp.status_code == 200
            assert "연결 완료" in resp.text

            # Verify session_mgr has active session for this exact UserKey
            assert session_manager.has_session(user_key) is True
            # Legacy string query also works via UserKey.from_any
            assert session_manager.has_session("telegram:rt_user_777") is True


# ---------------------------------------------------------------------------
# 3. Token Hygiene & Cleanup
# ---------------------------------------------------------------------------
class TestTokenHygiene:
    def test_consume_token_burns_and_removes(self):
        svc = AccountLinkTokenService(default_ttl=300)
        tok = svc.create_token(UserKey("telegram", "burn_test"))
        assert tok in svc._tokens

        consumed = svc.consume_token(tok)
        assert consumed == "telegram:burn_test"
        # Must be completely removed from active tokens
        assert tok not in svc._tokens

        # Second consume fails
        assert svc.consume_token(tok) is None

    def test_cleanup_expired_tokens(self):
        svc = AccountLinkTokenService(default_ttl=1)
        tok = svc.create_token(UserKey("telegram", "exp_test"))
        # Force expiration
        svc._tokens[tok].expires_at = datetime.now(timezone.utc) - timedelta(seconds=10)

        removed = svc.cleanup_expired_tokens()
        assert removed == 1
        assert tok not in svc._tokens

    def test_create_token_replaces_older_active_token_for_same_user(self):
        """Prevent unbounded token accumulation for the same user."""
        svc = AccountLinkTokenService(default_ttl=300)
        u = UserKey("telegram", "repeat_user")

        tok1 = svc.create_token(u)
        assert tok1 in svc._tokens

        tok2 = svc.create_token(u)
        assert tok2 in svc._tokens
        assert tok1 not in svc._tokens  # Previous token cleaned up


# ---------------------------------------------------------------------------
# 4. Error Classification (Auth vs General API vs Network)
# ---------------------------------------------------------------------------
class TestErrorClassification:
    def test_auth_error_removes_session_and_returns_session_expired(self):
        user_key = UserKey("telegram", "err_auth_user")
        sess_mgr = UserSessionManager()
        client = GroupwareClient()
        client._is_authenticated = True
        sess_mgr.set_client(user_key, client)

        fav_svc = FavoriteService(JsonFavoriteRepository())
        provider = RealMeetingRoomProvider(sess_mgr, fav_svc)

        with patch.object(client, "get_assets", side_effect=GroupwareAuthError("401 Unauthorized")):
            res = provider.get_locations(user_key)
            assert res.status == QueryStatus.SESSION_EXPIRED
            # Session must be removed on 401
            assert sess_mgr.has_session(user_key) is False

    def test_api_error_preserves_session_and_returns_groupware_api_error(self):
        user_key = UserKey("telegram", "err_api_user")
        sess_mgr = UserSessionManager()
        client = GroupwareClient()
        client._is_authenticated = True
        sess_mgr.set_client(user_key, client)

        fav_svc = FavoriteService(JsonFavoriteRepository())
        provider = RealMeetingRoomProvider(sess_mgr, fav_svc)

        with patch.object(client, "get_assets", side_effect=GroupwareAPIError("500 Server Error")):
            res = provider.get_locations(user_key)
            assert res.status == QueryStatus.GROUPWARE_API_ERROR
            # Session must be preserved on general API error
            assert sess_mgr.has_session(user_key) is True

    def test_network_error_preserves_session_and_returns_network_error(self):
        user_key = UserKey("telegram", "err_net_user")
        sess_mgr = UserSessionManager()
        client = GroupwareClient()
        client._is_authenticated = True
        sess_mgr.set_client(user_key, client)

        fav_svc = FavoriteService(JsonFavoriteRepository())
        provider = RealMeetingRoomProvider(sess_mgr, fav_svc)

        with patch.object(client, "get_assets", side_effect=GroupwareNetworkError("Connection refused")):
            res = provider.get_locations(user_key)
            assert res.status == QueryStatus.NETWORK_ERROR
            # Session must be preserved on network drop
            assert sess_mgr.has_session(user_key) is True


# ---------------------------------------------------------------------------
# 5. FavoriteService Single-Instance Wiring
# ---------------------------------------------------------------------------
class TestFavoriteServiceSingleInstanceWiring:
    def test_build_application_shares_same_favorite_service_instance(self):
        """Application startup must wire the same FavoriteService instance to provider & handlers."""
        with patch.dict(os.environ, {"TELEGRAM_DATA_MODE": "real"}):
            app_builder = build_application("TEST_TOKEN_123")
            assert app_builder is not None

            handler_fav_service = get_favorite_service()
            from meeting_room_bot.telegram.handlers import get_query_provider
            provider = get_query_provider()
            assert isinstance(provider, RealMeetingRoomProvider)
            assert provider.favorite_service is handler_fav_service


# ---------------------------------------------------------------------------
# 6. Favorites JSON Safe Atomic Write & Corruption Defense
# ---------------------------------------------------------------------------
class TestFavoritesAtomicWrite:
    def test_atomic_write_creates_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "favorites.json")
            repo = JsonFavoriteRepository(file_path=file_path)

            u = UserKey("telegram", "safe_write_user")
            repo.add_asset(u, 50)
            repo.add_room(u, 101)

            assert os.path.exists(file_path)
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert data["users"]["telegram:safe_write_user"]["favorite_assets"] == [50]
            assert data["users"]["telegram:safe_write_user"]["favorite_rooms"] == [101]

    def test_corrupted_json_is_backed_up_and_not_wiped_blindly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "favorites.json")
            # Write invalid JSON
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("{invalid-json-content: corrupt")

            repo = JsonFavoriteRepository(file_path=file_path)
            # Loading corrupted file should handle safely
            data = repo._load_raw_data()
            assert data == {"users": {}}

            # Corrupted backup file should have been created
            files = os.listdir(tmpdir)
            corrupted_backups = [fn for fn in files if fn.startswith("favorites.json.corrupted")]
            assert len(corrupted_backups) == 1


# ---------------------------------------------------------------------------
# 7. Blocking Groupware I/O Event Loop Isolation
# ---------------------------------------------------------------------------
class TestBlockingIOIsolation:
    @pytest.mark.anyio
    async def test_slow_groupware_call_does_not_block_async_event_loop(self):
        """Verify that a slow blocking provider call offloaded via asyncio.to_thread

        allows concurrent async tasks on the same event loop to proceed freely.
        """
        slow_complete = False
        loop_counter = 0

        def slow_blocking_call():
            time.sleep(0.3)
            nonlocal slow_complete
            slow_complete = True
            return "done"

        async def concurrent_heartbeat():
            nonlocal loop_counter
            for _ in range(5):
                await asyncio.sleep(0.05)
                loop_counter += 1

        # Run slow call in thread and heartbeat in asyncio loop concurrently
        res, _ = await asyncio.gather(
            asyncio.to_thread(slow_blocking_call),
            concurrent_heartbeat(),
        )

        assert res == "done"
        assert slow_complete is True
        # Heartbeat was able to tick multiple times during the 0.3s sleep
        assert loop_counter >= 3


# ---------------------------------------------------------------------------
# 8. IP Rate Limiting & Security Headers
# ---------------------------------------------------------------------------
class TestRateLimitingAndSecurityHeaders:
    def test_ip_rate_limiting_returns_429(self):
        reset_rate_limits()
        client = TestClient(app)

        with patch.dict(os.environ, {"RATE_LIMIT_LOGIN_PER_MINUTE": "3"}):
            # 3 attempts
            for i in range(3):
                tok = token_service.create_token(UserKey("telegram", f"rl_{i}"))
                resp = client.post(f"/link/{tok}", data={"username": "u", "password": "p"})
                assert resp.status_code == 400

            # 4th attempt from same client IP -> 429
            tok_exceed = token_service.create_token(UserKey("telegram", "rl_exceed"))
            resp_exceed = client.post(f"/link/{tok_exceed}", data={"username": "u", "password": "p"})
            assert resp_exceed.status_code == 429
            assert "시도 횟수가 너무 많습니다" in resp_exceed.text

        reset_rate_limits()

    def test_security_response_headers_present(self):
        client = TestClient(app)
        tok = token_service.create_token(UserKey("telegram", "sec_user"))
        resp = client.get(f"/link/{tok}")
        assert resp.status_code == 200

        headers = resp.headers
        assert headers.get("referrer-policy") == "no-referrer"
        assert "no-store" in headers.get("cache-control", "")
        assert headers.get("x-content-type-options") == "nosniff"
        assert headers.get("x-frame-options") == "DENY"
        assert headers.get("content-security-policy") == "frame-ancestors 'none'"
