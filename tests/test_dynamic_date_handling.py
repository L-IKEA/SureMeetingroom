"""Tests for Dynamic Asia/Seoul Date Handling in WHEN Flow and RealMeetingRoomProvider."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from meeting_room_bot.auth.session_manager import UserSessionManager
from meeting_room_bot.favorites.service import FavoriteService
from meeting_room_bot.groupware.client import GroupwareClient
from meeting_room_bot.models import UserKey
from meeting_room_bot.providers.base import QueryResult, QueryStatus
from meeting_room_bot.providers.real_provider import RealMeetingRoomProvider
from meeting_room_bot.services.meeting_room_service import MeetingRoomService
from meeting_room_bot.telegram.handlers import button_callback, set_query_provider, user_state_mgr
from meeting_room_bot.telegram.states import (
    CB_DATE_TODAY,
    CB_DATE_TOMORROW,
    CB_DUR_PREFIX,
    CB_MENU_WHEN,
    CB_SCOPE_ALL,
    CB_TIME_PREFIX,
)
from meeting_room_bot.utils.date_utils import (
    SEOUL_TZ,
    get_seoul_now,
    get_seoul_today_str,
    get_seoul_tomorrow_str,
    resolve_date_str,
)


class TestDateUtils:
    """Unit tests for date_utils resolution functions."""

    def test_resolve_date_str_today_and_tomorrow(self):
        """today and tomorrow are resolved dynamically to Seoul timezone."""
        fixed_now = datetime(2026, 10, 15, 14, 30, tzinfo=SEOUL_TZ)
        with patch("meeting_room_bot.utils.date_utils.get_seoul_now", return_value=fixed_now):
            assert get_seoul_today_str() == "2026-10-15"
            assert get_seoul_tomorrow_str() == "2026-10-16"

            assert resolve_date_str("today") == "2026-10-15"
            assert resolve_date_str("TODAY") == "2026-10-15"
            assert resolve_date_str("  today  ") == "2026-10-15"

            assert resolve_date_str("tomorrow") == "2026-10-16"
            assert resolve_date_str("TOMORROW") == "2026-10-16"
            assert resolve_date_str("  tomorrow  ") == "2026-10-16"

            assert resolve_date_str(None) == "2026-10-15"
            assert resolve_date_str("") == "2026-10-15"
            assert resolve_date_str("   ") == "2026-10-15"

            # Explicit dates must remain unchanged
            assert resolve_date_str("2026-12-25") == "2026-12-25"
            assert resolve_date_str("  2027-01-01  ") == "2027-01-01"

    def test_resolve_date_str_midnight_boundary(self):
        """Test date resolution across midnight boundary in Asia/Seoul."""
        # 1. 23:59:59 on Oct 15
        before_midnight = datetime(2026, 10, 15, 23, 59, 59, tzinfo=SEOUL_TZ)
        with patch("meeting_room_bot.utils.date_utils.get_seoul_now", return_value=before_midnight):
            assert resolve_date_str("today") == "2026-10-15"
            assert resolve_date_str("tomorrow") == "2026-10-16"

        # 2. 00:00:01 on Oct 16
        after_midnight = datetime(2026, 10, 16, 0, 0, 1, tzinfo=SEOUL_TZ)
        with patch("meeting_room_bot.utils.date_utils.get_seoul_now", return_value=after_midnight):
            assert resolve_date_str("today") == "2026-10-16"
            assert resolve_date_str("tomorrow") == "2026-10-17"


class TestRealProviderDynamicDate:
    """Verify RealMeetingRoomProvider resolves dates dynamically without hardcoding."""

    @pytest.fixture
    def setup_provider(self):
        session_mgr = UserSessionManager()
        fav_svc = MagicMock(spec=FavoriteService)
        provider = RealMeetingRoomProvider(session_mgr=session_mgr, favorite_service=fav_svc)

        uk = UserKey("telegram", "test_user_date")
        mock_client = MagicMock(spec=GroupwareClient)
        mock_client.is_authenticated = True
        session_mgr.set_client(uk, mock_client)

        mock_svc = MagicMock(spec=MeetingRoomService)
        provider._get_service = MagicMock(return_value=mock_svc)
        fav_svc.get_favorite_rooms.return_value = [(MagicMock(id=1), MagicMock(id=101, name="Room 101"))]
        mock_svc.get_available_favorite_rooms_at.return_value = [
            {"available_rooms": [MagicMock(name="Room 101")], "unavailable_rooms": []}
        ]
        mock_svc.get_available_rooms_at.return_value = [
            {"available_rooms": [MagicMock(name="Room 101")], "unavailable_rooms": []}
        ]

        return provider, uk, mock_svc

    def test_real_provider_date_today_resolution(self, setup_provider):
        """date_str='today' resolves to current Seoul date."""
        provider, uk, mock_svc = setup_provider
        fixed_now = datetime(2026, 10, 15, 11, 0, tzinfo=SEOUL_TZ)

        with patch("meeting_room_bot.utils.date_utils.get_seoul_now", return_value=fixed_now):
            res = provider.get_available_rooms_at(uk, date_str="today", start_time="14:00", duration=60, scope="fav")
            assert res.status == QueryStatus.SUCCESS

            call_kwargs = mock_svc.get_available_favorite_rooms_at.call_args[1]
            st_dt = call_kwargs["start_time"]
            assert st_dt == datetime(2026, 10, 15, 14, 0, tzinfo=SEOUL_TZ)

    def test_real_provider_date_tomorrow_resolution(self, setup_provider):
        """date_str='tomorrow' resolves to current Seoul date + 1 day."""
        provider, uk, mock_svc = setup_provider
        fixed_now = datetime(2026, 10, 15, 11, 0, tzinfo=SEOUL_TZ)

        with patch("meeting_room_bot.utils.date_utils.get_seoul_now", return_value=fixed_now):
            res = provider.get_available_rooms_at(uk, date_str="tomorrow", start_time="10:00", duration=30, scope="fav")
            assert res.status == QueryStatus.SUCCESS

            call_kwargs = mock_svc.get_available_favorite_rooms_at.call_args[1]
            st_dt = call_kwargs["start_time"]
            assert st_dt == datetime(2026, 10, 16, 10, 0, tzinfo=SEOUL_TZ)

    def test_real_provider_explicit_date_preserved(self, setup_provider):
        """Explicit YYYY-MM-DD string is preserved exactly."""
        provider, uk, mock_svc = setup_provider
        fixed_now = datetime(2026, 10, 15, 11, 0, tzinfo=SEOUL_TZ)

        with patch("meeting_room_bot.utils.date_utils.get_seoul_now", return_value=fixed_now):
            res = provider.get_available_rooms_at(uk, date_str="2026-12-25", start_time="15:00", duration=60, scope="fav")
            assert res.status == QueryStatus.SUCCESS

            call_kwargs = mock_svc.get_available_favorite_rooms_at.call_args[1]
            st_dt = call_kwargs["start_time"]
            assert st_dt == datetime(2026, 12, 25, 15, 0, tzinfo=SEOUL_TZ)


class TestTelegramWhenFlowDynamicDate:
    """Verify Telegram handlers dynamically store and propagate current Seoul date."""

    def _make_mock_update_and_query(self, user_id: str = "user_when_date"):
        update = MagicMock()
        query = AsyncMock()
        query.from_user.id = user_id
        update.effective_user.id = user_id
        update.callback_query = query
        context = MagicMock()
        return update, query, context

    @pytest.mark.anyio
    async def test_when_entry_stores_current_seoul_date(self):
        """Entering WHEN menu stores dynamic Seoul today date in state."""
        update, query, context = self._make_mock_update_and_query("user_date_1")
        query.data = CB_MENU_WHEN

        mock_provider = MagicMock()
        mock_provider.check_authentication.return_value = QueryResult(status=QueryStatus.SUCCESS)
        set_query_provider(mock_provider)

        fixed_now = datetime(2026, 10, 15, 9, 30, tzinfo=SEOUL_TZ)
        with patch("meeting_room_bot.telegram.handlers.get_seoul_today_str", return_value="2026-10-15"):
            await button_callback(update, context)

            state = user_state_mgr.get_state("user_date_1")
            assert state.get("date") == "2026-10-15"
            assert state.get("last_menu") == "when_time"

    @pytest.mark.anyio
    async def test_when_flow_full_step_and_scope_switching_preserves_date(self):
        """Full WHEN flow propagates dynamic date to provider and preserves it during scope switch."""
        uid = "user_date_flow"
        user_state_mgr.reset_state(uid)

        mock_provider = MagicMock()
        mock_provider.check_authentication.return_value = QueryResult(status=QueryStatus.SUCCESS)
        mock_provider.get_available_rooms_at.return_value = QueryResult(
            status=QueryStatus.SUCCESS,
            data={"rooms": ["Room 1"], "date": "2026-10-15", "start_time": "14:00", "end_time": "15:00"},
        )
        set_query_provider(mock_provider)

        fixed_now = datetime(2026, 10, 15, 9, 30, tzinfo=SEOUL_TZ)
        with patch("meeting_room_bot.telegram.handlers.get_seoul_today_str", return_value="2026-10-15"), \
             patch("meeting_room_bot.telegram.handlers.resolve_date_str", side_effect=resolve_date_str), \
             patch("meeting_room_bot.utils.date_utils.get_seoul_now", return_value=fixed_now):

            # 1. Entry: menu:when
            update, query, context = self._make_mock_update_and_query(uid)
            query.data = CB_MENU_WHEN
            await button_callback(update, context)
            assert user_state_mgr.get_state(uid)["date"] == "2026-10-15"

            # 2. Select Time: time:1400
            query.data = f"{CB_TIME_PREFIX}1400"
            await button_callback(update, context)
            assert user_state_mgr.get_state(uid)["time"] == "14:00"
            assert user_state_mgr.get_state(uid)["date"] == "2026-10-15"

            # 3. Select Duration: dur:60 -> calls provider with date="2026-10-15"
            query.data = f"{CB_DUR_PREFIX}60"
            await button_callback(update, context)

            call_args = mock_provider.get_available_rooms_at.call_args[1]
            assert call_args["date_str"] == "2026-10-15"
            assert call_args["start_time"] == "14:00"
            assert call_args["duration"] == 60

            # 4. Switch scope to ALL: scope:all -> retains date="2026-10-15"
            query.data = CB_SCOPE_ALL
            await button_callback(update, context)

            call_args_scope = mock_provider.get_available_rooms_at.call_args[1]
            assert call_args_scope["date_str"] == "2026-10-15"
            assert call_args_scope["scope"] == "all"

    @pytest.mark.anyio
    async def test_date_today_and_tomorrow_callbacks_dynamic_resolution(self):
        """Date callbacks resolve TODAY and TOMORROW dynamically."""
        uid = "user_date_cb"
        user_state_mgr.reset_state(uid)

        mock_provider = MagicMock()
        mock_provider.check_authentication.return_value = QueryResult(status=QueryStatus.SUCCESS)
        set_query_provider(mock_provider)

        fixed_now = datetime(2026, 10, 15, 12, 0, tzinfo=SEOUL_TZ)
        with patch("meeting_room_bot.telegram.handlers.get_seoul_today_str", return_value="2026-10-15"), \
             patch("meeting_room_bot.telegram.handlers.get_seoul_tomorrow_str", return_value="2026-10-16"):

            # CB_DATE_TODAY
            update, query, context = self._make_mock_update_and_query(uid)
            query.data = CB_DATE_TODAY
            await button_callback(update, context)
            assert user_state_mgr.get_state(uid)["date"] == "2026-10-15"

            # CB_DATE_TOMORROW
            query.data = CB_DATE_TOMORROW
            await button_callback(update, context)
            assert user_state_mgr.get_state(uid)["date"] == "2026-10-16"
