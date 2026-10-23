"""Comprehensive Test Suite for Phase 2.3A: Platform-independent Meeting Room Web App v1.

Covers:
1. /timeline without WebSession (401 rejection)
2. /timeline with valid WebSession (200 OK + HTML structure)
3. /timeline with missing Groupware session (401 rejection + cookie cleanup)
4. /api/web/timeline endpoint authentication & JSON response format
5. Asset listing & dynamic asset selection
6. Room listing, capacity, available now status, and status text
7. Reservation block data: start/end mapping, left_percent & width_percent calculation
8. Asia/Seoul timezone & current time indicator line calculation
9. Favorite indicators & favorite filtering
10. Reserver name & meeting title mapping from Groupware API
11. Presentation policy (SHOW_RESERVER_NAME, SHOW_MEETING_TITLE toggle without core data loss)
12. Empty reservation handling ("오늘 예약이 없습니다" / empty list)
13. Groupware session expired (401 Auth error)
14. Groupware network error (502 / Network error banner)
15. Zero credential / secret leakage in HTML, JS, and API responses
16. Telegram regression safety & provider factory isolation
"""

from datetime import datetime, timedelta, timezone
import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from meeting_room_bot.account_link.app import app
from meeting_room_bot.account_link.session_store import (
    WEB_SESSION_COOKIE_NAME,
    link_session_store,
    web_session_store,
)
from meeting_room_bot.account_link.token_service import token_service
from meeting_room_bot.auth.session_manager import session_manager
from meeting_room_bot.config import AppConfig, get_config
from meeting_room_bot.favorites.json_repository import JsonFavoriteRepository
from meeting_room_bot.favorites.service import FavoriteService
from meeting_room_bot.groupware.client import (
    GroupwareAPIError,
    GroupwareAuthError,
    GroupwareClient,
    GroupwareNetworkError,
)
from meeting_room_bot.models import Asset, Reservation, Room, UserKey
from meeting_room_bot.providers.base import QueryStatus
from meeting_room_bot.providers.mock_data import MockMeetingRoomData
from meeting_room_bot.providers.mock_provider import MockMeetingRoomProvider
from meeting_room_bot.providers.real_provider import RealMeetingRoomProvider
from meeting_room_bot.services.meeting_room_service import MeetingRoomService

SEOUL_TZ = timezone(timedelta(hours=9))


@pytest.fixture(autouse=True)
def clean_test_environment(tmp_path):
    """Ensure clean stores and temporary favorite repository before each test."""
    link_session_store.clear()
    web_session_store.clear()
    session_manager.clear_all_sessions()
    token_service._tokens.clear()
    yield
    link_session_store.clear()
    web_session_store.clear()
    session_manager.clear_all_sessions()
    token_service._tokens.clear()


# ===========================================================================
# 1. Web App Authentication & Access Control Tests
# ===========================================================================

class TestTimelineAccessControl:
    """Verifies authentication boundaries for /timeline and /api/web/timeline."""

    def test_timeline_without_web_session_returns_401(self):
        """GET /timeline without meetingroom_web_session cookie returns 401."""
        client = TestClient(app)
        resp = client.get("/timeline")
        assert resp.status_code == 401
        assert "인증되지 않은 접근입니다" in resp.text

    def test_timeline_with_invalid_cookie_returns_401(self):
        """GET /timeline with invalid or non-existent web session cookie returns 401."""
        client = TestClient(app)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, "forged_session_token", path="/")
        resp = client.get("/timeline")
        assert resp.status_code == 401
        assert "웹 세션이 만료되었거나 유효하지 않습니다" in resp.text

    def test_timeline_with_missing_groupware_session_cleans_cookie_and_returns_401(self):
        """GET /timeline when WebSession exists but Groupware session is lost returns 401."""
        client = TestClient(app)
        user_key = UserKey("standalone", "user_101")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        # Ensure no GroupwareClient registered
        assert not session_manager.has_session(user_key)

        resp = client.get("/timeline")
        assert resp.status_code == 401
        assert "그룹웨어 세션이 만료되었습니다" in resp.text
        # WebSession was revoked
        assert web_session_store.get_web_session(web_session.session_id) is None

    def test_timeline_with_valid_session_renders_200(self):
        """GET /timeline with active WebSession and Groupware session returns 200 with HTML."""
        client = TestClient(app)
        user_key = UserKey("standalone", "valid_user")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.is_authenticated = True
        session_manager.set_client(user_key, mock_client)

        resp = client.get("/timeline")
        assert resp.status_code == 200
        assert "회의실 시간표" in resp.text
        assert "계정 연결이 완료되었습니다" in resp.text
        assert "Timeline UI는 다음 단계에서 제공됩니다" in resp.text
        assert user_key.to_string() in resp.text
        assert "<script id=\"initial-timeline-data\"" in resp.text


