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

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from meeting_room_bot.account_link.app import create_app
from meeting_room_bot.account_link.token_service import AccountLinkTokenService
from meeting_room_bot.auth.session_manager import UserSessionManager
from meeting_room_bot.favorites.json_repository import JsonFavoriteRepository
from meeting_room_bot.favorites.service import FavoriteService
from meeting_room_bot.groupware.client import GroupwareClient
from meeting_room_bot.models import Asset, Room
from meeting_room_bot.models.user_key import UserKey
from meeting_room_bot.providers.mock_provider import MockMeetingRoomProvider
from meeting_room_bot.providers.real_provider import RealMeetingRoomProvider
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

    def test_user_key_canonicalization_lowercase_and_strip(self):
        """UserKey platform and platform_user_id must be stripped and platform lowercased."""
        uk1 = UserKey(" Telegram ", "  12345  ")
        assert uk1.platform == "telegram"
        assert uk1.platform_user_id == "12345"
        assert uk1.to_string() == "telegram:12345"

        uk2 = UserKey("KaKaO", "user_99")
        assert uk2.platform == "kakao"
        assert uk2.platform_user_id == "user_99"

    def test_user_key_integer_id_normalization(self):
        """Integer platform_user_id must be safely normalized to string."""
        uk = UserKey("telegram", 8296531540)
        assert uk.platform_user_id == "8296531540"
        assert uk == UserKey("telegram", "8296531540")
        assert hash(uk) == hash(UserKey("telegram", "8296531540"))

    def test_user_key_empty_platform_rejected(self):
        """Empty or non-string platform must raise ValueError or TypeError."""
        with pytest.raises(ValueError, match="platform must not be empty"):
            UserKey("", "123")
        with pytest.raises(ValueError, match="platform must not be empty"):
            UserKey("   ", "123")
        with pytest.raises(TypeError, match="platform must be a str"):
            UserKey(None, "123")

    def test_user_key_empty_platform_user_id_rejected(self):
        """Empty or None platform_user_id must raise ValueError."""
        with pytest.raises(ValueError, match="platform_user_id must not be empty"):
            UserKey("telegram", "")
        with pytest.raises(ValueError, match="platform_user_id must not be empty"):
            UserKey("telegram", "   ")
        with pytest.raises(ValueError, match="platform_user_id must not be None"):
            UserKey("telegram", None)

    def test_user_key_canonicalized_hash_and_equality_stability(self):
        """Canonicalized variations must produce identical equality and hash for dict keying."""
        k1 = UserKey(" TELEGRAM ", 456)
        k2 = UserKey("telegram", "456")
        k3 = UserKey.from_string("  telegram : 456  ")

        assert k1 == k2 == k3
        assert hash(k1) == hash(k2) == hash(k3)

        store = {k1: "session_val"}
        assert store[k2] == "session_val"
        assert store[k3] == "session_val"

    def test_user_key_colon_in_platform_rejected(self):
        """Platform must not contain colons (:) to prevent serialization ambiguity."""
        with pytest.raises(ValueError, match="must not contain ':'"):
            UserKey("foo:bar", "123")
        with pytest.raises(ValueError, match="must not contain ':'"):
            UserKey("telegram:sub", "123")

    def test_user_key_platform_character_validation(self):
        """Platform must contain only valid characters (alphanumeric, underscore, hyphen)."""
        with pytest.raises(ValueError, match="platform contains invalid characters"):
            UserKey("telegram!", "123")
        with pytest.raises(ValueError, match="platform contains invalid characters"):
            UserKey("my platform", "123")

        # Valid platforms must succeed
        uk1 = UserKey("telegram", "123")
        uk2 = UserKey("kakao", "123")
        uk3 = UserKey("future_platform", "123")
        uk4 = UserKey("teams-bot_1", "123")
        assert uk1.platform == "telegram"
        assert uk2.platform == "kakao"
        assert uk3.platform == "future_platform"
        assert uk4.platform == "teams-bot_1"

    def test_user_key_serialization_round_trip(self):
        """to_string() and from_string() must preserve exact equality round-trip."""
        test_keys = [
            UserKey("telegram", "123"),
            UserKey("kakao", "user_9988"),
            UserKey("future_platform", "sub_id:with:colons"),
            UserKey("teams-bot", "dept_room_5"),
        ]
        for uk in test_keys:
            serialized = uk.to_string()
            recovered = UserKey.from_string(serialized)
            assert recovered == uk
            assert hash(recovered) == hash(uk)
            assert str(recovered) == serialized


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

    def test_mock_provider_preserves_platform_namespace(self):
        """MockProvider must preserve platform namespace and not collapse IDs."""
        provider = MockMeetingRoomProvider()
        uk_tel = UserKey("telegram", "123")
        uk_kakao = UserKey("kakao", "123")

        fav_tel = provider.get_favorites(uk_tel)
        fav_kakao = provider.get_favorites(uk_kakao)

        assert fav_tel.data["user_id"] == "telegram:123"
        assert fav_kakao.data["user_id"] == "kakao:123"
        assert fav_tel.data["user_id"] != fav_kakao.data["user_id"]

    def test_mock_provider_favorites_namespace_isolation(self):
        """UserKey on telegram with no_fav must not affect kakao user with same ID."""
        provider = MockMeetingRoomProvider()
        uk_tel_nofav = UserKey("telegram", "no_fav")
        uk_kakao_nofav = UserKey("kakao", "no_fav")

        # telegram:no_fav is configured as empty favorites
        res_tel = provider.get_available_rooms_now(uk_tel_nofav, scope="fav")
        assert res_tel.status == QueryStatus.NO_FAVORITES

        # kakao:no_fav has isolated namespace, not treated as telegram:no_fav
        res_kakao = provider.get_available_rooms_now(uk_kakao_nofav, scope="fav")
        assert res_kakao.status == QueryStatus.SUCCESS


