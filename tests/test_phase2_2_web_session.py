"""Tests for Phase 2.2: Secure Account Linking & Web Session Foundation.

Covers:
1. One-time Token Exchange & Immediate URL Token Clearance (303 to /link/login)
2. Token consume & reuse rejection
3. LinkSession cookie generation, attributes, and path isolation
4. GET /link/login CSRF token injection and cookie verification
5. POST /link/login CSRF enforcement (invalid CSRF -> 403, 0 Groupware calls)
6. Credential hygiene (passwords never stored in session, store, or logged)
7. Successful login flow -> session_manager registration, WebSession creation, 303 /timeline
8. Failed login flow -> 400 error page, LinkSession consumed, guidance displayed
9. Protected /timeline verification:
   - Rejection without WebSession (401)
   - Rejection when WebSession exists but GroupwareClient session is missing (401, auto-cleans cookie)
   - Success when both WebSession and Groupware session are active (200 placeholder)
10. POST /logout termination:
   - Clears WebSession
   - Clears Groupware session in session_manager
   - Deletes WebSession cookie
11. Cookie Secure flag compliance (Local HTTP Secure=False, Production HTTPS Secure=True)
12. LinkSession and WebSession TTL expiration
"""

import concurrent.futures
from datetime import datetime, timedelta, timezone
import logging
import os
import re
import time
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from meeting_room_bot.account_link.app import app
from meeting_room_bot.account_link.session_store import (
    LINK_SESSION_COOKIE_NAME,
    WEB_SESSION_COOKIE_NAME,
    LinkSession,
    WebSession,
    link_session_store,
    web_session_store,
)
from meeting_room_bot.account_link.token_service import token_service
from meeting_room_bot.auth.session_manager import session_manager
from meeting_room_bot.config import get_config
from meeting_room_bot.groupware.client import GroupwareClient
from meeting_room_bot.models.user_key import UserKey


@pytest.fixture(autouse=True)
def clean_sessions_and_tokens():
    """Ensure clean stores before and after each test."""
    link_session_store.clear()
    web_session_store.clear()
    session_manager.clear_all_sessions()
    token_service._tokens.clear()
    yield
    link_session_store.clear()
    web_session_store.clear()
    session_manager.clear_all_sessions()
    token_service._tokens.clear()


