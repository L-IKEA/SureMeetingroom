"""Telegram Bot Async Event Handlers."""

import logging
from typing import Optional, Union
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest

from meeting_room_bot.favorites.json_repository import JsonFavoriteRepository
from meeting_room_bot.favorites.service import FavoriteService
from meeting_room_bot.models.user_key import UserKey
from meeting_room_bot.providers.base import (
    MeetingRoomQueryProvider,
    QueryResult,
    QueryStatus,
)
from meeting_room_bot.providers.mock_provider import MockMeetingRoomProvider
from meeting_room_bot.telegram.keyboards import (
    expired_keyboard,
    fav_add_asset_keyboard,
    fav_add_room_keyboard,
    fav_added_result_keyboard,
    fav_delete_keyboard,
    fav_select_asset_keyboard,
    favorites_keyboard,
    main_menu_keyboard,
    no_favorites_guidance_keyboard,
    result_now_keyboard,
    result_when_keyboard,
    room_detail_keyboard,
    session_expired_keyboard,
    unauthenticated_keyboard,
    when_date_keyboard,
    when_duration_keyboard,
    when_time_keyboard,
    where_location_keyboard,
    where_room_keyboard,
)
from meeting_room_bot.telegram.states import (
    CB_ASSET_PREFIX,
    CB_AUTH_CONNECT,
    CB_DATE_TODAY,
    CB_DATE_TOMORROW,
    CB_DUR_PREFIX,
    CB_FAV_ADD_ASSET,
    CB_FAV_ADD_ASSET_PREFIX,
    CB_FAV_ADD_ROOM,
    CB_FAV_ADD_ROOM_PREFIX,
    CB_FAV_DEL_ASSET_PREFIX,
    CB_FAV_DEL_ROOM_PREFIX,
    CB_FAV_REMOVE,
    CB_FAV_SEL_ASSET_PREFIX,
    CB_MENU_FAV,
    CB_MENU_NOW,
    CB_MENU_WHEN,
    CB_MENU_WHERE,
    CB_NAV_BACK,
    CB_NAV_HOME,
    CB_REFRESH_NOW,
    CB_ROOM_PREFIX,
    CB_SCOPE_ALL,
    CB_SCOPE_FAV,
    CB_TIME_PREFIX,
    user_state_mgr,
)

logger = logging.getLogger(__name__)

fav_service = FavoriteService(JsonFavoriteRepository())


async def safe_edit_message_text(query, text: str, reply_markup=None):
    """Edit message text safely, ignoring Telegram BadRequest 'Message is not modified' error."""
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except BadRequest as e:
        if "Message is not modified" in str(e):
            logger.debug("Message is not modified, ignoring duplicate edit.")
            return
        raise

# Active query provider instance (Dependency Injected)
_active_provider: MeetingRoomQueryProvider = MockMeetingRoomProvider()


def get_query_provider() -> MeetingRoomQueryProvider:
    """Get active query provider instance."""
    return _active_provider


def set_query_provider(provider: MeetingRoomQueryProvider):
    """Set active query provider instance."""
    global _active_provider
    _active_provider = provider


