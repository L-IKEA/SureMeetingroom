"""Groupware API Client implementation."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import requests


class GroupwareError(Exception):
    """Base exception for Groupware client errors."""
    pass


class GroupwareAuthError(GroupwareError):
    """Raised when Groupware authentication fails."""
    pass


class GroupwareNetworkError(GroupwareError):
    """Raised when network connection fails."""
    pass


class GroupwareAPIError(GroupwareError):
    """Raised when API returns non-200 status or error payload."""
    pass


class GroupwareClient:
    """HTTP Client for Groupware Meeting Room API using requests.Session."""

    def __init__(self, base_url: str = "https://gw.suresofttech.com"):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
        })

    @property
    def is_authenticated(self) -> bool:
        """Check if GroupwareClient session is authenticated."""
        return len(self.session.cookies) > 0 or getattr(self, "_is_authenticated", False)

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Helper method to send HTTP request and validate response."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, timeout=15, **kwargs)
        except requests.RequestException as e:
            raise GroupwareNetworkError(f"Network error while calling {endpoint}: {e}") from e

        if response.status_code == 401:
            raise GroupwareAuthError("Groupware authentication failed")

        try:
            data = response.json()
        except (ValueError, requests.JSONDecodeError) as e:
            raise GroupwareAPIError(f"Failed to parse JSON response from {endpoint}: {e}") from e

        if response.status_code != 200:
            msg = data.get("message") or f"HTTP {response.status_code}"
            if response.status_code in (401, 403) or str(data.get("code")) == "401":
                raise GroupwareAuthError("Groupware authentication failed")
            raise GroupwareAPIError(f"API Error ({response.status_code}): {msg}")

        # Check JSON payload code field
        code = str(data.get("code")) if data.get("code") is not None else ""
        if code == "401":
            raise GroupwareAuthError("Groupware authentication failed")
        elif code and code != "200":
            msg = data.get("message") or f"API response code {code}"
            raise GroupwareAPIError(f"API Error (code {code}): {msg}")

        return data

    def login(self, username: str, password: str) -> bool:
        """Authenticate with Groupware API.

        POST /api/login
        """
        payload = {
            "username": username,
            "password": password,
            "captcha": "",
            "returnUrl": "",
        }

        data = self._request("POST", "/api/login", json=payload)
        code = str(data.get("code")) if data.get("code") is not None else ""
        success = (code == "200")
        if success:
            self._is_authenticated = True
        return success

    def has_gosso_cookie(self) -> bool:
        """Check if GOSSOcookie exists in session cookies."""
        return "GOSSOcookie" in self.session.cookies

    def get_assets(self) -> Dict[str, Any]:
        """Fetch asset list.

        GET /api/asset
        """
        return self._request("GET", "/api/asset")

    def get_items(self, asset_id: int) -> Dict[str, Any]:
        """Fetch items (e.g. rooms) for a given asset ID.

        GET /api/asset/{asset_id}/item/?page=0&offset=100
        """
        endpoint = f"/api/asset/{asset_id}/item/"
        params = {"page": 0, "offset": 100}
        return self._request("GET", endpoint, params=params)

    def get_daily_reservations(
        self, asset_id: int, date_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch daily reservation status for a given asset ID.

        GET /api/asset/{asset_id}/items/daily
        fromDate parameter format: YYYY-MM-DDT00:00:00.000+09:00
        """
        if not date_str:
            seoul_tz = timezone(timedelta(hours=9))
            now_seoul = datetime.now(seoul_tz)
            date_str = now_seoul.strftime("%Y-%m-%dT00:00:00.000+09:00")

        endpoint = f"/api/asset/{asset_id}/items/daily"
        params = {"fromDate": date_str}
        return self._request("GET", endpoint, params=params)
