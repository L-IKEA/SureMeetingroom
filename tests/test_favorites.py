"""Pytest suite for Favorites module (models, repository, service)."""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.favorites import (
    Favorite,
    FavoriteService,
    FavoriteType,
    JsonFavoriteRepository,
)
from meeting_room_bot.groupware.client import GroupwareClient
from meeting_room_bot.models import Asset, Room
from meeting_room_bot.services import MeetingRoomService

SEOUL_TZ = timezone(timedelta(hours=9))


def make_dt(hour: int, minute: int, day: int = 11) -> datetime:
    return datetime(2026, 8, day, hour, minute, tzinfo=SEOUL_TZ)


@pytest.fixture
def temp_repo(tmp_path):
    json_path = tmp_path / "favorites_test.json"
    return JsonFavoriteRepository(str(json_path))


@pytest.fixture
def mock_meeting_service():
    service = MagicMock(spec=MeetingRoomService)
    client = MagicMock(spec=GroupwareClient)
    service.client = client

    asset50 = Asset(id=50, name="[판교] 5층 회의실", raw_name="[판교] 5층 회의실")
    asset60 = Asset(id=60, name="[판교] 6층 프로젝트룸", raw_name="[판교] 6층 프로젝트룸")

    service.get_meeting_assets.return_value = [asset50, asset60]

    def mock_get_items(asset_id):
        if asset_id == 50:
            return {
                "code": "200",
                "data": [
                    {"id": 130, "name": "회의실 5-1(6인 / TV)"},
                    {"id": 131, "name": "회의실 5-2(6인 / TV)"},
                ],
            }
        elif asset_id == 60:
            return {
                "code": "200",
                "data": [
                    {"id": 140, "name": "프로젝트룸 6-1(10인)"},
                ],
            }
        return {"code": "200", "data": []}

    client.get_items.side_effect = mock_get_items

    def mock_get_daily(asset_id, date_str=None):
        if asset_id == 50:
            return {
                "code": "200",
                "data": [
                    {
                        "id": 130,
                        "reservations": [
                            {"id": 1, "startTime": "2026-08-11T09:30:00+09:00", "endTime": "2026-08-11T10:30:00+09:00"}
                        ],
                    },
                    {
                        "id": 131,
                        "reservations": [
                            {"id": 2, "startTime": "2026-08-11T14:00:00+09:00", "endTime": "2026-08-11T15:00:00+09:00"}
                        ],
                    },
                ],
            }
        elif asset_id == 60:
            return {"code": "200", "data": []}
        return {"code": "200", "data": []}

    client.get_daily_reservations.side_effect = mock_get_daily

    return service


