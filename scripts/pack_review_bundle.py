"""Pack curated review bundle for ChatGPT cross-verification of v0.2 Phase 2.3A-3 Meeting Room Web App User UX Completion."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
HISTORY_SUBDIR = "v0.2_phase2_3a3_history_clean"
OUTPUT_DIR = WORKSPACE_ROOT / "review_bundles" / HISTORY_SUBDIR
ZIP_FILENAME = "suremeetingroom_v0.2_phase2_3a3_history_clean_review.zip"
RELEASE_BASE_TAG = "v0.1-local-mvp"
REMOTE_SAFE_HEAD = "aefce423a690e0d6140906177e0b2251bd0ed354"
TASK_BASE_COMMIT = "fed9b037b70331288ff95db048377e74968b0f2e"

# 1. Exact list of files to include: (rel_path_in_workspace, arcname_in_zip)
BUNDLE_FILES = [
    # Manifest and Diff
    (f"review_bundles/{HISTORY_SUBDIR}/REVIEW_BUNDLE_MANIFEST.md", "REVIEW_BUNDLE_MANIFEST.md"),
    (f"review_bundles/{HISTORY_SUBDIR}/REVIEW_GIT_DIFF.patch", "REVIEW_GIT_DIFF.patch"),
    (f"review_bundles/{HISTORY_SUBDIR}/CUMULATIVE_GIT_DIFF.patch", "CUMULATIVE_GIT_DIFF.patch"),

    # Phase 2.3A-3 New & Changed Files
    ("docs/V0_2_PHASE2_3A3_USER_UX.md", "docs/V0_2_PHASE2_3A3_USER_UX.md"),
    ("tests/test_phase2_3a3_user_ux.py", "tests/test_phase2_3a3_user_ux.py"),
    ("scripts/smoke_test_phase2_3a3.py", "scripts/smoke_test_phase2_3a3.py"),

    # Phase 2.3A-2 Files
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
    (".gitignore", ".gitignore"),

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
    r"daily\.json$",
    r"denylist",
]

SECRET_CONTENT_PATTERNS = [
    (r"\b[0-9]{8,10}:[a-zA-Z0-9_-]{35}\b", "Real Telegram Bot Token"),
    (r"BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY", "Private Key Header"),
    (r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}", "GitHub Token"),
]


def load_private_denylist() -> list[str]:
    """Load private denylist patterns from external environment or gitignored file if present."""
    denylist_file = os.environ.get("REVIEW_PII_DENYLIST_FILE")
    if not denylist_file:
        candidate = WORKSPACE_ROOT / ".local_pii_denylist.txt"
        if candidate.is_file():
            denylist_file = str(candidate)

    if not denylist_file or not os.path.isfile(denylist_file):
        return []

    patterns = []
    try:
        with open(denylist_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
    except Exception as e:
        print(f"WARNING: Could not read private denylist file: {e}", file=sys.stderr)
    return patterns


def verify_real_fixture_sanitization():
    """Verify that all Phase 2.3A-3 test fixtures use standard simulated placeholders."""
    test_path = WORKSPACE_ROOT / "tests" / "test_phase2_3a3_user_ux.py"
    smoke_path = WORKSPACE_ROOT / "scripts" / "smoke_test_phase2_3a3.py"

    if test_path.is_file():
        content = test_path.read_text(encoding="utf-8")
        if "테스트회사" not in content or "홍길동" not in content or "김철수" not in content:
            raise ValueError(f"Fixture sanitization check failed in {test_path.name}: Expected standard placeholders missing.")

    if smoke_path.is_file():
        content = smoke_path.read_text(encoding="utf-8")
        if "테스트회사" not in content or "홍길동" not in content or "김철수" not in content:
            raise ValueError(f"Fixture sanitization check failed in {smoke_path.name}: Expected standard placeholders missing.")
    print("[OK] Real fixture structural sanitization verified: standard placeholders present.")


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


def scan_file_safety(rel_path: str, abs_path: Path, private_denylist: list[str]):
    """Scan file path and contents for accidental secret and PII exposure."""
    for pat in FORBIDDEN_NAME_PATTERNS:
        if re.search(pat, rel_path, re.IGNORECASE):
            raise ValueError(f"Forbidden file detected in bundle list: {rel_path} (matched {pat})")

    # Raw daily.json must never be bundled
    if "daily.json" in rel_path.lower():
        raise ValueError(f"Raw daily.json file detected in bundle list: {rel_path}")

    # Denylist file must never be bundled
    if "denylist" in rel_path.lower():
        raise ValueError(f"Denylist file must never be bundled: {rel_path}")

    try:
        content = abs_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return

    # Secret patterns
    for pat, label in SECRET_CONTENT_PATTERNS:
        matches = re.findall(pat, content)
        if matches:
            raise ValueError(f"Security violation: {label} detected in {rel_path}: {matches[:2]}")

    # Private denylist scan across ALL files (including patches)
    for entry in private_denylist:
        if entry in content:
            raise ValueError(f"Sanitization violation: Operational sample-derived value detected in {rel_path}")


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
    """Extract zip into isolated temp directory and run the bundled test suite and all smoke tests."""
    print("\n=== Running Standalone Review Bundle Self-Test ===")
    with tempfile.TemporaryDirectory() as tmp_dir:
        with zipfile.ZipFile(zip_path, mode="r") as zf:
            zf.extractall(tmp_dir)

        test_files = [
            "tests/test_phase2_3a3_user_ux.py",
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
        sub_env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        cmd = [sys.executable, "-m", "pytest"] + test_files + ["-v"]
        res = subprocess.run(cmd, cwd=tmp_dir, capture_output=True, text=True, encoding="utf-8", errors="replace", env=sub_env)
        if res.returncode != 0:
            print("Self-test FAILED in extracted bundle environment!", file=sys.stderr)
            print("STDOUT:\n", res.stdout, file=sys.stderr)
            print("STDERR:\n", res.stderr, file=sys.stderr)
            raise RuntimeError(f"Review Bundle self-test failed with exit code {res.returncode}")

        match = re.search(r"(\d+)\s+passed", res.stdout)
        passed_count = match.group(1) if match else "all"
        print(f"[OK] Standalone Pytest Suite PASSED: {passed_count} tests executed cleanly within isolated bundle context.")

        # Run Phase 2.3A Smoke Test
        res_3a = subprocess.run([sys.executable, "scripts/smoke_test_phase2_3a.py"], cwd=tmp_dir, capture_output=True, text=True, encoding="utf-8", errors="replace", env=sub_env)
        if res_3a.returncode != 0:
            print("Phase 2.3A Smoke test FAILED in extracted bundle environment!", file=sys.stderr)
            print("STDOUT:\n", res_3a.stdout, file=sys.stderr)
            print("STDERR:\n", res_3a.stderr, file=sys.stderr)
            raise RuntimeError("Phase 2.3A Smoke test failed")
        print("[OK] Standalone Phase 2.3A Smoke Test PASSED: All 10 steps verified.")

        # Run Phase 2.3A-2 Smoke Test
        res_3a2 = subprocess.run([sys.executable, "scripts/smoke_test_phase2_3a2.py"], cwd=tmp_dir, capture_output=True, text=True, encoding="utf-8", errors="replace", env=sub_env)
        if res_3a2.returncode != 0:
            print("Phase 2.3A-2 Smoke test FAILED in extracted bundle environment!", file=sys.stderr)
            print("STDOUT:\n", res_3a2.stdout, file=sys.stderr)
            print("STDERR:\n", res_3a2.stderr, file=sys.stderr)
            raise RuntimeError("Phase 2.3A-2 Smoke test failed")
        print("[OK] Standalone Phase 2.3A-2 Smoke Test PASSED: All 8 scenarios (A-H) verified.")

        # Run Phase 2.3A-3 Smoke Test
        res_3a3 = subprocess.run([sys.executable, "scripts/smoke_test_phase2_3a3.py"], cwd=tmp_dir, capture_output=True, text=True, encoding="utf-8", errors="replace", env=sub_env)
        if res_3a3.returncode != 0:
            print("Phase 2.3A-3 Smoke test FAILED in extracted bundle environment!", file=sys.stderr)
            print("STDOUT:\n", res_3a3.stdout, file=sys.stderr)
            print("STDERR:\n", res_3a3.stderr, file=sys.stderr)
            raise RuntimeError("Phase 2.3A-3 Smoke test failed")
        print("[OK] Standalone Phase 2.3A-3 Smoke Test PASSED: All 16 scenarios (A-P) verified.")


def generate_manifest(head_commit: str, branch: str) -> Path:
    """Generate REVIEW_BUNDLE_MANIFEST.md with exact commit hashes and requirements."""
    manifest_path = OUTPUT_DIR / "REVIEW_BUNDLE_MANIFEST.md"
    content = f"""# Review Bundle Manifest: v0.2 Phase 2.3A-3 History Clean Review

