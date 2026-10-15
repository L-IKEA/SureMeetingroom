"""Pytest suite for Platform Abstraction, UserKey model, and Core Decoupling."""

import ast
from dataclasses import fields
from pathlib import Path
import sys
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.auth.session_manager import UserSessionManager
from meeting_room_bot.favorites.json_repository import JsonFavoriteRepository
from meeting_room_bot.favorites.service import FavoriteService
from meeting_room_bot.groupware.client import GroupwareClient
from meeting_room_bot.models.user_key import UserKey
from meeting_room_bot.providers.mock_provider import MockMeetingRoomProvider
from meeting_room_bot.providers.base import QueryStatus


class TestUserKeyModel:
    """Tests for UserKey identity model behavior, equality, and serialization."""

    def test_user_key_creation_and_fields(self):
        """UserKey should hold ONLY platform and platform_user_id (no internal user state)."""
        uk = UserKey(platform="telegram", platform_user_id="8296531540")
        assert uk.platform == "telegram"
        assert uk.platform_user_id == "8296531540"

        # Verify exact field names on UserKey dataclass
        field_names = [f.name for f in fields(UserKey)]
        assert field_names == ["platform", "platform_user_id"]
        assert "internal_user_id" not in field_names

        # Immutability check (frozen dataclass)
        with pytest.raises(Exception):
            uk.platform = "kakao"

    def test_user_key_equality_and_hash_stability(self):
        """Identical platform and ID must produce identical equality and hash for dict/cache keys."""
        uk1 = UserKey("telegram", "12345")
        uk2 = UserKey("telegram", "12345")
        uk_kakao = UserKey("kakao", "12345")

        assert uk1 == uk2
        assert hash(uk1) == hash(uk2)
        assert uk1 != uk_kakao
        assert hash(uk1) != hash(uk_kakao)

        # Dictionary key stability check
        store = {
            uk1: "telegram_session",
            uk_kakao: "kakao_session",
        }
        assert store[uk2] == "telegram_session"
        assert store[uk_kakao] == "kakao_session"
        assert len(store) == 2

    def test_user_key_serialization_and_str(self):
        """UserKey should serialize to 'platform:platform_user_id' format."""
        uk = UserKey(platform="telegram", platform_user_id="123456")
        assert uk.to_string() == "telegram:123456"
        assert str(uk) == "telegram:123456"

    def test_user_key_deserialization_from_string(self):
        """UserKey.from_string should correctly parse qualified and raw IDs."""
        uk1 = UserKey.from_string("telegram:8296531540")
        assert uk1 == UserKey("telegram", "8296531540")

        uk2 = UserKey.from_string("kakao:k_user_abc")
        assert uk2 == UserKey("kakao", "k_user_abc")

        # Plain ID defaults to telegram platform strictly for transition compatibility
        uk3 = UserKey.from_string("8296531540")
        assert uk3 == UserKey("telegram", "8296531540")

    def test_user_key_from_any_transition_layer(self):
        """UserKey.from_any should convert UserKey, str, and int for transition compatibility."""
        uk_direct = UserKey("telegram", "123")
        assert UserKey.from_any(uk_direct) is uk_direct

        assert UserKey.from_any("telegram:456") == UserKey("telegram", "456")
        assert UserKey.from_any("kakao:789") == UserKey("kakao", "789")
        assert UserKey.from_any("999") == UserKey("telegram", "999")
        assert UserKey.from_any(12345) == UserKey("telegram", "12345")

    def test_user_key_equality_independent_of_internal_user_or_account_mapping(self):
        """UserKey equality must depend solely on platform and platform_user_id.

        Internal user/account mapping (e.g. employee ID or AppUser) is managed
        in a separate layer and does not affect UserKey equality or hash stability.
        """
        uk_a = UserKey("telegram", "123")
        uk_b = UserKey("telegram", "123")

        # Two UserKey instances representing the same channel identity are always strictly equal
        assert uk_a == uk_b
        assert hash(uk_a) == hash(uk_b)

        # External mapping dictionary (e.g. ChannelIdentity -> AppUser / Employee ID)
        account_mapping = {
            uk_a: "emp_suresoft_001",
        }
        # Lookup using another UserKey instance with same channel identity succeeds
        assert account_mapping[uk_b] == "emp_suresoft_001"

        # UserKey itself contains no internal user ID attribute
        assert not hasattr(uk_a, "internal_user_id")

    def test_new_platform_adapter_explicit_construction(self):
        """New platform adapters (e.g. Kakao) must explicitly construct UserKey with platform.

        If a new platform adapter mistakenly passed a plain string '123' to Core,
        it would be resolved as 'telegram:123' due to legacy transition compatibility.
        Therefore, new platform adapters MUST explicitly construct UserKey(platform='kakao', ...).
        """
        # Raw string resolution fallback for v0.1 legacy compatibility
        assert UserKey.from_any("123").platform == "telegram"

        # Explicit construction by new platform adapter guarantees correct platform identity
        kakao_key = UserKey(platform="kakao", platform_user_id="123")
        assert kakao_key.platform == "kakao"
        assert kakao_key.to_string() == "kakao:123"
        # Guaranteed distinct from telegram user with same ID
        assert kakao_key != UserKey("telegram", "123")


