# -*- coding: utf-8 -*-
"""Strict architecture gate: modules must not import legacy persistence.

Ensures that src/modules/**/*.py never imports from src.infrastructure.persistence.
This prevents re-introduction of legacy persistence dependencies after migration.
"""

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODULES_DIR = PROJECT_ROOT / "src" / "modules"
FORBIDDEN_PREFIXES = ["src.infrastructure.persistence"]


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


def test_modules_no_legacy_persistence_imports():
    """No file under src/modules/ may import from src.infrastructure.persistence."""
    violations: list[str] = []
    for filepath in _collect_python_files(MODULES_DIR):
        rel = filepath.relative_to(PROJECT_ROOT).as_posix()
        for lineno, module in _extract_imports(filepath):
            for prefix in FORBIDDEN_PREFIXES:
                if module == prefix or module.startswith(prefix + "."):
                    violations.append(f"{rel}:{lineno} imports '{module}'")
    if violations:
        pytest.fail(
            "src/modules imports from legacy persistence path!\n\n"
            + "\n".join(f"  - {v}" for v in violations)
            + "\n\nFix: use module-local persistence adapters via src.modules.<m>.public."
        )
