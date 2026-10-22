# Review Bundle Manifest: v0.2 Phase 2.1 Checkpoint Hardening

## 1. Bundle Identification & Git Lineage
- **Bundle File**: `suremeetingroom_v0.2_phase2_1_checkpoint_review.zip`
- **History Directory**: `review_bundles/v0.2_phase2_1_checkpoint/`
- **Release Base Tag**: `v0.1-local-mvp` (`f214e39b607e0f28def41b4d0ee5630017b63d85`)
- **Task Base Commit**: `79ecbe9506285866480a906c804aca49e2d79d66`
- **Current HEAD Commit**: `f03fb7522ff60d08a908a96753476080880c4349`
- **Branch**: `feature/v0.2-platform-abstraction`
- **Generated Date**: 2026-10-19
- **Working Tree**: `CLEAN`
- **Patch Range**: `79ecbe9506285866480a906c804aca49e2d79d66..f03fb7522ff60d08a908a96753476080880c4349`
- **Cumulative Range**: `v0.1-local-mvp..f03fb7522ff60d08a908a96753476080880c4349`

---

## 2. Review Bundle Purpose & Scope
This review bundle contains the complete, curated, and independently testable set of files for verifying **v0.2 Phase 2.1 Final Checkpoint Hardening** prior to any GitHub push or external Cloud/HTTPS provisioning.

No actual Cloud deployment, external DNS modification, firewall change, or public certificate generation was performed in this task. No GitHub push was performed.

### Included Patch Criteria:
- **`REVIEW_GIT_DIFF.patch`**: Strictly generated against **Task Base Commit..Current HEAD** (`79ecbe9..f03fb75`), capturing all changes implemented in Phase 2.1 (excluding recursive review bundles).
- **`CUMULATIVE_GIT_DIFF.patch`**: Cumulative patch from Release Base Tag (`v0.1-local-mvp`..`f03fb75`) provided for complete full-lineage reference.

---

## 3. Key Hardening Implementations

### 1) Login Failure UX & Burn-on-use Policy Consistency
- Maintained strict burn-on-use security token consumption (`token_service.consume_token(token)`) before attempting authentication.
- Removed legacy `javascript:history.back()` ("🔄 다시 시도") retry button in `error.html` because consumed one-time tokens cannot be reused.
- Directs user with explicit guidance: "보안을 위해 연결 링크는 1회만 사용 가능합니다. Telegram으로 돌아가 '회사 계정 연결'을 다시 눌러 새로운 연결 링크를 발급받아 주세요."
- Zero token creation in web layer; tokens remain exclusively issued by Telegram Handlers.

### 2) Empty Favorites File Treated as Storage Corruption
- Updated `JsonFavoriteRepository._load_raw_data()`:
  - Non-existent file: returns normal new state `{"users": {}}`.
  - Existing file with 0 bytes or whitespace-only: raises `FavoriteStorageCorruptionError`, logs ERROR alert, creates timestamped `.corrupted.<timestamp>` backup, and strictly blocks overwriting with new/empty data.
  - Read and mutation operations both abort on corrupted file without silent data loss.

### 3) Presentation Layer Zero Security Token Guarantee
- Completely removed legacy fallback in `keyboards.py`. Presentation layer never imports `token_service` and has **0 `create_token` calls**.
- Keyboards accept exclusively `Optional[str] link_url`:
  - `link_url=None` (or localhost): No URL button.
  - `link_url="https://..."`: Renders `InlineKeyboardButton("🔐 회사 계정 연결", url=link_url)`.
- Token creation is strictly restricted to Handler / AccountLink orchestration.

### 4) Direct X-Forwarded-For Header Trust Elimination
- In `account_link/app.py`: eliminated naive direct reading of raw `X-Forwarded-For` request header.
- Client IP resolution relies exclusively on `request.client.host`.
- Reverse proxy header rewriting is delegated to Uvicorn's `ProxyHeadersMiddleware`, securely configured with `forwarded_allow_ips=config.forwarded_allow_ips` in `scripts/run_local_app.py` (and production runner).
- Client-spoofed `X-Forwarded-For` headers cannot evade rate limiting.
- Production default remains strict `127.0.0.1` (never `*`).

### 5) Rate Limit Store Automatic Cleanup & Capacity Defense
- Sliding-window IP table (`_login_attempts_by_ip`) in `app.py` includes automatic cleanup:
  - Purges stale IP entries older than 60 seconds whenever table exceeds 100 entries.
  - Enforces `MAX_RATE_LIMIT_ENTRIES = 10000`, pruning oldest 20% entries under spoofing flood attacks.
  - Explicit `cleanup_rate_limits(max_age_seconds=60.0)` helper function for testing and periodic maintenance.

### 6) Atomic Write Preserved
- `JsonFavoriteRepository` continues to use `threading.RLock()`, writing to unique temp files (`favorites.json.tmp.<pid>.<uuid>`), flushing, enforcing `os.fsync`, and atomically replacing via `os.replace`.

### 7) Single-Process Pilot Constraint Maintained
- `docs/V0_2_PHASE2_DEPLOYMENT_PLAN.md` explicitly documents:
  - **Server Instance = 1**
  - **Python Process = 1**
  - **Uvicorn Worker = 1** (`--workers 1`)
- Multi-worker and multi-instance prohibited until Shared Stores are implemented.

### 8) Blocking Groupware I/O Isolation (`asyncio.to_thread`)
- All blocking network I/O in `GroupwareClient` remains isolated from asyncio event loop using `await asyncio.to_thread(...)`.

### 9) Production Configuration Actual Wiring
- `src/meeting_room_bot/config.py` connected across:
  - `ACCOUNT_LINK_TOKEN_TTL` -> `token_service.py`
  - `FORWARDED_ALLOW_IPS` -> Uvicorn runner (`run_local_app.py`)
  - `RATE_LIMIT_LOGIN_PER_MINUTE` -> `app.py`
  - `GROUPWARE_BASE_URL` -> `groupware/client.py`
  - `FAVORITES_FILE_PATH` -> `favorites/json_repository.py`

### 10) URL Token Exposure Mitigation
- Security response headers implemented in `app.py` (`Referrer-Policy: no-referrer`, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Content-Security-Policy: frame-ancestors 'none'`).
- Documented clear status distinction:
  - **Security Response Headers**: Implemented in Phase 2.1
  - **Secure Cookie Exchange + 303 Redirect (`/link/<token>` -> `/link/login`)**: Planned Architecture in Phase 2.2

---

## 4. Test Verification
- **Baseline Tests (Phase 2.1 Start)**: 192 passed.
- **Enhanced Test Suite**: 219 passed, 0 failed, 0 skipped.
- **Execution Time**: ~3.4s.

---

## 5. Company Decision Gate (6 Items Pending Before Production Deployment)
1. **운영 서버 인프라**: 사내 VM vs 회사 승인 공식 Cloud
2. **외부 HTTPS 수신 경로**: 공인 443 오픈 vs 사내 기존 Web Gateway
3. **공인 도메인 및 인증서**: 사용할 사내 서브도메인 및 와일드카드 인증서 vs Let's Encrypt
4. **Telegram 아웃바운드**: 사내망에서 `api.telegram.org:443` HTTPS 아웃바운드 허용 여부
5. **Groupware API 도달성**: 후보 운영 서버에서 `gw.suresofttech.com` 네트워크 도달 테스트
6. **사내 계정 인증 정책**: 공식 SSO(OAuth2/SAML) 지원 여부 및 자체 웹 페이지 ID/PW 입력 정책 승인
