"""FastAPI Web Server for Groupware Account Linking."""

import logging
from pathlib import Path
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse

from meeting_room_bot.account_link.token_service import token_service
from meeting_room_bot.auth.session_manager import session_manager
from meeting_room_bot.groupware.client import GroupwareAuthError, GroupwareClient, GroupwareError

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def render_html(template_name: str, context: dict = None) -> str:
    """Render HTML template from templates directory using string substitution."""
    context = context or {}
    template_path = TEMPLATES_DIR / template_name
    html = template_path.read_text(encoding="utf-8")
    for key, val in context.items():
        placeholder_spaced = "{{ " + key + " }}"
        placeholder_tight = "{{" + key + "}}"
        str_val = str(val) if val is not None else ""
        html = html.replace(placeholder_spaced, str_val)
        html = html.replace(placeholder_tight, str_val)
    return html


def create_app() -> FastAPI:
    """Create and configure FastAPI Account Linking Application."""
    app = FastAPI(title="Suresoft Meeting Room Bot - Account Linking")

    @app.get("/link/{token}", response_class=HTMLResponse)
    async def get_login_page(token: str):
        """Render login form HTML if token is valid and unexpired."""
        user_id = token_service.validate_token(token)
        if not user_id:
            html = render_html("error.html", {"message": "유효하지 않거나 이미 만료된 계정 연결 링크입니다."})
            return HTMLResponse(content=html, status_code=400)

        html = render_html("login.html", {"token": token})
        return HTMLResponse(content=html)

    @app.post("/link/{token}", response_class=HTMLResponse)
    async def process_login(
        token: str,
        username: str = Form(...),
        password: str = Form(...),
    ):
        """Process login form submission and bind session to user_id upon success."""
        # 1. Validate and consume token (one-time use)
        user_id = token_service.consume_token(token)
        if not user_id:
            html = render_html("error.html", {"message": "유효하지 않거나 이미 만료된 계정 연결 링크입니다."})
            return HTMLResponse(content=html, status_code=400)

        # 2. Attempt Groupware login (password exists in memory transiently)
        client = GroupwareClient()
        try:
            success = client.login(username=username, password=password)
        except (GroupwareAuthError, GroupwareError) as e:
            logger.warning(f"[account_link] Groupware login failed for user_id={user_id}: {e}")
            success = False
        except Exception as e:
            logger.error(f"[account_link] Unexpected error during login for user_id={user_id}: {e}", exc_info=True)
            success = False

        # 3. Handle login result
        if success:
            # Bind authenticated GroupwareClient session to user_id
            session_manager.set_client(user_id, client)
            logger.info(f"[account_link] Successfully linked Groupware session for user_id: {user_id}")
            html = render_html("success.html")
            return HTMLResponse(content=html)
        else:
            html = render_html("error.html", {"message": "로그인에 실패했습니다. 아이디 또는 비밀번호를 확인해주세요."})
            return HTMLResponse(content=html, status_code=400)

    return app


app = create_app()
