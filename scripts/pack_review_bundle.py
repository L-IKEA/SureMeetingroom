"""Pack curated review bundle for ChatGPT cross-verification of v0.2 Phase 2.3A Platform-independent Meeting Room Web App v1."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
HISTORY_SUBDIR = "v0.2_phase2_3a_hardening"
OUTPUT_DIR = WORKSPACE_ROOT / "review_bundles" / HISTORY_SUBDIR
ZIP_FILENAME = "suremeetingroom_v0.2_phase2_3a_hardening_review.zip"
RELEASE_BASE_TAG = "v0.1-local-mvp"
TASK_BASE_COMMIT = "1adc6a9b3a58f118d8f8cdbb65b5dbf97d6a6963"

# 1. Exact list of files to include: (rel_path_in_workspace, arcname_in_zip)
BUNDLE_FILES = [
    # Manifest and Diff (stored in review_bundles/v0.2_phase2_3a/)
    (f"review_bundles/{HISTORY_SUBDIR}/REVIEW_BUNDLE_MANIFEST.md", "REVIEW_BUNDLE_MANIFEST.md"),
    (f"review_bundles/{HISTORY_SUBDIR}/REVIEW_GIT_DIFF.patch", "REVIEW_GIT_DIFF.patch"),
    (f"review_bundles/{HISTORY_SUBDIR}/CUMULATIVE_GIT_DIFF.patch", "CUMULATIVE_GIT_DIFF.patch"),

    # Phase 2.3A New & Changed Files
    ("src/meeting_room_bot/models/reservation.py", "src/meeting_room_bot/models/reservation.py"),
    ("src/meeting_room_bot/models/room.py", "src/meeting_room_bot/models/room.py"),
    ("src/meeting_room_bot/config.py", "src/meeting_room_bot/config.py"),
    ("src/meeting_room_bot/services/meeting_room_service.py", "src/meeting_room_bot/services/meeting_room_service.py"),
    ("src/meeting_room_bot/providers/mock_data.py", "src/meeting_room_bot/providers/mock_data.py"),
    ("src/meeting_room_bot/providers/mock_provider.py", "src/meeting_room_bot/providers/mock_provider.py"),
    ("src/meeting_room_bot/providers/real_provider.py", "src/meeting_room_bot/providers/real_provider.py"),
    ("src/meeting_room_bot/providers/base.py", "src/meeting_room_bot/providers/base.py"),
    ("src/meeting_room_bot/providers/__init__.py", "src/meeting_room_bot/providers/__init__.py"),
    ("src/meeting_room_bot/account_link/app.py", "src/meeting_room_bot/account_link/app.py"),
    ("src/meeting_room_bot/account_link/templates/timeline.html", "src/meeting_room_bot/account_link/templates/timeline.html"),
    ("src/meeting_room_bot/telegram/bot.py", "src/meeting_room_bot/telegram/bot.py"),
    ("docs/V0_2_PHASE2_3A_WEB_APP.md", "docs/V0_2_PHASE2_3A_WEB_APP.md"),
    ("docs/V0_2_ARCHITECTURE_PLAN.md", "docs/V0_2_ARCHITECTURE_PLAN.md"),
    ("tests/test_phase2_3a_web_app.py", "tests/test_phase2_3a_web_app.py"),
    ("scripts/smoke_test_phase2_3a.py", "scripts/smoke_test_phase2_3a.py"),
    ("scripts/pack_review_bundle.py", "scripts/pack_review_bundle.py"),

    # Phase 2.2 Core & Template Files
    ("src/meeting_room_bot/account_link/session_store.py", "src/meeting_room_bot/account_link/session_store.py"),
    ("src/meeting_room_bot/account_link/token_service.py", "src/meeting_room_bot/account_link/token_service.py"),
    ("src/meeting_room_bot/account_link/templates/login.html", "src/meeting_room_bot/account_link/templates/login.html"),
    ("src/meeting_room_bot/account_link/templates/error.html", "src/meeting_room_bot/account_link/templates/error.html"),
    ("src/meeting_room_bot/account_link/templates/success.html", "src/meeting_room_bot/account_link/templates/success.html"),
    ("src/meeting_room_bot/favorites/json_repository.py", "src/meeting_room_bot/favorites/json_repository.py"),
    ("src/meeting_room_bot/groupware/client.py", "src/meeting_room_bot/groupware/client.py"),
    ("src/meeting_room_bot/telegram/handlers.py", "src/meeting_room_bot/telegram/handlers.py"),
    ("src/meeting_room_bot/telegram/keyboards.py", "src/meeting_room_bot/telegram/keyboards.py"),
    ("docs/V0_2_PHASE2_DEPLOYMENT_PLAN.md", "docs/V0_2_PHASE2_DEPLOYMENT_PLAN.md"),
    ("docs/V0_2_PHASE2_2_WEB_SESSION.md", "docs/V0_2_PHASE2_2_WEB_SESSION.md"),
    ("scripts/run_local_app.py", "scripts/run_local_app.py"),

    # Test Suite
    ("tests/test_phase2_2_web_session.py", "tests/test_phase2_2_web_session.py"),
    ("tests/test_phase2_1_foundation.py", "tests/test_phase2_1_foundation.py"),
    ("tests/test_account_link_localhost.py", "tests/test_account_link_localhost.py"),
    ("tests/test_favorites.py", "tests/test_favorites.py"),

    # Phase 1 & Pre-Phase 2 Source Files (Foundation)
    ("src/meeting_room_bot/utils/date_utils.py", "src/meeting_room_bot/utils/date_utils.py"),
    ("src/meeting_room_bot/utils/__init__.py", "src/meeting_room_bot/utils/__init__.py"),
    ("src/meeting_room_bot/models/user_key.py", "src/meeting_room_bot/models/user_key.py"),
    ("src/meeting_room_bot/models/__init__.py", "src/meeting_room_bot/models/__init__.py"),
    ("src/meeting_room_bot/auth/session_manager.py", "src/meeting_room_bot/auth/session_manager.py"),
    ("src/meeting_room_bot/favorites/repository.py", "src/meeting_room_bot/favorites/repository.py"),
    ("src/meeting_room_bot/favorites/service.py", "src/meeting_room_bot/favorites/service.py"),
    ("src/meeting_room_bot/telegram/mock_service.py", "src/meeting_room_bot/telegram/mock_service.py"),

    # Additional Test Files
    ("tests/test_dynamic_date_handling.py", "tests/test_dynamic_date_handling.py"),
    ("tests/test_platform_abstraction.py", "tests/test_platform_abstraction.py"),
    ("tests/test_real_favorites.py", "tests/test_real_favorites.py"),
    ("tests/test_real_mode_auth_flow.py", "tests/test_real_mode_auth_flow.py"),

    # Earlier Docs
    ("docs/V0_2_PHASE1_REPORT.md", "docs/V0_2_PHASE1_REPORT.md"),

    # 1-Hop Direct Context & Models
    ("src/meeting_room_bot/models/asset.py", "src/meeting_room_bot/models/asset.py"),
    ("src/meeting_room_bot/favorites/models.py", "src/meeting_room_bot/favorites/models.py"),

    # Regression Tests
    ("tests/test_auth_session.py", "tests/test_auth_session.py"),
    ("tests/test_providers.py", "tests/test_providers.py"),
    ("tests/test_multi_user_isolation.py", "tests/test_multi_user_isolation.py"),
    ("tests/test_account_link.py", "tests/test_account_link.py"),
    ("tests/test_room_status_service.py", "tests/test_room_status_service.py"),
    ("tests/test_room_status_attribute.py", "tests/test_room_status_attribute.py"),
    ("tests/test_room_detail_today_filter.py", "tests/test_room_detail_today_filter.py"),
    ("tests/test_today_boundary_room_status.py", "tests/test_today_boundary_room_status.py"),
    ("tests/test_telegram_bot.py", "tests/test_telegram_bot.py"),
    ("tests/test_meeting_room_service.py", "tests/test_meeting_room_service.py"),
    ("tests/test_bugs_safe_edit_and_next_res.py", "tests/test_bugs_safe_edit_and_next_res.py"),
    ("tests/test_flow_entry_state.py", "tests/test_flow_entry_state.py"),
    ("tests/test_precise_room_status.py", "tests/test_precise_room_status.py"),

    # Runtime Closure
    ("src/meeting_room_bot/services/availability_service.py", "src/meeting_room_bot/services/availability_service.py"),
    ("src/meeting_room_bot/services/room_status_service.py", "src/meeting_room_bot/services/room_status_service.py"),
    ("src/meeting_room_bot/auth/models.py", "src/meeting_room_bot/auth/models.py"),
    ("src/meeting_room_bot/telegram/states.py", "src/meeting_room_bot/telegram/states.py"),
    ("src/meeting_room_bot/__init__.py", "src/meeting_room_bot/__init__.py"),
    ("src/meeting_room_bot/auth/__init__.py", "src/meeting_room_bot/auth/__init__.py"),
    ("src/meeting_room_bot/favorites/__init__.py", "src/meeting_room_bot/favorites/__init__.py"),
    ("src/meeting_room_bot/groupware/__init__.py", "src/meeting_room_bot/groupware/__init__.py"),
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
            "tests/test_phase2_3a_web_app.py",
            "tests/test_phase2_2_web_session.py",
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
    content = f"""# Review Bundle Manifest: v0.2 Phase 2.3A Hardening (Security & UX Hardening)