class TestFavoriteRepositoryAndService:

    def test_1_user_a_add_asset(self, temp_repo):
        """1. User A asset add."""
        result = temp_repo.add_asset("userA", 50)
        assert result is True
        favs = temp_repo.get_user_favorites("userA")
        assert 50 in favs.favorite_assets

    def test_2_user_b_add_asset(self, temp_repo):
        """2. User B asset add."""
        result = temp_repo.add_asset("userB", 60)
        assert result is True
        favs = temp_repo.get_user_favorites("userB")
        assert 60 in favs.favorite_assets

    def test_3_user_isolation(self, temp_repo):
        """3. User A and B data isolated."""
        temp_repo.add_asset("userA", 50)
        temp_repo.add_asset("userB", 60)

        favs_a = temp_repo.get_user_favorites("userA")
        favs_b = temp_repo.get_user_favorites("userB")

        assert 50 in favs_a.favorite_assets
        assert 60 not in favs_a.favorite_assets

        assert 60 in favs_b.favorite_assets
        assert 50 not in favs_b.favorite_assets

    def test_4_duplicate_asset_prevention(self, temp_repo):
        """4. Duplicate asset add returns False and stores only once."""
        first = temp_repo.add_asset("userA", 50)
        second = temp_repo.add_asset("userA", 50)

        assert first is True
        assert second is False

        favs = temp_repo.get_user_favorites("userA")
        assert len(favs.favorite_assets) == 1

    def test_5_duplicate_room_prevention(self, temp_repo):
        """5. Duplicate room add returns False and stores only once."""
        first = temp_repo.add_room("userA", 130)
        second = temp_repo.add_room("userA", 130)

        assert first is True
        assert second is False

        favs = temp_repo.get_user_favorites("userA")
        assert len(favs.favorite_rooms) == 1

    def test_6_asset_removal(self, temp_repo):
        """6. Asset removal."""
        temp_repo.add_asset("userA", 50)
        removed = temp_repo.remove_asset("userA", 50)

        assert removed is True
        favs = temp_repo.get_user_favorites("userA")
        assert 50 not in favs.favorite_assets

    def test_7_room_removal(self, temp_repo):
        """7. Room removal."""
        temp_repo.add_room("userA", 130)
        removed = temp_repo.remove_room("userA", 130)

        assert removed is True
        favs = temp_repo.get_user_favorites("userA")
        assert 130 not in favs.favorite_rooms

    def test_8_non_existent_favorite_removal(self, temp_repo):
        """8. Non-existent favorite removal returns False gracefully."""
        removed_asset = temp_repo.remove_asset("userA", 999)
        removed_room = temp_repo.remove_room("userA", 999)

        assert removed_asset is False
        assert removed_room is False

    def test_9_repository_persistence(self, tmp_path):
        """9. Re-instantiating repository loads persisted JSON data."""
        json_path = tmp_path / "persistence_test.json"
        repo1 = JsonFavoriteRepository(str(json_path))
        repo1.add_asset("userA", 50)
        repo1.add_room("userA", 130)

        repo2 = JsonFavoriteRepository(str(json_path))
        favs = repo2.get_user_favorites("userA")

        assert 50 in favs.favorite_assets
        assert 130 in favs.favorite_rooms

    def test_10_missing_json_initial_state(self, tmp_path):
        """10. Initial state with non-existent JSON file starts empty without error."""
        json_path = tmp_path / "non_existent.json"
        repo = JsonFavoriteRepository(str(json_path))

        favs = repo.get_user_favorites("userA")
        assert favs.is_empty()

    def test_11_malformed_json_handling(self, tmp_path):
        """11. Malformed JSON file falls back cleanly to empty state."""
        json_path = tmp_path / "corrupt.json"
        json_path.write_text("INVALID JSON {{{", encoding="utf-8")

        repo = JsonFavoriteRepository(str(json_path))
        favs = repo.get_user_favorites("userA")

        assert favs.is_empty()

    def test_12_asset_and_room_deduplication(self, temp_repo, mock_meeting_service):
        """12. Asset + Room favorite de-duplication in get_favorite_rooms."""
        fav_service = FavoriteService(repo=temp_repo, meeting_room_service=mock_meeting_service)
        # Asset 50 contains rooms 130 and 131.
        # Add both Asset 50 AND Room 130 explicitly.
        fav_service.add_asset("userA", 50)
        fav_service.add_room("userA", 130)

        favorite_rooms = fav_service.get_favorite_rooms("userA")
        room_ids = [r.id for _, r in favorite_rooms]

        # Room 130 should appear only ONCE
        assert room_ids.count(130) == 1
        assert 131 in room_ids
        assert len(room_ids) == 2

    def test_13_asset_room_expansion(self, temp_repo, mock_meeting_service):
        """13. Favoriting an asset expands to all rooms in that asset."""
        fav_service = FavoriteService(repo=temp_repo, meeting_room_service=mock_meeting_service)
        fav_service.add_asset("userA", 50)

        favorite_rooms = fav_service.get_favorite_rooms("userA")
        room_ids = [r.id for _, r in favorite_rooms]

        assert 130 in room_ids
        assert 131 in room_ids

    def test_14_single_room_favorite(self, temp_repo, mock_meeting_service):
        """14. Favoriting a single room resolves correctly."""
        fav_service = FavoriteService(repo=temp_repo, meeting_room_service=mock_meeting_service)
        fav_service.add_room("userA", 140)  # Room 140 in Asset 60

        favorite_rooms = fav_service.get_favorite_rooms("userA")
        assert len(favorite_rooms) == 1
        asset, room = favorite_rooms[0]
        assert asset.id == 60
        assert room.id == 140

    def test_15_user_with_zero_favorites(self, temp_repo, mock_meeting_service):
        """15. User with 0 favorites returns empty list."""
        fav_service = FavoriteService(repo=temp_repo, meeting_room_service=mock_meeting_service)
        result = fav_service.get_favorite_rooms("user_zero")

        assert result == []

    def test_16_get_available_favorite_rooms_now(self, temp_repo, mock_meeting_service):
        """16. get_available_favorite_rooms_now returns available rooms within user's favorites."""
        fav_service = FavoriteService(repo=temp_repo, meeting_room_service=mock_meeting_service)
        fav_service.add_asset("userA", 50)  # Contains room 130 (occupied at 10:00) & 131 (available)

        now = make_dt(10, 0)
        # We need real MeetingRoomService to test integration method
        meeting_service = MeetingRoomService(mock_meeting_service.client)
        meeting_service.get_meeting_assets = mock_meeting_service.get_meeting_assets
        fav_service.meeting_room_service = meeting_service

        avail = meeting_service.get_available_favorite_rooms_now("userA", fav_service, now=now)

        assert len(avail) == 1
        assert avail[0]["room"].id == 131

    def test_17_get_available_favorite_rooms_at(self, temp_repo, mock_meeting_service):
        """17. get_available_favorite_rooms_at returns available rooms for specific time slot."""
        fav_service = FavoriteService(repo=temp_repo, meeting_room_service=mock_meeting_service)
        fav_service.add_asset("userA", 50)

        req_start = make_dt(14, 0)
        req_end = make_dt(15, 0)

        meeting_service = MeetingRoomService(mock_meeting_service.client)
        meeting_service.get_meeting_assets = mock_meeting_service.get_meeting_assets
        fav_service.meeting_room_service = meeting_service

        results = meeting_service.get_available_favorite_rooms_at("userA", fav_service, req_start, req_end)

        assert len(results) == 1
        asset_res = results[0]
        avail_ids = [r.id for r in asset_res["available_rooms"]]
        unavail_ids = [r.id for r in asset_res["unavailable_rooms"]]

        # Room 131 has reservation at 14:00~15:00 in mock daily data -> unavailable
        # Room 130 has no reservation at 14:00~15:00 -> available
        assert 130 in avail_ids
        assert 131 in unavail_ids
