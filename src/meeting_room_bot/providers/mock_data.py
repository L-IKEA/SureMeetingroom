"""Platform-independent Mock Meeting Room Dataset and Query Logic."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from meeting_room_bot.config import get_config
from meeting_room_bot.models.asset import format_asset_all_location_label, format_asset_compact_label

SEOUL_TZ = timezone(timedelta(hours=9))


class MockMeetingRoomData:
    """Platform-independent mock meeting room dataset and query provider."""

    # Mock location status catalog per asset_id
    MOCK_LOCATIONS_DATA: Dict[int, Dict[str, Any]] = {
        10: {
            "asset_id": 10,
            "asset_name": "[판교] 1층 컨퍼런스홀",
            "short_label": "1층 컨퍼런스홀",
            "rooms": [
                {
                    "id": 110,
                    "name": "컨퍼런스홀 1-1",
                    "status": "🟢 사용 가능",
                    "note": "오늘 추가 예약 없음",
                    "capacity": 50,
                    "schedules": [],
                }
            ],
        },
        20: {
            "asset_id": 20,
            "asset_name": "[판교] 2층 평생교육원",
            "short_label": "2층 평생교육원",
            "rooms": [
                {
                    "id": 120,
                    "name": "교육실 2-1",
                    "status": "🟢 사용 가능",
                    "note": "오늘 추가 예약 없음",
                    "capacity": 30,
                    "schedules": [],
                }
            ],
        },
        30: {
            "asset_id": 30,
            "asset_name": "[판교] 3층 PDR룸(식당)",
            "short_label": "3층 PDR룸",
            "rooms": [
                {
                    "id": 130_0,
                    "name": "PDR룸 3-1",
                    "status": "🟢 사용 가능",
                    "note": "오늘 추가 예약 없음",
                    "capacity": 10,
                    "schedules": [],
                }
            ],
        },
        40: {
            "asset_id": 40,
            "asset_name": "[판교] 4층 회의실",
            "short_label": "4층 회의실",
            "rooms": [
                {
                    "id": 140,
                    "name": "회의실 4-1",
                    "status": "🟢 사용 가능",
                    "note": "오늘 추가 예약 없음",
                    "capacity": 6,
                    "schedules": ["09:00 ~ 10:00"],
                },
                {
                    "id": 141,
                    "name": "회의실 4-2",
                    "status": "🔴 사용 중",
                    "note": "16:00부터 사용 가능",
                    "capacity": 8,
                    "schedules": ["13:00 ~ 16:00"],
                },
                {
                    "id": 142,
                    "name": "회의실 4-3",
                    "status": "🟢 사용 가능",
                    "note": "15:00부터 예약",
                    "capacity": 10,
                    "schedules": ["15:00 ~ 17:00"],
                },
            ],
        },
        50: {
            "asset_id": 50,
            "asset_name": "[판교] 5층 회의실",
            "short_label": "5층 회의실",
            "rooms": [
                {
                    "id": 130,
                    "name": "회의실 5-1",
                    "status": "🔴 사용 중",
                    "note": "17:00부터 사용 가능",
                    "capacity": 6,
                    "schedules": ["09:00 ~ 09:30", "10:00 ~ 17:00"],
                },
                {
                    "id": 131,
                    "name": "회의실 5-2",
                    "status": "🟢 사용 가능",
                    "note": "오늘 추가 예약 없음",
                    "capacity": 6,
                    "schedules": ["09:00 ~ 09:30", "12:30 ~ 13:30"],
                },
                {
                    "id": 132,
                    "name": "보안룸 회의실 5-3",
                    "status": "🟢 사용 가능",
                    "note": "14:30부터 예약",
                    "capacity": 8,
                    "schedules": ["14:30 ~ 16:00"],
                },
                {
                    "id": 133,
                    "name": "보안룸 회의실 5-4",
                    "status": "🔴 사용 중",
                    "note": "15:00부터 사용 가능",
                    "capacity": 8,
                    "schedules": ["13:00 ~ 15:00"],
                },
            ],
        },
        60: {
            "asset_id": 60,
            "asset_name": "[판교] 6층 프로젝트룸",
            "short_label": "6층 프로젝트룸",
            "rooms": [
                {
                    "id": 160,
                    "name": "프로젝트룸 6-1",
                    "status": "🟢 사용 가능",
                    "note": "오늘 추가 예약 없음",
                    "capacity": 10,
                    "schedules": [],
                },
                {
                    "id": 161,
                    "name": "프로젝트룸 6-2",
                    "status": "🔴 사용 중",
                    "note": "18:00부터 사용 가능",
                    "capacity": 12,
                    "schedules": ["10:00 ~ 18:00"],
                },
            ],
        },
        70: {
            "asset_id": 70,
            "asset_name": "[판교] 7층 회의실",
            "short_label": "7층 회의실",
            "rooms": [
                {
                    "id": 170,
                    "name": "회의실 7-1",
                    "status": "🟢 사용 가능",
                    "note": "오늘 추가 예약 없음",
                    "capacity": 6,
                    "schedules": [],
                },
                {
                    "id": 171,
                    "name": "회의실 7-2",
                    "status": "🟢 사용 가능",
                    "note": "11:00부터 예약",
                    "capacity": 6,
                    "schedules": ["11:00 ~ 12:00"],
                },
                {
                    "id": 172,
                    "name": "회의실 7-3",
                    "status": "🔴 사용 중",
                    "note": "14:00부터 사용 가능",
                    "capacity": 8,
                    "schedules": ["10:00 ~ 14:00"],
                },
                {
                    "id": 173,
                    "name": "회의실 7-4",
                    "status": "🟢 사용 가능",
                    "note": "오늘 추가 예약 없음",
                    "capacity": 8,
                    "schedules": [],
                },
                {
                    "id": 174,
                    "name": "회의실 7-5",
                    "status": "🟢 사용 가능",
                    "note": "16:00부터 예약",
                    "capacity": 10,
                    "schedules": ["16:00 ~ 17:30"],
                },
                {
                    "id": 175,
                    "name": "회의실 7-6",
                    "status": "🔴 사용 중",
                    "note": "15:30부터 사용 가능",
                    "capacity": 12,
                    "schedules": ["13:30 ~ 15:30"],
                },
            ],
        },
        80: {
            "asset_id": 80,
            "asset_name": "[판교] 8층 회의실",
            "short_label": "8층 회의실",
            "rooms": [
                {
                    "id": 180,
                    "name": "회의실 8-1",
                    "status": "🟢 사용 가능",
                    "note": "16:00부터 예약",
                    "capacity": 6,
                    "schedules": ["16:00 ~ 17:00"],
                },
                {
                    "id": 181,
                    "name": "회의실 8-2",
                    "status": "🔴 사용 중",
                    "note": "15:00부터 사용 가능",
                    "capacity": 8,
                    "schedules": ["11:00 ~ 15:00"],
                },
                {
                    "id": 182,
                    "name": "회의실 8-3",
                    "status": "🟢 사용 가능",
                    "note": "오늘 추가 예약 없음",
                    "capacity": 10,
                    "schedules": [],
                },
            ],
        },
        90: {
            "asset_id": 90,
            "asset_name": "[판교] 9층 회의실",
            "short_label": "9층 회의실",
            "rooms": [
                {
                    "id": 190,
                    "name": "회의실 9-1",
                    "status": "🟢 사용 가능",
                    "note": "오늘 추가 예약 없음",
                    "capacity": 6,
                    "schedules": [],
                },
                {
                    "id": 191,
                    "name": "회의실 9-2",
                    "status": "🔴 사용 중",
                    "note": "17:00부터 사용 가능",
                    "capacity": 8,
                    "schedules": ["14:00 ~ 17:00"],
                },
            ],
        },
        100: {
            "asset_id": 100,
            "asset_name": "[판교] 10층 회의실/프로젝트룸/작업실",
            "short_label": "10층",
            "rooms": [
                {
                    "id": 200,
                    "name": "회의실 10-1",
                    "status": "🟢 사용 가능",
                    "note": "오늘 추가 예약 없음",
                    "capacity": 6,
                    "schedules": [],
                }
            ],
        },
        110: {
            "asset_id": 110,
            "asset_name": "[판교] 11층 회의실",
            "short_label": "11층 회의실",
            "rooms": [
                {
                    "id": 210,
                    "name": "회의실 11-1",
                    "status": "🟢 사용 가능",
                    "note": "오늘 추가 예약 없음",
                    "capacity": 6,
                    "schedules": [],
                }
            ],
        },
        120: {
            "asset_id": 120,
            "asset_name": "[판교] 12층 회의실",
            "short_label": "12층 회의실",
            "rooms": [
                {
                    "id": 220,
                    "name": "회의실 12-1",
                    "status": "🟢 사용 가능",
                    "note": "오늘 추가 예약 없음",
                    "capacity": 6,
                    "schedules": [],
                }
            ],
        },
        130: {
            "asset_id": 130,
            "asset_name": "[대전] 회의실",
            "short_label": "대전 회의실",
            "rooms": [
                {
                    "id": 230,
                    "name": "대전 회의실 A",
                    "status": "🟢 사용 가능",
                    "note": "오늘 추가 예약 없음",
                    "capacity": 8,
                    "schedules": [],
                }
            ],
        },
    }

    @staticmethod
    def has_favorites(user_id: Any) -> bool:
        """Check if mock user has registered favorites, preserving platform namespace."""
        u_str = user_id.to_string() if hasattr(user_id, "to_string") else str(user_id).strip()
        if u_str in ("no_fav_user", "empty", "no_fav", "telegram:no_fav_user", "telegram:empty", "telegram:no_fav"):
            return False
        return True

    @classmethod
    def get_mock_locations(cls) -> List[Dict[str, Any]]:
        """Return list of sample meeting room locations (Assets)."""
        locations = []
        for aid, data in cls.MOCK_LOCATIONS_DATA.items():
            locations.append({
                "id": aid,
                "name": data["asset_name"],
                "short_label": data.get("short_label") or format_asset_compact_label(data["asset_name"]),
                "is_fav": (aid in (50, 80)),
            })
        return locations

    @classmethod
    def get_mock_available_rooms_now(
        cls,
        scope: str = "fav",
        user_id: Any = "default",
    ) -> Dict[str, Any]:
        """Return mock currently available rooms based on scope."""
        if scope in ("fav", "favorites"):
            return {
                "scope_title": "⭐ 즐겨찾기 기준",
                "groups": [
                    {
                        "asset_name": "[판교] 5층",
                        "rooms": [
                            {"name": "회의실 5-2", "note": "오늘 추가 예약 없음"},
                            {"name": "보안룸 회의실 5-3", "note": "14:30부터 예약"},
                        ],
                    },
                    {
                        "asset_name": "[판교] 8층",
                        "rooms": [
                            {"name": "회의실 8-1", "note": "16:00부터 예약"},
                        ],
                    },
                ],
            }
        else:
            return {
                "scope_title": "🌐 전체 위치",
                "groups": [
                    {
                        "asset_name": "[판교] 4층",
                        "rooms": [{"name": "회의실 4-1", "note": "오늘 추가 예약 없음"}],
                    },
                    {
                        "asset_name": "[판교] 5층",
                        "rooms": [
                            {"name": "회의실 5-2", "note": "오늘 추가 예약 없음"},
                            {"name": "보안룸 회의실 5-3", "note": "14:30부터 예약"},
                        ],
                    },
                    {
                        "asset_name": "[판교] 8층",
                        "rooms": [{"name": "회의실 8-1", "note": "16:00부터 예약"}],
                    },
                ],
            }

    @classmethod
    def get_mock_available_rooms_at(
        cls,
        date_str: str = "2026-08-11",
        start_time: str = "14:00",
        duration: int = 60,
        scope: str = "fav",
        user_id: Any = "default",
    ) -> Dict[str, Any]:
        """Return mock rooms available for a specified time slot."""
        end_min = int(start_time.split(":")[1]) + duration
        end_hour = int(start_time.split(":")[0]) + (end_min // 60)
        end_min = end_min % 60
        end_time = f"{end_hour:02d}:{end_min:02d}"

        if scope in ("fav", "favorites"):
            available_rooms = [
                "🟢 회의실 5-2",
                "🟢 회의실 5-3",
                "🟢 회의실 8-1",
            ]
        else:
            available_rooms = [
                "🟢 컨퍼런스홀 1-1",
                "🟢 회의실 4-1",
                "🟢 회의실 5-2",
                "🟢 회의실 5-3",
                "🟢 프로젝트룸 6-1",
                "🟢 회의실 7-1",
                "🟢 회의실 8-1",
                "🟢 회의실 9-1",
            ]

        return {
            "date": date_str,
            "start_time": start_time,
            "end_time": end_time,
            "scope": scope,
            "available_rooms": available_rooms,
        }

    @classmethod
    def get_mock_location_status(cls, asset_id: int) -> Dict[str, Any]:
        """Return mock status of all rooms for a specified asset."""
        if asset_id in cls.MOCK_LOCATIONS_DATA:
            loc = cls.MOCK_LOCATIONS_DATA[asset_id]
            return {
                "asset_id": asset_id,
                "asset_name": loc["asset_name"],
                "rooms": [
                    {
                        "id": r["id"],
                        "name": r["name"],
                        "status": r["status"],
                        "note": r["note"],
                    }
                    for r in loc["rooms"]
                ],
            }

        # Fallback for non-existent asset_id
        return {
            "asset_id": asset_id,
            "asset_name": f"[판교] {asset_id}층 회의실",
            "rooms": [],
        }

    @classmethod
    def get_mock_room_detail(cls, asset_id: int, room_id: int) -> Optional[Dict[str, Any]]:
        """Return mock detail for a single room."""
        if asset_id in cls.MOCK_LOCATIONS_DATA:
            loc = cls.MOCK_LOCATIONS_DATA[asset_id]
            target_room = next((r for r in loc["rooms"] if r["id"] == room_id), None)
            if target_room:
                return {
                    "room_id": room_id,
                    "asset_id": asset_id,
                    "name": target_room["name"],
                    "capacity": target_room["capacity"],
                    "status_text": target_room["status"],
                    "schedules": target_room["schedules"],
                }

        # Global search fallback across all assets if asset_id did not match directly
        for aid, loc in cls.MOCK_LOCATIONS_DATA.items():
            target_room = next((r for r in loc["rooms"] if r["id"] == room_id), None)
            if target_room:
                return {
                    "room_id": room_id,
                    "asset_id": aid,
                    "name": target_room["name"],
                    "capacity": target_room["capacity"],
                    "status_text": target_room["status"],
                    "schedules": target_room["schedules"],
                }

        # Fallback for non-existent room_id
        return None

    @classmethod
    def get_mock_favorites(cls, user_id: Any) -> Dict[str, Any]:
        """Return mock favorites for a user, preserving platform namespace."""
        u_str = user_id.to_string() if hasattr(user_id, "to_string") else str(user_id).strip()
        return {
            "user_id": u_str,
            "assets": ["🏢 5층", "🏢 8층"],
            "rooms": ["🚪 10-2"],
        }

    @classmethod
    def get_mock_timeline_data(
        cls,
        asset_id: Optional[int] = None,
        user_key: Optional[Any] = None,
        target_date: Optional[datetime] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Generate mock timeline grid dataset for development and UI smoke testing."""
        config = get_config()

        if now is None:
            now = datetime.now(SEOUL_TZ)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=SEOUL_TZ)
        else:
            now = now.astimezone(SEOUL_TZ)

        if target_date is None:
            target_date = now
        elif target_date.tzinfo is None:
            target_date = target_date.replace(tzinfo=SEOUL_TZ)
        else:
            target_date = target_date.astimezone(SEOUL_TZ)

        start_hour = config.timeline_start_hour
        end_hour = config.timeline_end_hour
        if end_hour <= start_hour:
            start_hour, end_hour = 8, 20

        total_minutes = (end_hour - start_hour) * 60
        timeline_start = target_date.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        timeline_end = target_date.replace(hour=end_hour, minute=0, second=0, microsecond=0)

        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
        date_display = f"{target_date.year}년 {target_date.month}월 {target_date.day}일 ({weekday_names[target_date.weekday()]})"

        current_time_percent: Optional[float] = None
        if now.date() == target_date.date():
            now_offset = (now - timeline_start).total_seconds() / 60.0
            if total_minutes > 0:
                current_time_percent = max(0.0, min(100.0, (now_offset / total_minutes) * 100.0))

        # Build assets list
        mock_locs = cls.get_mock_locations()
        if not mock_locs:
            return {
                "date": target_date.strftime("%Y-%m-%d"),
                "date_display": date_display,
                "current_time": now.strftime("%H:%M"),
                "start_hour": start_hour,
                "end_hour": end_hour,
                "hours": list(range(start_hour, end_hour + 1)),
                "current_time_percent": None,
                "assets": [],
                "selected_asset": None,
                "rooms": [],
                "total_rooms": 0,
                "available_rooms_count": 0,
            }

        is_all_locations = (str(asset_id).strip().lower() == "all") if asset_id is not None else False

        if is_all_locations:
            selected_id = "all"
        else:
            try:
                selected_id = int(asset_id) if asset_id is not None and int(asset_id) in cls.MOCK_LOCATIONS_DATA else 70
            except (ValueError, TypeError):
                selected_id = 70
            if selected_id not in cls.MOCK_LOCATIONS_DATA:
                selected_id = mock_locs[0]["id"]

        assets_data = [
            {
                "id": loc["id"],
                "name": loc["name"],
                "short_label": format_asset_compact_label(loc["name"]),
                "selected": (not is_all_locations and loc["id"] == selected_id),
            }
            for loc in mock_locs
        ]

        raw_rooms_tuples: List[Tuple[int, str, str, Dict[str, Any]]] = []
        if is_all_locations:
            for loc in mock_locs:
                aid = loc["id"]
                ldata = cls.MOCK_LOCATIONS_DATA.get(aid, {})
                aname = ldata.get("asset_name", loc["name"])
                ashort = format_asset_all_location_label(aname)
                for r in ldata.get("rooms", []):
                    raw_rooms_tuples.append((aid, aname, ashort, r))
        else:
            loc_data = cls.MOCK_LOCATIONS_DATA.get(selected_id, {})
            aname = loc_data.get("asset_name", f"[판교] {selected_id}층")
            ashort = format_asset_compact_label(aname)
            for r in loc_data.get("rooms", []):
                raw_rooms_tuples.append((selected_id, aname, ashort, r))

        has_user_favs = cls.has_favorites(user_key) if user_key else True
        fav_rooms_pool = {170, 171, 140, 131, 180, 200}
        fav_assets_pool = {50, 70, 80}

        sample_meetings = [
            ("홍길동", "VCU 검증 회의"),
            ("신지호", "Sprint Planning"),
            ("김태현", "아키텍처 리뷰"),
            ("이수진", "고객사 기술 미팅"),
            ("박민우", "주간 팀 회의"),
            ("정하은", "QA 릴리즈 점검"),
            ("최동욱", "UX/UI 디자인 싱크"),
            ("한소희", "보안 점검 회의"),
        ]

        rooms_data: List[Dict[str, Any]] = []
        meeting_idx = 0

        for aid, aname, ashort, r in raw_rooms_tuples:
            room_id = r["id"]
            room_name = r["name"]
            capacity = r.get("capacity")
            is_fav = has_user_favs and ((aid in fav_assets_pool) or (room_id in fav_rooms_pool))

            schedules = r.get("schedules", [])
            res_blocks: List[Dict[str, Any]] = []
            is_available_now = True
            current_meeting_end = None
            next_meeting_start = None

            for s in schedules:
                if "~" not in s:
                    continue
                parts = s.split("~")
                s_str, e_str = parts[0].strip(), parts[1].strip()
                try:
                    sh, sm = map(int, s_str.split(":"))
                    eh, em = map(int, e_str.split(":"))
                    s_dt = target_date.replace(hour=sh, minute=sm, second=0, microsecond=0)
                    e_dt = target_date.replace(hour=eh, minute=em, second=0, microsecond=0)
                except Exception:
                    continue

                if s_dt <= now < e_dt:
                    is_available_now = False
                    current_meeting_end = e_dt
                elif now < s_dt and (next_meeting_start is None or s_dt < next_meeting_start):
                    next_meeting_start = s_dt

                if e_dt <= timeline_start or s_dt >= timeline_end:
                    continue

                clamped_start = max(s_dt, timeline_start)
                clamped_end = min(e_dt, timeline_end)
                start_offset = (clamped_start - timeline_start).total_seconds() / 60.0
                duration = (clamped_end - clamped_start).total_seconds() / 60.0

                left_pct = (start_offset / total_minutes) * 100.0
                width_pct = (duration / total_minutes) * 100.0
                if width_pct < 1.0:
                    width_pct = 1.0

                reserver, title = sample_meetings[meeting_idx % len(sample_meetings)]
                meeting_idx += 1

                reserver_name = reserver if config.show_reserver_name else None
                meeting_title = title if config.show_meeting_title else None

                res_blocks.append({
                    "id": meeting_idx,
                    "room_id": room_id,
                    "room_name": room_name,
                    "asset_id": aid,
                    "asset_name": aname,
                    "asset_short_label": ashort,
                    "start_time": s_str,
                    "end_time": e_str,
                    "start_iso": s_dt.isoformat(),
                    "end_iso": e_dt.isoformat(),
                    "reserver_name": reserver_name,
                    "meeting_title": meeting_title,
                    "left_percent": round(left_pct, 2),
                    "width_percent": round(width_pct, 2),
                })

            res_blocks.sort(key=lambda b: b["start_time"])

            next_start_str = next_meeting_start.strftime("%H:%M") if next_meeting_start else None
            available_mins = None
            if is_available_now and next_meeting_start:
                available_mins = max(0, int((next_meeting_start - now).total_seconds() // 60))

            if is_available_now:
                if next_meeting_start:
                    status_text = f"지금 비어있음 ({next_meeting_start.strftime('%H:%M')} 예약)"
                else:
                    status_text = "지금 빈 회의실"
            else:
                end_str = current_meeting_end.strftime("%H:%M") if current_meeting_end else ""
                status_text = f"사용 중 ({end_str}까지)" if end_str else "사용 중"

            rooms_data.append({
                "id": room_id,
                "name": room_name,
                "capacity": capacity,
                "favorite": is_fav,
                "is_available_now": is_available_now,
                "next_reservation_start": next_start_str,
                "available_until": next_start_str,
                "available_minutes": available_mins,
                "status_text": status_text,
                "reservations": res_blocks,
                "asset_id": aid,
                "asset_name": aname,
                "asset_short_label": ashort,
            })

        if is_all_locations:
            selected_asset_dict = {
                "id": "all",
                "name": "전체 위치",
                "short_label": "전체 위치",
            }
        else:
            loc_data = cls.MOCK_LOCATIONS_DATA.get(selected_id, {})
            selected_asset_dict = {
                "id": selected_id,
                "name": loc_data.get("asset_name", f"[판교] {selected_id}층"),
                "short_label": loc_data.get("short_label", f"{selected_id}층"),
            }

        return {
            "date": target_date.strftime("%Y-%m-%d"),
            "date_display": date_display,
            "current_time": now.strftime("%H:%M"),
            "start_hour": start_hour,
            "end_hour": end_hour,
            "hours": list(range(start_hour, end_hour + 1)),
            "current_time_percent": round(current_time_percent, 2) if current_time_percent is not None else None,
            "assets": assets_data,
            "selected_asset": selected_asset_dict,
            "rooms": rooms_data,
            "total_rooms": len(rooms_data),
            "available_rooms_count": sum(1 for rm in rooms_data if rm["is_available_now"]),
        }

    @classmethod
    def get_mock_web_availability(
        cls,
        asset_id: Optional[Union[int, str]] = None,
        start_time: str = "14:00",
        duration: int = 60,
        user_key: Optional[Any] = None,
        target_date: Optional[datetime] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Generate mock web availability dataset for WHEN mode."""
        from meeting_room_bot.models.room import Room
        from meeting_room_bot.models.reservation import Reservation
        from meeting_room_bot.services.availability_service import AvailabilityService

        if now is None:
            now = datetime.now(SEOUL_TZ)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=SEOUL_TZ)
        else:
            now = now.astimezone(SEOUL_TZ)

        if target_date is None:
            target_date = now
        elif target_date.tzinfo is None:
            target_date = target_date.replace(tzinfo=SEOUL_TZ)
        else:
            target_date = target_date.astimezone(SEOUL_TZ)

        try:
            sh, sm = map(int, start_time.strip().split(":"))
        except Exception:
            sh, sm = 14, 0
            start_time = "14:00"

        req_start = target_date.replace(hour=sh, minute=sm, second=0, microsecond=0)
        req_end = req_start + timedelta(minutes=duration)

        mock_locs = cls.get_mock_locations()
        if not mock_locs:
            return {
                "date": target_date.strftime("%Y-%m-%d"),
                "date_display": "",
                "start_time": start_time,
                "end_time": req_end.strftime("%H:%M"),
                "duration_minutes": duration,
                "assets": [],
                "selected_asset": None,
                "rooms": [],
                "total_rooms": 0,
                "available_rooms_count": 0,
            }

        is_all_locations = (str(asset_id).strip().lower() == "all") if asset_id is not None else False

        if is_all_locations:
            selected_id = "all"
        else:
            try:
                selected_id = int(asset_id) if asset_id is not None and int(asset_id) in cls.MOCK_LOCATIONS_DATA else 70
            except (ValueError, TypeError):
                selected_id = 70
            if selected_id not in cls.MOCK_LOCATIONS_DATA:
                selected_id = mock_locs[0]["id"]

        assets_data = [
            {
                "id": loc["id"],
                "name": loc["name"],
                "short_label": format_asset_compact_label(loc["name"]),
                "selected": (not is_all_locations and loc["id"] == selected_id),
            }
            for loc in mock_locs
        ]

        raw_rooms_tuples: List[Tuple[int, str, str, Dict[str, Any]]] = []
        if is_all_locations:
            for loc in mock_locs:
                aid = loc["id"]
                ldata = cls.MOCK_LOCATIONS_DATA.get(aid, {})
                aname = ldata.get("asset_name", loc["name"])
                ashort = format_asset_all_location_label(aname)
                for r in ldata.get("rooms", []):
                    raw_rooms_tuples.append((aid, aname, ashort, r))
        else:
            loc_data = cls.MOCK_LOCATIONS_DATA.get(selected_id, {})
            aname = loc_data.get("asset_name", f"[판교] {selected_id}층")
            ashort = format_asset_compact_label(aname)
            for r in loc_data.get("rooms", []):
                raw_rooms_tuples.append((selected_id, aname, ashort, r))

        has_user_favs = cls.has_favorites(user_key) if user_key else True
        fav_rooms_pool = {170, 171, 140, 131, 180, 200}
        fav_assets_pool = {50, 70, 80}

        rooms: List[Room] = []
        res_map: Dict[int, List[Reservation]] = {}
        res_counter = 1

        for aid, aname, ashort, r in raw_rooms_tuples:
            rid = r["id"]
            r_name = r["name"]
            cap = r.get("capacity")
            room_obj = Room(
                id=rid,
                asset_id=aid,
                name=r_name,
                capacity=cap,
                raw_name=r_name,
                asset_name=aname,
                asset_short_label=ashort,
            )
            rooms.append(room_obj)

            r_res: List[Reservation] = []
            for s in r.get("schedules", []):
                if "~" not in s:
                    continue
                parts = s.split("~")
                try:
                    s_parts = parts[0].strip().split(":")
                    e_parts = parts[1].strip().split(":")
                    s_dt = target_date.replace(hour=int(s_parts[0]), minute=int(s_parts[1]), second=0, microsecond=0)
                    e_dt = target_date.replace(hour=int(e_parts[0]), minute=int(e_parts[1]), second=0, microsecond=0)
                    r_res.append(Reservation(
                        id=res_counter,
                        room_id=rid,
                        start_time=s_dt,
                        end_time=e_dt,
                    ))
                    res_counter += 1
                except Exception:
                    continue
            res_map[rid] = r_res

        avail_rooms, _ = AvailabilityService.find_available_rooms(rooms, res_map, req_start, req_end)
        avail_room_ids = {rm.id for rm in avail_rooms}

        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
        date_display = f"{target_date.year}년 {target_date.month}월 {target_date.day}일 ({weekday_names[target_date.weekday()]})"

        rooms_list: List[Dict[str, Any]] = []
        for r in rooms:
            is_fav = has_user_favs and ((r.asset_id in fav_assets_pool) or (r.id in fav_rooms_pool))
            is_available = (r.id in avail_room_ids)
            rooms_list.append({
                "id": r.id,
                "name": r.name,
                "capacity": r.capacity,
                "favorite": is_fav,
                "available": is_available,
                "status_text": "사용 가능" if is_available else "예약 있음",
                "asset_id": r.asset_id,
                "asset_name": r.asset_name,
                "asset_short_label": r.asset_short_label,
            })

        if is_all_locations:
            selected_asset_dict = {
                "id": "all",
                "name": "전체 위치",
                "short_label": "전체 위치",
            }
        else:
            loc_data = cls.MOCK_LOCATIONS_DATA.get(selected_id, {})
            selected_asset_dict = {
                "id": selected_id,
                "name": loc_data.get("asset_name", f"[판교] {selected_id}층"),
                "short_label": loc_data.get("short_label", f"{selected_id}층"),
            }

        return {
            "date": target_date.strftime("%Y-%m-%d"),
            "date_display": date_display,
            "start_time": start_time,
            "end_time": req_end.strftime("%H:%M"),
            "duration_minutes": duration,
            "assets": assets_data,
            "selected_asset": selected_asset_dict,
            "rooms": rooms_list,
            "total_rooms": len(rooms_list),
            "available_rooms_count": len(avail_rooms),
        }

    @classmethod
    def get_mock_web_reservations(
        cls,
        asset_id: Optional[Union[int, str]] = None,
        query: Optional[str] = None,
        favorite_only: bool = False,
        user_key: Optional[Any] = None,
        target_date: Optional[datetime] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Generate mock reservations dataset for WHO mode."""
        if now is None:
            now = datetime.now(SEOUL_TZ)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=SEOUL_TZ)
        else:
            now = now.astimezone(SEOUL_TZ)

        if target_date is None:
            target_date = now
        elif target_date.tzinfo is None:
            target_date = target_date.replace(tzinfo=SEOUL_TZ)
        else:
            target_date = target_date.astimezone(SEOUL_TZ)

        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
        date_display = f"{target_date.year}년 {target_date.month}월 {target_date.day}일 ({weekday_names[target_date.weekday()]})"

        mock_locs = cls.get_mock_locations()
        is_all_locations = (asset_id is None or str(asset_id).strip().lower() == "all")

        target_asset_ids = []
        if is_all_locations:
            target_asset_ids = [loc["id"] for loc in mock_locs]
        else:
            try:
                aid = int(asset_id)
                if aid in cls.MOCK_LOCATIONS_DATA:
                    target_asset_ids = [aid]
            except Exception:
                target_asset_ids = [loc["id"] for loc in mock_locs]

        has_user_favs = cls.has_favorites(user_key) if user_key else True
        fav_rooms_pool = {170, 171, 140, 131, 180, 200}
        fav_assets_pool = {50, 70, 80}

        sample_meetings = [
            ("홍길동", "VCU 검증 회의"),
            ("신지호", "Sprint Planning"),
            ("김태현", "아키텍처 리뷰"),
            ("이수진", "고객사 기술 미팅"),
            ("박민우", "주간 팀 회의"),
            ("정하은", "QA 릴리즈 점검"),
            ("최동욱", "UX/UI 디자인 싱크"),
            ("한소희", "보안 점검 회의"),
        ]

        query_norm = query.strip().lower() if query else None
        all_reservations: List[Dict[str, Any]] = []
        res_idx = 0

        for aid in target_asset_ids:
            loc_data = cls.MOCK_LOCATIONS_DATA.get(aid, {})
            asset_name = loc_data.get("asset_name", f"[판교] {aid}층")
            short_label = format_asset_all_location_label(asset_name) if is_all_locations else format_asset_compact_label(asset_name)

            for r in loc_data.get("rooms", []):
                room_id = r["id"]
                room_name = r["name"]
                is_fav = has_user_favs and ((aid in fav_assets_pool) or (room_id in fav_rooms_pool))

                if favorite_only and not is_fav:
                    continue

                for s in r.get("schedules", []):
                    if "~" not in s:
                        continue
                    parts = s.split("~")
                    try:
                        sh, sm = map(int, parts[0].strip().split(":"))
                        eh, em = map(int, parts[1].strip().split(":"))
                        s_dt = target_date.replace(hour=sh, minute=sm, second=0, microsecond=0)
                        e_dt = target_date.replace(hour=eh, minute=em, second=0, microsecond=0)
                    except Exception:
                        continue

                    res_idx += 1
                    reserver, title = sample_meetings[res_idx % len(sample_meetings)]

                    if query_norm and query_norm not in reserver.lower():
                        continue

                    all_reservations.append({
                        "id": res_idx,
                        "room_id": room_id,
                        "room_name": room_name,
                        "asset_id": aid,
                        "asset_name": asset_name,
                        "asset_short_label": short_label,
                        "start": parts[0].strip(),
                        "end": parts[1].strip(),
                        "start_iso": s_dt.isoformat(),
                        "end_iso": e_dt.isoformat(),
                        "reserver_name": reserver,
                        "meeting_title": title,
                        "favorite": is_fav,
                    })

        all_reservations.sort(key=lambda x: (x["start_iso"], x["asset_id"], x["room_name"]))

        assets_data = [
            {
                "id": loc["id"],
                "name": loc["name"],
                "short_label": format_asset_compact_label(loc["name"]),
                "selected": (not is_all_locations and len(target_asset_ids) == 1 and loc["id"] == target_asset_ids[0]),
            }
            for loc in mock_locs
        ]

        if is_all_locations:
            selected_asset_dict = {
                "id": "all",
                "name": "전체 위치",
                "short_label": "전체 위치",
            }
        else:
            sel_id = target_asset_ids[0] if target_asset_ids else 70
            ldata = cls.MOCK_LOCATIONS_DATA.get(sel_id, {})
            selected_asset_dict = {
                "id": sel_id,
                "name": ldata.get("asset_name", f"[판교] {sel_id}층"),
                "short_label": format_asset_compact_label(ldata.get("asset_name", f"[판교] {sel_id}층")),
            }

        return {
            "date": target_date.strftime("%Y-%m-%d"),
            "date_display": date_display,
            "asset_id": "all" if is_all_locations else int(target_asset_ids[0]),
            "selected_asset": selected_asset_dict,
            "assets": assets_data,
            "query": query or "",
            "total_count": len(all_reservations),
            "reservations": all_reservations,
        }


# Backward-compatible alias for existing imports
MockTelegramService = MockMeetingRoomData
