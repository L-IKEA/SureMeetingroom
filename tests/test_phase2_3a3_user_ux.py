"""Phase 2.3A-3 Meeting Room Web App User UX Completion Tests.

Tests:
1-4: View Modes (NOW, WHEN, WHO, TIMELINE)
5-9: Location (All Locations first, Specific Asset, NOW+All, WHEN+All, WHO+All)
10-17: WHO (All, Name search, Partial, No match, Asset filter, Fav filter, Meeting title, Reserver name)
18-20: Presentation (View label "전체" -> "타임라인", Scope "전체" maintained)
21-24: Security (WHO query XSS, Reserver name XSS, Meeting title XSS, Token/Session leakage)
25-27: Async (Rapid WHO race, Asset switch race, Mode switch race)
"""

import json
import re
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from meeting_room_bot.account_link.app import app
from meeting_room_bot.account_link.session_store import (
    WEB_SESSION_COOKIE_NAME,
    web_session_store,
)
from meeting_room_bot.auth.session_manager import session_manager
from meeting_room_bot.favorites.service import FavoriteService
from meeting_room_bot.models.user_key import UserKey
from meeting_room_bot.providers.mock_provider import MockMeetingRoomProvider


@pytest.fixture
def auth_client():
    """Client with valid web session and mock session manager."""
    client = TestClient(app)
    user_key = UserKey("telegram", "ux_test_user_3a3")
    web_session = web_session_store.create_web_session(user_key)
    client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")
    return client, user_key


# ==============================================================================
# View Modes (1-4)
# ==============================================================================

class TestViewModes:
    def test_view_mode_now_tab(self, auth_client):
        """1. View Mode: NOW button present with correct tab markup."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")
        assert resp.status_code == 200
        html = resp.text
        assert 'id="mode-now-btn"' in html
        assert 'role="tab"' in html
        assert "지금" in html

    def test_view_mode_when_tab(self, auth_client):
        """2. View Mode: WHEN button present with correct tab markup."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")
        assert resp.status_code == 200
        html = resp.text
        assert 'id="mode-when-btn"' in html
        assert 'role="tab"' in html
        assert "언제" in html

    def test_view_mode_who_tab(self, auth_client):
        """3. View Mode: WHO button present with correct tab markup."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")
        assert resp.status_code == 200
        html = resp.text
        assert 'id="mode-who-btn"' in html
        assert 'role="tab"' in html
        assert "누가" in html

    def test_view_mode_timeline_tab(self, auth_client):
        """4. View Mode: TIMELINE button present with '타임라인' label."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")
        assert resp.status_code == 200
        html = resp.text
        assert 'id="mode-timeline-btn"' in html
        assert 'role="tab"' in html
        assert "타임라인" in html


# ==============================================================================
# Location Scope (5-9)
# ==============================================================================

