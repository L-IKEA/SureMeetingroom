"""Integrated Single-Process Local Application Runner for Telegram Bot & Account Link Server."""

import asyncio
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Load environment variables from .env
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

# Configure logging and suppress httpx Telegram Bot Token leak
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

import uvicorn
from meeting_room_bot.account_link.app import create_app
from meeting_room_bot.telegram.bot import build_application


async def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("[ERROR] TELEGRAM_BOT_TOKEN is missing or invalid in .env file.")
        sys.exit(1)

    data_mode = os.environ.get("TELEGRAM_DATA_MODE", "mock").lower()
    base_url = os.environ.get("ACCOUNT_LINK_BASE_URL", "http://localhost:8000")

    print("\n=======================================================")
    print("=== Starting Integrated Local Application ===")
    print(f"TELEGRAM_DATA_MODE    : {data_mode}")
    print(f"ACCOUNT_LINK_BASE_URL : {base_url}")
    print("=======================================================\n")
    print("Press Ctrl+C to stop.\n")

    # 1. Instantiate FastAPI Web Server with Config integration
    from meeting_room_bot.config import get_config
    app_config = get_config()

    fastapi_app = create_app()

    config = uvicorn.Config(
        app=fastapi_app,
        host=app_config.account_link_host,
        port=app_config.account_link_port,
        proxy_headers=True,
        forwarded_allow_ips=app_config.forwarded_allow_ips,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    # 2. Build Telegram Application
    bot_app = build_application(token)

    # 3. Run Telegram Polling and FastAPI Web Server concurrently in single process
    async with bot_app:
        await bot_app.start()
        await bot_app.updater.start_polling()

        try:
            await server.serve()
        finally:
            await bot_app.updater.stop()
            await bot_app.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nApplication stopped by user.")
