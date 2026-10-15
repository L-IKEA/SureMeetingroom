"""Pack curated review bundle for ChatGPT cross-verification of v0.2 Phase 1."""

import os
from pathlib import Path
import re
import sys
import tempfile
import zipfile

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

# 1. Exact list of files to include: (rel_path_in_workspace, arcname_in_zip)
BUNDLE_FILES = [
    # Manifest and Diff (stored in review_bundles/)
    ("review_bundles/REVIEW_BUNDLE_MANIFEST.md", "REVIEW_BUNDLE_MANIFEST.md"),
    ("review_bundles/REVIEW_GIT_DIFF.patch", "REVIEW_GIT_DIFF.patch"),
    # Changed Source Files (v0.2 Phase 1)
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
    ("src/meeting_room_bot/account_link/app.py", "src/meeting_room_bot/account_link/app.py"),
    ("src/meeting_room_bot/telegram/handlers.py", "src/meeting_room_bot/telegram/handlers.py"),
    ("src/meeting_room_bot/telegram/mock_service.py", "src/meeting_room_bot/telegram/mock_service.py"),
    # Changed Test File
    ("tests/test_platform_abstraction.py", "tests/test_platform_abstraction.py"),
    # Changed / Added Docs
    ("docs/V0_2_ARCHITECTURE_PLAN.md", "docs/V0_2_ARCHITECTURE_PLAN.md"),
    ("docs/V0_2_PHASE1_REPORT.md", "docs/V0_2_PHASE1_REPORT.md"),
    # 1-Hop Direct Context Files
    ("src/meeting_room_bot/models/asset.py", "src/meeting_room_bot/models/asset.py"),
    ("src/meeting_room_bot/models/room.py", "src/meeting_room_bot/models/room.py"),
    ("src/meeting_room_bot/models/reservation.py", "src/meeting_room_bot/models/reservation.py"),
    ("src/meeting_room_bot/favorites/models.py", "src/meeting_room_bot/favorites/models.py"),
    ("src/meeting_room_bot/groupware/client.py", "src/meeting_room_bot/groupware/client.py"),
    # Directly Related Regression Tests
    ("tests/test_auth_session.py", "tests/test_auth_session.py"),
    ("tests/test_favorites.py", "tests/test_favorites.py"),
    ("tests/test_providers.py", "tests/test_providers.py"),
    ("tests/test_multi_user_isolation.py", "tests/test_multi_user_isolation.py"),
]

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
    # Check forbidden filenames
    for pat in FORBIDDEN_NAME_PATTERNS:
        if re.search(pat, rel_path, re.IGNORECASE):
            raise ValueError(f"Forbidden file detected in bundle list: {rel_path} (matched {pat})")

    # Check content for sensitive secrets
    try:
        content = abs_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return

    for pat, label in SECRET_CONTENT_PATTERNS:
        matches = re.findall(pat, content)
        if matches:
            raise ValueError(f"Security violation: {label} detected in {rel_path}: {matches[:2]}")


def main():
    output_dir = WORKSPACE_ROOT / "review_bundles"
    output_dir.mkdir(parents=True, exist_ok=True)

    zip_filename = "suremeetingroom_v0.2_phase1_final_review.zip"
    zip_path = output_dir / zip_filename

    print(f"=== Creating Review Bundle: {zip_filename} ===")
    print(f"Base Directory: {WORKSPACE_ROOT}")
    print(f"Output Directory: {output_dir}")

    # Verify all files exist and are safe
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

    # Build ZIP archive
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for rel_path, abs_path, _, arcname in valid_files:
            # Store with normalized relative POSIX path inside the ZIP
            zf.write(abs_path, arcname=arcname.replace("\\", "/"))

    zip_size = zip_path.stat().st_size
    print(f"ZIP created successfully: {zip_path}")
    print(f"ZIP size: {zip_size:,} bytes ({zip_size / 1024:.2f} KB)")

    # Clean up root copies if present
    for cleanup_name in ["REVIEW_BUNDLE_MANIFEST.md", "REVIEW_GIT_DIFF.patch", zip_filename]:
        root_file = WORKSPACE_ROOT / cleanup_name
        if root_file.exists():
            root_file.unlink()

    # Verify ZIP integrity
    with zipfile.ZipFile(zip_path, mode="r") as zf:
        test_res = zf.testzip()
        if test_res is not None:
            raise RuntimeError(f"Corrupt file in ZIP: {test_res}")
        namelist = zf.namelist()
        print(f"ZIP integrity check PASSED ({len(namelist)} items in archive)")

    # Verify extraction in temporary directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        with zipfile.ZipFile(zip_path, mode="r") as zf:
            zf.extractall(tmp_dir)
        extracted_files = [str(p.relative_to(tmp_dir)).replace("\\", "/") for p in Path(tmp_dir).rglob("*") if p.is_file()]
        assert len(extracted_files) == len(BUNDLE_FILES), f"Extraction count mismatch: {len(extracted_files)} vs {len(BUNDLE_FILES)}"
        assert "REVIEW_BUNDLE_MANIFEST.md" in extracted_files
        assert "REVIEW_GIT_DIFF.patch" in extracted_files
        print("Self-verification: Extraction and manifest validation PASSED.")

    print("\n[SUCCESS] Review bundle ready.")


if __name__ == "__main__":
    main()