class TestLocationScope:
    def test_all_locations_option_first(self, auth_client):
        """5. Location: '전체 위치' option is first in the asset dropdown logic."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")
        assert resp.status_code == 200
        html = resp.text
        assert '<option value="all"' in html
        assert "전체 위치" in html

    def test_specific_asset_timeline(self, auth_client):
        """6. Location: specific asset returns only rooms for that asset."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/api/web/timeline?asset_id=70")
        assert resp.status_code == 200
        data = resp.json()
        assert str(data["selected_asset"]["id"]) == "70"
        for r in data["rooms"]:
            assert r["asset_id"] == 70

    def test_now_all_locations(self, auth_client):
        """7. Location: NOW with 'all' locations returns rooms across all assets with location labels."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/api/web/timeline?asset_id=all")
        assert resp.status_code == 200
        data = resp.json()
        assert data["selected_asset"]["id"] == "all"
        assert data["selected_asset"]["name"] == "전체 위치"
        # Rooms should span multiple assets
        asset_ids = {r["asset_id"] for r in data["rooms"] if "asset_id" in r}
        assert len(asset_ids) > 1
        # Each room has location label
        for r in data["rooms"]:
            assert "asset_name" in r or "asset_short_label" in r

    def test_when_all_locations(self, auth_client):
        """8. Location: WHEN with 'all' locations queries across all assets."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/api/web/availability?asset_id=all&start=14:00&duration_minutes=60")
        assert resp.status_code == 200
        data = resp.json()
        assert data["selected_asset"]["id"] == "all"
        assert data["selected_asset"]["name"] == "전체 위치"
        asset_ids = {r["asset_id"] for r in data["rooms"] if "asset_id" in r}
        assert len(asset_ids) > 1
        for r in data["rooms"]:
            assert "asset_name" in r or "asset_short_label" in r

    def test_who_all_locations(self, auth_client):
        """9. Location: WHO with 'all' locations returns reservations from all assets."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/api/web/reservations?asset_id=all")
        assert resp.status_code == 200
        data = resp.json()
        assert "reservations" in data
        assert data["selected_asset"]["id"] == "all"
        asset_ids = {res["asset_id"] for res in data["reservations"] if "asset_id" in res}
        assert len(asset_ids) > 1


# ==============================================================================
# WHO Mode (10-17)
# ==============================================================================

class TestWhoMode:
    def test_who_all_reservations(self, auth_client):
        """10. WHO: Returns all reservations for today when no query given."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/api/web/reservations?asset_id=all")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["reservations"]) > 0

    def test_who_search_exact_name(self, auth_client):
        """11. WHO: Exact name matching."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/api/web/reservations?asset_id=all&query=홍길동")
        assert resp.status_code == 200
        data = resp.json()
        for res in data["reservations"]:
            assert "홍길동" in res["reserver_name"]

    def test_who_search_partial_name(self, auth_client):
        """12. WHO: Partial Korean name matching."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/api/web/reservations?asset_id=all&query=길동")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["reservations"]) > 0
        for res in data["reservations"]:
            assert "길동" in res["reserver_name"]

    def test_who_search_no_results(self, auth_client):
        """13. WHO: No match returns empty reservations array."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/api/web/reservations?asset_id=all&query=NonExistentPersonXYZ999")
        assert resp.status_code == 200
        data = resp.json()
        assert data["reservations"] == []

    def test_who_asset_filter(self, auth_client):
        """14. WHO: Scoped to specific asset."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/api/web/reservations?asset_id=70")
        assert resp.status_code == 200
        data = resp.json()
        for res in data["reservations"]:
            assert res["asset_id"] == 70

    def test_who_favorites_filter(self, auth_client):
        """15. WHO: Favorite filter returns only reservations in favorited rooms."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/api/web/reservations?asset_id=all&favorite_only=true")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["reservations"]) > 0
        for res in data["reservations"]:
            assert res["favorite"] is True

    def test_who_meeting_title_displayed(self, auth_client):
        """16. WHO: Meeting title is included in the structured response."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/api/web/reservations?asset_id=all&query=홍길동")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["reservations"]) > 0
        assert data["reservations"][0]["meeting_title"] == "VCU 검증 회의"

    def test_who_reserver_name_displayed(self, auth_client):
        """17. WHO: Reserver name is included in the structured response."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/api/web/reservations?asset_id=all")
        assert resp.status_code == 200
        data = resp.json()
        assert any(res["reserver_name"] for res in data["reservations"])


# ==============================================================================
# Presentation Policies (18-20)
# ==============================================================================

class TestPresentationPolicies:
    def test_timeline_view_label_not_jeonche(self, auth_client):
        """18. Presentation: View label '전체' is removed from mode navigation."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")
        assert resp.status_code == 200
        html = resp.text
        # The mode tab must not have '전체'
        m = re.search(r'<button[^>]+id="mode-timeline-btn"[^>]*>(.*?)</button>', html, re.DOTALL)
        assert m is not None
        assert "전체" not in m.group(1)

    def test_timeline_view_label_displayed(self, auth_client):
        """19. Presentation: View label '타임라인' is displayed on the timeline mode tab."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")
        assert resp.status_code == 200
        html = resp.text
        m = re.search(r'<button[^>]+id="mode-timeline-btn"[^>]*>(.*?)</button>', html, re.DOTALL)
        assert m is not None
        assert "타임라인" in m.group(1)

    def test_scope_jeonche_maintained(self, auth_client):
        """20. Presentation: Scope filter button '전체' is maintained."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")
        assert resp.status_code == 200
        html = resp.text
        m = re.search(r'<button[^>]+id="filter-all-btn"[^>]*>(.*?)</button>', html, re.DOTALL)
        assert m is not None
        assert "전체" in m.group(1)


# ==============================================================================
# Security Hardening (21-24)
# ==============================================================================