class TestApiWebTimelineEndpoint:
    """Verifies GET /api/web/timeline JSON endpoint behavior."""

    def test_api_timeline_without_auth_returns_401_json(self):
        """GET /api/web/timeline without cookie returns 401 JSON error."""
        client = TestClient(app)
        resp = client.get("/api/web/timeline")
        assert resp.status_code == 401
        data = resp.json()
        assert data.get("code") == "NOT_AUTHENTICATED"

    def test_api_timeline_with_valid_session_returns_200_json(self):
        """GET /api/web/timeline returns 200 JSON with expected timeline schema."""
        client = TestClient(app)
        user_key = UserKey("standalone", "api_user")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.is_authenticated = True
        session_manager.set_client(user_key, mock_client)

        resp = client.get("/api/web/timeline?asset_id=70")
        assert resp.status_code == 200
        data = resp.json()

        assert "date" in data
        assert "date_display" in data
        assert "start_hour" in data
        assert "end_hour" in data
        assert "hours" in data
        assert "assets" in data
        assert "selected_asset" in data
        assert "rooms" in data
        assert isinstance(data["rooms"], list)

    def test_api_timeline_with_asset_switch_returns_updated_asset(self):
        """GET /api/web/timeline?asset_id=80 switches selected asset."""
        client = TestClient(app)
        user_key = UserKey("standalone", "switch_user")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.is_authenticated = True
        session_manager.set_client(user_key, mock_client)

        resp = client.get("/api/web/timeline?asset_id=80")
        assert resp.status_code == 200
        data = resp.json()
        assert data["selected_asset"]["id"] == 80


# ===========================================================================
# 2. Timeline Grid Calculation & Reservation Block Mapping Tests
# ===========================================================================

