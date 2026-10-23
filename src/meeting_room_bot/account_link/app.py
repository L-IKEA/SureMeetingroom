import asyncio
import json
import logging
from pathlib import Path
import secrets
import threading
import time
from typing import Dict, List
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from meeting_room_bot.account_link.session_store import link_session_store, web_session_store
from meeting_room_bot.account_link.token_service import token_service
from meeting_room_bot.auth.session_manager import session_manager
from meeting_room_bot.config import get_config
from meeting_room_bot.groupware.client import GroupwareAuthError, GroupwareClient, GroupwareError
from meeting_room_bot.models.user_key import UserKey
from meeting_room_bot.providers import QueryStatus, get_provider

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


from jinja2 import Environment, FileSystemLoader, select_autoescape

_jinja_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)
_jinja_env.policies["json.dumps_kwargs"] = {"ensure_ascii": False}


def render_html(template_name: str, context: dict = None) -> str:
    """Render HTML template using Jinja2 with autoescaping."""
    context = context or {}
    template = _jinja_env.get_template(template_name)
    return template.render(**context)


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

    # -----------------------------------------------------------------------
    # Phase 2.2 Routes: Exact path routes MUST precede parameter routes
    # -----------------------------------------------------------------------

    @app.get("/link/login", response_class=HTMLResponse)
    async def get_login_page(request: Request):
        """Render login form HTML if LinkSession is valid and active."""
        config = get_config()
        link_session_id = request.cookies.get(config.link_session_cookie_name)
        if not link_session_id:
            logger.warning("[account_link] Missing link session cookie on /link/login.")
            html = render_html("error.html", {"message": "계정 연결 세션이 유효하지 않거나 만료되었습니다."})
            return HTMLResponse(content=html, status_code=400)

        link_session = link_session_store.get_link_session(link_session_id)
        if not link_session:
            logger.warning("[account_link] Expired or invalid link session on /link/login.")
            html = render_html("error.html", {"message": "계정 연결 세션이 만료되었습니다. Telegram에서 새로운 연결 링크를 발급받아 주세요."})
            return HTMLResponse(content=html, status_code=400)

        html = render_html("login.html", {
            "csrf_token": link_session.csrf_token,
            "token": "",  # Form action now targets clean /link/login
        })
        return HTMLResponse(content=html)

    @app.post("/link/login")
    async def process_session_login(
        request: Request,
        username: str = Form(...),
        password: str = Form(...),
        csrf_token: str = Form(""),
    ):
        """Process login form submission verified by LinkSession cookie and CSRF token."""
        config = get_config()

        # 1. Validate LinkSession from Cookie
        link_session_id = request.cookies.get(config.link_session_cookie_name)
        if not link_session_id:
            logger.warning("[account_link] Missing link session cookie on POST /link/login.")
            html = render_html("error.html", {"message": "계정 연결 세션이 만료되었습니다. Telegram에서 새로운 연결 링크를 발급받아 주세요."})
            return HTMLResponse(content=html, status_code=400)

        link_session = link_session_store.get_link_session(link_session_id)
        if not link_session:
            logger.warning("[account_link] Invalid/expired link session on POST /link/login.")
            html = render_html("error.html", {"message": "계정 연결 세션이 만료되었습니다. Telegram에서 새로운 연결 링크를 발급받아 주세요."})
            return HTMLResponse(content=html, status_code=400)

        # 2. Strict CSRF verification using constant-time comparison (before consume to prevent session burning on forged CSRF)
        if not csrf_token or not secrets.compare_digest(link_session.csrf_token, csrf_token):
            logger.warning(f"[account_link] CSRF mismatch for user_key={link_session.user_key.to_string()}")
            html = render_html("error.html", {"message": "CSRF 검증에 실패했습니다. 유효하지 않은 요청입니다."})
            return HTMLResponse(content=html, status_code=403)

        # 3. Check IP rate limit strictly using request.client.host (before consume to prevent session burning on rate limit)
        client_ip = request.client.host if request.client else "127.0.0.1"
        if not check_ip_rate_limit(client_ip, config.rate_limit_login_per_minute):
            logger.warning(f"[account_link] Rate limit exceeded for IP={client_ip}")
            html = render_html("error.html", {"message": "로그인 시도 횟수가 너무 많습니다. 잠시 후 다시 시도해주세요."})
            return HTMLResponse(content=html, status_code=429)

        # 4. Atomically consume LinkSession before external Groupware API call
        # Guarantees that only a single concurrent request acquires session ownership.
        consumed_session = link_session_store.consume_link_session(link_session_id)
        if not consumed_session:
            logger.warning("[account_link] Concurrent replay or already consumed link session detected.")
            html = render_html("error.html", {"message": "이미 사용되었거나 처리 중인 요청입니다. 다시 시도해주세요."})
            response = HTMLResponse(content=html, status_code=400)
            response.delete_cookie(key=config.link_session_cookie_name, path="/link")
            return response

        # 5. Attempt Groupware login in worker thread to prevent event-loop blocking
        client = GroupwareClient()
        try:
            success = await asyncio.to_thread(client.login, username=username, password=password)
        except (GroupwareAuthError, GroupwareError) as e:
            logger.warning(f"[account_link] Groupware login failed for user_key={consumed_session.user_key}: {e}")
            success = False
        except Exception as e:
            logger.error(f"[account_link] Unexpected error during login for user_key={consumed_session.user_key}: {e}", exc_info=True)
            success = False

        # 6. Handle login result
        if success:
            user_key = consumed_session.user_key
            # Register authenticated GroupwareClient session in core UserSessionManager
            session_manager.set_client(user_key, client)
            logger.info(f"[account_link] Successfully linked Groupware session for user_key: {user_key.to_string()}")

            # Issue authenticated WebSession for /timeline access
            web_session = web_session_store.create_web_session(
                user_key=user_key,
                ttl_seconds=config.web_session_ttl_seconds,
            )

            # 303 Redirect to /timeline
            response = RedirectResponse(url="/timeline", status_code=303)
            response.set_cookie(
                key=config.web_session_cookie_name,
                value=web_session.session_id,
                max_age=config.web_session_ttl_seconds,
                httponly=True,
                samesite="lax",
                path="/",
                secure=config.is_secure_cookie,
            )
            response.delete_cookie(key=config.link_session_cookie_name, path="/link")
            return response
        else:
            html = render_html("error.html", {"message": "로그인에 실패했습니다. 아이디 또는 비밀번호를 확인해주세요."})
            response = HTMLResponse(content=html, status_code=400)
            response.delete_cookie(key=config.link_session_cookie_name, path="/link")
            return response

    @app.get("/link/{token}")
    async def exchange_token_and_redirect(token: str):
        """Consume one-time security token, create server-side LinkSession, and 303-redirect to /link/login.

        Guarantees that the one-time token vanishes from the browser URL immediately after the first GET.
        """
        config = get_config()

        # 1. Immediately consume token upon first access (burn-on-use)
        user_id = token_service.consume_token(token)
        if not user_id:
            logger.warning("[account_link] Token exchange failed: invalid or expired token.")
            html = render_html("error.html", {"message": "유효하지 않거나 이미 만료된 계정 연결 링크입니다."})
            return HTMLResponse(content=html, status_code=400)

        # 2. Create server-side LinkSession with CSRF token
        user_key = UserKey.from_any(user_id)
        link_session = link_session_store.create_link_session(
            user_key=user_key,
            ttl_seconds=config.account_link_web_session_ttl_seconds,
        )

        # 3. Set HttpOnly LinkSession cookie and 303 Redirect to clean /link/login URL
        response = RedirectResponse(url="/link/login", status_code=303)
        response.set_cookie(
            key=config.link_session_cookie_name,
            value=link_session.session_id,
            max_age=config.account_link_web_session_ttl_seconds,
            httponly=True,
            samesite="lax",
            path="/link",
            secure=config.is_secure_cookie,
        )
        return response

    # -----------------------------------------------------------------------
    # Phase 2.2 Protected Timeline Placeholder & Logout
    # -----------------------------------------------------------------------

    @app.get("/timeline", response_class=HTMLResponse)
    async def get_timeline_page(request: Request):
        """Protected Meeting Room Timeline Web App."""
        config = get_config()
        web_session_id = request.cookies.get(config.web_session_cookie_name)
        if not web_session_id:
            logger.warning("[account_link] Unauthorized access to /timeline: missing web session cookie.")
            html = render_html("error.html", {"message": "인증되지 않은 접근입니다. 계정을 먼저 연결해주세요."})
            return HTMLResponse(content=html, status_code=401)

        web_session = web_session_store.get_web_session(web_session_id)
        if not web_session:
            logger.warning("[account_link] Unauthorized access to /timeline: invalid or expired web session.")
            html = render_html("error.html", {"message": "웹 세션이 만료되었거나 유효하지 않습니다. 다시 계정을 연결해주세요."})
            return HTMLResponse(content=html, status_code=401)

        # Dual validation: WebSession exists AND GroupwareClient active in session_manager
        if not session_manager.has_session(web_session.user_key):
            logger.warning(f"[account_link] WebSession exists for {web_session.user_key} but Groupware session is missing (server restart or expired).")
            web_session_store.remove_web_session(web_session_id)
            html = render_html("error.html", {"message": "그룹웨어 세션이 만료되었습니다. 다시 계정을 연결해주세요."})
            response = HTMLResponse(content=html, status_code=401)
            response.delete_cookie(key=config.web_session_cookie_name, path="/")
            return response

        # Query timeline data via Provider
        asset_id_param = request.query_params.get("asset_id")
        target_asset_id = int(asset_id_param) if asset_id_param and asset_id_param.isdigit() else None

        provider = get_provider()
        result = await asyncio.to_thread(provider.get_timeline, user_id=web_session.user_key, asset_id=target_asset_id)

        error_message = ""
        initial_data = {}

        if result.status == QueryStatus.SESSION_EXPIRED:
            logger.warning(f"[account_link] Groupware session expired for {web_session.user_key} on /timeline")
            web_session_store.remove_web_session(web_session_id)
            html = render_html("error.html", {"message": "계정 연결이 만료되었습니다. 다시 연결해 주세요."})
            response = HTMLResponse(content=html, status_code=401)
            response.delete_cookie(key=config.web_session_cookie_name, path="/")
            return response
        elif result.status == QueryStatus.NOT_AUTHENTICATED:
            html = render_html("error.html", {"message": "계정 연결이 필요합니다."})
            return HTMLResponse(content=html, status_code=401)
        elif result.status == QueryStatus.NETWORK_ERROR:
            error_message = "회의실 정보를 불러오지 못했습니다. 네트워크 상태를 확인해주세요."
        elif result.status == QueryStatus.SUCCESS:
            initial_data = result.data
        else:
            error_message = "회의실 정보를 불러오지 못했습니다."

        html = render_html("timeline.html", {
            "user_display": web_session.user_key.to_string(),
            "initial_data": initial_data,
            "initial_data_json": json.dumps(initial_data, ensure_ascii=False),
            "error_message": error_message,
        })
        return HTMLResponse(content=html)

    @app.get("/api/web/timeline")
    async def get_web_timeline_api(request: Request):
        """Web App JSON API for dynamic timeline query and floor switching."""
        config = get_config()
        web_session_id = request.cookies.get(config.web_session_cookie_name)
        if not web_session_id:
            return JSONResponse(
                content={"error": "인증되지 않은 접근입니다. 계정 연결이 필요합니다.", "code": "NOT_AUTHENTICATED"},
                status_code=401,
            )

        web_session = web_session_store.get_web_session(web_session_id)
        if not web_session:
            return JSONResponse(
                content={"error": "웹 세션이 만료되었습니다. 다시 계정을 연결해주세요.", "code": "SESSION_EXPIRED"},
                status_code=401,
            )

        if not session_manager.has_session(web_session.user_key):
            web_session_store.remove_web_session(web_session_id)
            resp = JSONResponse(
                content={"error": "계정 연결이 만료되었습니다. 다시 연결해 주세요.", "code": "SESSION_EXPIRED"},
                status_code=401,
            )
            resp.delete_cookie(key=config.web_session_cookie_name, path="/")
            return resp

        asset_id_param = request.query_params.get("asset_id")
        target_asset_id = int(asset_id_param) if asset_id_param and asset_id_param.isdigit() else None

        provider = get_provider()
        result = await asyncio.to_thread(provider.get_timeline, user_id=web_session.user_key, asset_id=target_asset_id)

        if result.status == QueryStatus.SUCCESS:
            return JSONResponse(content=result.data, status_code=200)
        elif result.status == QueryStatus.SESSION_EXPIRED:
            web_session_store.remove_web_session(web_session_id)
            resp = JSONResponse(
                content={"error": "계정 연결이 만료되었습니다. 다시 연결해 주세요.", "code": "SESSION_EXPIRED"},
                status_code=401,
            )
            resp.delete_cookie(key=config.web_session_cookie_name, path="/")
            return resp
        elif result.status == QueryStatus.NOT_AUTHENTICATED:
            return JSONResponse(
                content={"error": "계정 연결이 필요합니다.", "code": "NOT_AUTHENTICATED"},
                status_code=401,
            )
        elif result.status == QueryStatus.NETWORK_ERROR:
            return JSONResponse(
                content={"error": "회의실 정보를 불러오지 못했습니다.", "code": "NETWORK_ERROR"},
                status_code=502,
            )
        else:
            return JSONResponse(
                content={"error": "회의실 정보를 불러오지 못했습니다.", "code": "GROUPWARE_ERROR"},
                status_code=500,
            )

    @app.post("/logout")
    async def process_logout(request: Request):
        """Terminate WebSession and remove associated Groupware session from UserSessionManager."""
        config = get_config()
        web_session_id = request.cookies.get(config.web_session_cookie_name)
        if web_session_id:
            web_session = web_session_store.remove_web_session(web_session_id)
            if web_session:
                session_manager.remove_session(web_session.user_key)
                logger.info(f"[account_link] Logged out user_key: {web_session.user_key.to_string()}")

        response = RedirectResponse(url="/link/login", status_code=303)
        response.delete_cookie(key=config.web_session_cookie_name, path="/")
        return response

    return app


app = create_app()
