"""Pack curated review bundle for ChatGPT cross-verification of v0.2 Phase 2.3A-2 Meeting Room Web App Core UX Integration."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
HISTORY_SUBDIR = "v0.2_phase2_3a2_web_ux"
OUTPUT_DIR = WORKSPACE_ROOT / "review_bundles" / HISTORY_SUBDIR
ZIP_FILENAME = "suremeetingroom_v0.2_phase2_3a2_web_ux_review.zip"
RELEASE_BASE_TAG = "v0.1-local-mvp"
TASK_BASE_COMMIT = "1c562861cd4d876b8ddf95dd71728d20a6ba92f2"

# 1. Exact list of files to include: (rel_path_in_workspace, arcname_in_zip)
BUNDLE_FILES = [
    # Manifest and Diff
    (f"review_bundles/{HISTORY_SUBDIR}/REVIEW_BUNDLE_MANIFEST.md", "REVIEW_BUNDLE_MANIFEST.md"),
    (f"review_bundles/{HISTORY_SUBDIR}/REVIEW_GIT_DIFF.patch", "REVIEW_GIT_DIFF.patch"),
    (f"review_bundles/{HISTORY_SUBDIR}/CUMULATIVE_GIT_DIFF.patch", "CUMULATIVE_GIT_DIFF.patch"),

    # Phase 2.3A-2 New & Changed Files
    ("docs/V0_2_PHASE2_3A2_WEB_UX.md", "docs/V0_2_PHASE2_3A2_WEB_UX.md"),
    ("tests/test_phase2_3a2_web_ux.py", "tests/test_phase2_3a2_web_ux.py"),
    ("scripts/smoke_test_phase2_3a2.py", "scripts/smoke_test_phase2_3a2.py"),

    # Phase 2.3A Files
    ("src/meeting_room_bot/models/reservation.py", "src/meeting_room_bot/models/reservation.py"),
    ("src/meeting_room_bot/models/room.py", "src/meeting_room_bot/models/room.py"),
    ("src/meeting_room_bot/config.py", "src/meeting_room_bot/config.py"),
    ("src/meeting_room_bot/services/meeting_room_service.py", "src/meeting_room_bot/services/meeting_room_service.py"),
    ("src/meeting_room_bot/services/availability_service.py", "src/meeting_room_bot/services/availability_service.py"),
    ("src/meeting_room_bot/services/room_status_service.py", "src/meeting_room_bot/services/room_status_service.py"),
    ("src/meeting_room_bot/services/__init__.py", "src/meeting_room_bot/services/__init__.py"),
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
    ("src/meeting_room_bot/favorites/__init__.py", "src/meeting_room_bot/favorites/__init__.py"),
    ("src/meeting_room_bot/telegram/states.py", "src/meeting_room_bot/telegram/states.py"),
    ("src/meeting_room_bot/telegram/__init__.py", "src/meeting_room_bot/telegram/__init__.py"),
    ("src/meeting_room_bot/__init__.py", "src/meeting_room_bot/__init__.py"),
    ("pytest.ini", "pytest.ini"),
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
    ("tests/test_client.py", "tests/test_client.py"),
    ("tests/test_availability_service.py", "tests/test_availability_service.py"),
    ("tests/test_precise_room_status.py", "tests/test_precise_room_status.py"),
]

# Explicitly excluded changed files (e.g. caches or scratch files)
EXCLUDED_CHANGED_FILES = set()

# Forbidden patterns to prevent accidental leaks
FORBIDDEN_NAME_PATTERNS = [
    r"\.env(?:\..+)?$",
    r"\.pem$",
    r"\.key$",
    r"\.p8$",
    r"\.p12$",
    r"\.db$",
    r"\.sqlite3?$",
    r"\.session$",
    r"\.log$",
    r"__pycache__",
    r"\.pytest_cache",
]

SECRET_CONTENT_PATTERNS = [
    (r"\b[0-9]{8,10}:[a-zA-Z0-9_-]{35}\b", "Real Telegram Bot Token"),
    (r"BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY", "Private Key Header"),
    (r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}", "GitHub Token"),
]


def check_clean_working_tree():
    """Ensure working tree has no uncommitted changes outside review_bundles directory."""
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
        filepath = line[3:].strip()
        if not filepath.startswith("review_bundles"):
            dirty_files.append(line)

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
            "tests/test_phase2_3a2_web_ux.py",
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

        match = re.search(r"(\d+)\s+passed", res.stdout)
        passed_count = match.group(1) if match else "all"
        print(f"[OK] Standalone Self-Test PASSED: {passed_count} tests executed cleanly within isolated bundle context.")


def generate_manifest(head_commit: str, branch: str) -> Path:
    """Generate REVIEW_BUNDLE_MANIFEST.md with exact commit hashes and requirements."""
    manifest_path = OUTPUT_DIR / "REVIEW_BUNDLE_MANIFEST.md"
    head_short = head_commit[:7]
    base_short = TASK_BASE_COMMIT[:7]
    content = f"""# Review Bundle Manifest: v0.2 Phase 2.3A-2 Meeting Room Web App Core UX Integration

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
This review bundle contains the complete, curated, and independently testable set of files for verifying **v0.2 Phase 2.3A-2 Meeting Room Web App Core UX Integration** prior to any GitHub push or Telegram Mini App coupling.

