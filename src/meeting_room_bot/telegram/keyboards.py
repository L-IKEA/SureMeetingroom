"""Telegram InlineKeyboard builders."""

from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

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
    CB_REFRESH_NOW,
    CB_ROOM_PREFIX,
    CB_SCOPE_ALL,
    CB_SCOPE_FAV,
    CB_TIME_PREFIX,
)


def format_location_label(full_name: str) -> str:
    """Format full location asset name to clean short label for inline keyboard buttons."""
    name = full_name.replace("[판교] ", "").replace("[대전] ", "")
    if "10층" in name:
        return "10층"
    if full_name == "[대전] 회의실":
        return "대전 회의실"
    return name


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Build main menu inline keyboard in 1 column (vertical) layout."""
    keyboard = [
        [InlineKeyboardButton("🟢 지금 빈 회의실", callback_data=CB_MENU_NOW)],
        [InlineKeyboardButton("🕐 언제 빈 회의실", callback_data=CB_MENU_WHEN)],
        [InlineKeyboardButton("🏢 어디 빈 회의실", callback_data=CB_MENU_WHERE)],
        [InlineKeyboardButton("⭐ 즐겨찾기 관리", callback_data=CB_MENU_FAV)],
    ]
    return InlineKeyboardMarkup(keyboard)


def result_now_keyboard(scope: str = "fav") -> InlineKeyboardMarkup:
    """Build navigation keyboard for '지금 빈 회의실' results."""
    if scope in ("fav", "favorites"):
        keyboard = [
            [
                InlineKeyboardButton("🌐 전체 위치로 조회", callback_data=CB_SCOPE_ALL),
                InlineKeyboardButton("🔄 새로고침", callback_data=CB_REFRESH_NOW),
            ],
            [
                InlineKeyboardButton("🏠 처음으로", callback_data=CB_NAV_HOME),
            ],
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("⭐ 즐겨찾기 기준", callback_data=CB_SCOPE_FAV),
                InlineKeyboardButton("🔄 새로고침", callback_data=CB_REFRESH_NOW),
            ],
            [
                InlineKeyboardButton("🏠 처음으로", callback_data=CB_NAV_HOME),
            ],
        ]
    return InlineKeyboardMarkup(keyboard)


def no_favorites_guidance_keyboard() -> InlineKeyboardMarkup:
    """Build guidance keyboard when user has no registered favorites."""
    keyboard = [
        [InlineKeyboardButton("⭐ 즐겨찾기 설정", callback_data=CB_MENU_FAV)],
        [InlineKeyboardButton("🌐 전체 위치로 조회", callback_data=CB_SCOPE_ALL)],
        [InlineKeyboardButton("🏠 처음으로", callback_data=CB_NAV_HOME)],
    ]
    return InlineKeyboardMarkup(keyboard)


def when_date_keyboard() -> InlineKeyboardMarkup:
    """Build date selection keyboard for '언제 빈 회의실'."""
    keyboard = [
        [
            InlineKeyboardButton("오늘", callback_data=CB_DATE_TODAY),
            InlineKeyboardButton("내일", callback_data=CB_DATE_TOMORROW),
        ],
        [
            InlineKeyboardButton("⬅️ 뒤로", callback_data=CB_NAV_BACK),
            InlineKeyboardButton("🏠 처음으로", callback_data=CB_NAV_HOME),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def when_time_keyboard() -> InlineKeyboardMarkup:
    """Build start time selection keyboard in 3 columns."""
    times = [
        "09:00", "09:30", "10:00",
        "10:30", "11:00", "11:30",
        "12:00", "12:30", "13:00",
        "13:30", "14:00", "14:30",
        "15:00", "15:30", "16:00",
        "16:30", "17:00", "17:30",
    ]

    rows = []
    current_row = []
    for t in times:
        t_clean = t.replace(":", "")
        btn = InlineKeyboardButton(t, callback_data=f"{CB_TIME_PREFIX}{t_clean}")
        current_row.append(btn)
        if len(current_row) == 3:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)

    rows.append([
        InlineKeyboardButton("⬅️ 뒤로", callback_data=CB_NAV_BACK),
        InlineKeyboardButton("🏠 처음으로", callback_data=CB_NAV_HOME),
    ])
    return InlineKeyboardMarkup(rows)


def when_duration_keyboard() -> InlineKeyboardMarkup:
    """Build duration selection keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("30분", callback_data=f"{CB_DUR_PREFIX}30"),
            InlineKeyboardButton("60분", callback_data=f"{CB_DUR_PREFIX}60"),
        ],
        [
            InlineKeyboardButton("90분", callback_data=f"{CB_DUR_PREFIX}90"),
            InlineKeyboardButton("120분", callback_data=f"{CB_DUR_PREFIX}120"),
        ],
        [
            InlineKeyboardButton("⬅️ 뒤로", callback_data=CB_NAV_BACK),
            InlineKeyboardButton("🏠 처음으로", callback_data=CB_NAV_HOME),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def result_when_keyboard(scope: str = "fav") -> InlineKeyboardMarkup:
    """Build result keyboard for '언제 빈 회의실'."""
    if scope in ("fav", "favorites"):
        keyboard = [
            [
                InlineKeyboardButton("🌐 전체 위치로 조회", callback_data=CB_SCOPE_ALL),
                InlineKeyboardButton("🔄 조건 다시 선택", callback_data=CB_MENU_WHEN),
            ],
            [
                InlineKeyboardButton("🏠 처음으로", callback_data=CB_NAV_HOME),
            ],
        ]
    else:
        keyboard = [
            [
                InlineKeyboardButton("⭐ 즐겨찾기 기준", callback_data=CB_SCOPE_FAV),
                InlineKeyboardButton("🔄 조건 다시 선택", callback_data=CB_MENU_WHEN),
            ],
            [
                InlineKeyboardButton("🏠 처음으로", callback_data=CB_NAV_HOME),
            ],
        ]
    return InlineKeyboardMarkup(keyboard)


def where_location_keyboard(locations: List[dict]) -> InlineKeyboardMarkup:
    """Build 2-column grid location list keyboard for ALL locations without pagination."""
    rows = []
    row = []
    for loc in locations:
        label = loc.get("short_label") or format_location_label(loc["name"])
        btn = InlineKeyboardButton(f"[{label}]", callback_data=f"{CB_ASSET_PREFIX}{loc['id']}")
        row.append(btn)
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([InlineKeyboardButton("🏠 처음으로", callback_data=CB_NAV_HOME)])
    return InlineKeyboardMarkup(rows)


def where_room_keyboard(asset_id: int, rooms: List[dict]) -> InlineKeyboardMarkup:
    """Build room selection keyboard for a specific location."""
    rows = []
    row = []
    for r in rooms:
        clean_name = r["name"].replace("회의실 ", "").replace("보안룸 ", "").replace("프로젝트룸 ", "").replace("컨퍼런스홀 ", "").replace("교육실 ", "").replace("PDR룸 ", "")
        btn = InlineKeyboardButton(f"[{clean_name}]", callback_data=f"{CB_ROOM_PREFIX}{r['id']}")
        row.append(btn)
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    rows.append([
        InlineKeyboardButton("⬅️ 위치 목록", callback_data=CB_MENU_WHERE),
        InlineKeyboardButton("🏠 처음으로", callback_data=CB_NAV_HOME),
    ])
    return InlineKeyboardMarkup(rows)


def room_detail_keyboard(asset_id: int) -> InlineKeyboardMarkup:
    """Build room detail navigation keyboard."""
    asset_name_map = {
        10: "1층",
        20: "2층",
        30: "3층",
        40: "4층",
        50: "5층",
        60: "6층",
        70: "7층",
        80: "8층",
        90: "9층",
        100: "10층",
        110: "11층",
        120: "12층",
        130: "대전",
    }
    floor_str = asset_name_map.get(asset_id, f"{asset_id}층")

    keyboard = [
        [
            InlineKeyboardButton(f"⬅️ {floor_str}으로", callback_data=f"{CB_ASSET_PREFIX}{asset_id}"),
            InlineKeyboardButton("🏠 처음으로", callback_data=CB_NAV_HOME),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def favorites_keyboard() -> InlineKeyboardMarkup:
    """Build favorites management keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("➕ 위치 추가", callback_data=CB_FAV_ADD_ASSET),
            InlineKeyboardButton("➕ 회의실 추가", callback_data=CB_FAV_ADD_ROOM),
        ],
        [
            InlineKeyboardButton("➖ 삭제", callback_data=CB_FAV_REMOVE),
            InlineKeyboardButton("🏠 처음으로", callback_data=CB_NAV_HOME),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def expired_keyboard() -> InlineKeyboardMarkup:
    """Build keyboard for expired state recovery."""
    keyboard = [
        [InlineKeyboardButton("🏠 처음으로", callback_data=CB_NAV_HOME)],
    ]
    return InlineKeyboardMarkup(keyboard)