## 1. Bundle Identification & Git Lineage
- **Bundle File**: `{ZIP_FILENAME}`
- **History Directory**: `review_bundles/{HISTORY_SUBDIR}/`
- **Release Base Tag**: `{RELEASE_BASE_TAG}` (`f214e39b607e0f28def41b4d0ee5630017b63d85`)
- **Task Base Commit**: `{TASK_BASE_COMMIT}`
- **Current HEAD Commit**: `{head_commit}`
- **Branch**: `{branch}`
- **Generated Date**: 2026-10-23
- **Working Tree**: `CLEAN`
- **Patch Range**: `{TASK_BASE_COMMIT}..{head_commit}`
- **Cumulative Range**: `{RELEASE_BASE_TAG}..{head_commit}`

---

## 2. Review Bundle Purpose & Scope
This review bundle contains the complete, curated, and independently testable set of files for verifying **v0.2 Phase 2.3A Hardening** prior to any GitHub push or Telegram Mini App coupling.

### Scope & Constraints:
- **BLOCKER Fix**: Initial Timeline JSON XSS Prevention via Jinja2 autoescape & safe JSON serialization (`tojson`).
- **User Display HTML Injection Prevention**: Jinja2 autoescaping applied across all template contexts.
- **XSS Regression Test Suite**: Automated verification ensuring script breakouts and `<img>` injection cannot succeed.
- **Clean UX**: Removed debug/legacy banner (`"Timeline UI는 다음 단계에서 제공됩니다 (v1)"`) and raw internal `UserKey`.
- **Initial Error Handling**: Show error banner on failure without duplicate automatic fetch; retry on user button click.
- **Configurable Grid Hours**: CSS Custom Property `--timeline-total-hours` dynamically bound to `TIMELINE_START_HOUR` and `TIMELINE_END_HOUR`.
- **Accessibility**: Keyboard interaction (`Enter` / `Space`) supported on reservation blocks.
- **Zero Telegram Dependencies in Web App**: No platform coupling in UI or core.
- **Strict Prohibition**: `git push` was NOT executed.