class TestRealProviderConcurrencyAndStatelessness:
    """Verify RealMeetingRoomProvider and FavoriteService are stateless and thread/concurrency safe."""

    def test_concurrent_users_no_shared_mutable_meeting_room_service(self):
        """Interleaved calls from user A and user B must never use the other's GroupwareClient."""
        session_mgr = UserSessionManager()
        repo = JsonFavoriteRepository()

        # User A setup
        uk_a = UserKey("telegram", "user_A")
        client_a = MagicMock(spec=GroupwareClient)
        client_a.is_authenticated = True
        client_a.get_assets.return_value = [{"id": 50, "name": "5층 회의실"}]
        client_a.get_items.return_value = [{"id": 501, "name": "회의실 5-1"}]
        client_a.get_daily_reservations.return_value = []
        session_mgr.set_client(uk_a, client_a)
        repo.add_room(uk_a, 501)

        # User B setup
        uk_b = UserKey("telegram", "user_B")
        client_b = MagicMock(spec=GroupwareClient)
        client_b.is_authenticated = True
        client_b.get_assets.return_value = [{"id": 80, "name": "8층 회의실"}]
        client_b.get_items.return_value = [{"id": 801, "name": "회의실 8-1"}]
        client_b.get_daily_reservations.return_value = []
        session_mgr.set_client(uk_b, client_b)
        repo.add_room(uk_b, 801)

        # Shared singleton FavoriteService and RealMeetingRoomProvider
        fav_service = FavoriteService(repo=repo)
        # Verify fav_service is completely stateless
        assert not hasattr(fav_service, "meeting_room_service")

        provider = RealMeetingRoomProvider(session_mgr=session_mgr, favorite_service=fav_service)

        # Interleave calls: A -> B -> A -> B
        # 1. User A queries favorites
        fav_a_1 = provider.get_favorites(uk_a)
        assert fav_a_1.status == QueryStatus.SUCCESS
        assert "🚪 회의실 5-1" in fav_a_1.data["rooms"]
        # Verify fav_service does not hold meeting_room_service attribute
        assert not hasattr(fav_service, "meeting_room_service")

        # 2. User B queries available rooms
        res_b = provider.get_available_rooms_now(uk_b, scope="fav")
        assert res_b.status == QueryStatus.SUCCESS
        assert not hasattr(fav_service, "meeting_room_service")

        # 3. User A queries available rooms again
        res_a = provider.get_available_rooms_now(uk_a, scope="fav")
        assert res_a.status == QueryStatus.SUCCESS
        assert not hasattr(fav_service, "meeting_room_service")

        # 4. User B queries favorites
        fav_b = provider.get_favorites(uk_b)
        assert fav_b.status == QueryStatus.SUCCESS
        assert "🚪 회의실 8-1" in fav_b.data["rooms"]
        assert not hasattr(fav_service, "meeting_room_service")

        # Verify Client Isolation: Client A was never called for B's asset/room, and vice versa
        for call_args in client_a.get_items.call_args_list:
            assert call_args[0][0] != 80  # Client A was never called for Asset 80
        for call_args in client_b.get_items.call_args_list:
            assert call_args[0][0] != 50  # Client B was never called for Asset 50

    def test_favorite_service_complete_statelessness(self, tmp_path):
        """FavoriteService must have zero client/meeting_room_service state and require per-call service."""
        from meeting_room_bot.favorites.json_repository import JsonFavoriteRepository
        repo = JsonFavoriteRepository(str(tmp_path / "fav.json"))
        fav_svc = FavoriteService(repo=repo)

        # 1. Verify no meeting_room_service attribute on FavoriteService
        assert not hasattr(fav_svc, "meeting_room_service")

        # 2. Add asset favorite
        uk = UserKey("telegram", "u100")
        fav_svc.add_asset(uk, 50)

        # 3. get_favorite_rooms without meeting_room_service must raise ValueError
        with pytest.raises(ValueError, match="meeting_room_service must be provided"):
            fav_svc.get_favorite_rooms(uk, meeting_room_service=None)


