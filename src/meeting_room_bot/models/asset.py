"""Asset model definition and filtering logic."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class Asset:
    """Represents an asset (location/category) in Groupware."""

    id: int
    name: str
    raw_name: str
    description: Optional[str] = None

    @classmethod
    def from_api_dict(cls, asset_dict: Dict[str, Any]) -> "Asset":
        """Construct Asset object from API dictionary."""
        asset_id = (
            asset_dict.get("id")
            or asset_dict.get("assetId")
            or asset_dict.get("seq")
        )
        if asset_id is None:
            raise ValueError("Asset dictionary missing 'id' field")

        raw_name = (
            asset_dict.get("name")
            or asset_dict.get("assetName")
            or asset_dict.get("title")
            or f"Asset {asset_id}"
        )
        raw_name = str(raw_name).strip()

        desc = asset_dict.get("description") or asset_dict.get("desc")

        return cls(
            id=int(asset_id),
            name=raw_name,
            raw_name=raw_name,
            description=str(desc).strip() if desc else None,
        )

    def is_meeting_space(self) -> bool:
        """Centralized exclude-list filter policy to identify meeting space assets.

        Excludes non-meeting room assets (e.g. vehicles, Zoom, remote support, PA).
        Any asset not explicitly matching an exclusion keyword is considered a meeting space.
        """
        name_lower = self.name.lower()

        # Central exclusion keywords
        excluded_keywords = [
            "차량",
            "법인차량",
            "zoom",
            "원격",
            "지원",
            "pa",
            "장비",
            "노트북",
            "모니터",
        ]

        return not any(kw in name_lower for kw in excluded_keywords)
