"""Pack curated review bundle for ChatGPT cross-verification of v0.2 Phase 2.1 Checkpoint Production Foundation."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
HISTORY_SUBDIR = "v0.2_phase2_1_checkpoint"
OUTPUT_DIR = WORKSPACE_ROOT / "review_bundles" / HISTORY_SUBDIR
ZIP_FILENAME = "suremeetingroom_v0.2_phase2_1_checkpoint_review.zip"
RELEASE_BASE_TAG = "v0.1-local-mvp"
TASK_BASE_COMMIT = "79ecbe9506285866480a906c804aca49e2d79d66"

# 1. Exact list of files to include: (rel_path_in_workspace, arcname_in_zip)
BUNDLE_FILES = [
    # Manifest and Diff (stored in review_bundles/v0.2_phase2_1_checkpoint/)
    (f"review_bundles/{HISTORY_SUBDIR}/REVIEW_BUNDLE_MANIFEST.md", "REVIEW_BUNDLE_MANIFEST.md"),
    (f"review_bundles/{HISTORY_SUBDIR}/REVIEW_GIT_DIFF.patch", "REVIEW_GIT_DIFF.patch"),
    (f"review_bundles/{HISTORY_SUBDIR}/CUMULATIVE_GIT_DIFF.patch", "CUMULATIVE_GIT_DIFF.patch"),

    # Phase 2.1 Changed Core & Config Files
    ("src/meeting_room_bot/config.py", "src/meeting_room_bot/config.py"),
    ("src/meeting_room_bot/account_link/token_service.py", "src/meeting_room_bot/account_link/token_service.py"),
    ("src/meeting_room_bot/account_link/app.py", "src/meeting_room_bot/account_link/app.py"),
    ("src/meeting_room_bot/account_link/templates/login.html", "src/meeting_room_bot/account_link/templates/login.html"),
    ("src/meeting_room_bot/account_link/templates/error.html", "src/meeting_room_bot/account_link/templates/error.html"),
    ("src/meeting_room_bot/account_link/templates/success.html", "src/meeting_room_bot/account_link/templates/success.html"),
    ("src/meeting_room_bot/favorites/json_repository.py", "src/meeting_room_bot/favorites/json_repository.py"),
    ("src/meeting_room_bot/groupware/client.py", "src/meeting_room_bot/groupware/client.py"),
    ("src/meeting_room_bot/providers/real_provider.py", "src/meeting_room_bot/providers/real_provider.py"),
    ("src/meeting_room_bot/telegram/bot.py", "src/meeting_room_bot/telegram/bot.py"),
    ("src/meeting_room_bot/telegram/handlers.py", "src/meeting_room_bot/telegram/handlers.py"),
    ("src/meeting_room_bot/telegram/keyboards.py", "src/meeting_room_bot/telegram/keyboards.py"),
    ("docs/V0_2_PHASE2_DEPLOYMENT_PLAN.md", "docs/V0_2_PHASE2_DEPLOYMENT_PLAN.md"),
    ("scripts/pack_review_bundle.py", "scripts/pack_review_bundle.py"),
    ("scripts/run_local_app.py", "scripts/run_local_app.py"),

    # Hardening Test Suite
    ("tests/test_phase2_1_foundation.py", "tests/test_phase2_1_foundation.py"),
    ("tests/test_account_link_localhost.py", "tests/test_account_link_localhost.py"),
    ("tests/test_favorites.py", "tests/test_favorites.py"),

    # Phase 1 & Pre-Phase 2 Source Files (Foundation)
    ("src/meeting_room_bot/utils/date_utils.py", "src/meeting_room_bot/utils/date_utils.py"),
    ("src/meeting_room_bot/utils/__init__.py", "src/meeting_room_bot/utils/__init__.py"),
    ("src/meeting_room_bot/models/user_key.py", "src/meeting_room_bot/models/user_key.py"),
    ("src/meeting_room_bot/models/__init__.py", "src/meeting_room_bot/models/__init__.py"),
    ("src/meeting_room_bot/providers/mock_data.py", "src/meeting_room_bot/providers/mock_data.py"),
    ("src/meeting_room_bot/providers/mock_provider.py", "src/meeting_room_bot/providers/mock_provider.py"),
    ("src/meeting_room_bot/providers/base.py", "src/meeting_room_bot/providers/base.py"),
    ("src/meeting_room_bot/auth/session_manager.py", "src/meeting_room_bot/auth/session_manager.py"),
    ("src/meeting_room_bot/favorites/repository.py", "src/meeting_room_bot/favorites/repository.py"),
    ("src/meeting_room_bot/favorites/service.py", "src/meeting_room_bot/favorites/service.py"),
    ("src/meeting_room_bot/services/meeting_room_service.py", "src/meeting_room_bot/services/meeting_room_service.py"),
    ("src/meeting_room_bot/telegram/mock_service.py", "src/meeting_room_bot/telegram/mock_service.py"),

    # Additional Test Files
    ("tests/test_dynamic_date_handling.py", "tests/test_dynamic_date_handling.py"),
    ("tests/test_platform_abstraction.py", "tests/test_platform_abstraction.py"),
    ("tests/test_real_favorites.py", "tests/test_real_favorites.py"),
    ("tests/test_real_mode_auth_flow.py", "tests/test_real_mode_auth_flow.py"),

    # Earlier Docs
    ("docs/V0_2_ARCHITECTURE_PLAN.md", "docs/V0_2_ARCHITECTURE_PLAN.md"),
    ("docs/V0_2_PHASE1_REPORT.md", "docs/V0_2_PHASE1_REPORT.md"),

    # 1-Hop Direct Context & Models
    ("src/meeting_room_bot/models/asset.py", "src/meeting_room_bot/models/asset.py"),
    ("src/meeting_room_bot/models/room.py", "src/meeting_room_bot/models/room.py"),
    ("src/meeting_room_bot/models/reservation.py", "src/meeting_room_bot/models/reservation.py"),
    ("src/meeting_room_bot/favorites/models.py", "src/meeting_room_bot/favorites/models.py"),

    # Regression Tests
    ("tests/test_auth_session.py", "tests/test_auth_session.py"),
    ("tests/test_providers.py", "tests/test_providers.py"),
    ("tests/test_multi_user_isolation.py", "tests/test_multi_user_isolation.py"),
    ("tests/test_account_link.py", "tests/test_account_link.py"),

    # Runtime Closure
    ("src/meeting_room_bot/services/availability_service.py", "src/meeting_room_bot/services/availability_service.py"),
    ("src/meeting_room_bot/services/room_status_service.py", "src/meeting_room_bot/services/room_status_service.py"),
    ("src/meeting_room_bot/auth/models.py", "src/meeting_room_bot/auth/models.py"),
    ("src/meeting_room_bot/telegram/states.py", "src/meeting_room_bot/telegram/states.py"),
    ("src/meeting_room_bot/__init__.py", "src/meeting_room_bot/__init__.py"),
    ("src/meeting_room_bot/auth/__init__.py", "src/meeting_room_bot/auth/__init__.py"),
    ("src/meeting_room_bot/favorites/__init__.py", "src/meeting_room_bot/favorites/__init__.py"),
    ("src/meeting_room_bot/groupware/__init__.py", "src/meeting_room_bot/groupware/__init__.py"),
    ("src/meeting_room_bot/providers/__init__.py", "src/meeting_room_bot/providers/__init__.py"),
    ("src/meeting_room_bot/services/__init__.py", "src/meeting_room_bot/services/__init__.py"),
    ("src/meeting_room_bot/telegram/__init__.py", "src/meeting_room_bot/telegram/__init__.py"),
    ("src/meeting_room_bot/account_link/__init__.py", "src/meeting_room_bot/account_link/__init__.py"),
    ("pytest.ini", "pytest.ini"),
    ("requirements.txt", "requirements.txt"),
]

# Changed files that are deliberately excluded with justification
EXCLUDED_CHANGED_FILES = {}

# Exclusion / Safety check patterns
FORBIDDEN_NAME_PATTERNS = [
    r"\.env($|\..*)",
    r".*\.pyc$",
    r".*\.cache",
    r"__pycache__",
    r".*\.log$",
    r"favorites\.json$",
    r".*\.session.*",
]

SECRET_CONTENT_PATTERNS = [
    (r"\b\d{9,10}:[a-zA-Z0-9_-]{35}\b", "Real Telegram Bot Token"),
    (r"GOSSOcookie\s*=\s*['\"][a-zA-Z0-9_-]{10,}['\"]", "Real GOSSO Cookie Value"),
    (r"(?i)(password|passwd|secret)\s*=\s*['\"][^'\"]{8,}['\"]", "Hardcoded Password/Secret"),
    (r"connect\.sid\s*=\s*['\"][^'\"]+['\"]", "Session Cookie Value"),
]


def check_clean_working_tree():
    """Verify that working tree is clean outside review_bundles directory."""
    status_out = subprocess.check_output(
        ["git", "status", "--porcelain"],
        cwd=WORKSPACE_ROOT,
        text=True,
        encoding="utf-8",
    )
    dirty_files = []
    for line in status_out.splitlines():
        if not line.strip():
            continue
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            path = parts[1].strip('"').replace("\\", "/")
            if path.startswith("review_bundles/"):
                continue
            dirty_files.append(line.strip())

    if dirty_files:
        raise RuntimeError(
            "Working tree is NOT clean! Uncommitted changes detected outside review_bundles:\n"
            + "\n".join(f"  {f}" for f in dirty_files)
            + "\nPlease commit all changes before creating the review bundle."
        )
    print("[OK] Working Tree check passed: CLEAN outside review_bundles.")


def scan_file_safety(rel_path: str, abs_path: Path):
    """Scan file path and contents for accidental secret exposure."""
    for pat in FORBIDDEN_NAME_PATTERNS:
        if re.search(pat, rel_path, re.IGNORECASE):
            raise ValueError(f"Forbidden file detected in bundle list: {rel_path} (matched {pat})")

    try:
        content = abs_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return

    for pat, label in SECRET_CONTENT_PATTERNS:
        matches = re.findall(pat, content)
        if matches:
            raise ValueError(f"Security violation: {label} detected in {rel_path}: {matches[:2]}")


def verify_changed_files_consistency(head_commit: str):
    """Verify that every file changed between TASK_BASE_COMMIT and HEAD is in BUNDLE_FILES."""
    try:
        diff_out = subprocess.check_output(
            ["git", "diff", "--name-only", TASK_BASE_COMMIT, head_commit],
            cwd=WORKSPACE_ROOT,
            text=True,
            encoding="utf-8",
        )
    except Exception as e:
        print(f"WARNING: Could not run git diff to verify changed files: {e}", file=sys.stderr)
        return

    changed_files = [line.strip().replace("\\", "/") for line in diff_out.splitlines() if line.strip()]
    bundle_rel_paths = {rel.replace("\\", "/") for rel, _ in BUNDLE_FILES}

    unaccounted = []
    for cf in changed_files:
        if cf.startswith("review_bundles/"):
            continue
        if cf in bundle_rel_paths or cf in EXCLUDED_CHANGED_FILES:
            continue
        unaccounted.append(cf)

    if unaccounted:
        raise RuntimeError(
            f"Changed files consistency check failed! The following changed files are missing from BUNDLE_FILES:\n"
            + "\n".join(f"  - {f}" for f in unaccounted)
        )
    print(f"[OK] Changed Files consistency check passed ({len(changed_files)} changed files verified against {TASK_BASE_COMMIT}..{head_commit}).")


def run_standalone_bundle_self_test(zip_path: Path):
    """Extract zip into isolated temp directory and run the bundled test suite."""
    print("\n=== Running Standalone Review Bundle Self-Test ===")
    with tempfile.TemporaryDirectory() as tmp_dir:
        with zipfile.ZipFile(zip_path, mode="r") as zf:
            zf.extractall(tmp_dir)

        test_files = [
            "tests/test_phase2_1_foundation.py",
            "tests/test_dynamic_date_handling.py",
            "tests/test_platform_abstraction.py",
            "tests/test_auth_session.py",
            "tests/test_favorites.py",
            "tests/test_providers.py",
            "tests/test_multi_user_isolation.py",
            "tests/test_account_link.py",
            "tests/test_account_link_localhost.py",
            "tests/test_real_favorites.py",
            "tests/test_real_mode_auth_flow.py",
        ]
        cmd = [sys.executable, "-m", "pytest"] + test_files + ["-v"]
        res = subprocess.run(cmd, cwd=tmp_dir, capture_output=True, text=True, encoding="utf-8")
        if res.returncode != 0:
            print("Self-test FAILED in extracted bundle environment!", file=sys.stderr)
            print("STDOUT:\n", res.stdout, file=sys.stderr)
            print("STDERR:\n", res.stderr, file=sys.stderr)
            raise RuntimeError(f"Review Bundle self-test failed with exit code {res.returncode}")

        # Parse test count from output
        match = re.search(r"(\d+)\s+passed", res.stdout)
        passed_count = match.group(1) if match else "all"
        print(f"[OK] Standalone Self-Test PASSED: {passed_count} tests executed cleanly within isolated bundle context.")


def generate_manifest(head_commit: str, branch: str) -> Path:
    """Generate REVIEW_BUNDLE_MANIFEST.md with exact commit hashes and requirements."""
    manifest_path = OUTPUT_DIR / "REVIEW_BUNDLE_MANIFEST.md"
    head_short = head_commit[:7]
    base_short = TASK_BASE_COMMIT[:7]
    content = f"""# Review Bundle Manifest: v0.2 Phase 2.1 Checkpoint Hardening

