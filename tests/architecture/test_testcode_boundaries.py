# -*- coding: utf-8 -*-
"""Architecture guard tests: enforce test code import boundaries.

These tests ensure that test files follow the same modular architecture
rules as production code — specifically, that API tests do not import
from legacy container paths or legacy db_models paths.
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_TEST_DIR = PROJECT_ROOT / "tests" / "api" / "v1"


def _collect_python_files(directory: Path) -> list[Path]:
    """Collect all .py files under *directory* recursively."""
    return sorted(directory.rglob("*.py"))


def _extract_imports(filepath: Path) -> list[tuple[int, str]]:
    """Parse *filepath* and return (line_number, module_name) for every import."""
    source = filepath.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((node.lineno, node.module))
    return imports


# ──────────────────────────────────────────────────────────
# Test: API tests must not import from legacy container
# ──────────────────────────────────────────────────────────

FORBIDDEN_PREFIXES = [
    "src.infrastructure.di.container",
]

LEGACY_EXCEPTIONS: set[str] = set()


class TestApiTestImportBoundaries:
    """Ensure API test files do not import from legacy container paths."""

    def test_no_container_imports_in_api_tests(self):
        """API tests must use module public imports, not container imports."""
        violations: list[str] = []
        for filepath in _collect_python_files(API_TEST_DIR):
            rel = filepath.relative_to(PROJECT_ROOT).as_posix()
            if rel in LEGACY_EXCEPTIONS:
                continue
            for lineno, module in _extract_imports(filepath):
                for prefix in FORBIDDEN_PREFIXES:
                    if module == prefix or module.startswith(prefix + "."):
                        violations.append(
                            f"{rel}:{lineno} imports '{module}' "
                            f"(forbidden: '{prefix}')"
                        )
        if violations:
            msg = (
                "API test files import from legacy container path!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nFix: use module public imports instead "
                "(e.g. src.modules.workspace.public)."
            )
            pytest.fail(msg)


# ──────────────────────────────────────────────────────────
# Test: ORM model registration covers required tables
# ──────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────
# Test: API tests must not import from legacy db_models
# ──────────────────────────────────────────────────────────

DB_MODELS_FORBIDDEN = [
    "src.infrastructure.persistence.db_models",
]

# Legacy exceptions: existing files that still use db_models directly.
# New files must NOT be added here — use module-level model paths instead.
DB_MODELS_LEGACY_EXCEPTIONS: set[str] = {
    "tests/api/v1/test_audio.py",
    "tests/api/v1/test_channels.py",
    "tests/api/v1/test_export.py",
    "tests/api/v1/test_favorites.py",
    "tests/api/v1/test_trash.py",
}


class TestApiTestDbModelsImportBoundaries:
    """Ensure API test files do not import from legacy db_models path."""

    def test_no_db_models_imports_in_api_tests(self):
        """API tests must use module-level model paths, not db_models directly."""
        violations: list[str] = []
        for filepath in _collect_python_files(API_TEST_DIR):
            rel = filepath.relative_to(PROJECT_ROOT).as_posix()
            if rel in DB_MODELS_LEGACY_EXCEPTIONS:
                continue
            for lineno, module in _extract_imports(filepath):
                for prefix in DB_MODELS_FORBIDDEN:
                    if module == prefix or module.startswith(prefix + "."):
                        violations.append(
                            f"{rel}:{lineno} imports '{module}' "
                            f"(forbidden: '{prefix}')"
                        )
        if violations:
            msg = (
                "API test files import from legacy db_models path!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nFix: use module-level model paths instead "
                "(e.g. src.modules.workspace.infrastructure.persistence.models)."
            )
            pytest.fail(msg)


# ──────────────────────────────────────────────────────────
# Test: ORM model registration covers required tables
# ──────────────────────────────────────────────────────────

REQUIRED_TABLES = {"channels", "chat_sessions", "chat_messages"}


class TestOrmModelRegistration:
    """Ensure register_orm_models() registers all required tables."""

    def test_register_orm_models_registers_required_tables(self):
        """After register_orm_models(), Base.metadata must contain core tables."""
        from src.core.database import Base, register_orm_models

        register_orm_models()
        tables = set(Base.metadata.tables.keys())

        missing = REQUIRED_TABLES - tables
        if missing:
            pytest.fail(
                f"register_orm_models() did not register tables: {missing}\n"
                f"Registered tables: {sorted(tables)}"
            )
