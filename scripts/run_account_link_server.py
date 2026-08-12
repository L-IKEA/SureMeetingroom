"""Runner script for Account Linking FastAPI Web Server using Uvicorn."""

import os
import sys
from pathlib import Path
import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from meeting_room_bot.account_link.app import create_app

if __name__ == "__main__":
    host = os.environ.get("ACCOUNT_LINK_HOST", "0.0.0.0")
    port = int(os.environ.get("ACCOUNT_LINK_PORT", "8000"))

    print(f"=== Starting Account Linking Web Server on http://{host}:{port} ===")
    app = create_app()
    uvicorn.run(app, host=host, port=port)
