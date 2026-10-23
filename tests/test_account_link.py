"""Pytest suite for Account Linking token service, FastAPI endpoints, and session binding."""

from datetime import datetime, timedelta, timezone
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
from meeting_room_bot.account_link.token_service import AccountLinkTokenService, token_service
from meeting_room_bot.auth.session_manager import UserSessionManager
from meeting_room_bot.favorites.models import UserFavorites
from meeting_room_bot.favorites.repository import FavoriteRepository
from meeting_room_bot.favorites.service import FavoriteService
from meeting_room_bot.groupware.client import GroupwareAuthError, GroupwareClient
from meeting_room_bot.providers.base import QueryStatus
from meeting_room_bot.providers.real_provider import RealMeetingRoomProvider
from meeting_room_bot.telegram.handlers import button_callback, set_query_provider


import re
from meeting_room_bot.account_link.session_store import link_session_store, web_session_store


def mock_login_success(self, username, password):
    self._is_authenticated = True
    return True


def mock_login_fail(self, username, password):
    self._is_authenticated = False
    return False


def _perform_phase2_2_login(client_app, token, username, password):
    """Execute official Phase 2.2 token exchange -> CSRF -> login flow."""
    resp_get = client_app.get(f"/link/{token}", follow_redirects=False)
    assert resp_get.status_code == 303
    cookie = resp_get.cookies.get("meetingroom_link_session")
    resp_form = client_app.get("/link/login", cookies={"meetingroom_link_session": cookie})
    match = re.search(r'name="csrf_token"\s+value="([^"]+)"', resp_form.text)
    csrf = match.group(1) if match else ""
    return client_app.post(
        "/link/login",
        data={"username": username, "password": password, "csrf_token": csrf},
        cookies={"meetingroom_link_session": cookie},
        follow_redirects=False,
    )


class TestAccountLinkTokenService:

    def test_1_2_token_generation_and_user_id_mapping(self):
        """Test 1 & 2: Link token generation and user_id mapping."""
        ts = AccountLinkTokenService()
        token = ts.create_token("1001", ttl_seconds=600)

        assert token is not None
        assert len(token) >= 20

        mapped_user_id = ts.validate_token(token)
        assert mapped_user_id == "1001"

    def test_3_token_expiration(self):
        """Test 3: Expired token is rejected."""
        ts = AccountLinkTokenService()
        token = ts.create_token("1002", ttl_seconds=-10)  # Already expired

        assert ts.validate_token(token) is None
        assert ts.consume_token(token) is None

    def test_4_token_one_time_use(self):
        """Test 4: Token is 1-time use only (cannot be reused)."""
        ts = AccountLinkTokenService()
        token = ts.create_token("1003", ttl_seconds=600)

        # First consumption succeeds
        assert ts.consume_token(token) == "1003"
        # Second consumption fails
        assert ts.consume_token(token) is None
        assert ts.validate_token(token) is None

    def test_5_invalid_token_rejected(self):
        """Test 5: Invalid or bogus token is rejected."""
        ts = AccountLinkTokenService()
        assert ts.validate_token("invalid_bogus_token") is None
        assert ts.consume_token("invalid_bogus_token") is None


