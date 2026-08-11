"""Telegram Bot Async Event Handlers."""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from meeting_room_bot.telegram.keyboards import (
    expired_keyboard,
    favorites_keyboard,
    main_menu_keyboard,
    no_favorites_guidance_keyboard,
    result_now_keyboard,
    result_when_keyboard,
    room_detail_keyboard,
    when_date_keyboard,
    when_duration_keyboard,
    when_time_keyboard,
    where_location_keyboard,
    where_room_keyboard,
)
from meeting_room_bot.telegram.mock_service import MockTelegramService
from meeting_room_bot.telegram.states import (
    CB_ASSET_PREFIX,
    CB_DATE_TODAY,
    CB_DATE_TOMORROW,
    CB_DUR_PREFIX,
    CB_FAV_ADD_ASSET,
    CB_FAV_ADD_ROOM,
    CB_FAV_REMOVE,
    CB_MENU_FAV,
    CB_MENU_NOW,
    CB_MENU_WHEN,
    CB_MENU_WHERE,
    CB_NAV_BACK,
    CB_NAV_HOME,
    CB_PAGE_PREFIX,
    CB_REFRESH_NOW,
    CB_ROOM_PREFIX,
    CB_SCOPE_ALL,
    CB_SCOPE_FAV,
    CB_TIME_PREFIX,
    user_state_mgr,
)

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /start command."""
    if not update.effective_user or not update.message:
        return

    user_id = str(update.effective_user.id)
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
    data = query.data or ""
    state = user_state_mgr.get_state(user_id)

    try:
        # 1. Navigation Home
        if data == CB_NAV_HOME:
            user_state_mgr.reset_state(user_id)
            text = "🤖 회의실 도우미\n\n원하는 기능을 선택하세요."
            await query.edit_message_text(text, reply_markup=main_menu_keyboard())
            return

        # 2. Navigation Back
        if data == CB_NAV_BACK:
            last_menu = state.get("last_menu", "home")
            if last_menu == "when_dur":
                user_state_mgr.update_state(user_id, last_menu="when_time")
                await query.edit_message_text("시작 시간을 선택하세요.", reply_markup=when_time_keyboard())
            else:
                user_state_mgr.reset_state(user_id)
                await query.edit_message_text("🤖 회의실 도우미\n\n원하는 기능을 선택하세요.", reply_markup=main_menu_keyboard())
            return

        # 3. Main Menu: 지금 빈 회의실 (Immediate Favorites Result or Guidance)
        if data == CB_MENU_NOW:
            user_state_mgr.update_state(user_id, last_menu="now", scope="fav")

            if not MockTelegramService.has_favorites(user_id):
                text = (
                    "⭐ 등록된 즐겨찾기가 없습니다.\n\n"
                    "자주 사용하는 층이나 회의실을 등록하면\n"
                    "필요한 회의실만 빠르게 확인할 수 있습니다."
                )
                await query.edit_message_text(text, reply_markup=no_favorites_guidance_keyboard())
                return

            mock_res = MockTelegramService.get_mock_available_rooms_now(scope="fav", user_id=user_id)
            lines = ["🟢 현재 빈 회의실", mock_res["scope_title"], ""]
            for group in mock_res["groups"]:
                lines.append(f"[{group['asset_name']}]")
                lines.append("")
                for r in group["rooms"]:
                    lines.append(f"🟢 {r['name']}")
                    lines.append(f"   {r['note']}")
                    lines.append("")

            text = "\n".join(lines).strip()
            await query.edit_message_text(text, reply_markup=result_now_keyboard(scope="fav"))
            return

        # 4. Main Menu: 언제 빈 회의실
        if data == CB_MENU_WHEN:
            user_state_mgr.update_state(user_id, last_menu="when_time", date="2026-08-11")
            await query.edit_message_text("시작 시간을 선택하세요.", reply_markup=when_time_keyboard())
            return

        # 5. Main Menu: 어디 빈 회의실
        if data == CB_MENU_WHERE:
            user_state_mgr.update_state(user_id, last_menu="where")
            locations = MockTelegramService.get_mock_locations()
            await query.edit_message_text(
                "어디 빈 회의실 - 위치 선택:",
                reply_markup=where_location_keyboard(locations),
            )
            return

        # 6. Main Menu: 즐겨찾기 관리
        if data == CB_MENU_FAV:
            user_state_mgr.update_state(user_id, last_menu="fav")
            fav_data = MockTelegramService.get_mock_favorites(user_id)

            assets_str = "\n".join(fav_data["assets"]) if fav_data["assets"] else "(없음)"
            rooms_str = "\n".join(fav_data["rooms"]) if fav_data["rooms"] else "(없음)"

            text = f"⭐ 내 즐겨찾기\n\n위치\n{assets_str}\n\n회의실\n{rooms_str}"
            await query.edit_message_text(text, reply_markup=favorites_keyboard())
            return

        # 7. Scope Queries: 전체 위치로 조회 (CB_SCOPE_ALL) or 즐겨찾기 기준 (CB_SCOPE_FAV)
        if data == CB_SCOPE_ALL:
            last_menu = state.get("last_menu", "now")
            user_state_mgr.update_state(user_id, scope="all")

            if "when" in last_menu:
                date_val = state.get("date", "2026-08-11")
                time_val = state.get("time", "14:00")
                dur_val = state.get("duration", 60)

                mock_res = MockTelegramService.get_mock_available_rooms_at(
                    date_str=date_val, start_time=time_val, duration=dur_val, scope="all", user_id=user_id
                )

                lines = [
                    f"🕐 {mock_res['date']}",
                    f"{mock_res['start_time']} ~ {mock_res['end_time']}",
                    "",
                    "사용 가능한 회의실 (전체 위치)",
                    "",
                ]
                for room_str in mock_res["available_rooms"]:
                    lines.append(room_str)

                text = "\n".join(lines).strip()
                await query.edit_message_text(text, reply_markup=result_when_keyboard(scope="all"))
                return

            else:  # Default 'now'
                mock_res = MockTelegramService.get_mock_available_rooms_now(scope="all", user_id=user_id)
                lines = ["🟢 현재 빈 회의실", mock_res["scope_title"], ""]
                for group in mock_res["groups"]:
                    lines.append(f"[{group['asset_name']}]")
                    lines.append("")
                    for r in group["rooms"]:
                        lines.append(f"🟢 {r['name']}")
                        lines.append(f"   {r['note']}")
                        lines.append("")

                text = "\n".join(lines).strip()
                await query.edit_message_text(text, reply_markup=result_now_keyboard(scope="all"))
                return

        if data == CB_SCOPE_FAV:
            if not MockTelegramService.has_favorites(user_id):
                text = (
                    "⭐ 등록된 즐겨찾기가 없습니다.\n\n"
                    "자주 사용하는 층이나 회의실을 등록하면\n"
                    "필요한 회의실만 빠르게 확인할 수 있습니다."
                )
                await query.edit_message_text(text, reply_markup=no_favorites_guidance_keyboard())
                return

            last_menu = state.get("last_menu", "now")
            user_state_mgr.update_state(user_id, scope="fav")

            if "when" in last_menu:
                date_val = state.get("date", "2026-08-11")
                time_val = state.get("time", "14:00")
                dur_val = state.get("duration", 60)

                mock_res = MockTelegramService.get_mock_available_rooms_at(
                    date_str=date_val, start_time=time_val, duration=dur_val, scope="fav", user_id=user_id
                )

                lines = [
                    f"🕐 {mock_res['date']}",
                    f"{mock_res['start_time']} ~ {mock_res['end_time']}",
                    "",
                    "사용 가능한 회의실",
                    "",
                ]
                for room_str in mock_res["available_rooms"]:
                    lines.append(room_str)

                text = "\n".join(lines).strip()
                await query.edit_message_text(text, reply_markup=result_when_keyboard(scope="fav"))
                return

            else:
                mock_res = MockTelegramService.get_mock_available_rooms_now(scope="fav", user_id=user_id)
                lines = ["🟢 현재 빈 회의실", mock_res["scope_title"], ""]
                for group in mock_res["groups"]:
                    lines.append(f"[{group['asset_name']}]")
                    lines.append("")
                    for r in group["rooms"]:
                        lines.append(f"🟢 {r['name']}")
                        lines.append(f"   {r['note']}")
                        lines.append("")

                text = "\n".join(lines).strip()
                await query.edit_message_text(text, reply_markup=result_now_keyboard(scope="fav"))
                return

        # 8. Refresh Now
        if data == CB_REFRESH_NOW:
            curr_scope = state.get("scope", "fav")
            mock_res = MockTelegramService.get_mock_available_rooms_now(scope=curr_scope, user_id=user_id)
            lines = ["🟢 현재 빈 회의실 (새로고침)", mock_res["scope_title"], ""]
            for group in mock_res["groups"]:
                lines.append(f"[{group['asset_name']}]")
                lines.append("")
                for r in group["rooms"]:
                    lines.append(f"🟢 {r['name']}")
                    lines.append(f"   {r['note']}")
                    lines.append("")
            text = "\n".join(lines).strip()
            await query.edit_message_text(text, reply_markup=result_now_keyboard(scope=curr_scope))
            return

        # 9. When flow steps: Date, Time, Duration
        if data in (CB_DATE_TODAY, CB_DATE_TOMORROW):
            date_val = "2026-08-11" if data == CB_DATE_TODAY else "2026-08-12"
            user_state_mgr.update_state(user_id, date=date_val, last_menu="when_time")
            await query.edit_message_text("시작 시간을 선택하세요.", reply_markup=when_time_keyboard())
            return

        if data.startswith(CB_TIME_PREFIX):
            time_raw = data.replace(CB_TIME_PREFIX, "")  # e.g. "1400"
            formatted_time = f"{time_raw[:2]}:{time_raw[2:]}"
            user_state_mgr.update_state(user_id, time=formatted_time, last_menu="when_dur")
            await query.edit_message_text("사용 시간을 선택하세요.", reply_markup=when_duration_keyboard())
            return

        if data.startswith(CB_DUR_PREFIX):
            dur_val = int(data.replace(CB_DUR_PREFIX, ""))
            user_state_mgr.update_state(user_id, duration=dur_val, last_menu="when", scope="fav")

            if not MockTelegramService.has_favorites(user_id):
                text = (
                    "⭐ 등록된 즐겨찾기가 없습니다.\n\n"
                    "자주 사용하는 층이나 회의실을 등록하면\n"
                    "필요한 회의실만 빠르게 확인할 수 있습니다."
                )
                await query.edit_message_text(text, reply_markup=no_favorites_guidance_keyboard())
                return

            date_val = state.get("date", "2026-08-11")
            time_val = state.get("time", "14:00")

            mock_res = MockTelegramService.get_mock_available_rooms_at(
                date_str=date_val, start_time=time_val, duration=dur_val, scope="fav", user_id=user_id
            )

            lines = [
                f"🕐 {mock_res['date']}",
                f"{mock_res['start_time']} ~ {mock_res['end_time']}",
                "",
                "사용 가능한 회의실",
                "",
            ]
            for room_str in mock_res["available_rooms"]:
                lines.append(room_str)

            text = "\n".join(lines).strip()
            await query.edit_message_text(text, reply_markup=result_when_keyboard(scope="fav"))
            return

        # 10. Location Pagination (Deprecated, fallback to all locations)
        if data.startswith(CB_PAGE_PREFIX):
            locations = MockTelegramService.get_mock_locations()
            await query.edit_message_text(
                "어디 빈 회의실 - 위치 선택:",
                reply_markup=where_location_keyboard(locations),
            )
            return

        # 11. Select Asset Location
        if data.startswith(CB_ASSET_PREFIX):
            asset_id = int(data.replace(CB_ASSET_PREFIX, ""))
            user_state_mgr.update_state(user_id, asset_id=asset_id, last_menu="where_asset")

            loc_status = MockTelegramService.get_mock_location_status(asset_id)
            lines = [f"🏢 {loc_status['asset_name']}", ""]

            for r in loc_status["rooms"]:
                lines.append(f"{r['status']} {r['name']}")
                if r.get("note"):
                    lines.append(f"   {r['note']}")
                lines.append("")

            text = "\n".join(lines).strip()
            await query.edit_message_text(
                text, reply_markup=where_room_keyboard(asset_id, loc_status["rooms"])
            )
            return

        # 12. Select Room Detail
        if data.startswith(CB_ROOM_PREFIX):
            room_id = int(data.replace(CB_ROOM_PREFIX, ""))
            asset_id = state.get("asset_id", 50)
            detail = MockTelegramService.get_mock_room_detail(asset_id, room_id)

            if not detail:
                text = "⚠️ 해당 회의실 정보를 찾을 수 없습니다."
                locations = MockTelegramService.get_mock_locations()
                await query.edit_message_text(text, reply_markup=where_location_keyboard(locations, page=0))
                return

            lines = [
                f"🚪 {detail['name']}",
                "",
                f"정원: {detail['capacity']}인",
                f"현재 상태: {detail['status_text']}",
                "",
                "오늘 예약 일정",
                "",
            ]
            if detail["schedules"]:
                for sched in detail["schedules"]:
                    lines.append(f"- {sched}")
            else:
                lines.append("- 예약 없음")

            text = "\n".join(lines).strip()
            await query.edit_message_text(text, reply_markup=room_detail_keyboard(detail["asset_id"]))
            return

        # 13. Favorites Actions Mock
        if data in (CB_FAV_ADD_ASSET, CB_FAV_ADD_ROOM, CB_FAV_REMOVE):
            text = f"⭐ 즐겨찾기 변경 기능 (Mock UI)\n\n선택된 작업: {data}"
            await query.edit_message_text(text, reply_markup=favorites_keyboard())
            return

        # Fallback for unhandled data
        text = "⚠️ 요청 상태가 만료되었습니다."
        await query.edit_message_text(text, reply_markup=expired_keyboard())

    except Exception as e:
        logger.error(f"Error handling callback_data '{data}': {e}", exc_info=True)
        text = "⚠️ 요청 상태가 만료되었습니다."
        try:
            await query.edit_message_text(text, reply_markup=expired_keyboard())
        except Exception:
            pass


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Global exception handler for Telegram bot."""
    logger.error("Exception while handling Telegram update:", exc_info=context.error)
