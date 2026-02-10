# -*- coding: utf-8 -*-
"""
Legacy absence tests: verify all legacy packages have been removed.

After the modular monolith migration, these directories must not exist:
- src/api
- src/application
- src/infrastructure/di
- src/infrastructure/persistence
- src/models
"""

from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
TESTS_DIR = PROJECT_ROOT / "tests"

BANNED_DIRECTORIES = [
    "api",
    "application",
    "domain",
    "infrastructure/di",
    "infrastructure/persistence",
    "models",
]

BANNED_TEST_DIRECTORIES = [
    "domain",
]


class TestLegacyAbsence:
    """Verify all legacy compatibility surfaces have been removed."""

    @pytest.mark.parametrize("rel_path", BANNED_DIRECTORIES)
    def test_legacy_directory_absent(self, rel_path: str):
        """Legacy directory must not exist."""
        directory = SRC_DIR / rel_path
        if directory.exists():
            files = sorted(f.relative_to(SRC_DIR).as_posix() for f in directory.rglob("*.py"))
            pytest.fail(
                f"Legacy directory src/{rel_path} still exists!\n"
                f"Files: {files}\n\n"
                f"All code must live in src/modules/ or src/shared/."
            )

    @pytest.mark.parametrize("rel_path", BANNED_TEST_DIRECTORIES)
    def test_legacy_test_directory_absent(self, rel_path: str):
        """Legacy test directory must not exist."""
        directory = TESTS_DIR / rel_path
        if directory.exists():
            files = sorted(
                f.relative_to(TESTS_DIR).as_posix()
                for f in directory.rglob("*")
                if f.is_file()
            )
            pytest.fail(
                f"Legacy test directory tests/{rel_path} still exists!\n"
                f"Files: {files}\n\n"
                f"All tests must live in module-aligned paths (e.g. tests/modules/...)."
            )

    def test_no_legacy_imports_in_src(self):
        """No src code should import from banned legacy roots."""
        import ast

        banned_prefixes = [
            "src.api.",
            "src.application.",
            "src.domain.",
            "src.infrastructure.di.",
            "src.infrastructure.persistence.",
            "src.models.",
        ]
        violations = []

        for py_file in SRC_DIR.rglob("*.py"):
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            except SyntaxError:
                continue

            rel = py_file.relative_to(SRC_DIR).as_posix()
            for node in ast.walk(tree):
                module = None
                if isinstance(node, ast.ImportFrom) and node.module:
                    module = node.module
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        module = alias.name

                if module:
                    for prefix in banned_prefixes:
                        if module.startswith(prefix) or module == prefix.rstrip("."):
                            violations.append(f"src/{rel}:{node.lineno} imports '{module}'")

        if violations:
            pytest.fail(
                "Legacy imports found in src/!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
            )