class TestAccountLinkingIntegrationWithUserKey:
    """Verify end-to-end Account Linking flow using UserKey."""

    def test_telegram_user_key_account_linking_integration(self):
        """Test full token creation -> HTTP login POST -> session binding -> UserKey lookup."""
        session_mgr = UserSessionManager()
        token_svc = AccountLinkTokenService()
        app = create_app()
        client_app = TestClient(app)

        uk_telegram = UserKey("telegram", "778899")

        # 1. Bot creates link token for UserKey
        token = token_svc.create_token(uk_telegram)
        assert token is not None

        def mock_login_success(self, username, password):
            self._is_authenticated = True
            return True

        # 2. Simulate User submitting login credentials via Web Form
        with patch("meeting_room_bot.account_link.app.session_manager", session_mgr), \
             patch("meeting_room_bot.account_link.app.token_service", token_svc), \
             patch.object(GroupwareClient, "login", side_effect=mock_login_success, autospec=True):

            resp = client_app.post(
                f"/link/{token}",
                data={"username": "emp_suresoft", "password": "mock_password"},
            )
            assert resp.status_code == 200
            assert "연동 완료" in resp.text or "성공" in resp.text

        # 3. Verify session is bound to Telegram UserKey
        assert session_mgr.has_session(uk_telegram) is True
        bound_client = session_mgr.get_client(uk_telegram)
        assert bound_client is not None
        assert bound_client.is_authenticated is True

        # 4. Verify same ID on Kakao has NO session (Namespace Isolation)
        uk_kakao = UserKey("kakao", "778899")
        assert session_mgr.has_session(uk_kakao) is False
        assert session_mgr.get_client(uk_kakao) is None
