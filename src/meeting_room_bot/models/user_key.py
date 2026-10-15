"""Platform-independent User Identity Key model (Channel Identity)."""

from dataclasses import dataclass
from typing import Union


@dataclass(frozen=True)
class UserKey:
    """Platform-independent channel identity identifying a user within a messaging platform.

    Architectural Principle:
    - UserKey represents ONLY the platform-specific channel identity (e.g. telegram:8296531540, kakao:k_12345).
    - It must NOT contain internal employee or corporate application user state (e.g. internal_user_id, emp_id),
      so that hash and equality remain strictly stable when used as dictionary/cache keys.
    - Future corporate user account mapping should be implemented as an independent mapping layer
      (e.g. AppUser / ChannelMapping) that links one or more UserKey instances to a single internal user.
    """

    platform: str
    platform_user_id: str

    def to_string(self) -> str:
        """Serialize UserKey to standard string format: 'platform:platform_user_id'."""
        return f"{self.platform}:{self.platform_user_id}"

    def __str__(self) -> str:
        return self.to_string()

    @classmethod
    def from_string(cls, raw: str, default_platform: str = "telegram") -> "UserKey":
        """Parse string formatted as 'platform:user_id' or raw 'user_id'.

        Note: default_platform='telegram' is provided strictly as a Transition Compatibility
        fallback for v0.1 legacy data and tests. New platform adapters must explicitly specify
        their platform when constructing UserKey.
        """
        raw_str = str(raw).strip()
        if ":" in raw_str:
            parts = raw_str.split(":", 1)
            return cls(platform=parts[0].lower(), platform_user_id=parts[1])
        return cls(platform=default_platform, platform_user_id=raw_str)

    @classmethod
    def from_any(
        cls,
        val: Union["UserKey", str, int],
        default_platform: str = "telegram",
    ) -> "UserKey":
        """Convert UserKey, string, or int to UserKey seamlessly (Transition Compatibility Layer)."""
        if isinstance(val, UserKey):
            return val
        return cls.from_string(str(val), default_platform=default_platform)
