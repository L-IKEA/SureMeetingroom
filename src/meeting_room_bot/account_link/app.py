import asyncio
import logging
from pathlib import Path
import threading
import time
from typing import Dict, List
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse

from meeting_room_bot.account_link.token_service import token_service
from meeting_room_bot.auth.session_manager import session_manager
from meeting_room_bot.config import get_config
from meeting_room_bot.groupware.client import GroupwareAuthError, GroupwareClient, GroupwareError
from meeting_room_bot.models.user_key import UserKey

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_login_attempts_by_ip: Dict[str, List[float]] = {}
_rate_limit_lock = threading.Lock()
MAX_RATE_LIMIT_ENTRIES = 10000


def cleanup_rate_limits(max_age_seconds: float = 60.0) -> int:
    """Purge stale rate limit tracking entries older than max_age_seconds. Return removed count."""
    now = time.time()
    removed = 0
    with _rate_limit_lock:
        stale_ips = [ip for ip, ts in _login_attempts_by_ip.items() if not ts or (now - ts[-1] > max_age_seconds)]
        for ip in stale_ips:
            del _login_attempts_by_ip[ip]
            removed += 1
    return removed


def check_ip_rate_limit(client_ip: str, limit_per_minute: int) -> bool:
    """Check sliding window rate limit for an IP address. Return True if allowed."""
    if limit_per_minute <= 0:
        return True
    now = time.time()
    with _rate_limit_lock:
        # Periodic cleanup of expired entries if dictionary grows
        if len(_login_attempts_by_ip) > 100:
            stale_ips = [ip for ip, ts in _login_attempts_by_ip.items() if not ts or (now - ts[-1] > 60.0)]
            for ip in stale_ips:
                del _login_attempts_by_ip[ip]

        # Prevent unbounded entry growth from randomized spoofed IPs
        if len(_login_attempts_by_ip) >= MAX_RATE_LIMIT_ENTRIES and client_ip not in _login_attempts_by_ip:
            sorted_ips = sorted(_login_attempts_by_ip.items(), key=lambda item: item[1][-1] if item[1] else 0)
            for ip, _ in sorted_ips[:MAX_RATE_LIMIT_ENTRIES // 5]:
                del _login_attempts_by_ip[ip]

        attempts = _login_attempts_by_ip.get(client_ip, [])
        valid_attempts = [t for t in attempts if now - t < 60.0]
        if len(valid_attempts) >= limit_per_minute:
            _login_attempts_by_ip[client_ip] = valid_attempts
            return False
        valid_attempts.append(now)
        _login_attempts_by_ip[client_ip] = valid_attempts
        return True


def reset_rate_limits():
    """Reset rate limiting table (useful for test isolation)."""
    with _rate_limit_lock:
        _login_attempts_by_ip.clear()


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

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        """Inject strict security response headers into all HTTP responses."""
        response = await call_next(request)
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"
        return response

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
        request: Request,
        token: str,
        username: str = Form(...),
        password: str = Form(...),
    ):
        """Process login form submission and bind session to user_id upon success."""
        # 0. Check IP rate limit strictly using request.client.host
        # In Reverse Proxy deployments, Uvicorn's ProxyHeadersMiddleware (configured with forwarded_allow_ips)
        # securely rewrites request.client.host ONLY from trusted proxies. We never trust raw X-Forwarded-For headers.
        client_ip = request.client.host if request.client else "127.0.0.1"

        config = get_config()
        if not check_ip_rate_limit(client_ip, config.rate_limit_login_per_minute):
            logger.warning(f"[account_link] Rate limit exceeded for IP={client_ip}")
            html = render_html("error.html", {"message": "로그인 시도 횟수가 너무 많습니다. 잠시 후 다시 시도해주세요."})
            return HTMLResponse(content=html, status_code=429)
        # 1. Validate and consume token (one-time use)
        user_id = token_service.consume_token(token)
        if not user_id:
            html = render_html("error.html", {"message": "유효하지 않거나 이미 만료된 계정 연결 링크입니다."})
            return HTMLResponse(content=html, status_code=400)

        # 2. Attempt Groupware login in worker thread to prevent event-loop blocking
        client = GroupwareClient()
        try:
            success = await asyncio.to_thread(client.login, username=username, password=password)
        except (GroupwareAuthError, GroupwareError) as e:
            logger.warning(f"[account_link] Groupware login failed for user_id={user_id}: {e}")
            success = False
        except Exception as e:
            logger.error(f"[account_link] Unexpected error during login for user_id={user_id}: {e}", exc_info=True)
            success = False

        # 3. Handle login result
        if success:
            # Explicitly reconstruct UserKey and bind authenticated GroupwareClient session
            user_key = UserKey.from_any(user_id)
            session_manager.set_client(user_key, client)
            logger.info(f"[account_link] Successfully linked Groupware session for user_key: {user_key.to_string()}")
            html = render_html("success.html")
            return HTMLResponse(content=html)
        else:
            html = render_html("error.html", {"message": "로그인에 실패했습니다. 아이디 또는 비밀번호를 확인해주세요."})
            return HTMLResponse(content=html, status_code=400)

    return app


app = create_app()
