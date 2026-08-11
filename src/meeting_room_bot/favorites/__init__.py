"""Favorites package."""

from meeting_room_bot.favorites.json_repository import JsonFavoriteRepository
from meeting_room_bot.favorites.models import Favorite, FavoriteType, UserFavorites
from meeting_room_bot.favorites.repository import FavoriteRepository
from meeting_room_bot.favorites.service import FavoriteService

__all__ = [
    "FavoriteType",
    "Favorite",
    "UserFavorites",
    "FavoriteRepository",
    "JsonFavoriteRepository",
    "FavoriteService",
]
