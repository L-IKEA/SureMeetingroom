"""Asset model definition and filtering logic."""

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


def get_site_and_subname(name: str) -> Tuple[Optional[str], str]:
    """Extract site prefix like [판교], [대전] and remainder subname."""
    if not name:
        return None, ""
    m = re.match(r"^\[(.*?)\]\s*(.*)$", name.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, name.strip()


def format_asset_all_location_label(name: str) -> str:
    """Format asset name for all-locations view, ensuring site/city is clearly retained.

    Examples:
      '[판교] 7층 회의실' -> '[판교] 7층'
      '[판교] 1층 컨퍼런스홀' -> '[판교] 1층 컨퍼런스홀'
      '[대전] 회의실' -> '[대전] 회의실'
      '판교 7층' -> '판교 7층'
    """
    if not name:
        return ""
    site, sub = get_site_and_subname(name)
    if site:
        if re.match(r"^\d+층\s*회의실$", sub):
            sub = sub.replace("회의실", "").strip()
        elif "10층" in sub:
            sub = "10층"
        if not sub:
            sub = "회의실"
        return f"[{site}] {sub}"
    return name.strip()


def format_asset_compact_label(name: str) -> str:
    """Format asset name for single-asset view (site prefix stripped).

    Examples:
      '[판교] 7층 회의실' -> '7층 회의실'
      '[대전] 회의실' -> '회의실'
      '[판교] 10층 회의실/프로젝트룸/작업실' -> '10층'
    """
    if not name:
        return ""
    site, sub = get_site_and_subname(name)
    if site:
        if "10층" in sub:
            return "10층"
        return sub if sub else name.strip()
    if "10층" in name:
        return "10층"
    return name.strip()


@dataclass
class Asset:
    """Represents an asset (location/category) in Groupware."""

    id: int
    name: str
    raw_name: str
    description: Optional[str] = None

    @property
    def all_location_label(self) -> str:
        """Label formatted for cross-asset / all-locations views (retaining site)."""
        return format_asset_all_location_label(self.name)

    @property
    def compact_label(self) -> str:
        """Label formatted for single-asset views (site prefix stripped)."""
        return format_asset_compact_label(self.name)

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
