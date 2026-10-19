# Review Bundle Manifest: v0.2 Phase 2.1 Production Foundation Hardening

## 1. Bundle Identification & Git Lineage
- **Bundle File**: `suremeetingroom_v0.2_phase2_1_foundation_review.zip`
- **History Directory**: `review_bundles/v0.2_phase2_1_foundation/`
- **Release Base Tag**: `v0.1-local-mvp` (`f214e39b607e0f28def41b4d0ee5630017b63d85`)
- **Task Base Commit**: `79ecbe9506285866480a906c804aca49e2d79d66`
- **Current HEAD Commit**: `5762ebd8464ad3213517b84f05e7410299c3dc8a`
- **Branch**: `feature/v0.2-platform-abstraction`
- **Generated Date**: 2026-10-19

---

## 2. Review Bundle Purpose & Scope
This review bundle contains the complete, curated, and independently testable set of files for verifying **v0.2 Phase 2.1: Production Foundation Hardening** prior to any external Cloud/HTTPS provisioning.

No actual Cloud deployment, external DNS modification, firewall change, or public certificate generation was performed in this task.

### Included Patch Criteria:
- **`REVIEW_GIT_DIFF.patch`**: Strictly generated against **Task Base Commit..Current HEAD** (`79ecbe9..c34b0b2`), capturing all changes implemented in Phase 2.1.
- **`CUMULATIVE_GIT_DIFF.patch`**: Cumulative patch from Release Base Tag (`v0.1-local-mvp`..HEAD) provided for complete full-lineage reference.

---

## 3. Key Hardening Implementations

### 1) Account Link Token Generation Unification
- Token creation was removed from `keyboards.py`. Presentation layer never creates security tokens.
- `handlers.py` generates the token once using `UserKey` (`user_key = UserKey("telegram", user_id)`), builds `link_url`, and passes `link_url` to `unauthenticated_keyboard(link_url=...)` and `session_expired_keyboard(link_url=...)`.
- In Local development mode (`ACCOUNT_LINK_BASE_URL` is localhost): token is generated once for terminal logging, while the keyboard renders guidance with 0 external URL buttons.
- In Production mode: exact same URL is passed to the Telegram InlineKeyboardButton.
- `UserKey` namespace (`telegram:12345`) is completely preserved, preventing collision with future platforms (`kakao:12345`).

### 2) Account Link Consumer UserKey Reconstruction
- In `account_link/app.py`: `token_service.consume_token(token)` returns the serialized string (`telegram:12345`).
- The consumer explicitly restores `UserKey.from_any(user_id)` before calling `session_manager.set_client(user_key, client)`.
- Legacy plain IDs are supported via the transition compatibility fallback.

### 3) Single-Process Pilot Constraint
- Documented in `docs/V0_2_PHASE2_DEPLOYMENT_PLAN.md`:
  - **Server Instance = 1**
  - **Python Process = 1**
  - **Uvicorn Worker = 1** (`--workers 1`)
- Multi-worker (`--workers 2+`), multi-replica, and multi-instance deployments are strictly forbidden during the pilot because `UserSessionManager`, `AccountLinkTokenService`, and `UserStateManager` reside in-memory.
- Multi-instance scaling is deferred until shared token and session stores are introduced.

### 4) Blocking Groupware I/O Event Loop Isolation (`asyncio.to_thread`)
- `GroupwareClient` uses synchronous `requests.Session`.
- All blocking network calls across FastAPI and Telegram callback handlers are offloaded to worker threads via `await asyncio.to_thread(...)`:
  - `client.login`
  - `provider.get_locations`
  - `provider.get_available_rooms_now`
  - `provider.get_available_rooms_at`
  - `provider.get_location_status`
  - `provider.get_room_detail`
- Prevents slow Groupware requests from blocking the asyncio event loop for other concurrent users.

