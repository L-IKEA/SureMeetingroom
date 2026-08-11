"""Unit tests for GroupwareClient and POC helper functions."""

import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from meeting_room_bot.groupware.client import (
    GroupwareAPIError,
    GroupwareAuthError,
    GroupwareClient,
    GroupwareNetworkError,
)
from login_poc import count_reservations, parse_rooms


class TestGroupwareClient(unittest.TestCase):

    def setUp(self):
        self.client = GroupwareClient("https://gw.suresofttech.com")

    def test_seoul_timezone_date_string(self):
        """Verify get_daily_reservations uses Asia/Seoul 00:00:00 ISO string."""
        with patch.object(self.client, "_request") as mock_req:
            mock_req.return_value = {"code": "200", "data": []}
            self.client.get_daily_reservations(50)

            mock_req.assert_called_once()
            args, kwargs = mock_req.call_args
            params = kwargs.get("params", {})
            from_date = params.get("fromDate", "")

            self.assertTrue(from_date.endswith("T00:00:00.000+09:00"))

    def test_login_success(self):
        """Verify successful login."""
        with patch.object(self.client.session, "request") as mock_request:
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_res.json.return_value = {"code": "200", "message": "OK"}
            mock_request.return_value = mock_res

            self.client.session.cookies.set("GOSSOcookie", "dummy_cookie_value")

            result = self.client.login("testuser", "testpass")
            self.assertTrue(result)
            self.assertTrue(self.client.has_gosso_cookie())

    def test_login_401_raises_auth_error(self):
        """Verify HTTP 401 raises GroupwareAuthError."""
        with patch.object(self.client.session, "request") as mock_request:
            mock_res = MagicMock()
            mock_res.status_code = 401
            mock_res.json.return_value = {"code": "401", "message": "Unauthorized"}
            mock_request.return_value = mock_res

            with self.assertRaises(GroupwareAuthError) as ctx:
                self.client.login("testuser", "wrongpass")
            self.assertIn("Groupware authentication failed", str(ctx.exception))

    def test_parse_rooms(self):
        """Verify extraction of room items from JSON."""
        sample_res = {
            "code": "200",
            "data": [
                {"id": 130, "name": "회의실 5-1(6인 / TV)"},
                {"id": 131, "name": "회의실 5-2(6인 / TV)"},
            ],
        }
        rooms = parse_rooms(sample_res)
        self.assertEqual(len(rooms), 2)
        self.assertEqual(rooms[0], (130, "회의실 5-1(6인 / TV)"))
        self.assertEqual(rooms[1], (131, "회의실 5-2(6인 / TV)"))

    def test_count_reservations(self):
        """Verify reservation count calculation."""
        sample_daily = {
            "code": "200",
            "data": [
                {"id": 130, "reservations": [{"id": 1}, {"id": 2}]},
                {"id": 131, "reservations": [{"id": 3}]},
            ],
        }
        count = count_reservations(sample_daily)
        self.assertEqual(count, 3)


if __name__ == "__main__":
    unittest.main()
