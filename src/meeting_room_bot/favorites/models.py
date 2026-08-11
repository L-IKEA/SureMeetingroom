"""Favorites data models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Set


class FavoriteType(str, Enum):
    """Enum representing favorite target types."""

    ASSET = "ASSET"
    ROOM = "ROOM"


@dataclass
class Favorite:
    """Represents a single favorite entry."""

    user_id: str
    type: FavoriteType
    target_id: int


@dataclass
class UserFavorites:
    """Represents all favorite assets and rooms for a specific user."""

    user_id: str
    favorite_assets: Set[int] = field(default_factory=set)
    favorite_rooms: Set[int] = field(default_factory=set)

    def is_empty(self) -> bool:
        return not self.favorite_assets and not self.favorite_rooms