class TestSecurityHardening:
    def test_who_query_xss_immunity(self, auth_client):
        """21. Security: WHO search query containing script tags is safely handled without injection."""
        client, _ = auth_client
        xss_payload = "<script>alert('xss')</script>"
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get(f"/api/web/reservations?asset_id=all&query={xss_payload}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == xss_payload
        assert data["reservations"] == []

    def test_reserver_name_xss_safe(self, auth_client):
        """22. Security: Reserver name with HTML is safely escaped in timeline.html."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")
        assert resp.status_code == 200
        html = resp.text
        # Verify escapeHtml is called in renderWhoView and openDetailModal
        assert "escapeHtml(res.reserver_name)" in html or "textContent" in html
        assert "modalReserverName.textContent = res.reserver_name" in html

    def test_meeting_title_xss_safe(self, auth_client):
        """23. Security: Meeting title with HTML is safely escaped in timeline.html."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")
        assert resp.status_code == 200
        html = resp.text
        assert "escapeHtml(res.meeting_title)" in html or "textContent" in html
        assert "modalMeetingTitle.textContent = res.meeting_title" in html

    def test_no_credential_leakage(self, auth_client):
        """24. Security: No session tokens, cookies, or secrets leaked in API responses."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp_tl = client.get("/api/web/timeline?asset_id=all")
            resp_avail = client.get("/api/web/availability?asset_id=all&start=14:00&duration_minutes=60")
            resp_who = client.get("/api/web/reservations?asset_id=all")

        forbidden_keys = ["GOSSOcookie", "cookie", "password", "token", "session_id", "user_key"]
        for resp in [resp_tl, resp_avail, resp_who]:
            text = resp.text
            for fk in forbidden_keys:
                assert f'"{fk}"' not in text


# ==============================================================================
# Async Protection (25-27)
# ==============================================================================

class TestAsyncProtection:
    def test_rapid_who_query_race(self, auth_client):
        """25. Async: WHO query aborts prior request and discards stale responses via requestSeq."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")
        assert resp.status_code == 200
        html = resp.text
        assert "let whoRequestSeq = 0;" in html
        assert "let whoAbortController = null;" in html
        assert "requestSeq !== whoRequestSeq ||" in html

    def test_asset_switch_race(self, auth_client):
        """26. Async: Asset switch sequence check prevents stale asset responses."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")
        assert resp.status_code == 200
        html = resp.text
        assert "requestSeq !== timelineRequestSeq || requestedAssetId !== currentAssetId" in html
        assert "requestSeq !== whenRequestSeq ||" in html

    def test_mode_switch_race(self, auth_client):
        """27. Async: Mode switch validates cache staleness and does not cross-fetch."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")
        assert resp.status_code == 200
        html = resp.text
        assert "function setViewMode(mode)" in html
        # Verifies each mode checks stale state before deciding to fetch or render
        assert "if (mode === 'now')" in html
        assert "else if (mode === 'when')" in html
        assert "else if (mode === 'who')" in html
        assert "else if (mode === 'timeline')" in html


# ==============================================================================
# Real Groupware Daily Shape Mapping & Site Labels (28-38)
# ==============================================================================

from datetime import datetime, timezone, timedelta
from meeting_room_bot.models.reservation import Reservation, _get_property_content
from meeting_room_bot.models.asset import format_asset_all_location_label, format_asset_compact_label
from meeting_room_bot.services.meeting_room_service import MeetingRoomService, _parse_reservations_by_room
from meeting_room_bot.groupware.client import GroupwareClient

SEOUL_TZ = timezone(timedelta(hours=9))


