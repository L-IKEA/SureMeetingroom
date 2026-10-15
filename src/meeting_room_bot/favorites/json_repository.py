"""JSON file implementation of FavoriteRepository."""

import json
from pathlib import Path
from typing import Any, Dict, List, Set, Union

from meeting_room_bot.favorites.models import Favorite, FavoriteType, UserFavorites
from meeting_room_bot.favorites.repository import FavoriteRepository
from meeting_room_bot.models.user_key import UserKey


class JsonFavoriteRepository(FavoriteRepository):
    """File-based repository storing user favorites in JSON format."""

    def __init__(self, file_path: str = "data/favorites.json"):
        self.file_path = Path(file_path)

    def _ensure_dir(self):
        """Create parent directory if it does not exist."""
        if self.file_path.parent:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _resolve_storage_key(self, user_id: Union[UserKey, str], users_dict: Dict[str, Any]) -> str:
        """Resolve storage key supporting both UserKey and legacy plain string ID."""
        if isinstance(user_id, UserKey):
            standard_key = user_id.to_string()
            if standard_key in users_dict:
                return standard_key
            if user_id.platform == "telegram" and user_id.platform_user_id in users_dict:
                return user_id.platform_user_id
            return standard_key

        raw = str(user_id).strip()
        if raw in users_dict:
            return raw
        if ":" not in raw and f"telegram:{raw}" in users_dict:
            return f"telegram:{raw}"
        return raw

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

    def get_user_favorites(self, user_id: Union[UserKey, str]) -> UserFavorites:
        """Get UserFavorites for specific user_id."""
        data = self._load_raw_data()
        users = data.get("users", {})
        key = self._resolve_storage_key(user_id, users)
        user_data = users.get(key, {})

        assets = set(user_data.get("favorite_assets", []))
        rooms = set(user_data.get("favorite_rooms", []))

        uid_str = user_id.to_string() if isinstance(user_id, UserKey) else str(user_id)
        return UserFavorites(
            user_id=uid_str,
            favorite_assets=assets,
            favorite_rooms=rooms,
        )

    def get_all(self, user_id: Union[UserKey, str]) -> List[Favorite]:
        """Get all Favorite entries for a user."""
        uf = self.get_user_favorites(user_id)
        result: List[Favorite] = []
        uid_str = user_id.to_string() if isinstance(user_id, UserKey) else str(user_id)

        for asset_id in sorted(uf.favorite_assets):
            result.append(Favorite(user_id=uid_str, type=FavoriteType.ASSET, target_id=asset_id))

        for room_id in sorted(uf.favorite_rooms):
            result.append(Favorite(user_id=uid_str, type=FavoriteType.ROOM, target_id=room_id))

        return result

    def add_asset(self, user_id: Union[UserKey, str], asset_id: int) -> bool:
        """Add asset ID to user's favorites (de-duplicated)."""
        data = self._load_raw_data()
        users = data.setdefault("users", {})
        key = self._resolve_storage_key(user_id, users)
        user_entry = users.setdefault(key, {"favorite_assets": [], "favorite_rooms": []})

        assets_set = set(user_entry.get("favorite_assets", []))
        if asset_id in assets_set:
            return False  # Already exists

        assets_set.add(asset_id)
        user_entry["favorite_assets"] = sorted(assets_set)
        self._save_raw_data(data)
        return True

    def add_room(self, user_id: Union[UserKey, str], room_id: int) -> bool:
        """Add room ID to user's favorites (de-duplicated)."""
        data = self._load_raw_data()
        users = data.setdefault("users", {})
        key = self._resolve_storage_key(user_id, users)
        user_entry = users.setdefault(key, {"favorite_assets": [], "favorite_rooms": []})

        rooms_set = set(user_entry.get("favorite_rooms", []))
        if room_id in rooms_set:
            return False  # Already exists

        rooms_set.add(room_id)
        user_entry["favorite_rooms"] = sorted(rooms_set)
        self._save_raw_data(data)
        return True

    def remove_asset(self, user_id: Union[UserKey, str], asset_id: int) -> bool:
        """Remove asset ID from user's favorites."""
        data = self._load_raw_data()
        users = data.get("users", {})
        key = self._resolve_storage_key(user_id, users)
        if key not in users:
            return False

        user_entry = users[key]
        assets_set = set(user_entry.get("favorite_assets", []))

        if asset_id not in assets_set:
            return False

        assets_set.remove(asset_id)
        user_entry["favorite_assets"] = sorted(assets_set)
        self._save_raw_data(data)
        return True

    def remove_room(self, user_id: Union[UserKey, str], room_id: int) -> bool:
        """Remove room ID from user's favorites."""
        data = self._load_raw_data()
        users = data.get("users", {})
        key = self._resolve_storage_key(user_id, users)
        if key not in users:
            return False

        user_entry = users[key]
        rooms_set = set(user_entry.get("favorite_rooms", []))

        if room_id not in rooms_set:
            return False

        rooms_set.remove(room_id)
        user_entry["favorite_rooms"] = sorted(rooms_set)
        self._save_raw_data(data)
        return True

    def clear(self, user_id: Union[UserKey, str]) -> bool:
        """Clear all favorites for a user."""
        data = self._load_raw_data()
        users = data.get("users", {})
        key = self._resolve_storage_key(user_id, users)
        if key in users:
            del users[key]
            self._save_raw_data(data)
            return True
        return False

