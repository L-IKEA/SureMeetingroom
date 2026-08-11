"""Script to run the Telegram Meeting Room Bot in polling mode."""

import logging
import os
import sys
from pathlib import Path

# Add project src to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from meeting_room_bot.telegram.bot import build_application

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("[FAIL] TELEGRAM_BOT_TOKEN environment variable is missing.")
        print()
        print("Please create a '.env' file in the project root containing:")
        print("TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather")
        print()
        sys.exit(1)

    print("=== Starting Telegram Meeting Room Bot (Polling Mode) ===")
    print("Bot Token loaded successfully.")
    print("Press Ctrl+C to stop.")
    print()

    try:
        app = build_application(token)
        app.run_polling()
    except KeyboardInterrupt:
        print("Bot stopped by user.")
    except Exception as e:
        logger.error(f"Failed to run Telegram Bot: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