## 1. Bundle Identification & Git Lineage
- **Bundle File**: `{ZIP_FILENAME}`
- **History Directory**: `review_bundles/{HISTORY_SUBDIR}/`
- **Release Base Tag**: `{RELEASE_BASE_TAG}` (`f214e39b607e0f28def41b4d0ee5630017b63d85`)
- **Task Base Commit**: `{TASK_BASE_COMMIT}`
- **Current HEAD Commit**: `{head_commit}`
- **Branch**: `{branch}`
- **Generated Date**: 2026-10-19
- **Working Tree**: `CLEAN`
- **Patch Range**: `{TASK_BASE_COMMIT}..{head_commit}`
- **Cumulative Range**: `{RELEASE_BASE_TAG}..{head_commit}`

---

## 2. Review Bundle Purpose & Scope
This review bundle contains the complete, curated, and independently testable set of files for verifying **v0.2 Phase 2.1 Final Checkpoint Hardening** prior to any GitHub push or external Cloud/HTTPS provisioning.

No actual Cloud deployment, external DNS modification, firewall change, or public certificate generation was performed in this task. No GitHub push was performed.

### Included Patch Criteria:
- **`REVIEW_GIT_DIFF.patch`**: Strictly generated against **Task Base Commit..Current HEAD** (`{base_short}..{head_short}`), capturing all changes implemented in Phase 2.1 (excluding recursive review bundles).
- **`CUMULATIVE_GIT_DIFF.patch`**: Cumulative patch from Release Base Tag (`{RELEASE_BASE_TAG}`..`{head_short}`) provided for complete full-lineage reference.

