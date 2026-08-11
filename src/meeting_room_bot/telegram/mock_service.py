"""Mock Service providing sample data for Telegram Bot UI layer."""

from typing import Any, Dict, List, Optional


class MockTelegramService:
    """Provides structured mock responses for Telegram UI buttons."""

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
    def has_favorites(user_id: str) -> bool:
        """Check if mock user has registered favorites."""
        if str(user_id) in ("no_fav_user", "empty", "no_fav"):
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
                "short_label": data.get("short_label", data["asset_name"]),
                "is_fav": (aid in (50, 80)),
            })
        return locations

    @classmethod
    def get_mock_available_rooms_now(cls, scope: str = "fav", user_id: str = "default") -> Dict[str, Any]:
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
        user_id: str = "default",
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
    def get_mock_favorites(cls, user_id: str) -> Dict[str, Any]:
        """Return mock favorites for a user."""
        return {
            "user_id": user_id,
            "assets": ["🏢 5층", "🏢 8층"],
            "rooms": ["🚪 10-2"],
        }
