"""Pack curated review bundle for ChatGPT cross-verification of v0.2 Phase 1 Complete."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
HISTORY_SUBDIR = "v0.2_pre_phase2_datefix"
OUTPUT_DIR = WORKSPACE_ROOT / "review_bundles" / HISTORY_SUBDIR
ZIP_FILENAME = "suremeetingroom_v0.2_pre_phase2_datefix_review.zip"
BASE_TAG = "v0.1-local-mvp"

# 1. Exact list of files to include: (rel_path_in_workspace, arcname_in_zip)
BUNDLE_FILES = [
    # Manifest and Diff (stored in review_bundles/v0.2_pre_phase2_datefix/)
    (f"review_bundles/{HISTORY_SUBDIR}/REVIEW_BUNDLE_MANIFEST.md", "REVIEW_BUNDLE_MANIFEST.md"),
    (f"review_bundles/{HISTORY_SUBDIR}/REVIEW_GIT_DIFF.patch", "REVIEW_GIT_DIFF.patch"),

    # Changed Source Files (v0.2 & Date Fix)
    ("src/meeting_room_bot/utils/date_utils.py", "src/meeting_room_bot/utils/date_utils.py"),
    ("src/meeting_room_bot/utils/__init__.py", "src/meeting_room_bot/utils/__init__.py"),
    ("src/meeting_room_bot/models/user_key.py", "src/meeting_room_bot/models/user_key.py"),
    ("src/meeting_room_bot/models/__init__.py", "src/meeting_room_bot/models/__init__.py"),
    ("src/meeting_room_bot/providers/mock_data.py", "src/meeting_room_bot/providers/mock_data.py"),
    ("src/meeting_room_bot/providers/mock_provider.py", "src/meeting_room_bot/providers/mock_provider.py"),
    ("src/meeting_room_bot/providers/base.py", "src/meeting_room_bot/providers/base.py"),
    ("src/meeting_room_bot/providers/real_provider.py", "src/meeting_room_bot/providers/real_provider.py"),
    ("src/meeting_room_bot/auth/session_manager.py", "src/meeting_room_bot/auth/session_manager.py"),
    ("src/meeting_room_bot/favorites/repository.py", "src/meeting_room_bot/favorites/repository.py"),
    ("src/meeting_room_bot/favorites/json_repository.py", "src/meeting_room_bot/favorites/json_repository.py"),
    ("src/meeting_room_bot/favorites/service.py", "src/meeting_room_bot/favorites/service.py"),
    ("src/meeting_room_bot/services/meeting_room_service.py", "src/meeting_room_bot/services/meeting_room_service.py"),
    ("src/meeting_room_bot/account_link/token_service.py", "src/meeting_room_bot/account_link/token_service.py"),
    ("src/meeting_room_bot/telegram/handlers.py", "src/meeting_room_bot/telegram/handlers.py"),
    ("src/meeting_room_bot/telegram/mock_service.py", "src/meeting_room_bot/telegram/mock_service.py"),
    ("scripts/pack_review_bundle.py", "scripts/pack_review_bundle.py"),

    # Changed / Added Test Files
    ("tests/test_dynamic_date_handling.py", "tests/test_dynamic_date_handling.py"),
    ("tests/test_favorites.py", "tests/test_favorites.py"),
    ("tests/test_platform_abstraction.py", "tests/test_platform_abstraction.py"),

    # Changed / Added Docs
    ("docs/V0_2_ARCHITECTURE_PLAN.md", "docs/V0_2_ARCHITECTURE_PLAN.md"),
    ("docs/V0_2_PHASE1_REPORT.md", "docs/V0_2_PHASE1_REPORT.md"),

    # 1-Hop Direct Context & Consumer Files
    ("src/meeting_room_bot/account_link/app.py", "src/meeting_room_bot/account_link/app.py"),
    ("src/meeting_room_bot/models/asset.py", "src/meeting_room_bot/models/asset.py"),
    ("src/meeting_room_bot/models/room.py", "src/meeting_room_bot/models/room.py"),
    ("src/meeting_room_bot/models/reservation.py", "src/meeting_room_bot/models/reservation.py"),
    ("src/meeting_room_bot/favorites/models.py", "src/meeting_room_bot/favorites/models.py"),
    ("src/meeting_room_bot/groupware/client.py", "src/meeting_room_bot/groupware/client.py"),

    # Directly Related Regression Tests
    ("tests/test_auth_session.py", "tests/test_auth_session.py"),
    ("tests/test_providers.py", "tests/test_providers.py"),
    ("tests/test_multi_user_isolation.py", "tests/test_multi_user_isolation.py"),

    # Runtime Closure (Required for Independent Test Execution)
    ("src/meeting_room_bot/services/availability_service.py", "src/meeting_room_bot/services/availability_service.py"),
    ("src/meeting_room_bot/services/room_status_service.py", "src/meeting_room_bot/services/room_status_service.py"),
    ("src/meeting_room_bot/auth/models.py", "src/meeting_room_bot/auth/models.py"),
    ("src/meeting_room_bot/telegram/keyboards.py", "src/meeting_room_bot/telegram/keyboards.py"),
    ("src/meeting_room_bot/telegram/states.py", "src/meeting_room_bot/telegram/states.py"),
    ("src/meeting_room_bot/__init__.py", "src/meeting_room_bot/__init__.py"),
    ("src/meeting_room_bot/auth/__init__.py", "src/meeting_room_bot/auth/__init__.py"),
    ("src/meeting_room_bot/favorites/__init__.py", "src/meeting_room_bot/favorites/__init__.py"),
    ("src/meeting_room_bot/groupware/__init__.py", "src/meeting_room_bot/groupware/__init__.py"),
    ("src/meeting_room_bot/providers/__init__.py", "src/meeting_room_bot/providers/__init__.py"),
    ("src/meeting_room_bot/services/__init__.py", "src/meeting_room_bot/services/__init__.py"),
    ("src/meeting_room_bot/telegram/__init__.py", "src/meeting_room_bot/telegram/__init__.py"),
    ("src/meeting_room_bot/account_link/__init__.py", "src/meeting_room_bot/account_link/__init__.py"),
    ("src/meeting_room_bot/account_link/templates/error.html", "src/meeting_room_bot/account_link/templates/error.html"),
    ("src/meeting_room_bot/account_link/templates/login.html", "src/meeting_room_bot/account_link/templates/login.html"),
    ("src/meeting_room_bot/account_link/templates/success.html", "src/meeting_room_bot/account_link/templates/success.html"),
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


def verify_changed_files_consistency():
    """Verify that every file changed since BASE_TAG is either in BUNDLE_FILES or EXCLUDED_CHANGED_FILES."""
    try:
        diff_out = subprocess.check_output(
            ["git", "diff", "--name-only", BASE_TAG],
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
    print(f"[OK] Changed Files consistency check passed ({len(changed_files)} changed files verified against BASE).")


def run_standalone_bundle_self_test(zip_path: Path):
    """Extract zip into isolated temp directory and run the bundled test suite."""
    print("\n=== Running Standalone Review Bundle Self-Test ===")
    with tempfile.TemporaryDirectory() as tmp_dir:
        with zipfile.ZipFile(zip_path, mode="r") as zf:
            zf.extractall(tmp_dir)

        test_files = [
            "tests/test_dynamic_date_handling.py",
            "tests/test_platform_abstraction.py",
            "tests/test_auth_session.py",
            "tests/test_favorites.py",
            "tests/test_providers.py",
            "tests/test_multi_user_isolation.py",
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


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = OUTPUT_DIR / ZIP_FILENAME

    print(f"=== Creating Review Bundle: {ZIP_FILENAME} ===")
    print(f"Base Tag / Commit: {BASE_TAG}")
    print(f"History Output Directory: {OUTPUT_DIR}")

    # 1. Update UTF-8 patch in history dir
    patch_path = OUTPUT_DIR / "REVIEW_GIT_DIFF.patch"
    diff_bytes = subprocess.check_output(
        ["git", "diff", BASE_TAG, "--", ".", ":(exclude)review_bundles"],
        cwd=WORKSPACE_ROOT,
    )
    patch_path.write_bytes(diff_bytes)
    print(f"[OK] Updated REVIEW_GIT_DIFF.patch ({len(diff_bytes):,} bytes, UTF-8)")

    # 2. Check changed files consistency
    verify_changed_files_consistency()

    # 3. Verify all files exist and are safe
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

    # 4. Build ZIP archive
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel_path, abs_path, _, arcname in valid_files:
            zf.write(abs_path, arcname=arcname.replace("\\", "/"))

    zip_size = zip_path.stat().st_size
    print(f"ZIP created successfully: {zip_path}")
    print(f"ZIP size: {zip_size:,} bytes ({zip_size / 1024:.2f} KB)")

    # 5. Verify ZIP integrity
    with zipfile.ZipFile(zip_path, mode="r") as zf:
        test_res = zf.testzip()
        if test_res is not None:
            raise RuntimeError(f"Corrupt file in ZIP: {test_res}")
        namelist = zf.namelist()
        print(f"ZIP integrity check PASSED ({len(namelist)} items in archive)")

    # 6. Run standalone self-test
    run_standalone_bundle_self_test(zip_path)

    print("\n[SUCCESS] Review bundle ready.")


if __name__ == "__main__":
    main()
