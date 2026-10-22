"""Telegram Application builder."""

import logging
import os
from typing import Optional
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
)

from meeting_room_bot.providers.base import MeetingRoomQueryProvider
from meeting_room_bot.telegram.handlers import (
    button_callback,
    error_handler,
    set_query_provider,
    start_command,
)

logger = logging.getLogger(__name__)

# Suppress verbose httpx/httpcore request logs containing Telegram Bot token
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_default_provider(favorite_service: Optional["FavoriteService"] = None) -> MeetingRoomQueryProvider:
    """Instantiate Provider based on TELEGRAM_DATA_MODE environment variable."""
    from meeting_room_bot.auth.session_manager import session_manager
    from meeting_room_bot.favorites.json_repository import JsonFavoriteRepository
    from meeting_room_bot.favorites.service import FavoriteService
    from meeting_room_bot.providers.mock_provider import MockMeetingRoomProvider
    from meeting_room_bot.providers.real_provider import RealMeetingRoomProvider

    mode = os.environ.get("TELEGRAM_DATA_MODE", "mock").strip().lower()
    if mode == "real":
        logger.info("[bot] Initializing RealMeetingRoomProvider (TELEGRAM_DATA_MODE=real)")
        if favorite_service is None:
            favorite_service = FavoriteService(JsonFavoriteRepository())
        return RealMeetingRoomProvider(session_mgr=session_manager, favorite_service=favorite_service)
    else:
        logger.info("[bot] Initializing MockMeetingRoomProvider (TELEGRAM_DATA_MODE=mock)")
        return MockMeetingRoomProvider()


def build_application(
    token: str,
    provider: Optional[MeetingRoomQueryProvider] = None,
    favorite_service: Optional["FavoriteService"] = None,
) -> Application:
    """Build and configure telegram Application instance with handlers."""
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        raise ValueError("Invalid Telegram Bot Token provided.")

    from meeting_room_bot.favorites.json_repository import JsonFavoriteRepository
    from meeting_room_bot.favorites.service import FavoriteService
    from meeting_room_bot.telegram.handlers import set_favorite_service

    if favorite_service is None:
        favorite_service = FavoriteService(JsonFavoriteRepository())

    set_favorite_service(favorite_service)

    if provider is None:
        provider = get_default_provider(favorite_service=favorite_service)

    set_query_provider(provider)

    app = ApplicationBuilder().token(token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)

    return app
