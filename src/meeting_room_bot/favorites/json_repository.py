"""JSON file implementation of FavoriteRepository."""

import json
from pathlib import Path
from typing import Any, Dict, List, Set

from meeting_room_bot.favorites.models import Favorite, FavoriteType, UserFavorites
from meeting_room_bot.favorites.repository import FavoriteRepository


class JsonFavoriteRepository(FavoriteRepository):
    """File-based repository storing user favorites in JSON format."""

    def __init__(self, file_path: str = "data/favorites.json"):
        self.file_path = Path(file_path)

    def _ensure_dir(self):
        """Create parent directory if it does not exist."""
        if self.file_path.parent:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_raw_data(self) -> Dict[str, Any]:
        """Load raw data dictionary from JSON file."""
        if not self.file_path.exists():
            return {"users": {}}

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {"users": {}}
                data = json.loads(content)
                if not isinstance(data, dict) or "users" not in data:
                    return {"users": {}}
                return data
        except Exception:
            # Fallback cleanly if file read or JSON parse fails
            return {"users": {}}

    def _save_raw_data(self, data: Dict[str, Any]):
        """Save data dictionary to JSON file."""
        self._ensure_dir()
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_user_favorites(self, user_id: str) -> UserFavorites:
        """Get UserFavorites for specific user_id."""
        data = self._load_raw_data()
        users = data.get("users", {})
        user_data = users.get(user_id, {})

        assets = set(user_data.get("favorite_assets", []))
        rooms = set(user_data.get("favorite_rooms", []))

        return UserFavorites(
            user_id=user_id,
            favorite_assets=assets,
            favorite_rooms=rooms,
        )

    def get_all(self, user_id: str) -> List[Favorite]:
        """Get all Favorite entries for a user."""
        uf = self.get_user_favorites(user_id)
        result: List[Favorite] = []

        for asset_id in sorted(uf.favorite_assets):
            result.append(Favorite(user_id=user_id, type=FavoriteType.ASSET, target_id=asset_id))

        for room_id in sorted(uf.favorite_rooms):
            result.append(Favorite(user_id=user_id, type=FavoriteType.ROOM, target_id=room_id))

        return result

    def add_asset(self, user_id: str, asset_id: int) -> bool:
        """Add asset ID to user's favorites (de-duplicated)."""
        data = self._load_raw_data()
        users = data.setdefault("users", {})
        user_entry = users.setdefault(user_id, {"favorite_assets": [], "favorite_rooms": []})

        assets_set = set(user_entry.get("favorite_assets", []))
        if asset_id in assets_set:
            return False  # Already exists

        assets_set.add(asset_id)
        user_entry["favorite_assets"] = sorted(assets_set)
        self._save_raw_data(data)
        return True

    def add_room(self, user_id: str, room_id: int) -> bool:
        """Add room ID to user's favorites (de-duplicated)."""
        data = self._load_raw_data()
        users = data.setdefault("users", {})
        user_entry = users.setdefault(user_id, {"favorite_assets": [], "favorite_rooms": []})

        rooms_set = set(user_entry.get("favorite_rooms", []))
        if room_id in rooms_set:
            return False  # Already exists

        rooms_set.add(room_id)
        user_entry["favorite_rooms"] = sorted(rooms_set)
        self._save_raw_data(data)
        return True

    def remove_asset(self, user_id: str, asset_id: int) -> bool:
        """Remove asset ID from user's favorites."""
        data = self._load_raw_data()
        users = data.get("users", {})
        if user_id not in users:
            return False

        user_entry = users[user_id]
        assets_set = set(user_entry.get("favorite_assets", []))

        if asset_id not in assets_set:
            return False

        assets_set.remove(asset_id)
        user_entry["favorite_assets"] = sorted(assets_set)
        self._save_raw_data(data)
        return True

    def remove_room(self, user_id: str, room_id: int) -> bool:
        """Remove room ID from user's favorites."""
        data = self._load_raw_data()
        users = data.get("users", {})
        if user_id not in users:
            return False

        user_entry = users[user_id]
        rooms_set = set(user_entry.get("favorite_rooms", []))

        if room_id not in rooms_set:
            return False

        rooms_set.remove(room_id)
        user_entry["favorite_rooms"] = sorted(rooms_set)
        self._save_raw_data(data)
        return True

    def clear(self, user_id: str) -> bool:
        """Clear all favorites for a user."""
        data = self._load_raw_data()
        users = data.get("users", {})
        if user_id in users:
            del users[user_id]
            self._save_raw_data(data)
            return True
        return False