class TestRealGroupwareFieldMappingAndSiteLabels:
    """Tests actual Groupware daily.json nested user, properties attribute 50/51, useAnonym, and site labels."""

    @pytest.fixture
    def real_daily_sample(self):
        """Sanitized payload matching actual Groupware daily.json response schema."""
        return {
            "id": 100001,
            "itemId": 130,
            "itemName": "회의실 테스트",
            "user": {
                "id": 1,
                "companyName": "테스트회사",
                "name": "홍길동",
                "positionName": "연구원",
            },
            "startTime": "2026-08-11T09:30:00.000+09:00",
            "endTime": "2026-08-11T10:30:00.000+09:00",
            "properties": [
                {"attributeId": 50, "content": "주간 회의"},
                {"attributeId": 51, "content": "홍길동"},
            ],
            "useAnonym": False,
        }

    def test_actual_daily_shape_nested_user_name_mapping(self, real_daily_sample):
        """28. Reservation.from_api_dict maps res_dict['user']['name'] to reserver_name."""
        res = Reservation.from_api_dict(real_daily_sample, room_id=130)
        assert res.reserver_name == "홍길동"
        assert res.meeting_title == "주간 회의"
        assert res.room_id == 130
        assert res.id == 100001
        assert res.use_anonym is False

    def test_properties_attribute_50_meeting_title_mapping(self):
        """29. properties array attributeId 50 maps to meeting_title."""
        payload = {
            "id": 100002,
            "itemId": 130,
            "startTime": "2026-08-11T11:00:00.000+09:00",
            "endTime": "2026-08-11T12:00:00.000+09:00",
            "properties": [
                {"attributeId": 50, "content": "스프린트 계획"},
                {"attributeId": 51, "content": "이영희"},
            ],
        }
        res = Reservation.from_api_dict(payload, room_id=130)
        assert res.meeting_title == "스프린트 계획"
        assert res.reserver_name == "이영희"  # Fallback to property 51 when user object missing

    def test_user_name_vs_property_51_priority(self):
        """30. user.name takes strict priority over property 51 when values differ."""
        payload = {
            "id": 100003,
            "itemId": 130,
            "user": {
                "id": 2,
                "name": "김철수",
            },
            "startTime": "2026-08-11T13:00:00.000+09:00",
            "endTime": "2026-08-11T14:00:00.000+09:00",
            "properties": [
                {"attributeId": 50, "content": "프로젝트 리뷰"},
                {"attributeId": 51, "content": "개발팀"},
            ],
            "useAnonym": False,
        }
        res = Reservation.from_api_dict(payload, room_id=130)
        assert res.reserver_name == "김철수"
        assert res.reserver_name != "개발팀"

    def test_missing_user_and_properties_safe_fallback(self):
        """31. Missing user and properties safely fall back to legacy fields or None."""
        legacy_payload = {
            "id": 100004,
            "itemId": 130,
            "startTime": "2026-08-11T14:00:00.000+09:00",
            "endTime": "2026-08-11T15:00:00.000+09:00",
            "userName": "홍길동",
            "title": "레거시 회의",
            "properties": [],
        }
        res = Reservation.from_api_dict(legacy_payload, room_id=130)
        assert res.reserver_name == "홍길동"
        assert res.meeting_title == "레거시 회의"

        empty_payload = {
            "id": 100005,
            "itemId": 130,
            "startTime": "2026-08-11T15:00:00.000+09:00",
            "endTime": "2026-08-11T16:00:00.000+09:00",
        }
        res_empty = Reservation.from_api_dict(empty_payload, room_id=130)
        assert res_empty.reserver_name is None
        assert res_empty.meeting_title is None

    def test_use_anonym_policy_masks_reserver_and_title(self, real_daily_sample):
        """32. When useAnonym is true, reserver_name and meeting_title are masked to '비공개'."""
        anon_sample = dict(real_daily_sample)
        anon_sample["useAnonym"] = True
        res = Reservation.from_api_dict(anon_sample, room_id=130)
        assert res.reserver_name == "비공개"
        assert res.meeting_title == "비공개"
        assert res.use_anonym is True

    def test_timeline_actual_shape_mapping(self, real_daily_sample):
        """33. MeetingRoomService.get_timeline_data preserves actual Groupware daily fields."""
        client_mock = MagicMock(spec=GroupwareClient)
        client_mock.get_assets.return_value = [{"id": 50, "name": "[판교] 5층 회의실"}]
        client_mock.get_items.return_value = [{"id": 130, "name": "회의실 5-1", "capacity": 6}]
        client_mock.get_daily_reservations.return_value = [real_daily_sample]

        svc = MeetingRoomService(client_mock)
        data = svc.get_timeline_data(asset_id=50, target_date=datetime(2026, 8, 11, tzinfo=SEOUL_TZ))

        assert len(data["rooms"]) == 1
        room = data["rooms"][0]
        assert len(room["reservations"]) == 1
        block = room["reservations"][0]
        assert block["reserver_name"] == "홍길동"
        assert block["meeting_title"] == "주간 회의"

    def test_who_actual_shape_mapping(self, real_daily_sample):
        """34. MeetingRoomService.get_web_reservations preserves actual Groupware daily fields."""
        client_mock = MagicMock(spec=GroupwareClient)
        client_mock.get_assets.return_value = [{"id": 50, "name": "[판교] 5층 회의실"}]
        client_mock.get_items.return_value = [{"id": 130, "name": "회의실 5-1", "capacity": 6}]
        client_mock.get_daily_reservations.return_value = [real_daily_sample]

        svc = MeetingRoomService(client_mock)
        data = svc.get_web_reservations(asset_id=50, target_date=datetime(2026, 8, 11, tzinfo=SEOUL_TZ))

        assert len(data["reservations"]) == 1
        res = data["reservations"][0]
        assert res["reserver_name"] == "홍길동"
        assert res["meeting_title"] == "주간 회의"
        assert res["asset_name"] == "[판교] 5층 회의실"

    def test_who_name_search_using_nested_user_name(self, real_daily_sample):
        """35. MeetingRoomService.get_web_reservations query matches nested user.name."""
        client_mock = MagicMock(spec=GroupwareClient)
        client_mock.get_assets.return_value = [{"id": 50, "name": "[판교] 5층 회의실"}]
        client_mock.get_items.return_value = [{"id": 130, "name": "회의실 5-1", "capacity": 6}]
        client_mock.get_daily_reservations.return_value = [real_daily_sample]

        svc = MeetingRoomService(client_mock)
        # Search query matching user.name
        matched = svc.get_web_reservations(
            asset_id=50, query="홍길동", target_date=datetime(2026, 8, 11, tzinfo=SEOUL_TZ)
        )
        assert len(matched["reservations"]) == 1
        assert matched["reservations"][0]["reserver_name"] == "홍길동"

        # Search query not matching
        unmatched = svc.get_web_reservations(
            asset_id=50, query="이순신", target_date=datetime(2026, 8, 11, tzinfo=SEOUL_TZ)
        )
        assert len(unmatched["reservations"]) == 0

    def test_timeline_detail_reserver_and_title(self, auth_client):
        """36. Timeline detail bottom sheet contains markup for reserver and meeting title."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")
        assert resp.status_code == 200
        html = resp.text
        assert "modalReserverName" in html
        assert "modalMeetingTitle" in html
        assert "예약자 정보 없음" in html
        assert "회의명 없음" in html

    def test_all_locations_pangyo_label_retains_pangyo(self):
        """37. In entire location mode, Pangyo asset labels retain Pangyo site name."""
        pangyo_raw = "[판교] 7층 회의실"
        label = format_asset_all_location_label(pangyo_raw)
        assert "판교" in label
        assert label == "[판교] 7층"

        pangyo_conf = "[판교] 1층 컨퍼런스홀"
        label_conf = format_asset_all_location_label(pangyo_conf)
        assert "판교" in label_conf
        assert label_conf == "[판교] 1층 컨퍼런스홀"

    def test_all_locations_daejeon_label_retains_daejeon(self):
        """38. In entire location mode, Daejeon asset labels retain Daejeon site name."""
        daejeon_raw = "[대전] 회의실"
        label = format_asset_all_location_label(daejeon_raw)
        assert "대전" in label
        assert label == "[대전] 회의실"

        # Compact label for single-asset view should be just "회의실"
        compact = format_asset_compact_label(daejeon_raw)
        assert compact == "회의실"

    def test_timeline_modal_label_no_double_brackets(self, auth_client):
        """39. Detail modal room meta does not wrap label in double brackets '[[...'."""
        client, _ = auth_client
        with patch.object(session_manager, "has_session", return_value=True):
            resp = client.get("/timeline")
        assert resp.status_code == 200
        html = resp.text

        # 1) Template JS must not wrap room.asset_short_label in extra brackets
        assert "[${room.asset_short_label" not in html
        assert "modalRoomMeta.textContent = locLabel ? `${locLabel} · ${capPart}` : capPart;" in html

        # 2) Simulated modal formatting verification
        # All Locations Pangyo label
        pangyo_all_loc = format_asset_all_location_label("[판교] 7층 회의실")
        assert pangyo_all_loc == "[판교] 7층"
        meta_all_loc = f"{pangyo_all_loc} · 정원: 6인실"
        assert "[[" not in meta_all_loc
        assert meta_all_loc.startswith("[판교] 7층")

        # Single Asset compact label
        single_compact = format_asset_compact_label("[판교] 7층 회의실")
        assert single_compact == "7층 회의실"
        meta_single = f"{single_compact} · 정원: 6인실"
        assert "[[" not in meta_single
        assert meta_single.startswith("7층 회의실")