class TestNamespaceIsolation:
    """Verify Telegram and Kakao users with identical IDs do not collide."""

    def test_telegram_and_kakao_distinct_keys(self):
        """Users with same ID on different platforms must have distinct UserKey."""
        uk_tel = UserKey("telegram", "common_id_123")
        uk_kakao = UserKey("kakao", "common_id_123")

        assert uk_tel != uk_kakao
        assert uk_tel.to_string() != uk_kakao.to_string()
        assert uk_tel.to_string() == "telegram:common_id_123"
        assert uk_kakao.to_string() == "kakao:common_id_123"

    def test_session_manager_platform_isolation(self):
        """UserSessionManager must isolate sessions for same ID across platforms."""
        mgr = UserSessionManager()

        client_tel = GroupwareClient()
        client_tel._is_authenticated = True
        client_tel._authenticated_user = "tel_employee"

        client_kakao = GroupwareClient()
        client_kakao._is_authenticated = True
        client_kakao._authenticated_user = "kakao_employee"

        uk_tel = UserKey("telegram", "999")
        uk_kakao = UserKey("kakao", "999")

        mgr.set_client(uk_tel, client_tel)
        mgr.set_client(uk_kakao, client_kakao)

        assert mgr.get_client(uk_tel) is client_tel
        assert mgr.get_client(uk_kakao) is client_kakao
        assert mgr.get_client(uk_tel) is not mgr.get_client(uk_kakao)

        # Removing telegram session leaves kakao session intact
        mgr.remove_session(uk_tel)
        assert mgr.has_session(uk_tel) is False
        assert mgr.has_session(uk_kakao) is True


class TestLegacyCompatibility:
    """Verify existing str-based user IDs continue to work via transition compatibility."""

    def test_session_manager_bidirectional_compatibility(self):
        """Verify session stored with str can be retrieved with UserKey and vice versa."""
        mgr = UserSessionManager()
        client = GroupwareClient()
        client._is_authenticated = True

        # Stored with str, retrieved with UserKey
        mgr.set_client("user_abc", client)
        assert mgr.has_session("user_abc") is True
        assert mgr.has_session(UserKey("telegram", "user_abc")) is True
        assert mgr.get_client(UserKey("telegram", "user_abc")) is client

        # Kakao key does not match legacy plain ID
        assert mgr.has_session(UserKey("kakao", "user_abc")) is False

        # Stored with UserKey, retrieved with str
        client2 = GroupwareClient()
        client2._is_authenticated = True
        mgr.set_client(UserKey("telegram", "user_def"), client2)
        assert mgr.has_session("user_def") is True
        assert mgr.get_client("user_def") is client2

    def test_favorites_repository_user_key_compatibility(self, tmp_path):
        """Verify JsonFavoriteRepository handles UserKey and legacy str properly."""
        json_file = tmp_path / "fav_test.json"
        repo = JsonFavoriteRepository(file_path=str(json_file))

        uk_tel = UserKey("telegram", "1001")
        uk_kakao = UserKey("kakao", "1001")

        # Add asset via UserKey
        assert repo.add_asset(uk_tel, 50) is True
        assert repo.add_asset(uk_kakao, 70) is True

        fav_tel = repo.get_user_favorites(uk_tel)
        fav_kakao = repo.get_user_favorites(uk_kakao)

        # Isolated sets
        assert fav_tel.favorite_assets == {50}
        assert fav_kakao.favorite_assets == {70}

        # Retrieval using plain str '1001' maps to telegram user (transition compatibility)
        fav_plain = repo.get_user_favorites("1001")
        assert fav_plain.favorite_assets == {50}


class TestCoreDependencyDecoupling:
    """Verify Core packages have ZERO direct imports of telegram packages."""

    def test_mock_provider_does_not_import_telegram(self):
        """Ensure MockMeetingRoomProvider file contains NO import of meeting_room_bot.telegram."""
        provider_file = SRC_DIR / "meeting_room_bot" / "providers" / "mock_provider.py"
        content = provider_file.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(provider_file))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("telegram"), f"Unexpected import in mock_provider: {alias.name}"
                    assert not alias.name.startswith("meeting_room_bot.telegram"), f"Unexpected import in mock_provider: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert not node.module.startswith("telegram"), f"Unexpected import from in mock_provider: {node.module}"
                    assert not node.module.startswith("meeting_room_bot.telegram"), f"Unexpected import from in mock_provider: {node.module}"

    def test_all_core_layers_have_zero_telegram_dependencies(self):
        """Verify auth, favorites, groupware, models, providers, services have ZERO telegram imports."""
        core_packages = ["auth", "favorites", "groupware", "models", "providers", "services"]
        violating_imports = []

        for pkg in core_packages:
            pkg_dir = SRC_DIR / "meeting_room_bot" / pkg
            for py_file in pkg_dir.glob("**/*.py"):
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name.startswith("telegram") or alias.name.startswith("meeting_room_bot.telegram"):
                                violating_imports.append((str(py_file.relative_to(PROJECT_ROOT)), alias.name))
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        if node.module.startswith("telegram") or node.module.startswith("meeting_room_bot.telegram"):
                            violating_imports.append((str(py_file.relative_to(PROJECT_ROOT)), node.module))

        assert violating_imports == [], f"Found forbidden telegram imports in core layers: {violating_imports}"


class TestMockProviderUserKeySupport:
    """Verify MockMeetingRoomProvider functions identically with UserKey."""

    def test_mock_provider_query_with_user_key(self):
        provider = MockMeetingRoomProvider()
        uk = UserKey("telegram", "12345")

        auth_res = provider.check_authentication(uk)
        assert auth_res.status == QueryStatus.SUCCESS

        loc_res = provider.get_locations(uk)
        assert loc_res.status == QueryStatus.SUCCESS
        assert len(loc_res.data["locations"]) > 0

        now_res = provider.get_available_rooms_now(uk, scope="fav")
        assert now_res.status == QueryStatus.SUCCESS
