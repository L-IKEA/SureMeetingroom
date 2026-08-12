"""Authentication and User Session Models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class UserSessionInfo:
    """Session metadata for a authenticated user."""

    user_id: str
    username: str
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
