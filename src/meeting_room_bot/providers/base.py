"""Abstract Provider Interface for Meeting Room queries."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional, Union

from meeting_room_bot.models.user_key import UserKey


class QueryStatus(str, Enum):
    """Status codes for query provider results."""

    SUCCESS = "SUCCESS"
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    NO_FAVORITES = "NO_FAVORITES"
    REQUEST_STATE_EXPIRED = "REQUEST_STATE_EXPIRED"
    GROUPWARE_API_ERROR = "GROUPWARE_API_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"


@dataclass
class QueryResult:
    """Standardized response container returned by MeetingRoomQueryProvider."""

    status: QueryStatus
    data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


class MeetingRoomQueryProvider(ABC):
    """Abstract Base Class for meeting room data providers (Mock vs Real).

    Architectural Principle:
    - Core internal operations are designed around UserKey (Platform-independent Channel Identity).
    - Union[UserKey, str] is maintained as a temporary Transition Compatibility Layer
      to support legacy v0.1 data and tests.
    - Platform adapters (Telegram, Kakao) must explicitly construct UserKey instances
      (e.g. UserKey("telegram", id), UserKey("kakao", id)) before invoking Core provider methods.
      Plain str must never be used by new platform adapters to prevent accidental default fallback.
    """

    @abstractmethod
    def check_authentication(self, user_id: Union[UserKey, str]) -> QueryResult:
        """Check if user has an active Groupware session. Accepts UserKey or legacy str (transition)."""
        pass

    @abstractmethod
    def get_locations(self, user_id: Union[UserKey, str]) -> QueryResult:
        """Query list of available location assets."""
        pass

    @abstractmethod
    def get_available_rooms_now(self, user_id: Union[UserKey, str], scope: str = "fav") -> QueryResult:
        """Query currently available rooms."""
        pass

    @abstractmethod
    def get_available_rooms_at(
        self,
        user_id: Union[UserKey, str],
        date_str: str,
        start_time: str,
        duration: int,
        scope: str = "fav",
    ) -> QueryResult:
        """Query rooms available at a specified time slot."""
        pass

    @abstractmethod
    def get_location_status(self, user_id: Union[UserKey, str], asset_id: int) -> QueryResult:
        """Query status of all rooms in a location/asset."""
        pass

    @abstractmethod
    def get_room_detail(self, user_id: Union[UserKey, str], asset_id: int, room_id: int) -> QueryResult:
        """Query detailed information for a single room."""
        pass

    @abstractmethod
    def get_favorites(self, user_id: Union[UserKey, str]) -> QueryResult:
        """Query registered user favorites."""
        pass

    @abstractmethod
    def get_timeline(
        self,
        user_id: Union[UserKey, str],
        asset_id: Optional[int] = None,
        target_date: Optional[datetime] = None,
    ) -> QueryResult:
        """Query timeline grid data for an asset location."""
        pass