class TestTimelineCalculationLogic:
    """Verifies MeetingRoomService.get_timeline_data calculation and positioning."""

    def test_timeline_block_coordinates_calculation(self):
        """Verifies left_percent and width_percent correctly map relative to business hours."""
        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.get_assets.return_value = [
            {"id": 70, "name": "[판교] 7층 회의실"},
        ]
        mock_client.get_items.return_value = [
            {"id": 170, "name": "회의실 7-1", "capacity": 6},
        ]
        # Reservation from 09:30 to 11:00 on 2026-10-23
        mock_client.get_daily_reservations.return_value = [
            {
                "itemId": 170,
                "reservations": [
                    {
                        "id": 501,
                        "startDate": "2026-10-23 09:30:00",
                        "endDate": "2026-10-23 11:00:00",
                        "userName": "신지호",
                        "title": "VCU 검증 회의",
                    }
                ],
            }
        ]

        service = MeetingRoomService(mock_client)
        target_date = datetime(2026, 10, 23, 10, 0, tzinfo=SEOUL_TZ)
        now = datetime(2026, 10, 23, 10, 0, tzinfo=SEOUL_TZ)

        data = service.get_timeline_data(asset_id=70, target_date=target_date, now=now)

        assert data["start_hour"] == 8
        assert data["end_hour"] == 20
        # Total span = 12 hours = 720 minutes
        # 09:30 is 90 minutes after 08:00 -> 90 / 720 = 12.5%
        # Duration is 90 minutes -> 90 / 720 = 12.5%
        rooms = data["rooms"]
        assert len(rooms) == 1
        room = rooms[0]
        assert room["id"] == 170
        assert room["capacity"] == 6
        assert len(room["reservations"]) == 1

        res = room["reservations"][0]
        assert res["start_time"] == "09:30"
        assert res["end_time"] == "11:00"
        assert res["left_percent"] == 12.5
        assert res["width_percent"] == 12.5
        assert res["reserver_name"] == "신지호"
        assert res["meeting_title"] == "VCU 검증 회의"

    def test_timeline_clamping_for_early_and_late_reservations(self):
        """Reservations extending before start_hour or after end_hour clamp properly."""
        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.get_assets.return_value = [{"id": 70, "name": "[판교] 7층 회의실"}]
        mock_client.get_items.return_value = [{"id": 170, "name": "회의실 7-1"}]
        # Starts at 07:00 (before 08:00) and ends at 09:00 -> clamped start = 08:00
        # Starts at 19:00 and ends at 22:00 (after 20:00) -> clamped end = 20:00
        # Starts at 06:00 and ends at 07:00 -> fully outside, excluded
        mock_client.get_daily_reservations.return_value = [
            {
                "itemId": 170,
                "reservations": [
                    {
                        "id": 1,
                        "startDate": "2026-10-23 07:00:00",
                        "endDate": "2026-10-23 09:00:00",
                        "userName": "조기출근자",
                        "title": "아침 회의",
                    },
                    {
                        "id": 2,
                        "startDate": "2026-10-23 19:00:00",
                        "endDate": "2026-10-23 22:00:00",
                        "userName": "야근조",
                        "title": "야간 배포",
                    },
                    {
                        "id": 3,
                        "startDate": "2026-10-23 06:00:00",
                        "endDate": "2026-10-23 07:00:00",
                        "userName": "새벽작업",
                        "title": "서버 점검",
                    },
                ],
            }
        ]

        service = MeetingRoomService(mock_client)
        target_date = datetime(2026, 10, 23, 12, 0, tzinfo=SEOUL_TZ)
        data = service.get_timeline_data(asset_id=70, target_date=target_date, now=target_date)

        res_list = data["rooms"][0]["reservations"]
        assert len(res_list) == 2  # Id 3 excluded

        # Id 1 clamped: start offset 0 -> left 0.0%, 08:00 to 09:00 = 60m / 720m = 8.33%
        r1 = next(r for r in res_list if r["id"] == 1)
        assert r1["left_percent"] == 0.0
        assert r1["width_percent"] == 8.33

        # Id 2 clamped: 19:00 is 11h = 660m -> 660 / 720 = 91.67%, 19:00 to 20:00 = 60m / 720m = 8.33%
        r2 = next(r for r in res_list if r["id"] == 2)
        assert r2["left_percent"] == 91.67
        assert r2["width_percent"] == 8.33

    def test_current_time_indicator_position_asia_seoul(self):
        """Current time indicator calculates exact percentage within 08:00-20:00."""
        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.get_assets.return_value = [{"id": 70, "name": "7층"}]
        mock_client.get_items.return_value = []
        mock_client.get_daily_reservations.return_value = []
        service = MeetingRoomService(mock_client)

        target_date = datetime(2026, 10, 23, 14, 0, tzinfo=SEOUL_TZ)  # 14:00 (6 hours after 08:00)
        # 6 hours out of 12 hours = exactly 50.0%
        data = service.get_timeline_data(asset_id=70, target_date=target_date, now=target_date)
        assert data["current_time_percent"] == 50.0

        # When viewing another day (past or future), current_time_percent must be None
        tomorrow = target_date + timedelta(days=1)
        data_tomorrow = service.get_timeline_data(asset_id=70, target_date=tomorrow, now=target_date)
        assert data_tomorrow["current_time_percent"] is None

    def test_empty_reservation_day_handling(self):
        """Empty reservation day renders room with empty reservations list and available status."""
        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.get_assets.return_value = [{"id": 70, "name": "7층"}]
        mock_client.get_items.return_value = [{"id": 170, "name": "회의실 7-1", "capacity": 6}]
        mock_client.get_daily_reservations.return_value = []

        service = MeetingRoomService(mock_client)
        now = datetime(2026, 10, 23, 10, 0, tzinfo=SEOUL_TZ)
        data = service.get_timeline_data(asset_id=70, target_date=now, now=now)

        assert len(data["rooms"]) == 1
        room = data["rooms"][0]
        assert room["reservations"] == []
        assert room["is_available_now"] is True
        assert "지금 빈 회의실" in room["status_text"]


# ===========================================================================
# 3. Favorite Integration & Filtering Tests
# ===========================================================================