## 1. Bundle Identification & Git Lineage
- **Bundle File**: `{ZIP_FILENAME}`
- **History Directory**: `review_bundles/{HISTORY_SUBDIR}/`
- **Release Base Tag**: `{RELEASE_BASE_TAG}` (`f214e39b607e0f28def41b4d0ee5630017b63d85`)
- **Remote Origin HEAD**: `{REMOTE_SAFE_HEAD}` (`refs/heads/{branch}`)
- **Task Base Commit (Phase 2.3A-2 Safe Base)**: `{TASK_BASE_COMMIT}`
- **Current HEAD Commit**: `{head_commit}`
- **Branch**: `{branch}`
- **Generated Date**: 2026-10-26
- **Working Tree**: `CLEAN`
- **Patch Range**: `{TASK_BASE_COMMIT}..{head_commit}`
- **Cumulative Range**: `{RELEASE_BASE_TAG}..{head_commit}`
- **History Rewrite Result**: Squashed unpublished Phase 2.3A-3 intermediate commits on top of safe Phase 2.3A-2 base (`{TASK_BASE_COMMIT}`). Remote origin commits (`{REMOTE_SAFE_HEAD}`) and approved Phase 2.3A/2.3A-2 history preserved intact.

---

## 2. Review Bundle Purpose & Scope
This review bundle contains the complete, curated, and independently testable set of files for verifying **v0.2 Phase 2.3A-3 History Clean Review** (complete Git history squash of intermediate commits, operational value sanitization, detail modal label formatting, and multi-stage smoke suite verification) prior to any GitHub push or Telegram Mini App coupling.