### 5) Auth Error vs General API Error vs Network Error Classification
In `RealMeetingRoomProvider`:
- `GroupwareAuthError` (401/403): removes user session from `session_mgr`, returns `QueryStatus.SESSION_EXPIRED`.
- `GroupwareAPIError` (500 / API payload error): preserves user session, returns `QueryStatus.GROUPWARE_API_ERROR`.
- `GroupwareNetworkError`: preserves user session, returns `QueryStatus.NETWORK_ERROR`.

### 6) FavoriteService / FavoriteRepository DI Single-Instance Unification
- `bot.py` creates a single `FavoriteRepository` and single `FavoriteService` during `build_application`.
- Injected into `RealMeetingRoomProvider` and `handlers.py` via `set_favorite_service`.
- Both core provider and telegram handlers share the exact same instance.

### 7) Favorites JSON Atomic Replace & Corruption Defense
- In `JsonFavoriteRepository`:
  - Multi-threaded protection with `threading.RLock()`.
  - Atomic write: writes to temporary file (`favorites.json.tmp.<pid>.<uuid>`), flushes, executes `os.fsync`, and replaces atomically via `os.replace`.
  - Corruption defense: invalid JSON is automatically isolated to `favorites.json.corrupted.<timestamp>`, preventing silent data loss.

### 8) Production Configuration Integration
- Introduced `src/meeting_room_bot/config.py` with `AppConfig`:
  - `ACCOUNT_LINK_TOKEN_TTL`: connected to `token_service.py`
  - `FORWARDED_ALLOW_IPS`: connected to uvicorn/reverse proxy
  - `RATE_LIMIT_LOGIN_PER_MINUTE`: connected to IP sliding-window limiter in `app.py`
  - `GROUPWARE_BASE_URL`: connected to `GroupwareClient.__init__`
  - `FAVORITES_FILE_PATH`: connected to `JsonFavoriteRepository.__init__`
- All local defaults are preserved.

### 9) URL Token Exposure Mitigation & Response Security Headers
- `app.py` middleware injects strict security response headers:
  - `Referrer-Policy: no-referrer`
  - `Cache-Control: no-store, no-cache, must-revalidate`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Content-Security-Policy: frame-ancestors 'none'`
  - `<meta name="referrer" content="no-referrer">` in templates
- Target flow documented in `V0_2_PHASE2_DEPLOYMENT_PLAN.md` (Exchange of token for secure session cookie + 303 redirect to `/link/login`).

### 10) Token Store Hygiene
- Burn-on-use: token popped from active dictionary upon `consume_token`.
- Periodic/triggered expiration cleanup: `cleanup_expired_tokens()`.
- Unbounded token replacement: `create_token` purges previous active tokens for the same user.

### 11) IP-Based Sliding Window Rate Limiting
- `app.py` enforces sliding-window rate limiting on `POST /link/{token}` based on client IP / `X-Forwarded-For`.
- Returns HTTP 429 Too Many Requests when rate limit is exceeded.

---

## 4. Test Verification
- **Baseline Tests**: 192 passed, 0 failed, 0 skipped.
- **New Foundation Tests (`tests/test_phase2_1_foundation.py`)**: 17 passed.
- **Total Repository Test Results**: **209 passed, 0 failed, 0 skipped**.
- **Execution Time**: ~2.7s.

---

## 5. Company Decision Gate (6 Items Pending Before Production Deployment)
1. **운영 서버 인프라**: 사내 VM vs 회사 승인 공식 Cloud
2. **외부 HTTPS 수신 경로**: 공인 443 오픈 vs 사내 기존 Web Gateway
3. **공인 도메인 및 인증서**: 사용할 사내 서브도메인 및 와일드카드 인증서 vs Let's Encrypt
4. **Telegram 아웃바운드**: 사내망에서 `api.telegram.org:443` HTTPS 아웃바운드 허용 여부
5. **Groupware API 도달성**: 후보 운영 서버에서 `gw.suresofttech.com` 네트워크 도달 테스트
6. **사내 계정 인증 정책**: 공식 SSO(OAuth2/SAML) 지원 여부 및 자체 웹 페이지 ID/PW 입력 정책 승인
