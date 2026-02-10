# -*- coding: utf-8 -*-
"""Global legacy-root import ban for source and test code.

After the modular monolith migration, these import roots are permanently
banned across the entire codebase (src/ and tests/):

- src.api
- src.application
- src.models
- src.infrastructure.di
- src.infrastructure.persistence

Any import matching these roots indicates a regression to removed
legacy compatibility surfaces.
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
TESTS_DIR = PROJECT_ROOT / "tests"

BANNED_ROOTS = (
    "src.api",
    "src.application",
    "src.domain",
    "src.models",
    "src.infrastructure.di",
    "src.infrastructure.persistence",
)


def _collect_python_files(*directories: Path) -> list[Path]:
    """Collect all .py files under given directories recursively."""
    files: list[Path] = []
    for d in directories:
        if d.exists():
            files.extend(d.rglob("*.py"))
    return sorted(files)


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
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.lineno, node.module))
    return imports


def _matches_any_banned(module: str) -> str | None:
    """Return the matched banned root if module imports from it, else None."""
    for root in BANNED_ROOTS:
        if module == root or module.startswith(root + "."):
            return root
    return None


class TestNoLegacyRootImports:
    """Ensure no code in src/ or tests/ imports from removed legacy roots."""

    def test_no_legacy_imports_in_src(self):
        """Source code must not import from any banned legacy root."""
        violations: list[str] = []
        for filepath in _collect_python_files(SRC_DIR):
            rel = filepath.relative_to(PROJECT_ROOT).as_posix()
            for lineno, module in _extract_imports(filepath):
                matched = _matches_any_banned(module)
                if matched:
                    violations.append(
                        f"{rel}:{lineno} imports '{module}' "
                        f"(banned root: '{matched}')"
                    )
        if violations:
            pytest.fail(
                "Legacy root imports found in src/!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nAll legacy compatibility surfaces have been removed. "
                "Use module-native paths (src.modules.*) or shared kernel "
                "(src.shared.kernel.contracts.*)."
            )

    def test_no_legacy_imports_in_tests(self):
        """Test code must not import from any banned legacy root."""
        violations: list[str] = []
        for filepath in _collect_python_files(TESTS_DIR):
            rel = filepath.relative_to(PROJECT_ROOT).as_posix()
            for lineno, module in _extract_imports(filepath):
                matched = _matches_any_banned(module)
                if matched:
                    violations.append(
                        f"{rel}:{lineno} imports '{module}' "
                        f"(banned root: '{matched}')"
                    )
        if violations:
            pytest.fail(
                "Legacy root imports found in tests/!\n\n"
                + "\n".join(f"  - {v}" for v in violations)
                + "\n\nAll legacy compatibility surfaces have been removed. "
                "Use module-native paths (src.modules.*) or shared kernel "
                "(src.shared.kernel.contracts.*)."
            )