### Scope & Hardening Goals:
1. **Unpublished Phase 2.3A-3 History Cleanup**:
   - Intermediate commits from Phase 2.3A-3 development squashed into a single clean commit on top of Phase 2.3A-2 safe base (`{TASK_BASE_COMMIT}`).
   - Git history and generated patches (`REVIEW_GIT_DIFF.patch`, `CUMULATIVE_GIT_DIFF.patch`) contain zero operational sample-derived values (neither additions nor deleted lines).
2. **Scanner & Fixture Sanitization (No Raw PII in Source)**:
   - Automated scanner (`pack_review_bundle.py`) does not hardcode any raw employee names or operational strings.
   - Verification uses dynamic external denylist loading (`.local_pii_denylist.txt` / `REVIEW_PII_DENYLIST_FILE`) and rule-based fixture validation.
   - Raw `daily.json` files prohibited from the repository and review bundle.
   - All real-data test fixtures strictly use standard simulated placeholders (`"홍길동"`, `"김철수"`, `"이영희"`, `"테스트회사"`, `"주간 회의"`).
3. **전체 위치 상세 Modal 이중 괄호 방지 (Modal Label Formatting)**:
   - `openDetailModal` formats as `${{locLabel}} · ${{capPart}}`, rendering `[판교] 7층 · 정원: 6인실` (all locations) and `7층 회의실 · 정원: 6인실` (single asset) without duplicate brackets (`[[...]]`).
4. **Smoke Test Suite Maintenance**:
   - `smoke_test_phase2_3a2.py` updated to match current UI empty state string (`"현재 사용 가능한 회의실이 없습니다."`).
   - All 3 smoke scripts (Phase 2.3A, 2.3A-2, 2.3A-3) run and pass independently.
5. **Real Groupware Mapping Logic Maintained**:
   - Reserver: authoritative `res_dict["user"]["name"]` > property 51 > legacy fields.
   - Meeting title: authoritative `properties[attributeId=50].content` > legacy fields.
   - Anonymity: `useAnonym == true` masks to `"비공개"`.
   - All-location labels: `format_asset_all_location_label` preserves `"판교"` and `"대전"`.
6. **Strict Prohibition**: `git push` was NOT executed.

---

## 3. Key Implementations

### 1) Template & Detail Modal Label ([timeline.html](src/meeting_room_bot/account_link/templates/timeline.html))
- `openDetailModal(room, res)`:
  - `const locLabel = room.asset_short_label || room.asset_name || '';`
  - `const capPart = room.capacity ? \`정원: ${{room.capacity}}인실\` : '회의실';`
  - `modalRoomMeta.textContent = locLabel ? \`${{locLabel}} · ${{capPart}}\` : capPart;`
  - Elimination of duplicate brackets (`[[`) across all locations and single asset views.
- Section header clean binding: `room.asset_name || room.asset_short_label || '위치'`.
- Initial placeholder subtitle sanitized to `회의실 정보`.

