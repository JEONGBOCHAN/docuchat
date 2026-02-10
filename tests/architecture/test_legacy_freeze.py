# -*- coding: utf-8 -*-
"""
Legacy freeze tests: prevent growth of legacy paths during modular transition.

New code MUST go into src/modules/*. These tests ensure that legacy paths
(src/application/use_cases, src/api/v1, src/infrastructure/di/container.py)
do not grow — no new files, no significant length increase.

If a test fails, it means new code was added to a legacy path instead
of the proper module under src/modules/.
"""

from pathlib import Path

import pytest


# ──────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"

# Snapshot of allowed files as of modular monolith transition start.
# Files in this list are allowed to exist. Any NEW .py file is a violation.

LEGACY_USE_CASES_ALLOWLIST = {
    "__init__.py",
    "audio_generation.py",
    "channel_crud.py",
    "chat.py",
    "conversation_memory.py",
    "document_crud.py",
    "document_summary.py",
    "exceptions.py",
    "favorite_crud.py",
    "generate_faq.py",
    "learning.py",
    "note_crud.py",
    "podcast.py",
    "process_query.py",
    "search_history.py",
    "search_with_citations.py",
    "summarize.py",
    "timeline_briefing.py",
}

LEGACY_API_V1_ALLOWLIST = {
    "__init__.py",
    "admin.py",
    "audio.py",
    "capacity.py",
    "channels.py",
    "chat.py",
    "citations.py",
    "dashboard.py",
    "deps.py",
    "documents.py",
    "export.py",
    "faq.py",
    "favorites.py",
    "google_drive.py",
    "health.py",
    "mcp.py",
    "notes.py",
    "preview.py",
    "router.py",
    "scheduler.py",
    "search.py",
    "study.py",
    "summarize.py",
    "timeline.py",
    "trash.py",
    "youtube.py",
}

# container.py line count at freeze point.
# Container is now a pure shim (~195 lines). Allow small tolerance.
CONTAINER_MAX_LINES = 250


# ──────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────

class TestLegacyFreeze:
    """Prevent new code from being added to legacy paths."""

    def test_no_new_use_case_files(self):
        """No new .py files should appear in src/application/use_cases/."""
        use_cases_dir = SRC_DIR / "application" / "use_cases"
        if not use_cases_dir.exists():
            return

        current_files = {
            f.name for f in use_cases_dir.iterdir()
            if f.is_file() and f.suffix == ".py"
        }
        new_files = current_files - LEGACY_USE_CASES_ALLOWLIST
        if new_files:
            msg = (
                "New files detected in legacy path src/application/use_cases/!\n\n"
                + "\n".join(f"  - {f}" for f in sorted(new_files))
                + "\n\nFix: add new use cases to src/modules/<module>/application/use_cases/ instead."
            )
            pytest.fail(msg)

    def test_no_new_api_v1_files(self):
        """No new .py files should appear in src/api/v1/."""
        api_dir = SRC_DIR / "api" / "v1"
        if not api_dir.exists():
            return

        current_files = {
            f.name for f in api_dir.iterdir()
            if f.is_file() and f.suffix == ".py"
        }
        new_files = current_files - LEGACY_API_V1_ALLOWLIST
        if new_files:
            msg = (
                "New files detected in legacy path src/api/v1/!\n\n"
                + "\n".join(f"  - {f}" for f in sorted(new_files))
                + "\n\nFix: add new API routes to src/modules/<module>/presentation/api/ instead."
            )
            pytest.fail(msg)

    def test_container_does_not_grow(self):
        """src/infrastructure/di/container.py must not grow beyond freeze limit."""
        container = SRC_DIR / "infrastructure" / "di" / "container.py"
        if not container.exists():
            return

        line_count = len(container.read_text(encoding="utf-8").splitlines())
        assert line_count <= CONTAINER_MAX_LINES, (
            f"container.py has {line_count} lines (limit: {CONTAINER_MAX_LINES}).\n"
            f"New DI logic should go into src/modules/<module>/infrastructure/di.py instead."
        )
