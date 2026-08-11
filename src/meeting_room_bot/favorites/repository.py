"""Abstract FavoriteRepository interface."""

from abc import ABC, abstractmethod
from typing import List
from meeting_room_bot.favorites.models import Favorite, UserFavorites


class FavoriteRepository(ABC):
    """Abstract interface for favorite storage repository."""

    @abstractmethod
    def get_all(self, user_id: str) -> List[Favorite]:
        """Get list of all Favorite objects for a specific user."""
        pass

    @abstractmethod
    def get_user_favorites(self, user_id: str) -> UserFavorites:
        """Get UserFavorites containing sets of favorite asset and room IDs."""
        pass

    @abstractmethod
    def add_asset(self, user_id: str, asset_id: int) -> bool:
        """Add an asset ID to user's favorites."""
        pass

    @abstractmethod
    def add_room(self, user_id: str, room_id: int) -> bool:
        """Add a room ID to user's favorites."""
        pass

    @abstractmethod
    def remove_asset(self, user_id: str, asset_id: int) -> bool:
        """Remove an asset ID from user's favorites."""
        pass

    @abstractmethod
    def remove_room(self, user_id: str, room_id: int) -> bool:
        """Remove a room ID from user's favorites."""
        pass

    @abstractmethod
    def clear(self, user_id: str) -> bool:
        """Clear all favorites for a specific user."""
        pass