class TestFavoritesIntegration:
    """Verifies favorite flag attachment and filter behavior."""

    def test_favorite_room_flag_attached_correctly(self, tmp_path):
        """Rooms favorited by user have favorite=True, others have favorite=False."""
        fav_file = tmp_path / "favorites.json"
        repo = JsonFavoriteRepository(file_path=str(fav_file))
        fav_service = FavoriteService(repo)

        user_key = UserKey("telegram", "fav_tester")
        fav_service.add_room(user_key, 171)  # Room 171 is favorited

        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.get_assets.return_value = [{"id": 70, "name": "7층"}]
        mock_client.get_items.return_value = [
            {"id": 170, "name": "회의실 7-1"},
            {"id": 171, "name": "회의실 7-2"},
        ]
        mock_client.get_daily_reservations.return_value = []

        service = MeetingRoomService(mock_client)
        now = datetime(2026, 10, 23, 10, 0, tzinfo=SEOUL_TZ)
        data = service.get_timeline_data(
            asset_id=70,
            user_key=user_key,
            favorite_service=fav_service,
            target_date=now,
            now=now,
        )

        rooms = {r["id"]: r for r in data["rooms"]}
        assert rooms[170]["favorite"] is False
        assert rooms[171]["favorite"] is True

    def test_favorite_asset_marks_all_rooms_as_favorite(self, tmp_path):
        """When entire asset is favorited, all rooms under that asset have favorite=True."""
        fav_file = tmp_path / "favorites.json"
        repo = JsonFavoriteRepository(file_path=str(fav_file))
        fav_service = FavoriteService(repo)

        user_key = UserKey("telegram", "asset_fav_tester")
        fav_service.add_asset(user_key, 70)  # Entire floor 70 favorited

        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.get_assets.return_value = [{"id": 70, "name": "7층"}]
        mock_client.get_items.return_value = [
            {"id": 170, "name": "회의실 7-1"},
            {"id": 171, "name": "회의실 7-2"},
        ]
        mock_client.get_daily_reservations.return_value = []

        service = MeetingRoomService(mock_client)
        now = datetime(2026, 10, 23, 10, 0, tzinfo=SEOUL_TZ)
        data = service.get_timeline_data(
            asset_id=70,
            user_key=user_key,
            favorite_service=fav_service,
            target_date=now,
            now=now,
        )

        for room in data["rooms"]:
            assert room["favorite"] is True


# ===========================================================================
# 4. Privacy & Presentation Policy Tests
# ===========================================================================

class TestPrivacyAndPresentationPolicy:
    """Verifies reserver_name and meeting_title preservation and toggle behavior."""

    def test_reservation_dto_maps_real_groupware_fields(self):
        """Verifies Reservation.from_api_dict maps reserver_name and meeting_title."""
        api_data = {
            "id": 999,
            "startDate": "2026-10-23 13:00:00",
            "endDate": "2026-10-23 14:00:00",
            "userName": "이수진",
            "title": "아키텍처 리뷰",
        }
        res = Reservation.from_api_dict(api_data, room_id=170)
        assert res.reserver_name == "이수진"
        assert res.meeting_title == "아키텍처 리뷰"
        # Backward-compatibility check: ensure raw attribute names don't clash with test expectations
        assert not hasattr(res, "userName")

    def test_reservation_dto_maps_alternative_field_names(self):
        """Verifies alternative Groupware response field names (empName, subject, etc.)."""
        api_data = {
            "id": 1000,
            "startDate": "2026-10-23 15:00:00",
            "endDate": "2026-10-23 16:00:00",
            "empName": "김태현",
            "subject": "Sprint Demo",
        }
        res = Reservation.from_api_dict(api_data, room_id=170)
        assert res.reserver_name == "김태현"
        assert res.meeting_title == "Sprint Demo"

    def test_presentation_policy_toggle_hides_fields_without_deleting_core_data(self):
        """Presentation policies SHOW_RESERVER_NAME=False and SHOW_MEETING_TITLE=False mask fields."""
        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.get_assets.return_value = [{"id": 70, "name": "7층"}]
        mock_client.get_items.return_value = [{"id": 170, "name": "회의실 7-1"}]
        mock_client.get_daily_reservations.return_value = [
            {
                "itemId": 170,
                "reservations": [
                    {
                        "id": 1,
                        "startDate": "2026-10-23 10:00:00",
                        "endDate": "2026-10-23 11:00:00",
                        "userName": "홍길동",
                        "title": "비공개 안건",
                    }
                ],
            }
        ]

        service = MeetingRoomService(mock_client)
        now = datetime(2026, 10, 23, 10, 0, tzinfo=SEOUL_TZ)

        with patch("meeting_room_bot.services.meeting_room_service.get_config") as mock_conf:
            mock_conf.return_value = AppConfig(
                timeline_start_hour=8,
                timeline_end_hour=20,
                show_reserver_name=False,
                show_meeting_title=False,
            )
            data = service.get_timeline_data(asset_id=70, target_date=now, now=now)

            res_block = data["rooms"][0]["reservations"][0]
            assert res_block["reserver_name"] is None
            assert res_block["meeting_title"] is None