class TestFastAPIAccountLinkEndpoints:

    @pytest.fixture
    def client_app(self):
        app = create_app()
        return TestClient(app)

    def test_6_login_success_saves_user_session(self, client_app):
        """Test 6: Login success binds GroupwareClient session in UserSessionManager."""
        session_mgr = UserSessionManager()
        token = token_service.create_token("user_success", ttl_seconds=600)

        with patch("meeting_room_bot.account_link.app.session_manager", session_mgr):
            with patch.object(GroupwareClient, "login", side_effect=mock_login_success, autospec=True):
                response = _perform_phase2_2_login(
                    client_app,
                    token,
                    "valid_user",
                    "valid_pw",
                )

                assert response.status_code == 303
                assert response.headers["location"] == "/timeline"
                assert session_mgr.has_session("user_success") is True

    def test_7_login_failure_does_not_save_session(self, client_app):
        """Test 7: Login failure does NOT save session in UserSessionManager."""
        session_mgr = UserSessionManager()
        token = token_service.create_token("user_fail", ttl_seconds=600)

        with patch("meeting_room_bot.account_link.app.session_manager", session_mgr):
            with patch.object(GroupwareClient, "login", side_effect=mock_login_fail, autospec=True):
                response = _perform_phase2_2_login(
                    client_app,
                    token,
                    "wrong_user",
                    "wrong_pw",
                )

                assert response.status_code == 400
                assert "로그인에 실패했습니다" in response.text
                assert session_mgr.has_session("user_fail") is False

    def test_8_password_is_not_stored(self, client_app):
        """Test 8: Password is not stored anywhere in memory variables, tokens, or session objects."""
        token = token_service.create_token("user_pass_check", ttl_seconds=600)
        custom_token_val = "DUMMY_CUSTOM_VAL_999"

        with patch.object(GroupwareClient, "login", side_effect=mock_login_success, autospec=True):
            _perform_phase2_2_login(
                client_app,
                token,
                "testuser",
                custom_token_val,
            )

        # Check TokenData does not contain password
        for _, tdata in token_service._tokens.items():
            assert custom_token_val not in str(tdata)

        # Check LinkSession and WebSession stores do not contain password
        for _, lsession in link_session_store._sessions.items():
            assert custom_token_val not in str(lsession)
        for _, wsession in web_session_store._sessions.items():
            assert custom_token_val not in str(wsession)

    def test_9_10_11_user_a_b_distinct_sessions(self, client_app):
        """Test 9, 10, 11: User A & User B distinct sessions."""
        session_mgr = UserSessionManager()

        token_a = token_service.create_token("user_A", ttl_seconds=600)
        token_b = token_service.create_token("user_B", ttl_seconds=600)

        with patch("meeting_room_bot.account_link.app.session_manager", session_mgr):
            with patch.object(GroupwareClient, "login", side_effect=mock_login_success, autospec=True):
                _perform_phase2_2_login(client_app, token_a, username="userA", password="pwA")
                _perform_phase2_2_login(client_app, token_b, username="userB", password="pwB")

        assert session_mgr.has_session("user_A") is True
        assert session_mgr.has_session("user_B") is True

        client_a = session_mgr.get_client("user_A")
        client_b = session_mgr.get_client("user_B")

        assert client_a is not client_b

    def test_12_post_login_real_provider_calls_service(self):
        """Test 12: Post-login Real Provider calls real MeetingRoomService."""
        session_mgr = UserSessionManager()
        fav_service = MagicMock(spec=FavoriteService)
        provider = RealMeetingRoomProvider(session_mgr=session_mgr, favorite_service=fav_service)

        mock_gw_client = MagicMock(spec=GroupwareClient)
        mock_gw_client.is_authenticated = True
        mock_gw_client.get_assets.return_value = [{"id": 50, "name": "5층 회의실"}]
        mock_gw_client.get_items.return_value = [{"id": 501, "name": "회의실 5-1"}]
        mock_gw_client.get_daily_reservations.return_value = []

        session_mgr.set_client("111", mock_gw_client)

        res = provider.get_available_rooms_now("111", scope="all")
        assert res.status == QueryStatus.SUCCESS
        assert len(res.data["groups"]) == 1

    def test_13_user_without_session_returns_not_authenticated(self):
        """Test 13: User without session returns NOT_AUTHENTICATED."""
        session_mgr = UserSessionManager()
        fav_service = MagicMock(spec=FavoriteService)
        provider = RealMeetingRoomProvider(session_mgr=session_mgr, favorite_service=fav_service)

        res = provider.get_available_rooms_now("unlinked_user", scope="fav")
        assert res.status == QueryStatus.NOT_AUTHENTICATED

    def test_14_auth_401_error_removes_user_session_only(self):
        """Test 14: 401 error removes session for that user only."""
        session_mgr = UserSessionManager()
        fav_service = MagicMock(spec=FavoriteService)
        provider = RealMeetingRoomProvider(session_mgr=session_mgr, favorite_service=fav_service)

        client_a = MagicMock(spec=GroupwareClient)
        client_a.is_authenticated = True
        client_a.get_assets.side_effect = GroupwareAuthError("401 Unauthorized")

        client_b = MagicMock(spec=GroupwareClient)
        client_b.is_authenticated = True

        session_mgr.set_client("user_a", client_a)
        session_mgr.set_client("user_b", client_b)

        res = provider.get_available_rooms_now("user_a", scope="all")

        assert res.status == QueryStatus.SESSION_EXPIRED
        assert session_mgr.has_session("user_a") is False
        assert session_mgr.has_session("user_b") is True

    @pytest.mark.anyio
    async def test_15_unlink_removes_user_session(self):
        """Test 15: Account Unlink (auth:unlink) removes session for that user."""
        session_mgr = UserSessionManager()
        fav_service = MagicMock(spec=FavoriteService)
        provider = RealMeetingRoomProvider(session_mgr=session_mgr, favorite_service=fav_service)
        set_query_provider(provider)

        client_a = GroupwareClient()
        client_a._is_authenticated = True
        session_mgr.set_client("777", client_a)
        assert session_mgr.has_session("777") is True

        # Simulate Telegram 'auth:unlink' button click
        update = MagicMock()
        user = MagicMock()
        user.id = 777
        update.effective_user = user
        query = MagicMock()
        query.data = "auth:unlink"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        with patch("meeting_room_bot.auth.session_manager.session_manager", session_mgr):
            await button_callback(update, MagicMock())

        assert session_mgr.has_session("777") is False
        query.edit_message_text.assert_called_once()
        args, _ = query.edit_message_text.call_args
        assert "🔓 그룹웨어 계정 연결이 해제되었습니다." in args[0]

    def test_16_favorites_isolation_maintained_per_user(self):
        """Test 16: Favorites isolation is maintained per Telegram user_id."""
        repo = MagicMock(spec=FavoriteRepository)
        repo.get_user_favorites.side_effect = lambda uid: (
            UserFavorites(user_id="user_11", favorite_assets={50}, favorite_rooms={501}) if uid == "user_11"
            else UserFavorites(user_id="user_22", favorite_assets={80}, favorite_rooms={801})
        )
        fav_service = FavoriteService(repo=repo)

        uf1 = fav_service.get_user_favorites("user_11")
        uf2 = fav_service.get_user_favorites("user_22")

        assert uf1.favorite_assets == {50}
        assert uf2.favorite_assets == {80}
        assert uf1.favorite_assets != uf2.favorite_assets
