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

    # 3. Security & Proxy
    forwarded_allow_ips: str = "127.0.0.1"
    rate_limit_login_per_minute: int = 10

    # 4. Groupware
    groupware_base_url: str = "https://gw.suresofttech.com"

    # 5. Data Persistence
    favorites_file_path: str = "data/favorites.json"

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
            forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1"),
            rate_limit_login_per_minute=int(os.environ.get("RATE_LIMIT_LOGIN_PER_MINUTE", "10")),
            groupware_base_url=os.environ.get("GROUPWARE_BASE_URL", "https://gw.suresofttech.com").rstrip("/"),
            favorites_file_path=os.environ.get("FAVORITES_FILE_PATH", "data/favorites.json"),
        )


def get_config() -> AppConfig:
    """Get active configuration loaded from environment."""
    return AppConfig.from_env()