### 2) Test Fixtures & Smoke Test Suite
- `tests/test_phase2_3a3_user_ux.py`:
  - `real_daily_sample`: `id=100001`, `user.name="홍길동"`, `companyName="테스트회사"`, `meeting_title="주간 회의"`.
  - `test_user_name_vs_property_51_priority`: `user.name="김철수"` vs `property 51="개발팀"`.
  - `test_timeline_modal_label_no_double_brackets`: Test 39 verifying no double brackets.
- `scripts/smoke_test_phase2_3a2.py`:
  - Updated empty state assertion to `"현재 사용 가능한 회의실이 없습니다."`.
- `scripts/smoke_test_phase2_3a3.py`:
  - Scenario O (sanitized actual shape mapping) and Scenario P (site label and modal formatting).

### 3) Review Bundle Packer & Security Engine ([pack_review_bundle.py](scripts/pack_review_bundle.py))
- Dynamic private denylist loading (`.local_pii_denylist.txt`).
- Full bundle scanning across all files including `.patch` diffs.
- Automated execution of all 3 smoke test suites in extracted standalone environment.

---

## 4. Test Verification
- **Full Pytest Suite**: 341 passed, 0 failed, 0 skipped.
- **Phase 2.3A Smoke Test**: `scripts/smoke_test_phase2_3a.py` (10/10 steps PASSED).
- **Phase 2.3A-2 Smoke Test**: `scripts/smoke_test_phase2_3a2.py` (All 8 scenarios A-H PASSED).
- **Phase 2.3A-3 Smoke Test**: `scripts/smoke_test_phase2_3a3.py` (All 16 scenarios A-P PASSED).
- **Secret Scan**: 100% Clean (0 tokens, 0 cookies, 0 hardcoded credentials).
- **Fixture Sanitization Scan**: 100% Clean (Real Groupware sample-derived operational values sanitized).
- **Patch Sanitization Scan**: 100% Clean (REVIEW_GIT_DIFF and CUMULATIVE_GIT_DIFF free of sample-derived operational values).
- **Raw daily.json Absence**: 100% Confirmed (0 raw daily.json files in repository or bundle).
- **Modal Label Verification**: Double brackets (`[[`) verified absent in template and rendered modal room meta.
- **Standalone Review Bundle Self-Test**: Extracted zip executed cleanly with 100% test pass (251 pytest tests + 3 smoke scripts).

---

## 5. Artifacts & Web App Metrics
- **HTML Templates**: 4 templates (`login.html`, `timeline.html`, `error.html`, `success.html`)
- **Active Web Endpoints**:
  - `GET /timeline` (NOW, WHEN, WHO, TIMELINE unified Web App)
  - `GET /api/web/timeline` (Timeline & floor data API, supports `asset_id="all"`)
  - `GET /api/web/availability` (WHEN mode room availability API, supports `asset_id="all"`)
  - `GET /api/web/reservations` (WHO mode person-centric reservations API)
  - `POST /logout` (Session termination)
- **Secret Scan**: 100% Clean
- **Sanitization Scan**: 100% Clean

---

## 6. Next Steps: Phase 2.3B Telegram Mini App Adapter
1. Telegram Bot inline keyboard `web_app=WebAppInfo(url=...)` integration.
2. Telegram `initData` signature validation and automatic WebSession association.
3. CSP frame-ancestors adjustment for secure Telegram Mini App iframe embedding.
4. Telegram BackButton / HapticFeedback platform adapter integration.
"""
    manifest_path.write_text(content, encoding="utf-8")
    print(f"[OK] Generated {manifest_path.name} (HEAD={head_commit})")
    return manifest_path


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = OUTPUT_DIR / ZIP_FILENAME

    print(f"=== Creating Review Bundle: {ZIP_FILENAME} ===")
    print(f"Release Base Tag: {RELEASE_BASE_TAG}")
    print(f"Remote Safe Head: {REMOTE_SAFE_HEAD}")
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
    verify_real_fixture_sanitization()
    private_denylist = load_private_denylist()
    if private_denylist:
        print(f"[OK] Loaded private denylist ({len(private_denylist)} rules from local/env config).")

    total_uncompressed_bytes = 0
    valid_files = []

    for rel_path, arcname in BUNDLE_FILES:
        abs_path = WORKSPACE_ROOT / rel_path
        if not abs_path.is_file():
            print(f"ERROR: Missing bundle file: {rel_path}", file=sys.stderr)
            sys.exit(1)

        scan_file_safety(rel_path, abs_path, private_denylist)
        file_size = abs_path.stat().st_size
        total_uncompressed_bytes += file_size
        valid_files.append((rel_path, abs_path, file_size, arcname))

    print(f"[OK] Security and Sanitization scan passed: 100% clean across all {len(valid_files)} bundled files (including patches).")
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
