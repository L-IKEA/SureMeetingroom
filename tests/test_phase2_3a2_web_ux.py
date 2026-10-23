"""Comprehensive Test Suite for Phase 2.3A-2: Meeting Room Web App Core UX Integration.

Covers:
NOW Mode:
1. Returns only currently available rooms (is_available_now=True)
2. Excludes rooms currently in use (is_available_now=False)
3. Next reservation start time and available duration (minutes)
4. All-day empty room ("오늘 남은 예약 없음" / next_reservation_start is None)
5. Favorite-only filtering in NOW mode
6. Asset/floor filtering in NOW mode

WHEN Mode:
7. Full interval availability calculation
8. Partial overlap exclusion
9. Boundary condition: reservation start == request end (allowed)
10. Boundary condition: reservation end == request start (allowed)
11. Favorite-only filtering in WHEN mode
12. Asset/floor filtering in WHEN mode
13. No available rooms condition (empty state)

UI & API Integration:
14. GET /api/web/availability endpoint returns 200 + structured JSON (no Telegram formatting strings)
15. GET /api/web/availability requires valid WebSession (401 on unauthorized)
16. NOW mode rendering structure in HTML
17. WHEN mode controls and container structure in HTML
18. TIMELINE mode preserved without regression
19. Asset selection dropdown integrated ("어디" integration)
20. Universal favorite toggle across modes
21. Loading spinner and explicit error retry
22. XSS protection and no credential/session leakage
23. Platform independence: Zero Telegram.WebApp dependency
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
from meeting_room_bot.auth.session_manager import session_manager
from meeting_room_bot.favorites.json_repository import JsonFavoriteRepository
from meeting_room_bot.favorites.service import FavoriteService
from meeting_room_bot.models import Asset, Reservation, Room, UserKey
from meeting_room_bot.providers.base import QueryResult, QueryStatus
from meeting_room_bot.providers.mock_data import MockMeetingRoomData
from meeting_room_bot.providers.mock_provider import MockMeetingRoomProvider
from meeting_room_bot.providers.real_provider import RealMeetingRoomProvider
from meeting_room_bot.services.availability_service import AvailabilityService
from meeting_room_bot.services.meeting_room_service import MeetingRoomService
from meeting_room_bot.services.room_status_service import RoomStatusService

SEOUL_TZ = timezone(timedelta(hours=9))


@pytest.fixture(autouse=True)
def clean_test_environment(tmp_path):
    """Ensure clean stores and temporary favorite repository before each test."""
    link_session_store.clear()
    web_session_store.clear()
    session_manager._sessions.clear()

    fav_file = tmp_path / "user_favorites.json"
    repo = JsonFavoriteRepository(file_path=str(fav_file))
    FavoriteService._instance = FavoriteService(repo=repo)

    yield

    FavoriteService._instance = None


class TestNowModeCoreLogic:
    """Tests 1-6: NOW mode availability, reservation boundaries, and filtering."""

    def test_now_returns_only_available_rooms(self):
        """1. Available rooms now have is_available_now=True."""
        now = datetime(2026, 8, 11, 14, 0, tzinfo=SEOUL_TZ)
        room = Room(id=170, asset_id=70, name="7-1", capacity=6, raw_name="7-1 (6인)")
        reservations = [
            Reservation(
                id=1,
                room_id=170,
                start_time=datetime(2026, 8, 11, 15, 0, tzinfo=SEOUL_TZ),
                end_time=datetime(2026, 8, 11, 16, 0, tzinfo=SEOUL_TZ),
            )
        ]

        status = RoomStatusService.calculate_status(room, reservations, now=now)
        assert status.is_available is True

    def test_now_excludes_busy_rooms(self):
        """2. Busy rooms at now have is_available_now=False."""
        now = datetime(2026, 8, 11, 14, 0, tzinfo=SEOUL_TZ)
        room = Room(id=172, asset_id=70, name="7-3", capacity=8, raw_name="7-3 (8인)")
        reservations = [
            Reservation(
                id=2,
                room_id=172,
                start_time=datetime(2026, 8, 11, 13, 30, tzinfo=SEOUL_TZ),
                end_time=datetime(2026, 8, 11, 14, 30, tzinfo=SEOUL_TZ),
            )
        ]

        status = RoomStatusService.calculate_status(room, reservations, now=now)
        assert status.is_available is False
        assert status.current_reservation_end == datetime(2026, 8, 11, 14, 30, tzinfo=SEOUL_TZ)

    def test_now_next_reservation_time_and_duration(self):
        """3. Next reservation start time and available duration in minutes."""
        now = datetime(2026, 8, 11, 14, 0, tzinfo=SEOUL_TZ)
        room = Room(id=170, asset_id=70, name="7-1", capacity=6, raw_name="7-1")
        reservations = [
            Reservation(
                id=1,
                room_id=170,
                start_time=datetime(2026, 8, 11, 14, 55, tzinfo=SEOUL_TZ),
                end_time=datetime(2026, 8, 11, 16, 0, tzinfo=SEOUL_TZ),
            )
        ]

        status = RoomStatusService.calculate_status(room, reservations, now=now)
        assert status.is_available is True
        assert status.next_reservation_start == datetime(2026, 8, 11, 14, 55, tzinfo=SEOUL_TZ)

        # Mock timeline dataset calculation
        mock_timeline = MockMeetingRoomData.get_mock_timeline_data(asset_id=70, now=now)
        assert "rooms" in mock_timeline
        r71 = next((r for r in mock_timeline["rooms"] if r["id"] == 170), None)
        assert r71 is not None
        assert "next_reservation_start" in r71
        assert "available_until" in r71
        assert "available_minutes" in r71

    def test_now_no_remaining_reservations(self):
        """4. Room with no reservations has next_reservation_start=None, available_minutes=None."""
        now = datetime(2026, 8, 11, 14, 0, tzinfo=SEOUL_TZ)
        room = Room(id=173, asset_id=70, name="7-4", capacity=8, raw_name="7-4")
        reservations = []

        status = RoomStatusService.calculate_status(room, reservations, now=now)
        assert status.is_available is True
        assert status.next_reservation_start is None

        mock_timeline = MockMeetingRoomData.get_mock_timeline_data(asset_id=70, now=now)
        r74 = next((r for r in mock_timeline["rooms"] if r["id"] == 173), None)
        assert r74 is not None
        assert r74["is_available_now"] is True
        assert r74["next_reservation_start"] is None
        assert r74["available_minutes"] is None

    def test_now_favorite_only_filter(self):
        """5. Favorite only filter in NOW dataset."""
        user_key = UserKey("telegram", "fav_now_user")
        fav_service = FavoriteService._instance
        fav_service.add_room(user_key, 170)

        now = datetime(2026, 8, 11, 14, 0, tzinfo=SEOUL_TZ)
        mock_timeline = MockMeetingRoomData.get_mock_timeline_data(asset_id=70, user_key=user_key, now=now)

        # Filter by favorite
        fav_rooms = [r for r in mock_timeline["rooms"] if r["favorite"]]
        assert len(fav_rooms) >= 1
        assert any(r["id"] == 170 for r in fav_rooms)

    def test_now_asset_filter(self):
        """6. Asset/floor filtering returns rooms for the selected asset."""
        now = datetime(2026, 8, 11, 14, 0, tzinfo=SEOUL_TZ)
        t70 = MockMeetingRoomData.get_mock_timeline_data(asset_id=70, now=now)
        t80 = MockMeetingRoomData.get_mock_timeline_data(asset_id=80, now=now)

        assert t70["selected_asset"]["id"] == 70
        assert t80["selected_asset"]["id"] == 80
        assert all(r["id"] in [170, 171, 172, 173, 174, 175] for r in t70["rooms"])
        assert all(r["id"] in [180, 181, 182] for r in t80["rooms"])


class TestWhenModeCoreLogic:
    """Tests 7-13: WHEN mode interval availability and boundary conditions."""

    def test_when_full_interval_availability(self):
        """7. Full interval availability check without conflicts."""
        room = Room(id=1, asset_id=70, name="Room 1", capacity=6, raw_name="Room 1")
        res_map = {1: []}

        req_start = datetime(2026, 8, 11, 14, 0, tzinfo=SEOUL_TZ)
        req_end = datetime(2026, 8, 11, 15, 0, tzinfo=SEOUL_TZ)

        avail, unavail = AvailabilityService.find_available_rooms([room], res_map, req_start, req_end)
        assert len(avail) == 1
        assert len(unavail) == 0

    def test_when_partial_overlap_excluded(self):
        """8. Partial overlap with requested interval is excluded."""
        room = Room(id=1, asset_id=70, name="Room 1", capacity=6, raw_name="Room 1")
        res_map = {
            1: [
                Reservation(
                    id=10,
                    room_id=1,
                    start_time=datetime(2026, 8, 11, 14, 30, tzinfo=SEOUL_TZ),
                    end_time=datetime(2026, 8, 11, 16, 0, tzinfo=SEOUL_TZ),
                )
            ]
        }

        req_start = datetime(2026, 8, 11, 14, 0, tzinfo=SEOUL_TZ)
        req_end = datetime(2026, 8, 11, 15, 0, tzinfo=SEOUL_TZ)

        avail, unavail = AvailabilityService.find_available_rooms([room], res_map, req_start, req_end)
        assert len(avail) == 0
        assert len(unavail) == 1

    def test_when_boundary_req_end_equals_res_start_allowed(self):
        """9. Reservation starts exactly when requested slot ends (res.start == req.end) -> allowed."""
        room = Room(id=1, asset_id=70, name="Room 1", capacity=6, raw_name="Room 1")
        res_map = {
            1: [
                Reservation(
                    id=10,
                    room_id=1,
                    start_time=datetime(2026, 8, 11, 15, 0, tzinfo=SEOUL_TZ),
                    end_time=datetime(2026, 8, 11, 16, 0, tzinfo=SEOUL_TZ),
                )
            ]
        }

        req_start = datetime(2026, 8, 11, 14, 0, tzinfo=SEOUL_TZ)
        req_end = datetime(2026, 8, 11, 15, 0, tzinfo=SEOUL_TZ)

        avail, unavail = AvailabilityService.find_available_rooms([room], res_map, req_start, req_end)
        assert len(avail) == 1
        assert len(unavail) == 0

    def test_when_boundary_req_start_equals_res_end_allowed(self):
        """10. Reservation ends exactly when requested slot starts (res.end == req.start) -> allowed."""
        room = Room(id=1, asset_id=70, name="Room 1", capacity=6, raw_name="Room 1")
        res_map = {
            1: [
                Reservation(
                    id=10,
                    room_id=1,
                    start_time=datetime(2026, 8, 11, 13, 0, tzinfo=SEOUL_TZ),
                    end_time=datetime(2026, 8, 11, 14, 0, tzinfo=SEOUL_TZ),
                )
            ]
        }

        req_start = datetime(2026, 8, 11, 14, 0, tzinfo=SEOUL_TZ)
        req_end = datetime(2026, 8, 11, 15, 0, tzinfo=SEOUL_TZ)

        avail, unavail = AvailabilityService.find_available_rooms([room], res_map, req_start, req_end)
        assert len(avail) == 1
        assert len(unavail) == 0

    def test_when_favorite_only_filtering(self):
        """11. WHEN availability supports favorite filtering."""
        user_key = UserKey("telegram", "fav_when_user")
        fav_service = FavoriteService._instance
        fav_service.add_room(user_key, 170)

        data = MockMeetingRoomData.get_mock_web_availability(
            asset_id=70,
            start_time="14:00",
            duration=60,
            user_key=user_key,
        )

        assert "rooms" in data
        fav_avail = [r for r in data["rooms"] if r["favorite"] and r["available"]]
        assert len(fav_avail) >= 1
        assert any(r["id"] == 170 for r in fav_avail)

    def test_when_asset_switch(self):
        """12. WHEN availability for different asset floors."""
        w70 = MockMeetingRoomData.get_mock_web_availability(asset_id=70, start_time="14:00", duration=60)
        w80 = MockMeetingRoomData.get_mock_web_availability(asset_id=80, start_time="14:00", duration=60)

        assert w70["selected_asset"]["id"] == 70
        assert w80["selected_asset"]["id"] == 80
        assert all(r["id"] in [170, 171, 172, 173, 174, 175] for r in w70["rooms"])
        assert all(r["id"] in [180, 181, 182] for r in w80["rooms"])

    def test_when_no_available_rooms(self):
        """13. WHEN no rooms are available returns empty available list."""
        room = Room(id=1, asset_id=70, name="Room 1", capacity=6, raw_name="Room 1")
        res_map = {
            1: [
                Reservation(
                    id=10,
                    room_id=1,
                    start_time=datetime(2026, 8, 11, 13, 0, tzinfo=SEOUL_TZ),
                    end_time=datetime(2026, 8, 11, 18, 0, tzinfo=SEOUL_TZ),
                )
            ]
        }

        req_start = datetime(2026, 8, 11, 14, 0, tzinfo=SEOUL_TZ)
        req_end = datetime(2026, 8, 11, 15, 0, tzinfo=SEOUL_TZ)

        avail, unavail = AvailabilityService.find_available_rooms([room], res_map, req_start, req_end)
        assert len(avail) == 0
        assert len(unavail) == 1


class TestWebAPIAndUIIntegration:
    """Tests 14-23: Web API endpoints, UI rendering, security, and platform independence."""

    def test_api_web_availability_success(self):
        """14. GET /api/web/availability returns 200 with structured JSON."""
        client = TestClient(app)
        user_key = UserKey("telegram", "api_when_user")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/api/web/availability?asset_id=70&start=14:00&duration_minutes=60")

        assert resp.status_code == 200
        data = resp.json()
        assert data["start_time"] == "14:00"
        assert data["end_time"] == "15:00"
        assert data["duration_minutes"] == 60
        assert "rooms" in data
        assert len(data["rooms"]) > 0

        # Structured schema check (no Telegram markdown messages)
        room0 = data["rooms"][0]
        assert "id" in room0
        assert "name" in room0
        assert "capacity" in room0
        assert "favorite" in room0
        assert "available" in room0
        assert "status_text" in room0
        # Must not contain Telegram formatting strings
        assert "🟢 회의실" not in room0["name"]

    def test_api_web_availability_auth_required(self):
        """15. GET /api/web/availability without session returns 401."""
        client = TestClient(app)
        resp = client.get("/api/web/availability?asset_id=70&start=14:00&duration_minutes=60")
        assert resp.status_code == 401
        assert resp.json()["code"] == "NOT_AUTHENTICATED"

    def test_now_mode_rendering_elements(self):
        """16. NOW mode rendering elements exist in /timeline HTML."""
        client = TestClient(app)
        user_key = UserKey("telegram", "ui_user_now")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")

        assert resp.status_code == 200
        html = resp.text

        # Mode buttons
        assert 'id="mode-now-btn"' in html
        assert 'id="mode-when-btn"' in html
        assert 'id="mode-timeline-btn"' in html
        # NOW container
        assert 'id="now-view-container"' in html
        assert 'id="now-cards-container"' in html

    def test_when_mode_controls_and_container(self):
        """17. WHEN mode controls and container exist in /timeline HTML."""
        client = TestClient(app)
        user_key = UserKey("telegram", "ui_user_when")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")

        assert resp.status_code == 200
        html = resp.text

        assert 'id="when-controls-panel"' in html
        assert 'id="when-start-time"' in html
        assert 'data-duration="30"' in html
        assert 'data-duration="60"' in html
        assert 'data-duration="90"' in html
        assert 'data-duration="120"' in html
        assert 'id="when-view-container"' in html
        assert 'id="when-cards-container"' in html

    def test_timeline_mode_preserved(self):
        """18. Phase 2.3A TIMELINE mode table and modal elements preserved."""
        client = TestClient(app)
        user_key = UserKey("telegram", "ui_user_timeline")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")

        assert resp.status_code == 200
        html = resp.text

        assert 'id="timeline-view-container"' in html
        assert 'id="timeline-scroll"' in html
        assert 'id="timeline-table"' in html
        assert 'id="detail-modal"' in html
        assert 'id="modal-room-name"' in html
        assert 'id="modal-time-range"' in html

    def test_asset_selection_dropdown_integrated(self):
        """19. Floor / Asset selector represents "어디" integration."""
        client = TestClient(app)
        user_key = UserKey("telegram", "ui_user_asset")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")

        assert resp.status_code == 200
        html = resp.text
        assert 'id="asset-select"' in html
        assert 'onchange="onAssetChange(this.value)"' in html

    def test_universal_favorite_toggle(self):
        """20. Universal favorite filter exists and works across modes."""
        client = TestClient(app)
        user_key = UserKey("telegram", "ui_user_fav")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")

        assert resp.status_code == 200
        html = resp.text
        assert 'id="filter-all-btn"' in html
        assert 'id="filter-fav-btn"' in html
        assert "onclick=\"setFilter('all')\"" in html
        assert "onclick=\"setFilter('fav')\"" in html

    def test_loading_and_error_states(self):
        """21. Loading spinner and explicit error retry handling."""
        client = TestClient(app)
        user_key = UserKey("telegram", "ui_user_loading")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")

        assert resp.status_code == 200
        html = resp.text
        assert 'id="loading-spinner"' in html
        assert 'id="error-container"' in html
        assert "onclick=\"retryActiveQuery()\"" in html or "onclick=\"loadTimelineData()\"" in html

    def test_security_xss_protection_and_token_leakage(self):
        """22. XSS protection maintained and no sensitive session tokens leaked."""
        client = TestClient(app)
        user_key = UserKey("telegram", "ui_user_sec")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        # Mock malicious data containing script breakout attempt
        xss_attack = '</script><script>window.XSS=1</script>'
        malicious_data = {
            "date": "2026-08-11",
            "date_display": xss_attack,
            "current_time": "14:00",
            "start_hour": 8,
            "end_hour": 20,
            "hours": [8, 9, 10],
            "assets": [{"id": 70, "name": xss_attack, "selected": True}],
            "selected_asset": {"id": 70, "name": xss_attack, "short_label": "7층"},
            "rooms": [
                {
                    "id": 999,
                    "name": xss_attack,
                    "capacity": 6,
                    "favorite": False,
                    "is_available_now": True,
                    "next_reservation_start": "15:00",
                    "available_until": "15:00",
                    "available_minutes": 60,
                    "status_text": xss_attack,
                    "reservations": [],
                }
            ],
            "total_rooms": 1,
            "available_rooms_count": 1,
        }

        mock_provider = MagicMock()
        mock_provider.get_timeline.return_value = QueryResult(
            status=QueryStatus.SUCCESS,
            data=malicious_data,
        )

        with patch("meeting_room_bot.account_link.app.get_provider", return_value=mock_provider):
            with patch.object(session_manager, "has_session", return_value=True):
                resp = client.get("/timeline")

        assert resp.status_code == 200
        html = resp.text

        # Ensure Jinja2 tojson serialized the breakout tag safely
        assert "</script><script>window.XSS=1</script>" not in html
        assert "\\u003c/script\\u003e\\u003cscript\\u003ewindow.XSS=1\\u003c/script\\u003e" in html or "\\u003c" in html

        # Zero credential or token leakage
        assert web_session.session_id not in html
        assert "password" not in html.lower()

    def test_platform_independence_zero_telegram_dependency(self):
        """23. Web App has zero Telegram.WebApp dependency."""
        client = TestClient(app)
        user_key = UserKey("telegram", "ui_user_platform")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")

        assert resp.status_code == 200
        html = resp.text

        assert "Telegram.WebApp" not in html
        assert "telegram-web-app.js" not in html
        assert "initData" not in html
        assert "MainButton" not in html