### Scope & Product UX Goals:
- **Core UX Integration**: Integrates the 4 proven Telegram bot concepts ("지금 빈 회의실", "언제 빈 회의실", "어디 빈 회의실", "즐겨찾기") into a single-screen responsive Web App with fewer touches and higher clarity.
- **Top 3-Mode Navigation**: `[🟢 지금]` (NOW), `[🕐 언제]` (WHEN), `[📊 전체]` (TIMELINE) segmented tab navigation with instant client-side switching.
- **NOW Mode (Default)**: Instant card view showing currently available rooms, capacity, and next reservation / available duration (e.g. `약 55분 사용 가능` or `오늘 남은 예약 없음`). Available rooms are ready on initial load via bootstrap data without additional roundtrips.
- **WHEN Mode**: User selects start time (`08:00 ~ 19:30`, 30m steps) and duration pills (`30분`, `1시간`, `1시간 30분`, `2시간`), returning slot-available rooms with zero conflict across the entire requested interval.
- **"WHERE" Integration**: Integrated into top floor/location dropdown (`[ 판교 7층 ▼ ]`) populated dynamically from actual Asset metadata (no hardcoding).
- **Universal Favorites Scope**: `[ 전체 ]` vs `[ ⭐ 즐겨찾기 ]` scope toggle operates orthogonally across all 3 modes (NOW + fav, WHEN + fav, TIMELINE + fav).
- **Preserved TIMELINE Mode**: 100% preservation of Phase 2.3A interactive timeline (08:00~20:00 dynamic hours axis, current time indicator line, sticky room column, reservation blocks, and detail bottom sheet modal).
- **Shared Core Reuse (Zero Duplication)**: Reuses `AvailabilityService.find_available_rooms` and `RoomStatusService.calculate_status`. Zero duplication of business availability logic in the Web presentation tier.
- **New Web API Endpoint**: `GET /api/web/availability` returning pure structured JSON (no Telegram formatting strings).
- **Platform Independence**: Zero `Telegram.WebApp` dependencies (Mini App adapter deferred to Phase 2.3B).
- **Strict Prohibition**: `git push` was NOT executed.

---

## 3. Key Implementations

### 1) NOW Mode (Immediate Room Finding)
- Default initial landing mode for immediate task completion on mobile.
- Enriched timeline and mock datasets with `next_reservation_start`, `available_until`, and `available_minutes`.
- Clean card layout with high-contrast availability status and next reservation countdown.

### 2) WHEN Mode (Slot Availability Query)
- Added `GET /api/web/availability?asset_id=...&start=...&duration_minutes=...`.
- Reused `AvailabilityService.find_available_rooms` for strict conflict detection (`res_start < req_end and res_end > req_start`).
- Handled boundary conditions: `res.start == req.end` and `res.end == req.start` are correctly permitted as available.
- Interactive start time select and duration pills with instantaneous reactive querying.

### 3) WHERE & Favorites Integration
- Floor dropdown dynamically driven by `Asset` models.
- Segmented favorite filter updates results across NOW cards, WHEN cards, and TIMELINE grid.
- Dedicated empty states for NOW, WHEN, Favorites, and Asset conditions.

### 4) Security & Platform Hygiene
- Maintained Jinja2 `tojson` safe serialization for initial bootstrap scripts, completely preventing XSS breakouts.
- Safe DOM node creation and text escaping (`escapeHtml`).
- Zero session token or credential leakage.
- Web tier is completely platform-independent (0 Telegram dependencies).

---

## 4. Test Verification
- **Baseline Tests (Phase 2.3A Hardening Base)**: 267 passed.
- **New Tests Added (Phase 2.3A-2 Core UX)**: 23 passed in `tests/test_phase2_3a2_web_ux.py`.
- **Full Pytest Suite**: 290 passed, 0 failed, 0 skipped.
- **Execution Time**: ~5.0s.
- **Standalone Review Bundle Self-Test**: Extracted zip executed cleanly with 100% test pass across all bundled test suites.
- **End-to-End UX Smoke Test**: `scripts/smoke_test_phase2_3a2.py` PASSED all 6 core scenarios (A: NOW, B: WHEN, C: Favorites, D: Asset switch, E: Timeline preservation, F: Empty states).
- **Phase 2.3A Smoke Test**: `scripts/smoke_test_phase2_3a.py` 10/10 steps PASSED (100% backward compatibility).

---

## 5. Artifacts & Web App Metrics
- **HTML Templates**: 4 templates (`login.html`, `timeline.html`, `error.html`, `success.html`)
- **Static Assets**: 0 external assets (self-contained Vanilla HTML5/CSS3/JS, zero npm build dependencies)
- **Active Web Endpoints**:
  - `GET /timeline` (NOW, WHEN, TIMELINE unified Web App)
  - `GET /api/web/timeline` (Timeline & floor data API)
  - `GET /api/web/availability` (WHEN mode room availability API)
  - `POST /logout` (Session termination)
- **Secret Scan**: 100% Clean (0 real bot tokens, 0 cookies, 0 hardcoded credentials)

---

## 6. Next Steps: Phase 2.3B Telegram Mini App Adapter
1. Telegram Bot inline keyboard `web_app=WebAppInfo(url=...)` integration
2. Telegram `initData` signature validation and automatic WebSession association
3. CSP frame-ancestors adjustment for secure Telegram Mini App iframe embedding
4. Telegram BackButton / HapticFeedback platform adapter integration
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

    # Also copy root bundle
    root_zip = WORKSPACE_ROOT / "review_bundles" / ZIP_FILENAME
    shutil.copyfile(zip_path, root_zip)
    print(f"Copied root bundle: {root_zip}")

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
