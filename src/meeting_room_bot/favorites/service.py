"""FavoriteService implementing business logic for user favorites."""

from typing import Any, Dict, List, Optional, Set, Tuple

from meeting_room_bot.favorites.models import Favorite, UserFavorites
from meeting_room_bot.favorites.repository import FavoriteRepository
from meeting_room_bot.models import Asset, Room


class FavoriteService:
    """Application Service managing user-isolated favorite locations and rooms."""

    def __init__(self, repo: FavoriteRepository, meeting_room_service: Optional[Any] = None):
        self.repo = repo
        self.meeting_room_service = meeting_room_service

    def get_favorites(self, user_id: str) -> List[Favorite]:
        """Get list of all Favorite objects for a user."""
        return self.repo.get_all(user_id)

    def get_user_favorites(self, user_id: str) -> UserFavorites:
        """Get UserFavorites container for a user."""
        return self.repo.get_user_favorites(user_id)

    def add_asset(self, user_id: str, asset_id: int) -> bool:
        """Add asset ID to user's favorites."""
        return self.repo.add_asset(user_id, asset_id)

    def add_room(self, user_id: str, room_id: int) -> bool:
        """Add room ID to user's favorites."""
        return self.repo.add_room(user_id, room_id)

    def remove_asset(self, user_id: str, asset_id: int) -> bool:
        """Remove asset ID from user's favorites."""
        return self.repo.remove_asset(user_id, asset_id)

    def remove_room(self, user_id: str, room_id: int) -> bool:
        """Remove room ID from user's favorites."""
        return self.repo.remove_room(user_id, room_id)

    def clear(self, user_id: str) -> bool:
        """Clear all favorites for a user."""
        return self.repo.clear(user_id)

    def get_favorite_rooms(self, user_id: str) -> List[Tuple[Asset, Room]]:
        """Expand user's asset and room favorites into actual Room objects, removing duplicates.

        If user has 0 favorites, returns empty list [].
        """
        uf = self.repo.get_user_favorites(user_id)
        if uf.is_empty():
            return []

        if self.meeting_room_service is None:
            return []

        # Map room_id -> (Asset, Room) for deduplication
        resolved_map: Dict[int, Tuple[Asset, Room]] = {}

        all_assets = self.meeting_room_service.get_meeting_assets()
        asset_dict = {a.id: a for a in all_assets}

        # 1. Expand asset favorites to all rooms in those assets
        for asset_id in uf.favorite_assets:
            asset = asset_dict.get(asset_id)
            if not asset:
                continue
            try:
                item_res = self.meeting_room_service.client.get_items(asset_id)
                from meeting_room_bot.services.meeting_room_service import _parse_rooms
                rooms = _parse_rooms(item_res, asset_id)
                for r in rooms:
                    resolved_map[r.id] = (asset, r)
            except Exception:
                continue

        # 2. Add individual room favorites (if not already included)
        for room_id in uf.favorite_rooms:
            if room_id in resolved_map:
                continue  # Already included via asset favorite

            # Search across assets for this room_id
            found = False
            for asset in all_assets:
                try:
                    item_res = self.meeting_room_service.client.get_items(asset.id)
                    from meeting_room_bot.services.meeting_room_service import _parse_rooms
                    rooms = _parse_rooms(item_res, asset.id)
                    target_r = next((r for r in rooms if r.id == room_id), None)
                    if target_r:
                        resolved_map[target_r.id] = (asset, target_r)
                        found = True
                        break
                except Exception:
                    continue

            if not found:
                # Fallback dummy asset and room if item API call didn't find details
                dummy_asset = Asset(id=0, name="Favorite Room", raw_name="Favorite Room")
                dummy_room = Room(id=room_id, asset_id=0, name=f"Room {room_id}", capacity=None, raw_name=f"Room {room_id}")
                resolved_map[room_id] = (dummy_asset, dummy_room)

        return list(resolved_map.values())
