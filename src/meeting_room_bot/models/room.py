"""Room model definition and parsing logic."""

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Room:
    """Represents a meeting room."""

    id: int
    asset_id: int
    name: str
    capacity: Optional[int]
    raw_name: str

    @classmethod
    def from_api_dict(cls, item_dict: Dict[str, Any], asset_id: int) -> "Room":
        """Construct a Room object from Groupware API item dictionary."""
        room_id = (
            item_dict.get("id")
            or item_dict.get("itemId")
            or item_dict.get("assetItemId")
        )
        if room_id is None:
            raise ValueError("Room dictionary missing 'id' field")

        raw_name = (
            item_dict.get("name")
            or item_dict.get("itemName")
            or item_dict.get("title")
            or item_dict.get("assetItemName")
            or f"Room {room_id}"
        )
        raw_name = str(raw_name).strip()

        name, capacity = cls.parse_raw_name(raw_name)

        return cls(
            id=int(room_id),
            asset_id=int(asset_id),
            name=name,
            capacity=capacity,
            raw_name=raw_name,
        )

    @staticmethod
    def parse_raw_name(raw_name: str) -> tuple[str, Optional[int]]:
        """Parse raw room name into clean name and capacity.

        Example: "회의실 5-1(6인 / TV)" -> ("회의실 5-1", 6)
        Failure fallback: (raw_name, None)
        """
        if not raw_name:
            return "", None

        try:
            # Match pattern like "회의실 5-1(6인 / TV)" or "소회의실 ( 10 인 )"
            match = re.search(r"^(.*?)\s*\(\s*(\d+)\s*인.*?\)\s*$", raw_name)
            if match:
                clean_name = match.group(1).strip()
                capacity = int(match.group(2))
                return clean_name, capacity

            # Fallback 1: match capacity inside parentheses
            cap_match = re.search(r"\(\s*(\d+)\s*인.*?\)", raw_name)
            capacity = int(cap_match.group(1)) if cap_match else None

            # Fallback 2: strip parentheses part for clean name if '(' present
            name_match = re.search(r"^(.*?)\s*\(", raw_name)
            clean_name = name_match.group(1).strip() if name_match else raw_name.strip()

            return clean_name or raw_name, capacity
        except Exception:
            # Parsing must never fail
            return raw_name, None