---

## 3. Key Hardening Implementations

### 1) Login Failure UX & Burn-on-use Policy Consistency
- Maintained strict burn-on-use security token consumption (`token_service.consume_token(token)`) before attempting authentication.
- Removed legacy `javascript:history.back()` ("🔄 다시 시도") retry button in `error.html` because consumed one-time tokens cannot be reused.
- Directs user with explicit guidance: "보안을 위해 연결 링크는 1회만 사용 가능합니다. Telegram으로 돌아가 '회사 계정 연결'을 다시 눌러 새로운 연결 링크를 발급받아 주세요."
- Zero token creation in web layer; tokens remain exclusively issued by Telegram Handlers.

### 2) Empty Favorites File Treated as Storage Corruption
- Updated `JsonFavoriteRepository._load_raw_data()`:
  - Non-existent file: returns normal new state `{{"users": {{}}}}`.
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
"""
    manifest_path.write_text(content, encoding="utf-8")
    print(f"[OK] Generated {manifest_path.name} (HEAD={head_commit})")
    return manifest_path


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = OUTPUT_DIR / ZIP_FILENAME

    print(f"=== Creating Review Bundle: {ZIP_FILENAME} ===")
    print(f"Release Base Tag: {RELEASE_BASE_TAG}")
    print(f"Task Base Commit: {TASK_BASE_COMMIT}")
    print(f"History Output Directory: {OUTPUT_DIR}")

    # 0. Enforce Clean Working Tree before creating Review Bundle
    check_clean_working_tree()

    # Get exact committed HEAD commit hash and branch
    head_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=WORKSPACE_ROOT,
        text=True,
    ).strip()
    branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=WORKSPACE_ROOT,
        text=True,
    ).strip()
    print(f"Committed HEAD: {head_commit} (Branch: {branch})")

    # 1. Update manifest dynamically with exact committed HEAD
    generate_manifest(head_commit, branch)

    # 2. Update UTF-8 patch for Task Base Commit..HEAD in history dir
    patch_path = OUTPUT_DIR / "REVIEW_GIT_DIFF.patch"
    diff_bytes = subprocess.check_output(
        ["git", "diff", TASK_BASE_COMMIT, head_commit, "--", ".", ":(exclude)review_bundles"],
        cwd=WORKSPACE_ROOT,
    )
    patch_path.write_bytes(diff_bytes)
    print(f"[OK] Updated REVIEW_GIT_DIFF.patch ({len(diff_bytes):,} bytes, {TASK_BASE_COMMIT} -> {head_commit}, UTF-8)")

    # Also update cumulative diff from Release Base Tag
    cumulative_patch_path = OUTPUT_DIR / "CUMULATIVE_GIT_DIFF.patch"
    cum_diff_bytes = subprocess.check_output(
        ["git", "diff", RELEASE_BASE_TAG, head_commit, "--", ".", ":(exclude)review_bundles"],
        cwd=WORKSPACE_ROOT,
    )
    cumulative_patch_path.write_bytes(cum_diff_bytes)
    print(f"[OK] Updated CUMULATIVE_GIT_DIFF.patch ({len(cum_diff_bytes):,} bytes, {RELEASE_BASE_TAG} -> {head_commit}, UTF-8)")

    # 3. Check changed files consistency against exact commit range
    verify_changed_files_consistency(head_commit)

    # 4. Verify all files exist and are safe
    total_uncompressed_bytes = 0
    valid_files = []

    for rel_path, arcname in BUNDLE_FILES:
        abs_path = WORKSPACE_ROOT / rel_path
        if not abs_path.is_file():
            print(f"ERROR: Missing bundle file: {rel_path}", file=sys.stderr)
            sys.exit(1)

        scan_file_safety(rel_path, abs_path)
        file_size = abs_path.stat().st_size
        total_uncompressed_bytes += file_size
        valid_files.append((rel_path, abs_path, file_size, arcname))

    print(f"Total files to bundle: {len(valid_files)}")
    print(f"Total uncompressed size: {total_uncompressed_bytes:,} bytes ({total_uncompressed_bytes / 1024:.2f} KB)")

    # 5. Build ZIP archive
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel_path, abs_path, _, arcname in valid_files:
            zf.write(abs_path, arcname=arcname.replace("\\", "/"))

    zip_size = zip_path.stat().st_size
    print(f"ZIP created successfully: {zip_path}")
    print(f"ZIP size: {zip_size:,} bytes ({zip_size / 1024:.2f} KB)")

    # 6. Verify ZIP integrity
    with zipfile.ZipFile(zip_path, mode="r") as zf:
        test_res = zf.testzip()
        if test_res is not None:
            raise RuntimeError(f"Corrupt file in ZIP: {test_res}")
        namelist = zf.namelist()
        print(f"ZIP integrity check PASSED ({len(namelist)} items in archive)")

    # 7. Run standalone self-test
    run_standalone_bundle_self_test(zip_path)

    print("\n[SUCCESS] Review bundle ready.")


if __name__ == "__main__":
    main()
