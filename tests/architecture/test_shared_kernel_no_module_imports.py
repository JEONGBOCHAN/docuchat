# -*- coding: utf-8 -*-
"""Verify shared kernel does not import from any module.

src/shared/ must never depend on src/modules/.
This ensures the shared kernel remains a true dependency-free foundation.
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SHARED_DIR = PROJECT_ROOT / "src" / "shared"


def _collect_python_files(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.rglob("*.py"))


def _extract_imports(filepath: Path) -> list[tuple[int, str]]:
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


def test_shared_kernel_no_module_imports():
    """src/shared/ must not import from src.modules.*."""
    violations: list[str] = []

    for filepath in _collect_python_files(SHARED_DIR):
        rel = filepath.relative_to(PROJECT_ROOT).as_posix()
        for lineno, module in _extract_imports(filepath):
            if module == "src.modules" or module.startswith("src.modules."):
                violations.append(f"{rel}:{lineno} imports '{module}'")

    if violations:
        pytest.fail(
            "Shared kernel imports from modules!\n\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nsrc/shared/ must never depend on src/modules/."
        )
