"""Telegram Application builder."""

import logging
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
)

from meeting_room_bot.telegram.handlers import (
    button_callback,
    error_handler,
    start_command,
)

logger = logging.getLogger(__name__)


def build_application(token: str) -> Application:
    """Build and configure telegram Application instance with handlers."""
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        raise ValueError("Invalid Telegram Bot Token provided.")

    app = ApplicationBuilder().token(token).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_error_handler(error_handler)

    return app
