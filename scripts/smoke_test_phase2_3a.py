"""Smoke test script for Phase 2.3A Meeting Room Web App v1.

Verifies the end-to-end user flow:
1. One-time Link Token generation
2. Token exchange (GET /link/{token} -> 303 to /link/login with LinkSession cookie)
3. Login form rendering (GET /link/login with CSRF token)
4. Authentication & WebSession issuance (POST /link/login -> 303 to /timeline)
5. Web App rendering (GET /timeline -> 200 with HTML, initial JSON, floor dropdown)
6. Web API query (GET /api/web/timeline -> 200 JSON with rooms & reservations)
7. Dynamic floor switching (GET /api/web/timeline?asset_id=80 -> 200 JSON for 8th floor)
8. Unauthorized boundary check (GET /timeline without cookie -> 401)
9. Logout termination (POST /logout -> 303, session destroyed)
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Setup path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fastapi.testclient import TestClient
from meeting_room_bot.account_link.app import app
from meeting_room_bot.account_link.session_store import (
    LINK_SESSION_COOKIE_NAME,
    WEB_SESSION_COOKIE_NAME,
    link_session_store,
    web_session_store,
)
from meeting_room_bot.account_link.token_service import token_service
from meeting_room_bot.auth.session_manager import session_manager
from meeting_room_bot.groupware.client import GroupwareClient
from meeting_room_bot.models.user_key import UserKey


def run_smoke_test():
    print("=" * 60)
    print("  SureMeetingRoom Bot - Phase 2.3A Web App Smoke Test")
    print("=" * 60)

    client = TestClient(app)
    user_key = UserKey("telegram", "smoke_test_user")

    # Step 1: Generate one-time security token
    token = token_service.create_token(user_key)
    print(f"\n[1] Generated one-time link token: {token[:8]}...")

    # Step 2: Token exchange
    resp_exchange = client.get(f"/link/{token}", follow_redirects=False)
    assert resp_exchange.status_code == 303, f"Expected 303, got {resp_exchange.status_code}"
    assert resp_exchange.headers["location"] == "/link/login"
    link_cookie = resp_exchange.cookies.get(LINK_SESSION_COOKIE_NAME)
    assert link_cookie, "LinkSession cookie missing!"
    print(f"[2] Token exchange successful -> 303 to /link/login (LinkSession set)")

    # Step 3: GET /link/login to obtain CSRF token
    client.cookies.set(LINK_SESSION_COOKIE_NAME, link_cookie, path="/link")
    resp_login_page = client.get("/link/login")
    assert resp_login_page.status_code == 200
    import re
    csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', resp_login_page.text)
    assert csrf_match, "CSRF token not found in login form HTML"
    csrf_token = csrf_match.group(1)
    print(f"[3] GET /link/login returned 200 (CSRF token: {csrf_token[:8]}...)")

    # Step 4: POST /link/login to authenticate
    # Mock GroupwareClient.login to succeed in mock environment
    original_login = GroupwareClient.login

    def mock_login(self, username, password):
        self._is_authenticated = True
        return True

    GroupwareClient.login = mock_login
    try:
        resp_auth = client.post(
            "/link/login",
            data={
                "username": "tester",
                "password": "valid_password",
                "csrf_token": csrf_token,
            },
            follow_redirects=False,
        )
        assert resp_auth.status_code == 303, f"Expected 303, got {resp_auth.status_code}"
        assert resp_auth.headers["location"] == "/timeline"
        web_cookie = resp_auth.cookies.get(WEB_SESSION_COOKIE_NAME)
        assert web_cookie, "WebSession cookie missing after login!"
        print(f"[4] POST /link/login successful -> 303 to /timeline (WebSession issued)")
    finally:
        GroupwareClient.login = original_login

    # Step 5: GET /timeline with WebSession
    client.cookies.set(WEB_SESSION_COOKIE_NAME, web_cookie, path="/")
    resp_timeline = client.get("/timeline")
    assert resp_timeline.status_code == 200, f"Expected 200, got {resp_timeline.status_code}"
    assert "회의실 시간표" in resp_timeline.text
    assert "Timeline UI는 다음 단계에서 제공됩니다" not in resp_timeline.text
    assert "<script id=\"initial-timeline-data\"" in resp_timeline.text
    assert "<script id=\"initial-error-data\"" in resp_timeline.text
    print(f"[5] GET /timeline rendered 200 OK (HTML + Safe Initial Bootstrap JSON)")

    # Step 6: GET /api/web/timeline JSON endpoint
    resp_api = client.get("/api/web/timeline")
    assert resp_api.status_code == 200, f"Expected 200, got {resp_api.status_code}"
    api_data = resp_api.json()
    assert "rooms" in api_data
    assert "assets" in api_data
    assert len(api_data["rooms"]) > 0
    print(f"[6] GET /api/web/timeline returned 200 JSON ({len(api_data['rooms'])} rooms loaded)")

    # Step 7: Dynamic floor switching via API
    resp_switch = client.get("/api/web/timeline?asset_id=80")
    assert resp_switch.status_code == 200
    switch_data = resp_switch.json()
    assert switch_data["selected_asset"]["id"] == 80
    print(f"[7] GET /api/web/timeline?asset_id=80 switched floor successfully (Asset: {switch_data['selected_asset']['name']})")

    # Step 8: Unauthorized boundary check
    unauth_client = TestClient(app)
    resp_unauth = unauth_client.get("/timeline")
    assert resp_unauth.status_code == 401
    print(f"[8] Unauthorized access rejected with 401 correctly")

    # Step 9: POST /logout
    resp_logout = client.post("/logout", follow_redirects=False)
    assert resp_logout.status_code == 303
    assert not session_manager.has_session(user_key)
    print(f"[9] POST /logout terminated session cleanly")

    # Step 10: XSS Security Smoke Check (Malicious reservation title & room name)
    import json
    from unittest.mock import patch
    from meeting_room_bot.providers.base import QueryResult, QueryStatus

    xss_user = UserKey("telegram", "smoke_xss_user")
    xss_session = web_session_store.create_web_session(xss_user)
    gw_xss = GroupwareClient()
    gw_xss._is_authenticated = True
    gw_xss._cookies = {"JSESSIONID": "mock"}
    session_manager.set_client(xss_user, gw_xss)
    client.cookies.set(WEB_SESSION_COOKIE_NAME, xss_session.session_id, path="/")

    malicious_room = "회의실 </script><script>window.SMOKE_XSS=1</script>"
    malicious_title = "</script><script>window.TITLE_XSS=1</script>"
    mock_payload = {
        "rooms": [{
            "id": 999,
            "name": malicious_room,
            "reservations": [{
                "id": 1,
                "room_name": malicious_room,
                "meeting_title": malicious_title,
                "reserver_name": "<img src=x onerror=alert(1)>",
                "start_time": "10:00",
                "end_time": "11:00",
                "left_percent": 16.67,
                "width_percent": 8.33,
            }],
        }]
    }
    mock_xss_provider = MagicMock()
    mock_xss_provider.get_timeline.return_value = QueryResult(status=QueryStatus.SUCCESS, data=mock_payload)

    with patch("meeting_room_bot.account_link.app.get_provider", return_value=mock_xss_provider):
        resp_xss = client.get("/timeline")
        assert resp_xss.status_code == 200
        # Executable tags MUST NOT be injected into HTML
        assert "<script>window.SMOKE_XSS=1</script>" not in resp_xss.text
        assert "<script>window.TITLE_XSS=1</script>" not in resp_xss.text
        # Initial script element must not be prematurely broken
        json_match = re.search(r'<script id="initial-timeline-data"[^>]*>(.*?)</script>', resp_xss.text, re.DOTALL)
        assert json_match, "Initial timeline script not found"
        raw_json = json_match.group(1).strip()
        assert "</script>" not in raw_json, "Literal </script> found inside bootstrap script"
        parsed = json.loads(raw_json)
        assert parsed["rooms"][0]["name"] == malicious_room
        assert parsed["rooms"][0]["reservations"][0]["meeting_title"] == malicious_title
    print(f"[10] XSS injection smoke check passed (Malicious tags safely escaped in JSON bootstrap)")

    print("\n" + "=" * 60)
    print("  ALL 10 SMOKE TEST STEPS PASSED SUCCESSFULLY! (PASS)")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_smoke_test()