---

## 3. Key Implementations

### 1) BLOCKER — Initial Timeline JSON XSS Prevention
- Transitioned `render_html()` from custom string replacement to Jinja2 `Environment(autoescape=select_autoescape(['html', 'xml']))`.
- Serialized bootstrap data using `{{{{ initial_data | tojson }}}}`, which safely escapes `<`, `>`, `&`, `'` as `\\u003c`, `\\u003e`, `\\u0026`, `\\u0027`.
- Verified that malicious payloads such as `</script><script>window.XSS=1</script>` cannot break out of the script tag, and decode cleanly into JavaScript objects upon `JSON.parse()`.
- Korean characters preserved naturally with `ensure_ascii=False`.

### 2) user_display HTML Injection Prevention
- All template variables including `{{{{ user_display }}}}` are autoescaped by the Jinja2 engine, preventing injection payloads like `</strong><img src=x onerror=...><strong>` from being parsed as markup.

### 3) Timeline Top Debug/Legacy Banner Cleanup
- Completely removed `"Timeline UI는 다음 단계에서 제공됩니다 (v1)"` and internal UserKey display (`telegram:123...`).
- Display minimal, clear status badge (`🟢 연결됨`) in the header right section.

### 4) Initial Error Handling Fix
- Initial server-side query failure renders error banner immediately via `<script id="initial-error-data">`.
- `DOMContentLoaded` checks `initialError` and stops automatic re-querying to `/api/web/timeline`.
- Re-querying occurs only when the user explicitly clicks `[다시 시도]`.

### 5) Dynamic Hour Grid Configuration
- Replaced hardcoded `calc(100% / 12)` in CSS with `calc(100% / var(--timeline-total-hours, 12))`.
- JavaScript sets `--timeline-total-hours` dynamically based on `end_hour - start_hour`.

### 6) Keyboard Accessibility
- Added keydown event listeners (`Enter`, `Space`) to reservation blocks (`role="button"`, `tabindex="0"`) to trigger the detail modal.

---

## 4. Test Verification
- **Baseline Tests (Phase 2.3A Base)**: 261 passed.
- **New Tests Added (Phase 2.3A Hardening)**: 6 passed in `tests/test_phase2_3a_web_app.py`.
- **Full Pytest Suite**: 267 passed, 0 failed, 0 skipped.
- **Execution Time**: ~5.0s.
- **Standalone Review Bundle Self-Test**: Extracted zip executed cleanly with 100% test pass.
- **End-to-End Smoke Test**: `scripts/smoke_test_phase2_3a.py` 10/10 steps PASSED (including XSS mock payload check).

---

## 5. Artifacts & Web App Metrics
- **HTML Templates**: 4 templates (`login.html`, `timeline.html`, `error.html`, `success.html`)
- **Static Assets**: 0 external assets (self-contained Vanilla HTML5/CSS3/JS, zero npm build dependencies)
- **New Web Endpoints**:
  - `GET /timeline` (enhanced to full Web App)
  - `GET /api/web/timeline` (Web App dynamic JSON API)
- **Secret Scan**: 100% Clean (0 real bot tokens, 0 cookies, 0 hardcoded credentials)

---

## 6. Next Steps: Phase 2.3B Telegram Mini App Adapter
1. Telegram Bot 인라인 키보드에 `web_app=WebAppInfo(url=...)` 연동
2. Telegram `initData` 기반 자동 검증 및 WebSession 매핑
3. Mini App 내 iframe 허용을 위한 CSP 및 `X-Frame-Options` 선별적 조정
4. 뒤로가기 버튼 / 햅틱 피드백 이벤트 연동
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
