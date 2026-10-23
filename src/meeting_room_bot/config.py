"""Centralized Configuration for SureMeetingRoom Bot."""

from dataclasses import dataclass
import os


@dataclass
class AppConfig:
    """Application configuration loaded from environment variables with sensible defaults."""

    # 1. Telegram & Mode
    telegram_bot_token: str = ""
    telegram_data_mode: str = "mock"

    # 2. Account Link & HTTPS
    account_link_base_url: str = "http://localhost:8000"
    account_link_host: str = "0.0.0.0"
    account_link_port: int = 8000
    account_link_token_ttl: int = 600
    account_link_web_session_ttl_seconds: int = 300
    web_session_ttl_seconds: int = 86400
    link_session_cookie_name: str = "meetingroom_link_session"
    web_session_cookie_name: str = "meetingroom_web_session"

    # 3. Security & Proxy
    forwarded_allow_ips: str = "127.0.0.1"
    rate_limit_login_per_minute: int = 10

    # 4. Groupware
    groupware_base_url: str = "https://gw.suresofttech.com"

    # 5. Data Persistence
    favorites_file_path: str = "data/favorites.json"

    # 6. Web Timeline & Presentation Policy
    timeline_start_hour: int = 8
    timeline_end_hour: int = 20
    show_reserver_name: bool = True
    show_meeting_title: bool = True

    @property
    def is_secure_cookie(self) -> bool:
        """Return True if base URL is HTTPS, ensuring Secure cookie flag in production."""
        return self.account_link_base_url.lower().startswith("https://")

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load configuration from environment variables."""
        return cls(
            telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            telegram_data_mode=os.environ.get("TELEGRAM_DATA_MODE", "mock").strip().lower(),
            account_link_base_url=os.environ.get("ACCOUNT_LINK_BASE_URL", "http://localhost:8000").rstrip("/"),
            account_link_host=os.environ.get("ACCOUNT_LINK_HOST", "0.0.0.0"),
            account_link_port=int(os.environ.get("ACCOUNT_LINK_PORT", "8000")),
            account_link_token_ttl=int(os.environ.get("ACCOUNT_LINK_TOKEN_TTL", "600")),
            account_link_web_session_ttl_seconds=int(os.environ.get("ACCOUNT_LINK_WEB_SESSION_TTL_SECONDS", "300")),
            web_session_ttl_seconds=int(os.environ.get("WEB_SESSION_TTL_SECONDS", "86400")),
            link_session_cookie_name=os.environ.get("LINK_SESSION_COOKIE_NAME", "meetingroom_link_session"),
            web_session_cookie_name=os.environ.get("WEB_SESSION_COOKIE_NAME", "meetingroom_web_session"),
            forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1"),
            rate_limit_login_per_minute=int(os.environ.get("RATE_LIMIT_LOGIN_PER_MINUTE", "10")),
            groupware_base_url=os.environ.get("GROUPWARE_BASE_URL", "https://gw.suresofttech.com").rstrip("/"),
            favorites_file_path=os.environ.get("FAVORITES_FILE_PATH", "data/favorites.json"),
            timeline_start_hour=int(os.environ.get("TIMELINE_START_HOUR", "8")),
            timeline_end_hour=int(os.environ.get("TIMELINE_END_HOUR", "20")),
            show_reserver_name=os.environ.get("SHOW_RESERVER_NAME", "true").strip().lower() in ("true", "1", "yes"),
            show_meeting_title=os.environ.get("SHOW_MEETING_TITLE", "true").strip().lower() in ("true", "1", "yes"),
        )


def get_config() -> AppConfig:
    """Get active configuration loaded from environment."""
    return AppConfig.from_env()