class TestTokenExchangeAndLinkSession:
    def test_get_link_token_consumes_token_and_redirects_303(self):
        """GET /link/{token} immediately consumes token and redirects 303 to /link/login with cookie."""
        client = TestClient(app)
        user_key = UserKey("telegram", "exchange_user_1")
        tok = token_service.create_token(user_key)
        assert tok in token_service._tokens

        # Call with follow_redirects=False to verify 303 contract
        resp = client.get(f"/link/{tok}", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/link/login"

        # 1. Token must be consumed immediately upon GET
        assert tok not in token_service._tokens
        assert token_service.consume_token(tok) is None

        # 2. Cookie must be set
        set_cookie = resp.headers.get("set-cookie", "")
        assert LINK_SESSION_COOKIE_NAME in set_cookie
        assert "Path=/link" in set_cookie
        assert "HttpOnly" in set_cookie
        assert "SameSite=lax" in set_cookie

    def test_reusing_consumed_token_fails(self):
        """Once token is consumed on initial GET, subsequent GET /link/{token} fails with 400."""
        client = TestClient(app)
        user_key = UserKey("telegram", "reuse_user")
        tok = token_service.create_token(user_key)

        # First exchange succeeds
        resp1 = client.get(f"/link/{tok}", follow_redirects=False)
        assert resp1.status_code == 303

        # Second attempt with same token fails
        resp2 = client.get(f"/link/{tok}", follow_redirects=False)
        assert resp2.status_code == 400
        assert "유효하지 않거나 이미 만료된 계정 연결 링크입니다" in resp2.text

    def test_post_link_token_legacy_route_rejected_with_zero_login_calls(self):
        """Direct POST /link/{token} is completely removed and rejected with 405 (0 Groupware calls)."""
        client = TestClient(app)
        user_key = UserKey("telegram", "legacy_forbidden_user")
        tok = token_service.create_token(user_key)

        with patch.object(GroupwareClient, "login", autospec=True) as mock_login:
            resp = client.post(
                f"/link/{tok}",
                data={"username": "user", "password": "password"},
                follow_redirects=False,
            )

            # FastAPI returns 405 Method Not Allowed because only GET is routed on /link/{token}
            assert resp.status_code in (404, 405)
            # GroupwareClient.login must NEVER be called
            assert mock_login.call_count == 0

    def test_redirect_followed_clears_token_from_browser_url(self):
        """When following redirect, browser arrives at /link/login with 200 and zero token in URL."""
        client = TestClient(app)
        user_key = UserKey("telegram", "url_clean_user")
        tok = token_service.create_token(user_key)

        # Default TestClient follows redirects
        resp = client.get(f"/link/{tok}")
        assert resp.status_code == 200
        assert resp.url.path == "/link/login"
        assert tok not in str(resp.url)


class TestLoginSessionAndCSRF:
    def test_get_login_without_cookie_rejected(self):
        """Direct GET /link/login without LinkSession cookie returns 400."""
        client = TestClient(app)
        resp = client.get("/link/login")
        assert resp.status_code == 400
        assert "계정 연결 세션이 유효하지 않거나 만료되었습니다" in resp.text

    def test_get_login_with_valid_cookie_injects_csrf_token(self):
        """GET /link/login with valid LinkSession renders form with hidden csrf_token."""
        client = TestClient(app)
        user_key = UserKey("telegram", "csrf_form_user")
        session = link_session_store.create_link_session(user_key)

        client.cookies.set(LINK_SESSION_COOKIE_NAME, session.session_id, path="/link")
        resp = client.get("/link/login")
        assert resp.status_code == 200
        assert f'name="csrf_token" value="{session.csrf_token}"' in resp.text
        assert 'action="/link/login"' in resp.text

    def test_post_login_invalid_csrf_returns_403_and_calls_zero_groupware(self):
        """POST /link/login with mismatched/missing CSRF returns 403 and never invokes Groupware login."""
        client = TestClient(app)
        user_key = UserKey("telegram", "csrf_fail_user")
        session = link_session_store.create_link_session(user_key)
        client.cookies.set(LINK_SESSION_COOKIE_NAME, session.session_id, path="/link")

        with patch.object(GroupwareClient, "login", return_value=True) as mock_login:
            # 1. Missing CSRF
            resp_missing = client.post("/link/login", data={"username": "u", "password": "p", "csrf_token": ""})
            assert resp_missing.status_code == 403
            assert mock_login.call_count == 0

            # 2. Tampered CSRF
            resp_tampered = client.post("/link/login", data={"username": "u", "password": "p", "csrf_token": "tampered_token_xyz"})
            assert resp_tampered.status_code == 403
            assert mock_login.call_count == 0


class TestLoginExecutionAndWebSession:
    def test_login_success_creates_web_session_and_redirects_to_timeline(self):
        """Successful login registers session_manager, creates WebSession, and 303 redirects to /timeline."""
        client = TestClient(app)
        user_key = UserKey("telegram", "login_ok_user")
        session = link_session_store.create_link_session(user_key)
        client.cookies.set(LINK_SESSION_COOKIE_NAME, session.session_id, path="/link")

        def mock_login(self, username, password):
            self._is_authenticated = True
            return True

        with patch.object(GroupwareClient, "login", side_effect=mock_login, autospec=True):
            resp = client.post(
                "/link/login",
                data={"username": "emp_101", "password": "valid_password", "csrf_token": session.csrf_token},
                follow_redirects=False,
            )

        assert resp.status_code == 303
        assert resp.headers["location"] == "/timeline"

        # 1. Groupware session registered in session_manager
        assert session_manager.has_session(user_key) is True

        # 2. LinkSession consumed
        assert link_session_store.get_link_session(session.session_id) is None

        # 3. WebSession created and returned in cookie
        set_cookie = resp.headers.get("set-cookie", "")
        assert WEB_SESSION_COOKIE_NAME in set_cookie
        assert "Path=/" in set_cookie
        assert "HttpOnly" in set_cookie

    def test_login_failure_consumes_link_session_and_renders_error(self):
        """Failed credentials consumes LinkSession, deletes cookie, and renders error guidance."""
        client = TestClient(app)
        user_key = UserKey("telegram", "login_fail_user")
        session = link_session_store.create_link_session(user_key)
        client.cookies.set(LINK_SESSION_COOKIE_NAME, session.session_id, path="/link")

        with patch.object(GroupwareClient, "login", return_value=False):
            resp = client.post(
                "/link/login",
                data={"username": "emp_101", "password": "wrong_password", "csrf_token": session.csrf_token},
                follow_redirects=False,
            )

        assert resp.status_code == 400
        assert "로그인에 실패했습니다" in resp.text
        # LinkSession is consumed so it cannot be retried
        assert link_session_store.get_link_session(session.session_id) is None
        assert session_manager.has_session(user_key) is False

    def test_passwords_not_stored_in_sessions_or_stores(self):
        """Verify plain passwords never leak into LinkSession, WebSession, or memory store structures."""
        client = TestClient(app)
        user_key = UserKey("telegram", "secret_guard_user")
        session = link_session_store.create_link_session(user_key)
        client.cookies.set(LINK_SESSION_COOKIE_NAME, session.session_id, path="/link")
        secret_pw = "TOP_SECRET_PASS_9988!"

        with patch.object(GroupwareClient, "login", return_value=True):
            client.post(
                "/link/login",
                data={"username": "emp_102", "password": secret_pw, "csrf_token": session.csrf_token},
                follow_redirects=False,
            )

        # Check LinkSessionStore and WebSessionStore
        for _, ls in link_session_store._sessions.items():
            assert secret_pw not in str(ls)
        for _, ws in web_session_store._sessions.items():
            assert secret_pw not in str(ws)

    def test_concurrent_replay_prevention_single_winner(self):
        """Simultaneous POST /link/login with identical cookie & CSRF yields exactly 1 success and 1 rejection."""
        user_key = UserKey("telegram", "concurrent_replay_user")
        session = link_session_store.create_link_session(user_key)

        login_calls = []

        def mock_login_with_delay(self, username, password):
            login_calls.append(1)
            time.sleep(0.05)  # simulate Groupware network delay
            self._is_authenticated = True
            return True

        def submit_login():
            c = TestClient(app)
            return c.post(
                "/link/login",
                data={"username": "emp_conc", "password": "conc_password", "csrf_token": session.csrf_token},
                cookies={LINK_SESSION_COOKIE_NAME: session.session_id},
                follow_redirects=False,
            )

        with patch.object(GroupwareClient, "login", side_effect=mock_login_with_delay, autospec=True):
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                f1 = executor.submit(submit_login)
                f2 = executor.submit(submit_login)
                res1 = f1.result()
                res2 = f2.result()

        status_codes = sorted([res1.status_code, res2.status_code])
        # Exactly one 303 (success) and one 400 (replay rejection)
        assert status_codes == [303, 400], f"Expected [303, 400] but got {status_codes}"

        # GroupwareClient.login must be called EXACTLY ONCE
        assert len(login_calls) == 1, f"GroupwareClient.login called {len(login_calls)} times! Expected exactly 1."

        # Exactly 1 WebSession created
        assert len(web_session_store._sessions) == 1
        assert session_manager.has_session(user_key) is True

    def test_sensitive_credentials_and_tokens_not_in_application_logs(self, caplog):
        """Verify plain passwords and one-time tokens never appear in application logs."""
        caplog.set_level(logging.DEBUG)

        client = TestClient(app)
        user_key = UserKey("telegram", "audit_log_user")
        secret_token = token_service.create_token(user_key)
        secret_pw = "VERY_CONFIDENTIAL_PASS_12345!"

        # 1. Token Exchange
        resp_get = client.get(f"/link/{secret_token}", follow_redirects=False)
        assert resp_get.status_code == 303
        link_cookie = resp_get.cookies.get(LINK_SESSION_COOKIE_NAME)

        # 2. Form view
        resp_form = client.get("/link/login", cookies={LINK_SESSION_COOKIE_NAME: link_cookie})
        csrf = re.search(r'name="csrf_token"\s+value="([^"]+)"', resp_form.text).group(1)

        def mock_login(self, username, password):
            self._is_authenticated = True
            return True

        # 3. Post login
        with patch.object(GroupwareClient, "login", side_effect=mock_login, autospec=True):
            resp_post = client.post(
                "/link/login",
                data={"username": "audit_user", "password": secret_pw, "csrf_token": csrf},
                cookies={LINK_SESSION_COOKIE_NAME: link_cookie},
                follow_redirects=False,
            )
            assert resp_post.status_code == 303

        # 4. Timeline view
        web_cookie = resp_post.cookies.get(WEB_SESSION_COOKIE_NAME)
        resp_tl = client.get("/timeline", cookies={WEB_SESSION_COOKIE_NAME: web_cookie})
        assert resp_tl.status_code == 200

        # Verify application log messages specifically (meeting_room_bot package logs)
        app_log_text = "\n".join(
            record.getMessage()
            for record in caplog.records
            if record.name.startswith("meeting_room_bot")
        )
        assert secret_pw not in app_log_text, "Password leaked into application logs!"
        assert secret_token not in app_log_text, "One-time token leaked into application logs!"
        assert link_cookie not in app_log_text, "LinkSession ID leaked into application logs!"
        assert web_cookie not in app_log_text, "WebSession ID leaked into application logs!"


class TestProtectedTimelineEndpoint:
    def test_timeline_without_web_session_returns_401(self):
        """GET /timeline without WebSession cookie returns 401."""
        client = TestClient(app)
        resp = client.get("/timeline")
        assert resp.status_code == 401
        assert "인증되지 않은 접근입니다" in resp.text

    def test_timeline_with_web_session_but_no_groupware_session_returns_401(self):
        """GET /timeline when WebSession exists but server restarted / Groupware lost returns 401."""
        client = TestClient(app)
        user_key = UserKey("telegram", "orphan_user")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        # Groupware session is intentionally NOT in session_manager (e.g. server restart)
        assert session_manager.has_session(user_key) is False

        resp = client.get("/timeline")
        assert resp.status_code == 401
        assert "그룹웨어 세션이 만료되었습니다" in resp.text
        # WebSession is revoked
        assert web_session_store.get_web_session(web_session.session_id) is None

    def test_timeline_with_valid_web_session_and_groupware_returns_200_placeholder(self):
        """GET /timeline with active WebSession and active Groupware session returns 200 placeholder."""
        client = TestClient(app)
        user_key = UserKey("telegram", "timeline_happy_user")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        # Mock authenticated GroupwareClient
        gw_client = GroupwareClient()
        gw_client._is_authenticated = True
        session_manager.set_client(user_key, gw_client)

        resp = client.get("/timeline")
        assert resp.status_code == 200
        assert "회의실 시간표" in resp.text
        assert "계정 연결이 완료되었습니다" in resp.text
        assert "Timeline UI는 다음 단계에서 제공됩니다" in resp.text
        assert "telegram:timeline_happy_user" in resp.text


class TestLogoutFlow:
    def test_post_logout_clears_web_session_and_groupware_session(self):
        """POST /logout deletes WebSession, Groupware session, and clears cookie."""
        client = TestClient(app)
        user_key = UserKey("telegram", "logout_user")
        web_session = web_session_store.create_web_session(user_key)
        client.cookies.set(WEB_SESSION_COOKIE_NAME, web_session.session_id, path="/")

        gw_client = GroupwareClient()
        gw_client._is_authenticated = True
        session_manager.set_client(user_key, gw_client)

        resp = client.post("/logout", follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/link/login"

        # 1. WebSession cleared
        assert web_session_store.get_web_session(web_session.session_id) is None

        # 2. Groupware session removed
        assert session_manager.has_session(user_key) is False

        # 3. Subsequent /timeline call returns 401
        resp_after = client.get("/timeline")
        assert resp_after.status_code == 401


class TestSessionStoreTTLAndSecurity:
    def test_link_session_ttl_expiration(self):
        """LinkSession past TTL is treated as expired and deleted."""
        user_key = UserKey("telegram", "ttl_link_user")
        # 1-second TTL
        session = link_session_store.create_link_session(user_key, ttl_seconds=1)
        assert link_session_store.get_link_session(session.session_id) is not None

        # Artificially expire
        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert link_session_store.get_link_session(session.session_id) is None

    def test_web_session_ttl_expiration(self):
        """WebSession past TTL is treated as expired and deleted."""
        user_key = UserKey("telegram", "ttl_web_user")
        session = web_session_store.create_web_session(user_key, ttl_seconds=1)
        assert web_session_store.get_web_session(session.session_id) is not None

        # Artificially expire
        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert web_session_store.get_web_session(session.session_id) is None

    def test_cookie_secure_flag_local_vs_https(self):
        """Local HTTP -> Secure=False; Production HTTPS -> Secure=True."""
        client = TestClient(app)

        # 1. Local HTTP mode
        with patch.dict(os.environ, {"ACCOUNT_LINK_BASE_URL": "http://localhost:8000"}):
            user_key = UserKey("telegram", "local_user")
            tok = token_service.create_token(user_key)
            resp_local = client.get(f"/link/{tok}", follow_redirects=False)
            set_cookie_local = resp_local.headers.get("set-cookie", "")
            # Secure flag must NOT be set on plain HTTP
            assert "Secure" not in set_cookie_local

        # 2. Production HTTPS mode
        with patch.dict(os.environ, {"ACCOUNT_LINK_BASE_URL": "https://meeting.suresofttech.com"}):
            user_key2 = UserKey("telegram", "prod_user")
            tok2 = token_service.create_token(user_key2)
            resp_prod = client.get(f"/link/{tok2}", follow_redirects=False)
            set_cookie_prod = resp_prod.headers.get("set-cookie", "")
            # Secure flag MUST be set on HTTPS
            assert "Secure" in set_cookie_prod
