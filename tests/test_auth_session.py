"""Pytest suite for UserSessionManager, session isolation, and 401 handling."""

import logging
import sys
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.auth.session_manager import UserSessionManager
from meeting_room_bot.groupware.client import GroupwareClient


class TestUserSessionManager:

    def test_user_session_isolation(self):
        """Verify User A and User B sessions are strictly isolated."""
        mgr = UserSessionManager()

        client_a = GroupwareClient()
        client_a._authenticated_user = "user_a"
        client_a._is_authenticated = True

        client_b = GroupwareClient()
        client_b._authenticated_user = "user_b"
        client_b._is_authenticated = True

        mgr.set_client("111", client_a)
        mgr.set_client("222", client_b)

        # 1. Check sessions exist
        assert mgr.has_session("111") is True
        assert mgr.has_session("222") is True

        # 2. Check clients retrieved are different instances
        retrieved_a = mgr.get_client("111")
        retrieved_b = mgr.get_client("222")

        assert retrieved_a is client_a
        assert retrieved_b is client_b
        assert retrieved_a is not retrieved_b
        assert retrieved_a._authenticated_user == "user_a"
        assert retrieved_b._authenticated_user == "user_b"

    def test_removing_user_session_leaves_others_intact(self):
        """Verify removing User A session leaves User B session intact."""
        mgr = UserSessionManager()

        client_a = GroupwareClient()
        client_a._authenticated_user = "user_a"
        client_a._is_authenticated = True

        client_b = GroupwareClient()
        client_b._authenticated_user = "user_b"
        client_b._is_authenticated = True

        mgr.set_client("111", client_a)
        mgr.set_client("222", client_b)

        # Remove User A
        mgr.remove_session("111")

        assert mgr.has_session("111") is False
        assert mgr.get_client("111") is None

        # User B still active
        assert mgr.has_session("222") is True
        assert mgr.get_client("222") is client_b

    def test_non_existent_session_returns_false(self):
        """Verify user without session returns has_session == False and get_client == None."""
        mgr = UserSessionManager()
        assert mgr.has_session("999") is False
        assert mgr.get_client("999") is None

    def test_cookie_secret_not_logged(self, caplog):
        """Verify session cookie secrets are never output to logger."""
        mgr = UserSessionManager()
        client = GroupwareClient()
        client._authenticated_user = "user_secret"
        client.session.cookies.set("SESSION_COOKIE_NAME", "SUPER_SECRET_COOKIE_12345")

        with caplog.at_level(logging.INFO):
            mgr.set_client("111", client)

        # Ensure cookie string value does NOT appear in log records
        assert "SUPER_SECRET_COOKIE_12345" not in caplog.text