async def handle_unauthenticated_or_expired(query, status: QueryStatus, user_id: Union[UserKey, str] = "default_user") -> bool:
    """Check status and edit message if unauthenticated or expired. Return True if handled."""
    from meeting_room_bot.account_link.token_service import token_service
    from meeting_room_bot.telegram.keyboards import is_localhost_url
    import os

    base_url = os.environ.get("ACCOUNT_LINK_BASE_URL", "http://localhost:8000").rstrip("/")
    is_dev = is_localhost_url(base_url)

    user_key = UserKey.from_any(user_id)
    platform_uid = user_key.platform_user_id

    if status == QueryStatus.NOT_AUTHENTICATED:
        if is_dev:
            token = token_service.create_token(user_key)
            link_url = f"{base_url}/link/{token}"
            logger.info(f"\n[DEV] Account linking required for user_id: {platform_uid}\n[DEV] Open this URL in the PC browser:\n{link_url}\n")
            text = (
                "🔐 그룹웨어 계정 연결이 필요합니다.\n\n"
                "현재 로컬 개발 모드입니다.\n"
                "PC 브라우저에서 계정 연결을 진행해주세요."
            )
        else:
            text = (
                "🔐 그룹웨어 계정 연결이 필요합니다.\n\n"
                "회사 계정을 연결한 후 회의실 조회가 가능합니다."
            )
        await safe_edit_message_text(query, text, reply_markup=unauthenticated_keyboard(platform_uid))
        return True

    elif status == QueryStatus.SESSION_EXPIRED:
        if is_dev:
            token = token_service.create_token(user_key)
            link_url = f"{base_url}/link/{token}"
            logger.info(f"\n[DEV] Session expired for user_id: {platform_uid}\n[DEV] Open this URL in the PC browser to reconnect:\n{link_url}\n")
            text = (
                "🔐 그룹웨어 로그인 세션이 만료되었습니다.\n\n"
                "현재 로컬 개발 모드입니다.\n"
                "PC 브라우저에서 다시 연결해주세요."
            )
        else:
            text = (
                "🔐 그룹웨어 로그인 세션이 만료되었습니다.\n\n"
                "다시 로그인하여 계정을 연결해주세요."
            )
        await safe_edit_message_text(query, text, reply_markup=session_expired_keyboard(platform_uid))
        return True
    elif status == QueryStatus.NO_FAVORITES:
        text = (
            "⭐ 등록된 즐겨찾기가 없습니다.\n\n"
            "자주 사용하는 층이나 회의실을 등록하면\n"
            "필요한 회의실만 빠르게 확인할 수 있습니다."
        )
        await safe_edit_message_text(query, text, reply_markup=no_favorites_guidance_keyboard())
        return True
    elif status == QueryStatus.REQUEST_STATE_EXPIRED:
        text = "⚠️ 요청 상태가 만료되었습니다."
        await safe_edit_message_text(query, text, reply_markup=expired_keyboard())
        return True
    elif status in (QueryStatus.GROUPWARE_API_ERROR, QueryStatus.NETWORK_ERROR):
        text = "⚠️ 그룹웨어 서비스 조회 중 오류가 발생했습니다."
        await safe_edit_message_text(query, text, reply_markup=expired_keyboard())
        return True
    return False


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start command."""
    if not update.effective_user or not update.message:
        return

    user_id = str(update.effective_user.id)

    # Reset ONLY temporary UI flow state
    user_state_mgr.reset_state(user_id)

    text = "🤖 회의실 도우미\n\n원하는 기능을 선택하세요."
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for all InlineKeyboard callback queries."""
    query = update.callback_query
    if not query or not update.effective_user:
        return

    await query.answer()

    user_id = str(update.effective_user.id)
    user_key = UserKey(platform="telegram", platform_user_id=user_id)
    data = query.data or ""
    state = user_state_mgr.get_state(user_id)
    provider = get_query_provider()

    try:
        logger.info(f"[telegram] user_id={user_id} callback={data}")

        # Account Connect Callback
        if data == CB_AUTH_CONNECT:
            text = (
                "🔐 그룹웨어 계정 연결\n\n"
                "아래 버튼을 눌러 그룹웨어 계정으로 로그인해주세요."
            )
            await safe_edit_message_text(query, text, reply_markup=unauthenticated_keyboard(user_id))
            return

        # Account Unlink Callback
        if data == "auth:unlink":
            from meeting_room_bot.auth.session_manager import session_manager
            session_manager.remove_session(user_key)
            text = "🔓 그룹웨어 계정 연결이 해제되었습니다."
            await safe_edit_message_text(query, text, reply_markup=expired_keyboard())
            return

        # 1. Navigation Home: ALWAYS reset UI state and render main menu cleanly
        if data == CB_NAV_HOME:
            user_state_mgr.reset_state(user_id)
            text = "🤖 회의실 도우미\n\n원하는 기능을 선택하세요."
            await safe_edit_message_text(query, text, reply_markup=main_menu_keyboard())
            return

        # 2. Navigation Back
        if data == CB_NAV_BACK:
            last_menu = state.get("last_menu", "home")
            if last_menu == "when_dur":
                user_state_mgr.update_state(user_id, last_menu="when_time")
                await safe_edit_message_text(query, "시작 시간을 선택하세요.", reply_markup=when_time_keyboard())
            else:
                user_state_mgr.reset_state(user_id)
                await safe_edit_message_text(query, "🤖 회의실 도우미\n\n원하는 기능을 선택하세요.", reply_markup=main_menu_keyboard())
            return

        # 3. Main Menu: 지금 빈 회의실
        if data == CB_MENU_NOW:
            logger.info(f"[telegram] user_id={user_id} callback=menu:now starting NOW flow")
            user_state_mgr.update_state(user_id, last_menu="now", scope="fav")
            res = provider.get_available_rooms_now(user_id=user_key, scope="fav")

            if await handle_unauthenticated_or_expired(query, res.status, user_key):
                return

            lines = ["🟢 현재 빈 회의실", res.data.get("scope_title", ""), ""]
            for group in res.data.get("groups", []):
                lines.append(f"[{group['asset_name']}]")
                lines.append("")
                for r in group["rooms"]:
                    lines.append(f"🟢 {r['name']}")
                    lines.append(f"   {r['note']}")
                    lines.append("")

            text = "\n".join(lines).strip()
            await safe_edit_message_text(query, text, reply_markup=result_now_keyboard(scope="fav"))
            return

        # 4. Main Menu: 언제 빈 회의실 (Check Auth at Entry!)
        if data == CB_MENU_WHEN:
            logger.info(f"[telegram] user_id={user_id} callback=menu:when starting WHEN flow")
            auth_res = provider.check_authentication(user_key)
            if await handle_unauthenticated_or_expired(query, auth_res.status, user_key):
                return

            user_state_mgr.update_state(user_id, last_menu="when_time", date="2026-08-11")
            await safe_edit_message_text(query, "시작 시간을 선택하세요.", reply_markup=when_time_keyboard())
            return

        # 5. Main Menu: 어디 빈 회의실
        if data == CB_MENU_WHERE:
            logger.info(f"[telegram] user_id={user_id} callback=menu:where starting WHERE flow")
            user_state_mgr.update_state(user_id, last_menu="where")
            res = provider.get_locations(user_id=user_key)

            if await handle_unauthenticated_or_expired(query, res.status, user_key):
                return

            locations = res.data.get("locations", [])
            await safe_edit_message_text(
                query,
                "어디 빈 회의실 - 위치 선택:",
                reply_markup=where_location_keyboard(locations),
            )
            return

        # 6. Main Menu: 즐겨찾기 관리
        if data == CB_MENU_FAV:
            logger.info(f"[telegram] user_id={user_id} callback=menu:fav starting FAVORITES flow")
            user_state_mgr.update_state(user_id, last_menu="fav")
            auth_res = provider.check_authentication(user_key)
            if await handle_unauthenticated_or_expired(query, auth_res.status, user_key):
                return

            uf = fav_service.get_user_favorites(user_key)
            if uf.is_empty():
                text = "⭐ 내 즐겨찾기\n\n등록된 즐겨찾기가 없습니다.\n\n위치나 회의실을 등록해보세요."
                await safe_edit_message_text(query, text, reply_markup=favorites_keyboard())
                return

            # Resolve location and room names using provider
            loc_res = provider.get_locations(user_id=user_key)
            asset_name_map = {}
            if loc_res.status == QueryStatus.SUCCESS:
                for loc in loc_res.data.get("locations", []):
                    asset_name_map[loc["id"]] = loc.get("name", f"Asset {loc['id']}")

            asset_lines = []
            for aid in uf.favorite_assets:
                asset_lines.append(f"- {asset_name_map.get(aid, f'위치 {aid}')}")

            room_lines = []
            for rid in uf.favorite_rooms:
                room_lines.append(f"- 회의실 ID: {rid}")

            assets_str = "\n".join(asset_lines) if asset_lines else "(없음)"
            rooms_str = "\n".join(room_lines) if room_lines else "(없음)"

            text = f"⭐ 내 즐겨찾기\n\n🏢 위치\n{assets_str}\n\n🚪 회의실\n{rooms_str}"
            await safe_edit_message_text(query, text, reply_markup=favorites_keyboard())
            return

        # 7. Scope Queries: 전체 위치로 조회 (CB_SCOPE_ALL) or 즐겨찾기 기준 (CB_SCOPE_FAV)
        if data in (CB_SCOPE_ALL, CB_SCOPE_FAV):
            target_scope = "all" if data == CB_SCOPE_ALL else "fav"
            last_menu = state.get("last_menu", "now")
            user_state_mgr.update_state(user_id, scope=target_scope)

            if "when" in last_menu:
                date_val = state.get("date", "2026-08-11")
                time_val = state.get("time", "14:00")
                dur_val = state.get("duration", 60)

                res = provider.get_available_rooms_at(
                    user_id=user_key,
                    date_str=date_val,
                    start_time=time_val,
                    duration=dur_val,
                    scope=target_scope,
                )

                if await handle_unauthenticated_or_expired(query, res.status, user_key):
                    return

                header = "사용 가능한 회의실 (전체 위치)" if target_scope == "all" else "사용 가능한 회의실"
                lines = [
                    f"🕐 {res.data.get('date', date_val)}",
                    f"{res.data.get('start_time', time_val)} ~ {res.data.get('end_time', '')}",
                    "",
                    header,
                    "",
                ]
                for room_str in res.data.get("available_rooms", []):
                    lines.append(room_str)

                text = "\n".join(lines).strip()
                await safe_edit_message_text(query, text, reply_markup=result_when_keyboard(scope=target_scope))
                return

            else:  # Default 'now'
                res = provider.get_available_rooms_now(user_id=user_key, scope=target_scope)

                if await handle_unauthenticated_or_expired(query, res.status, user_key):
                    return

                lines = ["🟢 현재 빈 회의실", res.data.get("scope_title", ""), ""]
                for group in res.data.get("groups", []):
                    lines.append(f"[{group['asset_name']}]")
                    lines.append("")
                    for r in group["rooms"]:
                        lines.append(f"🟢 {r['name']}")
                        lines.append(f"   {r['note']}")
                        lines.append("")

                text = "\n".join(lines).strip()
                await safe_edit_message_text(query, text, reply_markup=result_now_keyboard(scope=target_scope))
                return

        # 8. Refresh Now
        if data == CB_REFRESH_NOW:
            curr_scope = state.get("scope", "fav")
            res = provider.get_available_rooms_now(user_id=user_key, scope=curr_scope)

            if await handle_unauthenticated_or_expired(query, res.status, user_key):
                return

            lines = ["🟢 현재 빈 회의실 (새로고침)", res.data.get("scope_title", ""), ""]
            for group in res.data.get("groups", []):
                lines.append(f"[{group['asset_name']}]")
                lines.append("")
                for r in group["rooms"]:
                    lines.append(f"🟢 {r['name']}")
                    lines.append(f"   {r['note']}")
                    lines.append("")
            text = "\n".join(lines).strip()
            await safe_edit_message_text(query, text, reply_markup=result_now_keyboard(scope=curr_scope))
            return

        # 9. When flow steps: Date, Time, Duration
        if data in (CB_DATE_TODAY, CB_DATE_TOMORROW):
            auth_res = provider.check_authentication(user_key)
            if await handle_unauthenticated_or_expired(query, auth_res.status, user_key):
                return

            date_val = "2026-08-11" if data == CB_DATE_TODAY else "2026-08-12"
            user_state_mgr.update_state(user_id, date=date_val, last_menu="when_time")
            await safe_edit_message_text(query, "시작 시간을 선택하세요.", reply_markup=when_time_keyboard())
            return

        if data.startswith(CB_TIME_PREFIX):
            auth_res = provider.check_authentication(user_key)
            if await handle_unauthenticated_or_expired(query, auth_res.status, user_key):
                return

            time_raw = data.replace(CB_TIME_PREFIX, "")  # e.g. "1400"
            formatted_time = f"{time_raw[:2]}:{time_raw[2:]}"
            logger.info(f"[telegram] user_id={user_id} callback={data} start_time stored: {formatted_time}")
            user_state_mgr.update_state(user_id, time=formatted_time, last_menu="when_dur")
            await safe_edit_message_text(query, "사용 시간을 선택하세요.", reply_markup=when_duration_keyboard())
            return

        if data.startswith(CB_DUR_PREFIX):
            auth_res = provider.check_authentication(user_key)
            if await handle_unauthenticated_or_expired(query, auth_res.status, user_key):
                return

            # Multi-step state validation: Check if time was selected
            has_time = "time" in state
            logger.info(f"[telegram] user_id={user_id} callback={data} start_time exists={has_time}")
            if not has_time:
                await handle_unauthenticated_or_expired(query, QueryStatus.REQUEST_STATE_EXPIRED, user_key)
                return

            dur_val = int(data.replace(CB_DUR_PREFIX, ""))
            user_state_mgr.update_state(user_id, duration=dur_val, last_menu="when", scope="fav")

            date_val = state.get("date", "2026-08-11")
            time_val = state.get("time", "14:00")

            res = provider.get_available_rooms_at(
                user_id=user_key,
                date_str=date_val,
                start_time=time_val,
                duration=dur_val,
                scope="fav",
            )

            if await handle_unauthenticated_or_expired(query, res.status, user_key):
                return

            lines = [
                f"🕐 {res.data.get('date', date_val)}",
                f"{res.data.get('start_time', time_val)} ~ {res.data.get('end_time', '')}",
                "",
                "사용 가능한 회의실",
                "",
            ]
            for room_str in res.data.get("available_rooms", []):
                lines.append(room_str)

            text = "\n".join(lines).strip()
            await safe_edit_message_text(query, text, reply_markup=result_when_keyboard(scope="fav"))
            return

        # 10. Select Asset Location
        if data.startswith(CB_ASSET_PREFIX):
            asset_id = int(data.replace(CB_ASSET_PREFIX, ""))
            user_state_mgr.update_state(user_id, asset_id=asset_id, last_menu="where_asset")

            res = provider.get_location_status(user_id=user_key, asset_id=asset_id)

            if await handle_unauthenticated_or_expired(query, res.status, user_key):
                return

            loc_status = res.data
            lines = [f"🏢 {loc_status.get('asset_name', '')}", ""]

            for r in loc_status.get("rooms", []):
                lines.append(f"{r['status']} {r['name']}")
                if r.get("note"):
                    lines.append(f"   {r['note']}")
                lines.append("")

            text = "\n".join(lines).strip()
            await safe_edit_message_text(
                query, text, reply_markup=where_room_keyboard(asset_id, loc_status.get("rooms", []))
            )
            return

        # 11. Select Room Detail
        if data.startswith(CB_ROOM_PREFIX):
            room_id = int(data.replace(CB_ROOM_PREFIX, ""))
            asset_id = state.get("asset_id", 50)
            res = provider.get_room_detail(user_id=user_key, asset_id=asset_id, room_id=room_id)

            if await handle_unauthenticated_or_expired(query, res.status, user_key):
                return

            detail = res.data
            lines = [
                f"🚪 {detail['name']}",
                "",
                f"정원: {detail.get('capacity', 6)}인",
                f"현재 상태: {detail.get('status_text', '')}",
                "",
                "오늘 예약 일정",
                "",
            ]
            if detail.get("schedules"):
                for sched in detail["schedules"]:
                    lines.append(f"- {sched}")
            else:
                lines.append("- 예약 없음")

            text = "\n".join(lines).strip()
            await safe_edit_message_text(query, text, reply_markup=room_detail_keyboard(detail.get("asset_id", asset_id)))
            return

        # 12. Favorite Flow: Add Asset Location
        if data == CB_FAV_ADD_ASSET:
            auth_res = provider.check_authentication(user_key)
            if await handle_unauthenticated_or_expired(query, auth_res.status, user_key):
                return

            res = provider.get_locations(user_id=user_key)
            if await handle_unauthenticated_or_expired(query, res.status, user_key):
                return

            locations = res.data.get("locations", [])
            await safe_edit_message_text(
                query,
                "⭐ 즐겨찾기에 추가할 위치를 선택하세요.",
                reply_markup=fav_add_asset_keyboard(locations),
            )
            return

        if data.startswith(CB_FAV_ADD_ASSET_PREFIX):
            auth_res = provider.check_authentication(user_key)
            if await handle_unauthenticated_or_expired(query, auth_res.status, user_key):
                return

            asset_id = int(data.replace(CB_FAV_ADD_ASSET_PREFIX, ""))
            added = fav_service.add_asset(user_key, asset_id)

            res = provider.get_locations(user_id=user_key)
            asset_name = f"위치 {asset_id}"
            if res.status == QueryStatus.SUCCESS:
                for loc in res.data.get("locations", []):
                    if loc["id"] == asset_id:
                        asset_name = loc.get("name", asset_name)
                        break

            if added:
                text = f"✅ 즐겨찾기에 추가했습니다.\n\n🏢 {asset_name}"
            else:
                text = f"ℹ️ 이미 즐겨찾기에 등록된 위치입니다.\n\n🏢 {asset_name}"

            await safe_edit_message_text(query, text, reply_markup=fav_added_result_keyboard("asset"))
            return

        # 13. Favorite Flow: Add Room
        if data == CB_FAV_ADD_ROOM:
            auth_res = provider.check_authentication(user_key)
            if await handle_unauthenticated_or_expired(query, auth_res.status, user_key):
                return

            res = provider.get_locations(user_id=user_key)
            if await handle_unauthenticated_or_expired(query, res.status, user_key):
                return

            locations = res.data.get("locations", [])
            await safe_edit_message_text(
                query,
                "⭐ 회의실을 추가할 위치를 선택하세요.",
                reply_markup=fav_select_asset_keyboard(locations),
            )
            return

        if data.startswith(CB_FAV_SEL_ASSET_PREFIX):
            auth_res = provider.check_authentication(user_key)
            if await handle_unauthenticated_or_expired(query, auth_res.status, user_key):
                return

            asset_id = int(data.replace(CB_FAV_SEL_ASSET_PREFIX, ""))
            user_state_mgr.update_state(user_id, asset_id=asset_id)
            res = provider.get_location_status(user_id=user_key, asset_id=asset_id)
            if await handle_unauthenticated_or_expired(query, res.status, user_key):
                return

            rooms = res.data.get("rooms", [])
            await safe_edit_message_text(
                query,
                "⭐ 즐겨찾기에 추가할 회의실을 선택하세요.",
                reply_markup=fav_add_room_keyboard(asset_id, rooms),
            )
            return

        if data.startswith(CB_FAV_ADD_ROOM_PREFIX):
            auth_res = provider.check_authentication(user_key)
            if await handle_unauthenticated_or_expired(query, auth_res.status, user_key):
                return

            room_id = int(data.replace(CB_FAV_ADD_ROOM_PREFIX, ""))
            added = fav_service.add_room(user_key, room_id)

            if added:
                text = f"✅ 즐겨찾기에 추가했습니다.\n\n🚪 회의실 (ID: {room_id})"
            else:
                text = f"ℹ️ 이미 즐겨찾기에 등록된 회의실입니다.\n\n🚪 회의실 (ID: {room_id})"

            await safe_edit_message_text(query, text, reply_markup=fav_added_result_keyboard("room"))
            return

        # 14. Favorite Flow: Remove Item
        if data == CB_FAV_REMOVE:
            auth_res = provider.check_authentication(user_key)
            if await handle_unauthenticated_or_expired(query, auth_res.status, user_key):
                return

            uf = fav_service.get_user_favorites(user_key)
            if uf.is_empty():
                text = "⭐ 삭제할 즐겨찾기 항목이 없습니다."
                await safe_edit_message_text(query, text, reply_markup=favorites_keyboard())
                return

            loc_res = provider.get_locations(user_id=user_key)
            asset_items = []
            if loc_res.status == QueryStatus.SUCCESS:
                for loc in loc_res.data.get("locations", []):
                    if loc["id"] in uf.favorite_assets:
                        asset_items.append(loc)

            room_items = [{"id": rid, "name": f"회의실 {rid}"} for rid in uf.favorite_rooms]

            text = "➖ 삭제할 즐겨찾기 항목을 선택하세요."
            await safe_edit_message_text(query, text, reply_markup=fav_delete_keyboard(asset_items, room_items))
            return

        if data.startswith(CB_FAV_DEL_ASSET_PREFIX):
            auth_res = provider.check_authentication(user_key)
            if await handle_unauthenticated_or_expired(query, auth_res.status, user_key):
                return

            asset_id = int(data.replace(CB_FAV_DEL_ASSET_PREFIX, ""))
            fav_service.remove_asset(user_key, asset_id)
            text = "✅ 즐겨찾기에서 삭제했습니다."
            await safe_edit_message_text(query, text, reply_markup=fav_added_result_keyboard("asset"))
            return

        if data.startswith(CB_FAV_DEL_ROOM_PREFIX):
            auth_res = provider.check_authentication(user_key)
            if await handle_unauthenticated_or_expired(query, auth_res.status, user_key):
                return

            room_id = int(data.replace(CB_FAV_DEL_ROOM_PREFIX, ""))
            fav_service.remove_room(user_key, room_id)
            text = "✅ 즐겨찾기에서 삭제했습니다."
            await safe_edit_message_text(query, text, reply_markup=fav_added_result_keyboard("room"))
            return

        # True multi-step state loss fallback for unhandled data
        await handle_unauthenticated_or_expired(query, QueryStatus.REQUEST_STATE_EXPIRED, user_key)

    except BadRequest as e:
        if "Message is not modified" in str(e):
            logger.debug(f"[telegram] Message is not modified for user_id={user_id}: {e}")
            return
        logger.error(f"[telegram] Telegram BadRequest for user_id={user_id}: {e}")
        await handle_unauthenticated_or_expired(query, QueryStatus.REQUEST_STATE_EXPIRED, user_key)
    except Exception as e:
        logger.error(f"Error handling callback_data '{data}': {e}", exc_info=True)
        auth_check = provider.check_authentication(user_key)
        if auth_check.status == QueryStatus.NOT_AUTHENTICATED:
            await handle_unauthenticated_or_expired(query, QueryStatus.NOT_AUTHENTICATED, user_key)
        else:
            await handle_unauthenticated_or_expired(query, QueryStatus.REQUEST_STATE_EXPIRED, user_key)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Global exception handler for Telegram bot."""
    logger.error("Exception while handling Telegram update:", exc_info=context.error)