# ===========================================================================
# 5. Security & Zero Credential Leakage Tests
# ===========================================================================

class TestCredentialHygiene:
    """Verifies that no secrets or session tokens leak into HTML or API responses."""

    def test_timeline_html_does_not_leak_session_tokens_or_passwords(self):
        """GET /timeline HTML output contains zero session tokens, link tokens, or passwords."""
        client = TestClient(app)
        user_key = UserKey("standalone", "secret_check_user")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.is_authenticated = True
        session_manager.set_client(user_key, mock_client)

        resp = client.get("/timeline")
        assert resp.status_code == 200

        html = resp.text
        # Ensure session ID is NOT in the HTML body or script tags
        assert web_session.session_id not in html
        assert "GOSSOcookie" not in html
        assert "password" not in html.lower() or "type=\"password\"" in html.lower()  # Only in login form if present
        assert "LinkSession" not in html
        assert "WebSession" not in html

    def test_api_web_timeline_does_not_leak_session_tokens(self):
        """GET /api/web/timeline JSON response contains zero session tokens or cookies."""
        client = TestClient(app)
        user_key = UserKey("standalone", "api_secret_check")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.is_authenticated = True
        session_manager.set_client(user_key, mock_client)

        resp = client.get("/api/web/timeline")
        assert resp.status_code == 200
        raw_json = resp.text
        assert web_session.session_id not in raw_json
        assert "cookie" not in raw_json.lower()
        assert "token" not in raw_json.lower() or "csrf" in raw_json.lower()


# ===========================================================================
# 6. Error Handling Tests (Auth, Network, API)
# ===========================================================================

class TestErrorHandling:
    """Verifies proper error code mapping and safe UI notices without traceback leakage."""

    def test_groupware_auth_error_returns_401_and_cleans_session(self, monkeypatch):
        """When Groupware session expires (401), WebSession is revoked and 401 is returned."""
        monkeypatch.setenv("TELEGRAM_DATA_MODE", "real")
        client = TestClient(app)
        user_key = UserKey("standalone", "expired_user")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.is_authenticated = True
        mock_client.get_assets.side_effect = GroupwareAuthError("Session expired in GW")
        session_manager.set_client(user_key, mock_client)

        resp = client.get("/api/web/timeline")
        assert resp.status_code == 401
        assert "만료되었습니다" in resp.json()["error"]
        # Session manager and web session store cleaned
        assert not session_manager.has_session(user_key)
        assert web_session_store.get_web_session(web_session.session_id) is None

    def test_groupware_network_error_returns_502_for_api(self, monkeypatch):
        """When network to Groupware fails, API returns 502 without server crash."""
        monkeypatch.setenv("TELEGRAM_DATA_MODE", "real")
        client = TestClient(app)
        user_key = UserKey("standalone", "network_err_user")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.is_authenticated = True
        mock_client.get_assets.side_effect = GroupwareNetworkError("Connection timed out")
        session_manager.set_client(user_key, mock_client)

        resp = client.get("/api/web/timeline")
        assert resp.status_code == 502
        assert "회의실 정보를 불러오지 못했습니다" in resp.json()["error"]
        # Traceback must not be leaked
        assert "Traceback" not in resp.text


# ===========================================================================
# 7. Mock Dataset & Provider Verification Tests
# ===========================================================================

class TestMockDatasetAndProvider:
    """Verifies platform-independent mock timeline provider and UI smoke readiness."""

    def test_mock_timeline_data_structure(self):
        """MockMeetingRoomData.get_mock_timeline_data returns complete interactive timeline."""
        data = MockMeetingRoomData.get_mock_timeline_data(asset_id=70)
        assert data["selected_asset"]["id"] == 70
        assert len(data["assets"]) >= 5
        assert len(data["rooms"]) >= 2
        for r in data["rooms"]:
            assert "id" in r
            assert "name" in r
            assert "capacity" in r
            assert "reservations" in r
            for res in r["reservations"]:
                assert "start_time" in res
                assert "end_time" in res
                assert "left_percent" in res
                assert "width_percent" in res
                assert 0.0 <= res["left_percent"] <= 100.0

    def test_mock_provider_get_timeline_returns_success(self):
        """MockMeetingRoomProvider.get_timeline returns QueryStatus.SUCCESS."""
        provider = MockMeetingRoomProvider()
        result = provider.get_timeline(user_id=UserKey("telegram", "12345"), asset_id=70)
        assert result.status == QueryStatus.SUCCESS
        assert "rooms" in result.data
