"""Abstract Provider Interface for Meeting Room queries."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


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
    """Abstract Base Class for meeting room data providers (Mock vs Real)."""

    @abstractmethod
    def check_authentication(self, user_id: str) -> QueryResult:
        """Check if user has an active Groupware session."""
        pass

    @abstractmethod
    def get_locations(self, user_id: str) -> QueryResult:
        """Query list of available location assets."""
        pass

    @abstractmethod
    def get_available_rooms_now(self, user_id: str, scope: str = "fav") -> QueryResult:
        """Query currently available rooms."""
        pass

    @abstractmethod
    def get_available_rooms_at(
        self,
        user_id: str,
        date_str: str,
        start_time: str,
        duration: int,
        scope: str = "fav",
    ) -> QueryResult:
        """Query rooms available at a specified time slot."""
        pass

    @abstractmethod
    def get_location_status(self, user_id: str, asset_id: int) -> QueryResult:
        """Query status of all rooms in a location/asset."""
        pass

    @abstractmethod
    def get_room_detail(self, user_id: str, asset_id: int, room_id: int) -> QueryResult:
        """Query detailed information for a single room."""
        pass

    @abstractmethod
    def get_favorites(self, user_id: str) -> QueryResult:
        """Query registered user favorites."""
        pass
