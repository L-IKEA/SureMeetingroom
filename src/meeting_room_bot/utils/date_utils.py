"""Date and Timezone Utilities for Asia/Seoul (KST)."""

from datetime import datetime, timedelta, timezone
from typing import Optional

SEOUL_TZ = timezone(timedelta(hours=9))


def get_seoul_now() -> datetime:
    """Return current timezone-aware datetime in Asia/Seoul (+09:00)."""
    return datetime.now(SEOUL_TZ)


def get_seoul_today_str() -> str:
    """Return today's date formatted as YYYY-MM-DD in Asia/Seoul."""
    return get_seoul_now().strftime("%Y-%m-%d")


def get_seoul_tomorrow_str() -> str:
    """Return tomorrow's date formatted as YYYY-MM-DD in Asia/Seoul."""
    return (get_seoul_now() + timedelta(days=1)).strftime("%Y-%m-%d")


def resolve_date_str(date_str: Optional[str]) -> str:
    """Resolve a date string ('today', 'tomorrow', or 'YYYY-MM-DD') into YYYY-MM-DD in Asia/Seoul.

    - None or empty/whitespace string -> Seoul today
    - 'today' (case-insensitive) -> Seoul today
    - 'tomorrow' (case-insensitive) -> Seoul tomorrow
    - Otherwise (e.g. 'YYYY-MM-DD') -> returns stripped date_str
    """
    if not date_str or not str(date_str).strip():
        return get_seoul_today_str()

    normalized = date_str.strip().lower()
    if normalized == "today":
        return get_seoul_today_str()
    elif normalized == "tomorrow":
        return get_seoul_tomorrow_str()

    return date_str.strip()
